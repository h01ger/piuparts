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
import re
import argparse

import piupartslib
from piupartslib.conf import MissingSection
from piupartslib.dwke import *


CONFIG_FILE = "/etc/piuparts/piuparts.conf"
DISTRO_CONFIG_FILE = "/etc/piuparts/distros.conf"
KPR_DIRS = ('pass', 'bugged', 'affected', 'fail')

TPL_EXT = '.tpl'

PROB_TPL = \
"""<tr class="titlerow"><td class="titlecell">
$HEADER in $SECTION, sorted by reverse dependency count.
</td></tr><tr class="normalrow"><td class="contentcell2">
$HELPTEXT
<p>The commandline to find these logs is: <pre>
COMMAND='$COMMAND'
</pre></p>
</td></tr><tr class="titlerow"><td class="alerttitlecell">Please file bugs!</td></tr><tr class="normalrow"><td class="contentcell2" colspan="3">
<ul>
$PACKAGE_LIST</ul>
<p>Affected packages in $SECTION: $COUNT</p></td></tr>
"""

UNKNOWN_TPL = \
"""<tr class="titlerow"><td class="titlecell">
Packages with unknown failures detected in $SECTION, sorted by reverse dependency count.
</td></tr><tr class="normalrow"><td class="contentcell2">
<p>Please investigate and improve detection of known error types!</p>
</td></tr><tr class="titlerow"><td class="alerttitlecell">Please file bugs!</td></tr><tr class="normalrow"><td class="contentcell2" colspan="3">
<ul>
$PACKAGE_LIST
</ul>
<p>Affected packages in $SECTION: $COUNT</p></td></tr>
"""

PKG_ERROR_TPL = \
"""<li>$RDEPS - <a href=\"$LOG\">$LOG</a>
    (<a href=\"http://packages.qa.debian.org/$SDIR/$SPKG.html\" target=\"_blank\">PTS</a>)
    (<a href=\"http://bugs.debian.org/$PACKAGE?dist=unstable\" target=\"_blank\">BTS</a>)
$BUG</li>
"""

class WKE_Config(piupartslib.conf.Config):
    """Configuration parameters for Well Known Errors"""

    def __init__(self):
        self.section = 'global'

        piupartslib.conf.Config.__init__(self, self.section,
            {
                "sections": "report",
                "output-directory": "html",
                "master-directory": ".",
                "known-problem-directory": "@sharedir@/piuparts/known_problems",
                "proxy": None,
            }, "")

class WKE_Section_Config(piupartslib.conf.Config):

    def __init__(self, section):
        self.section = section

        piupartslib.conf.Config.__init__(self, self.section,
            {
                "mirror": None,
                "distro": None,
                "area": None,
                "arch": None,
                "upgrade-test-distros": None,
            }, "",  defaults_section="global")


def setup_logging(log_level):
    logger = logging.getLogger()
    logger.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)


def pts_subdir(source):
    if source[:3] == "lib":
        return source[:4]
    else:
        return source[:1]

def source_pkg(pkgspec, db):
    source_name = db.get_control_header(get_pkg(pkgspec), "Source")

    return source_name

def get_pkgspec(logpath):
    """For a log full file spec, return the pkgspec (<pkg>_<version)"""
    return logpath.split('/')[-1]

def get_bug_text(logpath):
    bugpath = replace_ext(logpath, BUG_EXT)

    txt = ""
    if os.path.exists(bugpath):
        bf = open(bugpath, 'r')
        txt = bf.read()
        bf.close()

    return txt

def section_path(logpath):
    """Convert a full log path name to one relative to the section directory"""
    return '/'.join([get_where(logpath), get_pkgspec(logpath)])

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
            or (mtime(logdict[pkgspec])>mtime(cachedict[pkgspec]) and not skipnewer)\
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

            kf = open(get_kpr_path(logpath), 'a')

            for problem in problem_list:
                if problem.has_problem(logbody, where):
                    kf.write("%s/%s.log %s\n" % (where, pkg_spec, problem.name))

            kf.close()
        except IOError:
            logging.error("File error processing %s" % logpath)

    return len(needs_kpr)

def populate_tpl(tmpl, vals):

    for key in vals:
        tmpl = re.sub("\$%s" % key, str(vals[key]), tmpl)

    return tmpl

