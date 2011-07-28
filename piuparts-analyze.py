#!/usr/bin/python
#
# Copyright 2005 Lars Wirzenius (liw@iki.fi)
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

This program looks at piuparts log files in ./fail, and compares them to
log files in ./bugged. If it finds one in ./fail that has the same
error messages as one in ./bugged, it copies the headers to the one in ./fail
and moves it to ./bugged. This is useful for repetitive uploads of the
same package that do not fix the problem.

"""


import os
import re
import shutil
import sys


error_pattern = re.compile(r"(?<=\n).*error.*\n?", flags=re.IGNORECASE)
chroot_pattern = re.compile(r"tmp/tmp.*?'")


def find_logs(dir):
    return [os.path.join(dir, x) 
                for x in os.listdir(dir) if x.endswith(".log")]


def package_name(log):
    return os.path.basename(log).split("_", 1)[0]


def find_bugged_logs(failed_log):
    package = package_name(failed_log)
    pat = "/" + package + "_"
    return [x for x in find_logs("bugged") if pat in x]


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
    f = file(log, "r")
    data = f.read()
    f.close()
    headers = []
    cont = False
    for line in data.split("\n\n", 1)[0].split("\n"):
        if line.startswith("Start:"):
            cont = True
        elif cont and line[:1].isspace():
            pass
        else:
            headers.append(line)
            cont = False
    headers = "\n".join(headers)
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


def mark_bugged(failed_log, bugged_log):
    print "Moving", failed_log, "to bugged"

    headers = extract_headers(bugged_log)
    prepend_to_file(failed_log, headers)
    if os.path.isdir(".bzr"):
        assert "'" not in failed_log
        os.system("bzr move '%s' bugged" % failed_log)
    else:
        os.rename(failed_log, 
                  os.path.join("bugged", os.path.basename(failed_log)))


def mark_logs_with_known_bugs():        
    for failed_log in find_logs("fail"):
        failed_errors = extract_errors(failed_log)
        for bugged_log in find_bugged_logs(failed_log):
            bugged_errors = extract_errors(bugged_log)
            if failed_errors == bugged_errors:
                mark_bugged(failed_log, bugged_log)
                break


def report_packages_with_many_logs():
    failed_logs = find_logs("fail")
    packages = {}
    for failed_log in failed_logs:
        package = package_name(failed_log)
        packages[package] = packages.get(package, []) + [failed_log]
    for package, failed_logs in packages.iteritems():
        printed = False
        if len(failed_logs) > 1:
            print "Many failures:"
            for failed_log in failed_logs:
                print "  ", failed_log
            printed = True
        bugged_logs = find_bugged_logs(failed_logs[0])
        if bugged_logs:
            print "Already bugged?"
            for failed_log in failed_logs + bugged_logs:
                print "  ", failed_log
            printed = True
        if printed:
            print


def main():
    mark_logs_with_known_bugs()
    report_packages_with_many_logs()


if __name__ == "__main__":
    main()
