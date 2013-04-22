#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2013 David Steele (dsteele@gmail.com)
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
import time
import re
from collections import namedtuple

import piupartslib
from piupartslib.conf import MissingSection


CONFIG_FILE = "/etc/piuparts/piuparts.conf"
DISTRO_CONFIG_FILE = "/etc/piuparts/distros.conf"
KPR_DIRS = ( 'pass', 'bugged', 'affected', 'fail' )

KPR_EXT = '.kpr'
BUG_EXT = '.bug'
LOG_EXT = '.log'
TPL_EXT = '.tpl'

PROB_TPL = \
"""<table class="righttable"><tr class="titlerow"><td class="titlecell">
$HEADER in $SECTION, sorted by reverse dependency count.
</td></tr><tr class="normalrow"><td class="contentcell2">
$HELPTEXT
<p>The commandline to find these logs is: <pre>
COMMAND='$COMMAND'
</pre></p>
</td></tr><tr class="titlerow"><td class="alerttitlecell">Please file bugs!</td></tr><tr class="normalrow"><td class="contentcell2" colspan="3">
<ul>
$PACKAGE_LIST</ul>
<p>Affected packages in $SECTION: $COUNT</p></td></tr></table>
"""

UNKNOWN_TPL = \
"""<table class="righttable"><tr class="titlerow"><td class="titlecell">
Packages with unknown failures detected in $SECTION, sorted by reverse dependency count.
</td></tr><tr class="normalrow"><td class="contentcell2">
<p>Please investigate and improve detection of known error types!</p>
</td></tr><tr class="titlerow"><td class="alerttitlecell">Please file bugs!</td></tr><tr class="normalrow"><td class="contentcell2" colspan="3">
<ul>
$PACKAGE_LIST
</ul>
<p>Affected packages in $SECTION: $COUNT</p></td></tr></table>
"""

PKG_ERROR_TPL = \
"""<li>$RDEPS - <a href=\"$LOG\">$LOG</a>
    (<a href=\"http://packages.qa.debian.org/$SDIR/$SPKG.html\" target=\"_blank\">PTS</a>)
    (<a href=\"http://bugs.debian.org/$PACKAGE?dist=unstable\" target=\"_blank\">BTS</a>)
$BUG</li>
"""

class WKE_Config( piupartslib.conf.Config ):
    """Configuration parameters for Well Known Errors"""

    def __init__( self ):
        self.section = 'global'

        piupartslib.conf.Config.__init__( self, self.section,
            {
                "sections": "report",
                "output-directory": "html",
                "master-directory": ".",
                "known-problem-directory": None,
                "proxy": None,
            }, "" )

class WKE_Section_Config( piupartslib.conf.Config ):

    def __init__( self, section ):
        self.section = section

        piupartslib.conf.Config.__init__( self, self.section,
            {
                "mirror": None,
                "distro": None,
                "area": None,
                "arch": None,
                "upgrade-test-distros": None,
            }, "",  defaults_section="global" )

