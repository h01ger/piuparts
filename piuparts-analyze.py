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
# this program. If not, see <https://www.gnu.org/licenses/>


"""Analyze failed piuparts logs and move them around when the errors are known.

This program looks at piuparts log files in ./fail, and queries the bts to find
out if bugs have been filed already. If so, it moves them to ./bugged.
It tries to detect if new versions of bugged packages are uploaded without solving
the bug and will then update the bts with the new found versions, and copy the
headers of the log in ./fail to the one in ./bugged and vice versa. It will then
move the failed log to ./bugged as well.

"""
from __future__ import print_function  # Requires Py 2.6 or later

import os
import sys
import time
import re
import shutil
import subprocess
import fcntl

import debianbts
import apt_pkg
from signal import alarm, signal, SIGALRM
from collections import deque

import piupartslib.conf
from piupartslib.conf import MissingSection


CONFIG_FILE = "/etc/piuparts/piuparts.conf"

apt_pkg.init_system()

error_pattern = re.compile(r"(?<=\n).*error.*\n?", flags=re.IGNORECASE)
chroot_pattern = re.compile(r"tmp/tmp.*?'")

############################################################################

class BTS_Timeout(Exception):
    pass


def alarm_handler(signum, frame):
    raise BTS_Timeout


class PiupartsBTS():

    def __init__(self):
        self._bugs_usertagged_piuparts = None
        self._bugs_in_package = dict()
        self._bugs_affecting_package = dict()
        self._bug_versions = dict()

        self._queries = 0
        self._misses = 0

    def all_piuparts_bugs(self):
        if self._bugs_usertagged_piuparts is None:
            self._bugs_usertagged_piuparts = debianbts.get_usertag("debian-qa@lists.debian.org", 'piuparts')['piuparts']
        return self._bugs_usertagged_piuparts

    def bugs_in(self, package):
        if not package in self._bugs_in_package:
            self._misses += 1
            signal(SIGALRM, alarm_handler)
            alarm(120)
            bugs = debianbts.get_bugs('package', package, 'bugs', self.all_piuparts_bugs(), 'archive', 'both')
            bugs += debianbts.get_bugs('package', 'src:' + package, 'bugs', self.all_piuparts_bugs(), 'archive', 'both')
            alarm(0)
            self._bugs_in_package[package] = sorted(set(bugs), reverse=True)
        self._queries += 1
        return self._bugs_in_package[package]

    def bugs_affecting(self, package):
        if not package in self._bugs_affecting_package:
            self._misses += 1
            signal(SIGALRM, alarm_handler)
            alarm(120)
            bugs = debianbts.get_bugs('affects', package, 'bugs', self.all_piuparts_bugs(), 'archive', 'both')
            bugs += debianbts.get_bugs('affects', 'src:' + package, 'bugs', self.all_piuparts_bugs(), 'archive', 'both')
            alarm(0)
            self._bugs_affecting_package[package] = sorted(set(bugs), reverse=True)
        self._queries += 1
        return self._bugs_affecting_package[package]

    def bug_versions(self, bug):
        """Gets a list of only the version numbers for which the bug is found.
        Newest versions are returned first."""
        # debianbts returns it in the format package/1.2.3 or 1.2.3 which will become 1.2.3
        if not bug in self._bug_versions:
            self._misses += 1
            signal(SIGALRM, alarm_handler)
            alarm(60)
            found_versions = debianbts.get_status(bug)[0].found_versions
            alarm(0)
            versions = []
            for found_version in found_versions:
                v = found_version.rsplit('/', 1)[-1]
                if v == "None":
                    # ignore $DISTRO/None versions
                    pass
                else:
                    versions.append(v)
            self._bug_versions[bug] =  list(reversed(sorted(versions, cmp=apt_pkg.version_compare))) or ['~']
        self._queries += 1
        return self._bug_versions[bug]

    def print_stats(self):
        print("PiupartsBTS: %d queries, %d forwarded to debianbts" % (self._queries, self._misses))


piupartsbts = PiupartsBTS()

############################################################################

class Busy(Exception):

    def __init__(self):
        self.args = "section is locked by another process",


class Config(piupartslib.conf.Config):
    def __init__(self, section="global", defaults_section=None):
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
                                         {
                                         "sections": "report",
                                         "master-directory": ".",
                                         },
                                         defaults_section=defaults_section)


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
    with open(log, "r") as f:
        data = f.read()
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
    with open(log, "r") as f:
        data = f.read()
    headers = []
    headers = data.partition("\nExecuting:")[0]
    if headers and not headers.endswith("\n"):
        headers += "\n"
    return headers


def prepend_to_file(filename, data):
    with open(filename, "r") as f:
        old_data = f.read()
    with open(filename + ".tmp", "w") as f:
        f.write(data)
        f.write(old_data)

    shutil.copymode(filename, filename + ".tmp")

    os.rename(filename, filename + "~")
    os.rename(filename + ".tmp", filename)
    os.remove(filename + "~")


def write_bug_file(failed_log, bugs):
    if bugs:
        with open(os.path.splitext(failed_log)[0] + '.bug', "w") as f:
            for bug in bugs:
                f.write('<a href="https://bugs.debian.org/%s" target="_blank">#%s</a>\n' % (bug, bug))


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
            abugs = piupartsbts.bugs_affecting(pname)
            bugs = piupartsbts.bugs_in(pname)
            for bug in abugs + bugs:
                if moved:
                    break
                if bug in abugs:
                    bugged = "affected"
                else:
                    bugged = "bugged"
                found_versions = piupartsbts.bug_versions(bug)
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
            print(sys.exc_info()[0])
        alarm(0)


def main():
    conf = Config()
    conf.read(CONFIG_FILE)

    master_directory = conf["master-directory"]
    if len(sys.argv) > 1:
        sections = sys.argv[1:]
    else:
        sections = conf['sections'].split()

    with open(os.path.join(master_directory, "analyze.lock"), "we") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            if sys.stdout.isatty():
                sys.exit("another piuparts-analyze process is already running")
            else:
                sys.exit(0)

        todo = deque([(s, 0) for s in sections])
        while len(todo):
            (section_name, next_try) = todo.popleft()
            now = time.time()
            if (now < next_try):
                print("Sleeping while section is busy")
                time.sleep(max(30, next_try - now) + 30)
            print(time.strftime("%a %b %2d %H:%M:%S %Z %Y", time.localtime()))
            print("%s:" % section_name)
            try:
                section_directory = os.path.join(master_directory, section_name)
                if not os.path.exists(section_directory):
                    raise MissingSection("", section_name)
                with open(os.path.join(section_directory, "master.lock"), "we") as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except IOError:
                        raise Busy()

                    oldcwd = os.getcwd()
                    os.chdir(section_directory)
                    mark_logs_with_reported_bugs()
                    os.chdir(oldcwd)
            except Busy:
                print("Section is busy")
                todo.append((section_name, time.time() + 300))
            except MissingSection as e:
                print("Configuration Error in section '%s': %s" % (section_name, e))
            print("")

        print(time.strftime("%a %b %2d %H:%M:%S %Z %Y", time.localtime()))
        piupartsbts.print_stats()


if __name__ == "__main__":
    main()

# vi:set et ts=4 sw=4 :
