# -*- coding: utf-8 -*-

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
#  "_comment": "Debian Piuparts Package Results - http://anonscm.debian.org/...
#  "_date": "Wed Feb 26 01:48:43 UTC 2014",
#  "_id": "Piuparts Package Test Results Summary",
#  "_type": "source",
#  "_version": "1.0",
#  "packages": {
#   "0ad": {
#    "overall": [
#     "X",
#     "http://localhost/piuparts/sid-fail-broken-symlinks/source/0/0ad.html"
#    ],
#    "stable": [
#     "P",
#     "http://localhost/piuparts/wheezy/source/0/0ad.html"
#    ],
#    "unstable": [
#     "X",
#     "http://localhost/piuparts/sid-fail-broken-symlinks/source/0/0ad.html"
#    ]
#   },
#   "0ad-data": {
#  ...
#  }
#
#
# The packages are listed by source package. E.g. "unstable" here is a
# reporting-section (see README_server.txt). The single character flags are
# defined in worst_flag() below. The URL is a human friendly page for
# inspecting the results for that package/distribution.
#
# Binary package results are combined into source package results. The 'worst'
# flag in the group is reported ("F" is worst overall).
#
# For the global summary, the packages 'worst' result across reporting-sections
# is used. In the case of a tie, the more-important-precedence
# section/reporting-section result is used.
#
# The global file also includes an 'overall' reporting-section, which contains
# the 'worst' result across the other reporting-sections.


import json
import datetime

class SummaryException(Exception):
    pass

SUMMID = "Piuparts Package Test Results Summary"
SUMMVER = "1.0"

def new_summ():
    cdate_array = datetime.datetime.utcnow().ctime().split()
    utcdate = " ".join(cdate_array[:-1] + ["UTC"] + [cdate_array[-1]])

    return({
               "_id"      : SUMMID,
               "_version" : SUMMVER,
               "_date"    : utcdate,
               "_comment" : "Debian Piuparts Package Results - " \
                            "http://anonscm.debian.org/gitweb/?p=piuparts/piuparts.git" \
                            ";a=blob;f=piupartslib/pkgsummary.py;hb=refs/heads/develop",
               "_type"    : "source",
               "packages" : {},
          })

def worst_flag(*args):
    sev = {
            'F': 0, # fail
            'X': 1, # blocked by failure
            'W': 2, # waiting
            'P': 3, # passed, or essential
            '-': 4, # does not exist
          }

    return(min([(sev[x],x) for x in args])[1])

def add_summ(summ, rep_sec, pkg, flag, url):
    """Add a flag/url result to summ for a package in a reporting-section"""

    pdict = summ["packages"]

    if pkg not in pdict:
        pdict[pkg] = {}

    if rep_sec in pdict[pkg]:
        old_flag = pdict[pkg][rep_sec][0]

        if old_flag != worst_flag(old_flag, flag):
            pdict[pkg][rep_sec] = [flag, url]
    else:
        pdict[pkg][rep_sec] = [flag, url]

    return summ

def merge_summ(summ, sec_summ):
    """Merge a sector summary into the global summary"""

    spdict = sec_summ["packages"]

    for pkg in spdict:
        for rep_sec in spdict[pkg]:
            flag, url = spdict[pkg][rep_sec]
            add_summ(summ, rep_sec, pkg, flag, url)
            add_summ(summ, "overall", pkg, flag, url)

    return summ

def summ_write(summ, fname):
    with open(fname, 'w') as fl:
        json.dump(summ, fl, sort_keys=True, indent=1)

def summ_read(fname):
    with open(fname, 'r') as fl:
        result = json.load(fl)

    if result["_id"] != SUMMID or result["_version"] != SUMMVER:
        raise SummaryException('Summary JSON header mismatch')

    return result
