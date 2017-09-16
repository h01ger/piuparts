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

    def __init__(self, section="global", defaults_section=None):
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
                                         {
                                         "sections": "report",
                                         "master-directory": ".",
                                         "known-problem-directory": "@sharedir@/piuparts/known_problems",
                                         "exclude-known-problems": None,
                                         },
                                         defaults_section=defaults_section)


def setup_logging(log_level):
    logger = logging.getLogger()
    logger.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)


def process_section(section, config, problem_list,
                    recheck=False, recheck_failed=False, pkgsdb=None):
    """ Update .bug and .kpr files for logs in this section """

    sectiondir = os.path.join(config['master-directory'], section)
    workdirs = [os.path.join(sectiondir, x) for x in KPR_DIRS]

    if not os.access(sectiondir, os.F_OK):
        raise MissingSection("", section)

    if True:
        [os.mkdir(x) for x in workdirs if not os.path.exists(x)]

        logdict = get_file_dict(workdirs, LOG_EXT)
        kprdict = get_file_dict(workdirs, KPR_EXT)
        bugdict = get_file_dict(workdirs, BUG_EXT)

        del_cnt = clean_cache_files(logdict, kprdict, recheck, recheck_failed)
        clean_cache_files(logdict, bugdict, skipnewer=True)

        kprdict = get_file_dict(workdirs, KPR_EXT)

        section_config = WKE_Config(section=section, defaults_section="global")
        section_config.read(CONFIG_FILE)
        if section_config['exclude-known-problems']:
            excluded = section_config['exclude-known-problems'].split()
            problem_list = [p for p in problem_list if p.name not in excluded]

        add_cnt = make_kprs(logdict, kprdict, problem_list)

        return (del_cnt, add_cnt)


def detect_well_known_errors(sections, config, problem_list, recheck, recheck_failed):

    for section in sections:
        try:
            logging.info(time.strftime("%a %b %2d %H:%M:%S %Z %Y", time.localtime()))
            logging.info("%s:" % section)

            (del_cnt, add_cnt) = \
                process_section(section, config, problem_list,
                                recheck, recheck_failed)

            logging.info("parsed logfiles: %d removed, %d added" % (del_cnt, add_cnt))
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

    if True:
        sections = args.sections
        if not sections:
            sections = conf['sections'].split()

        problem_list = create_problem_list(conf['known-problem-directory'])

        detect_well_known_errors(sections, conf, problem_list, args.recheck,
                                 args.recheck_failed)

# vi:set et ts=4 sw=4 :
