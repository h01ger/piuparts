#!/usr/bin/python

# Copyright 2014 David Steele (dsteele@gmail.com)
#
# This file is part of Piuparts
#
# Piuparts is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# Piuparts is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.


# Piuparts summary generation module
#
# This module is used to create exportable section and global package testing
# result summaries.
#
# The canonical location for section summaries is at
#
#     https://piuparts.debian.org/<section>/summary.json
#
# The global summary is at
#
#     https://piuparts.debian.org/summary.json
#
# Example output:
#
# summary.json
# {
#  "_comment": "Debian Piuparts Package Results - https://piuparts.debian.org/...",
#  "_date": "Wed Feb 26 01:48:43 UTC 2014",
#  "_id": "Piuparts Package Test Results Summary",
#  "_type": "source",
#  "_version": "1.0",
#  "packages": {
#   "0ad": {
#    "overall": [
#     "X",
#     0,
#     "http://localhost/piuparts/sid-fail-broken-symlinks/source/0/0ad.html"
#    ],
#    "stable": [
#     "P",
#     0,
#     "http://localhost/piuparts/wheezy/source/0/0ad.html"
#    ],
#    "unstable": [
#     "X",
#     0,
#     "http://localhost/piuparts/sid-fail-broken-symlinks/source/0/0ad.html"
#    ]
#   },
#   "0ad-data": {
#  ...
#  }
#
#
# The packages are listed by source package. E.g. "unstable" here is a
# json-section (see README_server.txt). The single character flags are
# defined below. The number is the number of packages which
# are blocked from testing due to a failed package. The URL is a human
# friendly page for inspecting the results for that package/distribution.
#
# Binary package results are combined into source package results. The 'worst'
# flag in the group is reported ("F" is worst overall).
#
# For the global summary, the packages 'worst' result across json-sections
# is used. In the case of a tie, the more-important-precedence
# section/json-section result is used.
#
# The global file also includes an 'overall' json-section, which contains
# the 'worst' result across the other json-sections.
from __future__ import print_function  # Requires Py 2.6 or later

import json
import datetime
from collections import namedtuple, defaultdict


class SummaryException(Exception):
    pass

SUMMID = "Piuparts Package Test Results Summary"
SUMMVER = "1.0"

DEFSEC = 'overall'

FlagInfo = namedtuple('FlagInfo', ['word', 'priority', 'states'])

flaginfo = {
    'F': FlagInfo('Failed', 0, ["failed-testing"]),
            'X': FlagInfo('Blocked', 1, [
                          "cannot-be-tested",
                          "dependency-failed-testing",
                          "dependency-cannot-be-tested",
                          "dependency-does-not-exist",
                          ]),
            'W': FlagInfo('Waiting', 2, [
                          "waiting-to-be-tested",
                          "waiting-for-dependency-to-be-tested",
                          ]),
            'P': FlagInfo('Passed', 3, [
                          "essential-required",
                          "successfully-tested",
                          ]),
            '-': FlagInfo('Unknown', 4, [
                          "does-not-exist",
                          "unknown",
                          ]),
}

state2flg = dict([(y, x[0]) for x in flaginfo.iteritems() for y in x[1].states])


def worst_flag(*flags):
    try:
        flag = min(*flags, key=lambda x: flaginfo[x].priority)
    except KeyError:
        raise SummaryException("Unknown flag in " + flags.__repr__())

    return(flag)


def get_flag(state):
    try:
        flag = state2flg[state]
    except KeyError:
        raise SummaryException("Unknown state - " + state)

    return(flag)


def new_summary():
    cdate_array = datetime.datetime.utcnow().ctime().split()
    utcdate = " ".join(cdate_array[:-1] + ["UTC"] + [cdate_array[-1]])

    # define the packages struct. The default should never be the one added
    dfltentry = ['-', 0, 'invalid url']
    pkgstruct = defaultdict(lambda: defaultdict(lambda: dfltentry))

    return({
        "_id": SUMMID,
               "_version": SUMMVER,
               "_date": utcdate,
               "_comment": "Debian Piuparts Package Results - "
                            "https://salsa.debian.org/debian/piuparts/raw/"
                            "develop/piupartslib/pkgsummary.py",
               "_type": "source",
               "packages": pkgstruct,
    })


def add_summary(summary, rep_sec, pkg, flag, block_cnt, url):
    if not flag in flaginfo or not isinstance(block_cnt, int) \
            or not url.startswith('http'):
        raise SummaryException("Invalid summary argument")

    pdict = summary["packages"]

    [old_flag, old_cnt, old_url] = pdict[pkg][rep_sec]
    block_cnt = max(block_cnt, old_cnt)
    if old_flag != worst_flag(old_flag, flag):
        pdict[pkg][rep_sec] = [flag, block_cnt, url]
    else:
        pdict[pkg][rep_sec] = [old_flag, block_cnt, old_url]

    return summary


def merge_summary(gbl_summ, sec_summ):
    spdict = sec_summ["packages"]

    for pkg in spdict:
        for rep_sec in spdict[pkg]:
            flag, block_cnt, url = spdict[pkg][rep_sec]
            add_summary(gbl_summ, rep_sec, pkg, flag, block_cnt, url)
            add_summary(gbl_summ, DEFSEC, pkg, flag, block_cnt, url)

    return gbl_summ


def tooltip(summary, pkg):
    """Returns e.g. "Failed in testing and stable, blocking 5 packages"."""

    tip = ''

    pkgdict = summary['packages']

    if pkg in pkgdict:
        flag, block_cnt, url = pkgdict[pkg][DEFSEC]

        sections = [x for x in pkgdict[pkg] if x != DEFSEC]
        applicable = [x for x in sections if pkgdict[pkg][x][0] == flag]

        tip = flaginfo[flag].word

        if len(applicable) > 2:
            tip += ' in ' + ', '.join(applicable[:-1]) + ' and ' + applicable[-1]
        elif len(applicable) == 2:
            tip += ' in ' + ' and '.join(applicable)
        elif len(applicable) == 1:
            tip += ' in ' + applicable[0]

        if block_cnt:
            tip += ", blocking %d packages" % block_cnt

        tip += '.'

    return tip


def write_summary(summary, fname):
    with open(fname, 'w') as fl:
        json.dump(summary, fl, sort_keys=True, indent=1)


def read_summary(fname):
    with open(fname, 'r') as fl:
        result = json.load(fl)

    if result["_id"] != SUMMID or result["_version"] != SUMMVER:
        raise SummaryException('Summary JSON header mismatch')

    return result

if __name__ == '__main__':
    import sys

    # read a global summary file and return DDPO info by package
    summary = read_summary(sys.argv[1])

    for pkg in summary['packages']:
        flag, blocked, url = summary['packages'][pkg][DEFSEC]

        print(pkg, flag, url, tooltip(summary, pkg))