class Problem():
    """ Encapsulate a particular known problem """

    def __init__(self, probpath):
        """probpath is the path to the problem definition file"""

        self.probpath = probpath
        self.name = os.path.basename(probpath)
        self.short_name = os.path.splitext( self.name )[0]

        self.tags_are_valid = True

        self.required_tags = [ "PATTERN", "WHERE", "ISSUE",
                               "HEADER", "HELPTEXT"]
        self.optional_tags = ["EXCLUDE_PATTERN", "EXPLAIN", "PRIORITY"]


        self.init_problem()

        for tag in self.required_tags:
            if not tag in self.__dict__:
                self.tags_are_valid = False

        self.inc_re = re.compile( self.PATTERN )

        if "EXCLUDE_PATTERN" in self.__dict__:
            self.exc_re = re.compile( self.EXCLUDE_PATTERN )
        else:
            self.exc_re = None

    def valid(self):
        return self.tags_are_valid

    def init_problem(self):
        """Load problem file parameters (HELPTEXT="foo" -> self.HELPTEXT)"""

        pb = open( self.probpath, 'r' )
        probbody = pb.read()
        pb.close()

        tagged = re.sub( "^([A-Z]+=)", "<hdr>\g<0>", probbody, 0, re.MULTILINE)

        for chub in re.split( '<hdr>', tagged )[1:]:

            (name,value) = re.split( "=", chub, 1, re.MULTILINE )

            while value[-1] == '\n':
                value = value[:-1]

            if  re.search( "^\'.+\'$", value, re.MULTILINE|re.DOTALL ) \
             or re.search( '^\".+\"$', value, re.MULTILINE|re.DOTALL ):
                value = value[1:-1]

            if name in self.required_tags or name in self.optional_tags:
                self.__dict__[name] = value
            else:
                self.tags_are_valid = False

        self.WHERE = self.WHERE.split(" ")

    def has_problem(self, logbody, where):
        """Does the log text 'logbody' contain this known problem?"""

        if where in self.WHERE:
            if self.inc_re.search( logbody, re.MULTILINE ):
                for line in logbody.splitlines():
                    if self.inc_re.search( line ):
                        if self.exc_re == None \
                               or not self.exc_re.search(line):
                            return( True )

        return( False )

    def get_command(self):

        cmd = "grep -E \"%s\"" % self.PATTERN

        if "EXCLUDE_PATTERN" in self.__dict__:
            cmd += " | grep -v -E \"%s\"" % self.EXCLUDE_PATTERN

        return(cmd)

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
                kp = open( get_kpr_path(logpath), 'r' )

                for line in kp.readlines():
                    (where, problem) = self.parse_kpr_line( line )

                    self.failures.append( make_failure(where, problem, pkgspec) )

                kp.close()
            except IOError:
                print "Error processing %s" % get_kpr_path(logpath)

    def parse_kpr_line( self, line ):
        """Parse a line in a kpr file into where (e.g. 'pass') and problem name"""

        m = re.search( "^([a-z]+)/.+ (.+)$", line )
        return( m.group(1), m.group(2) )

    def sort_by_path( self ):
        self.failures.sort(key=lambda x: self.logdict[x.pkgspec])

    def sort_by_bugged_and_rdeps( self, pkgsdb ):
        self.pkgsdb = pkgsdb

        def keyfunc( x, pkgsdb=self.pkgsdb, logdict=self.logdict):
            try:
                pkg_name = get_pkg(x.pkgspec)
                rdeps = pkgsdb.get_package(pkg_name).rrdep_count()
            except KeyError:
                rdeps = 0

            is_failed = get_where(logdict[x.pkgspec]) == "fail"

            return( (not is_failed, -rdeps, logdict[x.pkgspec]) )

        self.failures.sort( key=keyfunc )

    def filtered( self, problem ):
        return([x for x in self.failures if problem==x.problem])

def make_failure( where, problem, pkgspec ):
    return(namedtuple('Failure', 'where problem pkgspec')(where, problem, pkgspec))

def get_where( logpath ):
    """Convert a path to a log file to the 'where' component (e.g. 'pass')"""
    return( logpath.split('/')[-2] )

def replace_ext( fpath, newext ):
    basename = os.path.splitext( os.path.split(fpath)[1] )[0]
    return('/'.join( fpath.split('/')[:-1] + [basename + newext] ))

def get_pkg( pkgspec ):
    return( pkgspec.split('_')[0] )

def get_kpr_path( logpath ):
    """Return the kpr file path for a particular log path"""
    return( replace_ext( logpath, KPR_EXT ) )

def pts_subdir( source ):
    if source[:3] == "lib":
      return source[:4]
    else:
      return source[:1]

def source_pkg( pkgspec, db ):
    source_name = db.get_control_header(get_pkg(pkgspec), "Source")

    return( source_name )

def get_file_dict( workdirs, ext ):
    """For files in [workdirs] with extension 'ext', create a dict of
       <pkgname>_<version>: <path>"""

    filedict = {}

    for dir in workdirs:
        for fl in os.listdir(dir):
            if os.path.splitext(fl)[1] == ext:
                filedict[os.path.splitext(os.path.basename(fl))[0]] \
                    = os.path.join(dir,fl)

    return filedict

def get_pkgspec( logpath ):
    """For a log full file spec, return the pkgspec (<pkg>_<version)"""
    return( logpath.split('/')[-1] )

