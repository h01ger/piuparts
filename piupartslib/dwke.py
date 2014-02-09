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
import logging
import re
from collections import namedtuple


KPR_EXT = '.kpr'
BUG_EXT = '.bug'
LOG_EXT = '.log'


class Problem():
    """ Encapsulate a particular known problem """

    def __init__(self, probpath):
        """probpath is the path to the problem definition file"""

        self.probpath = probpath
        self.name = os.path.basename(probpath)
        self.short_name = os.path.splitext(self.name)[0]

        self.tags_are_valid = True

        self.required_tags = ["PATTERN", "WHERE", "ISSUE",
                              "HEADER", "HELPTEXT"]
        self.optional_tags = ["EXCLUDE_PATTERN", "EXPLAIN", "PRIORITY"]


        self.init_problem()

        for tag in self.required_tags:
            if not tag in self.__dict__:
                self.tags_are_valid = False

        if "PATTERN" in self.__dict__:
            self.inc_re = re.compile(self.PATTERN)
        else:
            self.inc_re = None

        if "EXCLUDE_PATTERN" in self.__dict__:
            self.exc_re = re.compile(self.EXCLUDE_PATTERN)
        else:
            self.exc_re = None

    def valid(self):
        return self.tags_are_valid

    def init_problem(self):
        """Load problem file parameters (HELPTEXT="foo" -> self.HELPTEXT)"""

        pb = open(self.probpath, 'r')
        probbody = pb.read()
        pb.close()

        tagged = re.sub("^([A-Z]+=)", "<hdr>\g<0>", probbody, 0, re.MULTILINE)

        for chub in re.split('<hdr>', tagged)[1:]:

            (name, value) = re.split("=", chub, 1, re.MULTILINE)

            while value[-1] == '\n':
                value = value[:-1]

            if  re.search("^\'.+\'$", value, re.MULTILINE|re.DOTALL) \
             or re.search('^\".+\"$', value, re.MULTILINE|re.DOTALL):
                value = value[1:-1]

            if name in self.required_tags or name in self.optional_tags:
                self.__dict__[name] = value
            else:
                self.tags_are_valid = False

        self.WHERE = self.WHERE.split(" ")

    def has_problem(self, logbody, where):
        """Does the log text 'logbody' contain this known problem?"""

        if where in self.WHERE:
            if self.inc_re.search(logbody, re.MULTILINE):
                for line in logbody.splitlines():
                    if self.inc_re.search(line):
                        if self.exc_re == None \
                               or not self.exc_re.search(line):
                            return True

        return False

    def get_command(self):

        cmd = "grep -E \"%s\"" % self.PATTERN

        if "EXCLUDE_PATTERN" in self.__dict__:
            cmd += " | grep -v -E \"%s\"" % self.EXCLUDE_PATTERN

        return cmd


class FailureManager():
    """Class to track known failures encountered, by package,
       where (e.g. 'fail'), and known problem type"""

    def __init__(self, logdict):
        """logdict is {pkgspec: fulllogpath} across all log files"""

        self.logdict = logdict
        self.failures = []

        self.load_failures()

    def load_failures(self):
        """Collect failures across all kpr files, as named tuples"""

        for pkgspec in self.logdict:
            logpath = self.logdict[pkgspec]
            try:
                kp = open(get_kpr_path(logpath), 'r')

                for line in kp.readlines():
                    (where, problem) = self.parse_kpr_line(line)

                    self.failures.append(make_failure(where, problem, pkgspec))

                kp.close()
            except IOError:
                logging.error("Error processing %s" % get_kpr_path(logpath))

    def parse_kpr_line(self, line):
        """Parse a line in a kpr file into where (e.g. 'pass') and problem name"""

        m = re.search("^([a-z]+)/.+ (.+)$", line)
        return (m.group(1), m.group(2))

    def sort_by_path(self):
        self.failures.sort(key=lambda x: self.logdict[x.pkgspec])

    def sort_by_bugged_and_rdeps(self, pkgsdb):
        self.pkgsdb = pkgsdb

        def keyfunc(x, pkgsdb=self.pkgsdb, logdict=self.logdict):
            rdeps = pkgsdb.rrdep_count(get_pkg(x.pkgspec))

            is_failed = get_where(logdict[x.pkgspec]) == "fail"

            return (not is_failed, -rdeps, logdict[x.pkgspec])

        self.failures.sort(key=keyfunc)

    def filtered(self, problem):
        return [x for x in self.failures if problem==x.problem]


def make_failure(where, problem, pkgspec):
    return (namedtuple('Failure', 'where problem pkgspec')(where, problem, pkgspec))

def get_where(logpath):
    """Convert a path to a log file to the 'where' component (e.g. 'pass')"""
    return logpath.split('/')[-2]

def replace_ext(fpath, newext):
    basename = os.path.splitext(os.path.split(fpath)[1])[0]
    return '/'.join(fpath.split('/')[:-1] + [basename + newext])

def get_pkg(pkgspec):
    return pkgspec.split('_')[0]

def get_kpr_path(logpath):
    """Return the kpr file path for a particular log path"""
    return replace_ext(logpath, KPR_EXT)

def get_file_dict(workdirs, ext):
    """For files in [workdirs] with extension 'ext', create a dict of
       <pkgname>_<version>: <path>"""

    filedict = {}

    for dir in workdirs:
        for fl in os.listdir(dir):
            if os.path.splitext(fl)[1] == ext:
                filedict[os.path.splitext(os.path.basename(fl))[0]] \
                    = os.path.join(dir, fl)

    return filedict


def create_problem_list(pdir):

    plist = []

    for pfile in [x for x in sorted(os.listdir(pdir)) if x.endswith(".conf")]:
        prob = Problem(os.path.join(pdir, pfile))

        if prob.valid():
            plist.append(prob)
        else:
            logging.error("Keyword error in %s - skipping" % pfile)

    return plist

# vi:set et ts=4 sw=4 :