def update_tpl(basedir, section, problem, failures, logdict, ftpl, ptpl, pkgsdb):

    pkg_text = ""
    bugged_section = False
    for failure in failures:

        pkgspec = failure.pkgspec
        bin_pkg = get_pkg(pkgspec)
        rdep_cnt = pkgsdb.rrdep_count(bin_pkg)
        pkg_obj = pkgsdb.get_package(bin_pkg)

        if not pkg_obj is None:
            src_pkg = source_pkg(pkgspec, pkgsdb)
        else:
            src_pkg = bin_pkg

        if bugged_section is False and get_where(logdict[pkgspec]) != 'fail':
            bugged_section = True
            pkg_text += "</ul><ul>\n"

        pkg_text += populate_tpl(ftpl, {
                                'LOG': section_path(logdict[pkgspec]),
                                'PACKAGE': bin_pkg,
                                'BUG': get_bug_text(logdict[pkgspec]),
                                'RDEPS': rdep_cnt,
                                'SDIR':pts_subdir(src_pkg),
                                'SPKG':src_pkg,
                                   })

    if len(pkg_text):
        pf = open(os.path.join(basedir, failures[0].problem[:-5] + TPL_EXT), 'w')
        tpl_text = populate_tpl(ptpl, {
                                'HEADER': problem.HEADER,
                                'SECTION': section,
                                'HELPTEXT': problem.HELPTEXT,
                                'COMMAND': problem.get_command(),
                                'PACKAGE_LIST': pkg_text,
                                'COUNT': len(failures),
                                })

        pf.write(tpl_text)
        pf.close()

def update_html(section, logdict, problem_list, failures, config, pkgsdb):

    html_dir = os.path.join(config['output-directory'], section)
    if not os.path.exists(html_dir):
        os.makedirs(html_dir)

    for problem in problem_list:
        update_tpl(html_dir, section, problem,
                   failures.filtered(problem.name),
                   logdict,
                   PKG_ERROR_TPL, PROB_TPL, pkgsdb)

    # Make a failure list of all failed packages that don't show up as known
    failedpkgs = set([x for x in logdict.keys()
                     if get_where(logdict[x]) != 'pass'])
    knownfailpkgs = set([failure.pkgspec for failure in failures.failures])
    unknownsasfailures = [make_failure("", "unknown_failures.conf", x)
                         for x in failedpkgs.difference(knownfailpkgs)]

    def keyfunc(x, pkgsdb=pkgsdb, logdict=logdict):
        rdeps = pkgsdb.rrdep_count(get_pkg(x.pkgspec))

        is_failed = get_where(logdict[x.pkgspec]) == "fail"

        return (not is_failed, -rdeps, logdict[x.pkgspec])

    unknownsasfailures.sort(key=keyfunc)

    update_tpl(html_dir, section, problem_list[0], unknownsasfailures,
               logdict,
               PKG_ERROR_TPL, UNKNOWN_TPL, pkgsdb)

def process_section(section, config, problem_list,
                    recheck=False, recheck_failed=False, pkgsdb=None):
    """ Update .bug and .kpr files for logs in this section """

    # raises MissingSection if the section does not exist in piuparts.conf
    section_config = WKE_Section_Config(section)
    section_config.read(CONFIG_FILE)

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

    if not pkgsdb:
        distro_config = piupartslib.conf.DistroConfig(
                        DISTRO_CONFIG_FILE, section_config["mirror"])

        sectiondir = os.path.join(config['master-directory'], section)
        pkgsdb = piupartslib.packagesdb.PackagesDB(prefix=sectiondir)
        pkgsdb.load_packages_urls(
                distro_config.get_packages_urls(
                    section_config.get_distro(),
                    section_config.get_area(),
                    section_config.get_arch()))

    failures = FailureManager(logdict)
    failures.sort_by_bugged_and_rdeps(pkgsdb)

    update_html(section, logdict, problem_list, failures, config, pkgsdb)

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
                 description="Detect/process well known errors to html",
                 epilog="""
This script processes all log files against defined "known_problem" files,
caching the problems found, by package, into ".kpr" files. The cached data
is summarized into html ".tpl" files in <html_dir>/<section>, which are then
incorporated by piuparts-report into the final web reports.
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
    if conf["proxy"]:
        os.environ["http_proxy"] = conf["proxy"]

    sections = args.sections
    if not sections:
        sections = conf['sections'].split()

    problem_list = create_problem_list(conf['known-problem-directory'])

    detect_well_known_errors(sections, conf, problem_list, args.recheck,
                             args.recheck_failed)

# vi:set et ts=4 sw=4 :