def get_bug_text(logpath):
    bugpath = replace_ext(logpath, BUG_EXT)

    txt = ""
    if os.path.exists(bugpath):
        bf = open( bugpath, 'r' )
        txt = bf.read()
        bf.close()

    return txt

def section_path( logpath ):
    """Convert a full log path name to one relative to the section directory"""
    return( '/'.join( [get_where(logpath), get_pkgspec(logpath)] ) )

def mtime( path ):
    return os.path.getmtime(path)

def clean_cache_files( logdict, cachedict, recheck=False, recheck_failed=False,
   skipnewer=False ):
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

            try:
                os.remove(cachedict[pkgspec])
                count = count + 1
            except OSError:
                print "Error deleting %s" % cachedict[pkgspec]
      except IOError:
	# logfile may have disappeared
	pass

    return( count )

def make_kprs( logdict, kprdict, problem_list ):
    """Create kpr files, as necessary, so every log file has one
       kpr entries are e.g.
           fail/xorg-docs_1:1.6-1.log broken_symlinks_error.conf"""

    needs_kpr = set(logdict.keys()).difference(set(kprdict.keys()))

    for pkg_spec in needs_kpr:
        logpath = logdict[pkg_spec]

        try:
            lb = open( logpath, 'r' )
            logbody = lb.read()
            lb.close()

            where = get_where( logpath )

            kf = open( get_kpr_path(logpath), 'a')

            for problem in problem_list:
                if( problem.has_problem( logbody, where ) ):
                    kf.write( "%s/%s.log %s\n" % (where, pkg_spec, problem.name) )

            kf.close()
        except IOError:
            print "File error processing %s" % logpath

    return( len(needs_kpr) )

def populate_tpl( tmpl, vals ):

    for key in vals:
        tmpl = re.sub( "\$%s" % key, str(vals[key]), tmpl )

    return tmpl

def update_tpl( basedir, section, problem, failures, logdict, ftpl, ptpl, pkgsdb ):

    pkg_text = ""
    bugged_section = False
    for failure in failures:

        pkgspec = failure.pkgspec
        bin_pkg = get_pkg(pkgspec)
        try:
            src_pkg = source_pkg(pkgspec, pkgsdb)
            rdep_cnt = pkgsdb.get_package(bin_pkg).rrdep_count()
        except KeyError:
            src_pkg = bin_pkg
            rdep_cnt = 0

        if (not bugged_section) and "bugged" in logdict[pkgspec]:
            bugged_section = True
            pkg_text += "<br>\n"

        pkg_text += populate_tpl(ftpl, {
                                'LOG': section_path(logdict[pkgspec]),
                                'PACKAGE': bin_pkg,
                                'BUG': get_bug_text(logdict[pkgspec]),
                                'RDEPS': rdep_cnt,
                                'SDIR':pts_subdir(src_pkg),
                                'SPKG':src_pkg,
                                   } )

    if len(pkg_text):
        pf = open(os.path.join(basedir, failures[0].problem[:-5] + TPL_EXT),'w')
        tpl_text = populate_tpl( ptpl, {
                                'HEADER': problem.HEADER,
                                'SECTION': section,
                                'HELPTEXT': problem.HELPTEXT,
                                'COMMAND': problem.get_command(),
                                'PACKAGE_LIST': pkg_text,
                                'COUNT': len(failures),
                                } )

        pf.write( tpl_text )
        pf.close()

def update_html( section, logdict, problem_list, failures, config, pkgsdb ):

    html_dir = os.path.join( config['output-directory'], section )
    if not os.path.exists( html_dir ):
        os.mkdir( html_dir )

    for problem in problem_list:
        update_tpl( html_dir, section, problem,
                    failures.filtered(problem.name),
                    logdict,
                    PKG_ERROR_TPL, PROB_TPL, pkgsdb )

    # Make a failure list of all failed packages that don't show up as known
    failedpkgs = set([x for x in logdict.keys()
                     if get_where(logdict[x]) != 'pass'])
    knownfailpkgs = set([failure.pkgspec for failure in failures.failures])
    unknownsasfailures = [make_failure("","unknown_failures.conf",x)
                         for x in failedpkgs.difference(knownfailpkgs)]

    def keyfunc( x, pkgsdb=pkgsdb, logdict=logdict):
        try:
            pkg_name = get_pkg(x.pkgspec)
            rdeps = pkgsdb.get_package(pkg_name).rrdep_count()
        except KeyError:
            rdeps = 0

        is_failed = get_where(logdict[x.pkgspec]) == "fail"

        return( (not is_failed, -rdeps, logdict[x.pkgspec]) )

    unknownsasfailures.sort( key=keyfunc )

    update_tpl( html_dir, section, problem_list[0], unknownsasfailures,
                logdict,
                PKG_ERROR_TPL, UNKNOWN_TPL, pkgsdb )

