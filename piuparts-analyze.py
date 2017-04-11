#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# Copyright 2011 Mika Pflüger (debian@mikapflueger.de)
# Copyright © 2012-2017 Andreas Beckmann (anbe@debian.org)
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA


"""Analyze failed piuparts logs and move them around when the errors are known.

This program looks at piuparts log files in ./fail, and queries the bts to find
out if bugs have been filed already. If so, it moves them to ./bugged.
It tries to detect if new versions of bugged packages are uploaded without solving
the bug and will then update the bts with the new found versions, and copy the
headers of the log in ./fail to the one in ./bugged and vice versa. It will then
move the failed log to ./bugged as well.

"""


import os
import sys
import re
import shutil
import subprocess

import debianbts
import apt_pkg

apt_pkg.init_system()

error_pattern = re.compile(r"(?<=\n).*error.*\n?", flags=re.IGNORECASE)
chroot_pattern = re.compile(r"tmp/tmp.*?'")
distro = "?"


def find_logs(directory):
    """Returns list of logfiles sorted by age, newest first."""
    logs = [os.path.join(directory, x)
            for x in os.listdir(directory) if x.endswith(".log")]
    return [y[1] for y in reversed(sorted([(os.path.getmtime(x), x) for x in logs]))]


def find_bugged_logs(failed_log):
    package = package_name(failed_log)
    pat = "/" + package + "_"
    return [x for x in find_logs("bugged") + find_logs("affected") if pat in x]


def package_name(log):
    return os.path.basename(log).split("_", 1)[0]


def package_version(log):
    return os.path.basename(log).split("_", 1)[1].rstrip('.log')


def package_source_version(log):
    version = package_version(log)
    possible_binnmu_part = version.rsplit('+', 1)[-1]
    if possible_binnmu_part.startswith('b') and possible_binnmu_part[1:].isdigit():
        # the package version contains a binnmu-part which is not part of the source version
        # and therefore not accepted/tracked by the bts. Remove it.
        version = version.rsplit('+', 1)[0]
    return version


def extract_errors(log):
    """This pretty stupid implementation is basically just 'grep -i error', and then
    removing the timestamps and the name of the chroot and the package version itself."""
    f = open(log)
    data = f.read()
    f.close()
    whole = ''
    pversion = package_version(log)
    for match in error_pattern.finditer(data):
        text = match.group()
        # Get rid of timestamps
        if text[:1].isdigit():
            text = text.split(" ", 1)[1]
        # Get rid of chroot names
        if 'tmp/tmp' in text:
            text = re.sub(chroot_pattern, "chroot'", text)
        # Get rid of the package version
        text = text.replace(pversion, '')
        whole += text
    return whole


def extract_headers(log):
    f = open(log)
    data = f.read()
    f.close()
    headers = []
    headers = data.partition("\nExecuting:")[0]
    if headers and not headers.endswith("\n"):
        headers += "\n"
    return headers


def prepend_to_file(filename, data):
    f = file(filename, "r")
    old_data = f.read()
    f.close()
    f = file(filename + ".tmp", "w")
    f.write(data)
    f.write(old_data)
    f.close()

    shutil.copymode(filename, filename + ".tmp")

    os.rename(filename, filename + "~")
    os.rename(filename + ".tmp", filename)
    os.remove(filename + "~")


def get_bug_versions(bug):
    """Gets a list of only the version numbers for which the bug is found.
    Newest versions are returned first."""
    # debianbts returns it in the format package/1.2.3 or 1.2.3 which will become 1.2.3
    versions = []
    for found_version in debianbts.get_status(bug)[0].found_versions:
        v = found_version.rsplit('/', 1)[-1]
        if v == "None":
            # only allow the distro-qualified "$distro/None" version
            if found_version == distro + "/" + v:
                versions.append(v)
        else:
            versions.append(v)
    return list(reversed(sorted(versions, cmp=apt_pkg.version_compare))) or ['~']


def write_bug_file(failed_log, bugs):
    if bugs:
        f = file(os.path.splitext(failed_log)[0] + '.bug', "w")
        for bug in bugs:
            f.write('<a href="https://bugs.debian.org/%s" target="_blank">#%s</a>\n' % (bug, bug))
        f.close()


