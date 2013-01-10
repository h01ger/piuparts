#!/usr/bin/python

import ConfigParser
import piupartslib
import os
import time
import re
import subprocess

CONFIG_FILE = "/etc/piuparts/piuparts.conf"
KPR_DIRS = ( 'pass', 'bugged', 'affected', 'fail' )

# tmp-use new extensions, so python script can be developed alongside the bash
KPR_EXT = '.kprn'
BUG_EXT = '.bug'
LOG_EXT = '.log'

class WKE_Config( piupartslib.conf.Config ):
    """Configuration parameters for Well Known Errors"""

    def __init__( self ):
        self.section = 'global'

        piupartslib.conf.Config.__init__( self, self.section,
            {
                "sections": "sid",
                "master-directory": "/var/lib/piuparts/master/",
                "known-problem-directory": "/usr/share/piuparts/known_problems",
            }, "" )

class Problem():
    """ Encapsulate a particular known problem """

    def __init__(self, probpath):
        """probpath is the path to the problem definition file"""

        self.probpath = probpath
        self.name = os.path.basename(probpath)
        self.short_name = os.path.splitext( self.name )[0]

        self.init_problem()

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

            self.__dict__[name] = value

        self.WHERE = self.WHERE.split(" ")

    def has_problem(self, logbody, where):
        """Does the log text 'logbody' contain this known problem?"""

        if where in self.WHERE:

            s = subprocess.Popen( self.COMMAND, stdin=subprocess.PIPE,
                 stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True )
            s.communicate( logbody )

            if s.returncode != 1:
                return( True )

        return( False )

def get_where( logpath ):
    """Convert a path to a log file to the 'where' component (e.g. 'pass')"""
    return( logpath.split('/')[-2] )

def replace_ext( fpath, newext ):
    basename = os.path.splitext( os.path.split(fpath)[1] )[0]
    return('/'.join( fpath.split('/')[:-1] + [basename + newext] ))

def get_kpr_path( logpath ):
    """Return the kpr file path for a particular log path"""
    return( replace_ext( logpath, KPR_EXT ) )

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

def mtime( path ):
    return os.path.getmtime(path)

def clean_cache_files( logdict, cachedict, skipnewer=False ):
    """Delete files in cachedict if the corresponding logdict file is missing
       or newer"""

    count = 0
    for pkgspec in cachedict:
        if pkgspec not in logdict \
        or (mtime(logdict[pkgspec]) > mtime(cachedict[pkgspec])
            and not skipnewer) \
        or get_where(logdict[pkgspec]) != get_where(cachedict[pkgspec]):

            try:
                os.remove(cachedict[pkgspec])
                count = count + 1
            except OSError:
                print "Error deleting %s" % cachedict[pkgspec]

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

def process_section( section, config, problem_list ):
    """ Update .bug and .kpr files for logs in this section """

    sectiondir = os.path.join( config['master-directory'], section )
    workdirs = [ os.path.join(sectiondir,x) for x in KPR_DIRS ]

    if not os.access( sectiondir, os.F_OK ):
        return

    [os.mkdir(x) for x in workdirs if not os.path.exists(x)]

    (logdict, kprdict, bugdict) = [ get_file_dict(workdirs, x ) \
            for x in [LOG_EXT, KPR_EXT, BUG_EXT] ]

    del_cnt = clean_cache_files( logdict, kprdict )
    clean_cache_files( logdict, bugdict, True )

    (kprdict, bugdict) = [get_file_dict(workdirs,x) for x in [KPR_EXT, BUG_EXT]]

    add_cnt = make_kprs( logdict, kprdict, problem_list )

def detect_well_known_errors( config, problem_list ):

    for section in config['sections'].split(" "):
        print time.strftime( "%a %b %2d %H:%M:%S %Z %Y", time.localtime() )
        print "%s:" % section

        process_section( section, config, problem_list )

    print time.strftime( "%a %b %2d %H:%M:%S %Z %Y", time.localtime() )

def create_problem_list( pdir ):

    pfiles = [x for x in sorted(os.listdir(pdir)) if x.endswith(".conf")]
    plist = [Problem(os.path.join(pdir,x)) for x in pfiles]

    return plist

if __name__ == '__main__':

    conf = WKE_Config()
    conf.read( CONFIG_FILE )

    problem_list = create_problem_list( conf['known-problem-directory'] )

    detect_well_known_errors( conf, problem_list )
