#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2013 David Steele (dsteele@gmail.com)
# Copyright © 2014 Andreas Beckmann (anbe@debian.org)
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


import ConfigParser
import os
import sys
import time
import logging
import argparse

import piupartslib
from piupartslib.conf import MissingSection
from piupartslib.dwke import *


CONFIG_FILE = "/etc/piuparts/piuparts.conf"
KPR_DIRS = ('pass', 'bugged', 'affected', 'fail')


class WKE_Config(piupartslib.conf.Config):

    """Configuration parameters for Well Known Errors"""

    def __init__(self):
        self.section = 'global'

        piupartslib.conf.Config.__init__(self, self.section,
                                         {
                                         "sections": "report",
                                         "master-directory": ".",
                                         "known-problem-directory": "@sharedir@/piuparts/known_problems",
                                         }, "")


def setup_logging(log_level):
    logger = logging.getLogger()
    logger.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)


def write_file(filename, contents):
    with file(filename, "w") as f:
        f.write(contents)


def mtime(path):
    return os.path.getmtime(path)


def clean_cache_files(logdict, cachedict, recheck=False, recheck_failed=False,
                      skipnewer=False):
    """Delete files in cachedict if the corresponding logdict file is missing
       or newer"""

    count = 0
    for pkgspec in cachedict:
        try:
            if pkgspec not in logdict \
                or (mtime(logdict[pkgspec]) > mtime(cachedict[pkgspec]) and not skipnewer)\
                or get_where(logdict[pkgspec]) != get_where(cachedict[pkgspec])\
                or recheck\
                    or (recheck_failed and not get_where(cachedict[pkgspec]) in ['pass']):
                os.remove(cachedict[pkgspec])
                count = count + 1
        except (IOError, OSError):
            # logfile may have disappeared
            pass

    return count


def make_kprs(logdict, kprdict, problem_list):
    """Create kpr files, as necessary, so every log file has one
       kpr entries are e.g.
           fail/xorg-docs_1:1.6-1.log broken_symlinks_error.conf"""

    needs_kpr = set(logdict.keys()).difference(set(kprdict.keys()))

    for pkg_spec in needs_kpr:
        logpath = logdict[pkg_spec]

        try:
            lb = open(logpath, 'r')
            logbody = lb.read()
            lb.close()

            where = get_where(logpath)

            kprs = ""
            for problem in problem_list:
                if problem.has_problem(logbody, where):
                    kprs += "%s/%s.log %s\n" % (where, pkg_spec, problem.name)

            if not where in ['pass'] and not len(kprs):
                kprs += "%s/%s.log %s\n" % (where, pkg_spec, "unclassified_failures.conf")

            write_file(get_kpr_path(logpath), kprs)
        except IOError:
            logging.error("File error processing %s" % logpath)

    return len(needs_kpr)


def process_section(section, config, problem_list,
                    recheck=False, recheck_failed=False, pkgsdb=None):
    """ Update .bug and .kpr files for logs in this section """

    sectiondir = os.path.join(config['master-directory'], section)
    workdirs = [os.path.join(sectiondir, x) for x in KPR_DIRS]

    if not os.access(sectiondir, os.F_OK):
        raise MissingSection("", section)

    [os.mkdir(x) for x in workdirs if not os.path.exists(x)]

    logdict = get_file_dict(workdirs, LOG_EXT)
    kprdict = get_file_dict(workdirs, KPR_EXT)
    bugdict = get_file_dict(workdirs, BUG_EXT)

    del_cnt = clean_cache_files(logdict, kprdict, recheck, recheck_failed)
    clean_cache_files(logdict, bugdict, skipnewer=True)

    kprdict = get_file_dict(workdirs, KPR_EXT)

    add_cnt = make_kprs(logdict, kprdict, problem_list)

    failures = FailureManager(logdict)

    return (del_cnt, add_cnt, failures)


def detect_well_known_errors(sections, config, problem_list, recheck, recheck_failed):

    for section in sections:
        try:
            logging.info(time.strftime("%a %b %2d %H:%M:%S %Z %Y", time.localtime()))
            logging.info("%s:" % section)

            (del_cnt, add_cnt, failures) = \
                process_section(section, config, problem_list,
                                recheck, recheck_failed)

            logging.info("parsed logfiles: %d removed, %d added" % (del_cnt, add_cnt))

            for prob in problem_list:
                pcount = len(failures.filtered(prob.name))
                if pcount:
                    logging.info("%7d %s" % (pcount, prob.name))
        except MissingSection:
            pass

    logging.info(time.strftime("%a %b %2d %H:%M:%S %Z %Y", time.localtime()))


if __name__ == '__main__':
    setup_logging(logging.DEBUG)

    parser = argparse.ArgumentParser(
        description="Detect well known errors",
                 epilog="""
This script processes all log files against defined "known_problem" files,
caching the problems found, by package, into ".kpr" files.
""")

    parser.add_argument('sections', nargs='*', metavar='SECTION',
                        help="limit processing to the listed SECTION(s)")

    parser.add_argument('--recheck', dest='recheck', action='store_true',
                        help="recheck all log files (delete cache)")

    parser.add_argument('--recheck-failed', dest='recheck_failed',
                        action='store_true',
                        help="recheck failed log files (delete cache)")

    args = parser.parse_args()

    conf = WKE_Config()
    conf.read(CONFIG_FILE)

    sections = args.sections
    if not sections:
        sections = conf['sections'].split()

    problem_list = create_problem_list(conf['known-problem-directory'])

    detect_well_known_errors(sections, conf, problem_list, args.recheck,
                             args.recheck_failed)

# vi:set et ts=4 sw=4 :