def process_section( section, config, problem_list,
                     recheck=False, recheck_failed=False, pkgsdb=None ):
    """ Update .bug and .kpr files for logs in this section """

    # raises MissingSection if the section does not exist in piuparts.conf
    section_config = WKE_Section_Config( section )
    section_config.read( CONFIG_FILE )

    sectiondir = os.path.join( config['master-directory'], section )
    workdirs = [ os.path.join(sectiondir,x) for x in KPR_DIRS ]

    if not os.access( sectiondir, os.F_OK ):
        return

    [os.mkdir(x) for x in workdirs if not os.path.exists(x)]

    (logdict, kprdict, bugdict) = [ get_file_dict(workdirs, x ) \
            for x in [LOG_EXT, KPR_EXT, BUG_EXT] ]

    del_cnt = clean_cache_files( logdict, kprdict, recheck, recheck_failed )
    clean_cache_files( logdict, bugdict, skipnewer=True )

    (kprdict, bugdict) = [get_file_dict(workdirs,x) for x in [KPR_EXT, BUG_EXT]]

    add_cnt = make_kprs( logdict, kprdict, problem_list )

    if not pkgsdb:
        oldcwd = os.getcwd()
        os.chdir(config['master-directory'])

        distro_config = piupartslib.conf.DistroConfig(
                        DISTRO_CONFIG_FILE, section_config["mirror"])

        pkgsdb = piupartslib.packagesdb.PackagesDB(prefix=section)

        pkgs_url = distro_config.get_packages_url(
                   section_config.get_distro(),
                   section_config.get_area(),
                   section_config.get_arch() )
        pkg_fl = piupartslib.open_packages_url(pkgs_url)
        pkgsdb.read_packages_file(pkg_fl)
        pkg_fl.close()

        pkgsdb.compute_package_states()
        pkgsdb.calc_rrdep_counts()

        os.chdir(oldcwd)

    failures = FailureManager( logdict )
    failures.sort_by_bugged_and_rdeps(pkgsdb)

    update_html( section, logdict, problem_list, failures, config, pkgsdb )

    return( del_cnt, add_cnt, failures )

def detect_well_known_errors( config, problem_list, recheck, recheck_failed ):

    for section in config['sections'].split():
      try:
        print time.strftime( "%a %b %2d %H:%M:%S %Z %Y", time.localtime() )
        print "%s:" % section

        ( del_cnt, add_cnt, failures ) = \
                  process_section( section, config, problem_list,
                                   recheck, recheck_failed )

        print "parsed logfiles: %d removed, %d added" % (del_cnt, add_cnt)

        for prob in problem_list:
            pcount = len(failures.filtered(prob.name))
            if pcount:
                print "%7d %s" % (pcount, prob.name)
      except MissingSection:
        pass

    print time.strftime( "%a %b %2d %H:%M:%S %Z %Y", time.localtime() )

def create_problem_list( pdir ):

    plist = []

    for pfile in [x for x in sorted(os.listdir(pdir)) if x.endswith(".conf")]:
        prob = Problem(os.path.join(pdir,pfile))

        if prob.valid():
            plist.append(prob)
        else:
            print "Keyword error in %s - skipping" % pfile

    return plist

if __name__ == '__main__':

    conf = WKE_Config()
    conf.read( CONFIG_FILE )
    if conf["proxy"]:
        os.environ["http_proxy"] = conf["proxy"]

    problem_list = create_problem_list( conf['known-problem-directory'] )

    detect_well_known_errors( conf, problem_list, False, False )

# vi:set et ts=4 sw=4 :