def move_to_bugged(failed_log, bugged="bugged", bug=None):
    print("Moving %s to %s (#%s)" % (failed_log, bugged, bug))
    os.rename(failed_log, os.path.join(bugged, os.path.basename(failed_log)))
    if bug is not None:
        write_bug_file(os.path.join(bugged, os.path.basename(failed_log)), [bug])


def mark_bugged_version(failed_log, bugged_log):
    """Copies the headers from the old log to the new log and vice versa and
    moves the new log to bugged. Removes the old log in bugged."""
    bugged_headers = extract_headers(bugged_log)
    failed_headers = extract_headers(failed_log)
    prepend_to_file(failed_log, bugged_headers)
    prepend_to_file(bugged_log, failed_headers)
    move_to_bugged(failed_log)


def bts_update_found(bugnr, newversion):
    if "DEBEMAIL" in os.environ and os.environ["DEBEMAIL"]:
        # subprocess.check_call(('bts', 'found', bugnr, newversion))
        print(' '.join(('bts', 'found', str(bugnr), newversion)))


def mark_logs_with_reported_bugs():
    for failed_log in find_logs("fail") + find_logs("untestable"):
        try:
            pname = package_name(failed_log)
            pversion = package_source_version(failed_log)
            try:
                failed_errors = extract_errors(failed_log)
            except IOError:
                print('IOError while processing %s' % failed_log)
                continue
            moved = False
            abugs = piuparts_bugs_affecting(pname)
            bugs = piuparts_bugs_in(pname)
            for bug in abugs + bugs:
                if moved:
                    break
                if bug in abugs:
                    bugged = "affected"
                else:
                    bugged = "bugged"
                found_versions = get_bug_versions(bug)
                if pversion in found_versions:
                    move_to_bugged(failed_log, bugged, bug)
                    moved = True
                    break
                for bug_version in found_versions:
                    # print('DEBUG: %s/%s #%d %s' % (pname, pversion, bug, bug_version))

                    if apt_pkg.version_compare(pversion, bug_version) > 0:  # pversion > bug_version
                        bugged_logs = find_bugged_logs(failed_log)
                        if not bugged_logs and not moved:
                            print('%s/%s: Maybe the bug was filed earlier: https://bugs.debian.org/%d against %s/%s'
                                  % (pname, pversion, bug, pname, bug_version))
                            break
                        for bugged_log in bugged_logs:
                            old_pversion = package_source_version(bugged_log)
                            bugged_errors = extract_errors(bugged_log)
                            if (apt_pkg.version_compare(old_pversion, bug_version) == 0  # old_pversion == bug_version
                                and
                                    failed_errors == bugged_errors):
                                # a bug was filed for an old version of the package,
                                # and the errors were the same back then - assume it is the same bug.
                                if not moved:
                                    mark_bugged_version(failed_log, bugged_log)
                                    moved = True
                                    bts_update_found(bug, pversion)
                                    break
            if not moved:
                write_bug_file(failed_log, abugs + bugs)
        except KeyboardInterrupt:
            raise
        except:
            print('ERROR processing %s' % failed_log)
            print sys.exc_info()[0]


piuparts_usertags_cache = None


def all_piuparts_bugs():
    global piuparts_usertags_cache
    if piuparts_usertags_cache is None:
        piuparts_usertags_cache = debianbts.get_usertag("debian-qa@lists.debian.org", 'piuparts')['piuparts']
    return piuparts_usertags_cache


def piuparts_bugs_in(package):
    bugs = debianbts.get_bugs('package', package, 'bugs', all_piuparts_bugs(), 'archive', 'both')
    bugs += debianbts.get_bugs('package', 'src:' + package, 'bugs', all_piuparts_bugs(), 'archive', 'both')
    return sorted(set(bugs), reverse=True)


def piuparts_bugs_affecting(package):
    bugs = debianbts.get_bugs('affects', package, 'bugs', all_piuparts_bugs(), 'archive', 'both')
    bugs += debianbts.get_bugs('affects', 'src:' + package, 'bugs', all_piuparts_bugs(), 'archive', 'both')
    return sorted(set(bugs), reverse=True)


def main():
    if len(sys.argv) > 1:
        global distro
        distro = sys.argv[1]
    mark_logs_with_reported_bugs()


if __name__ == "__main__":
    main()

# vi:set et ts=4 sw=4 :
