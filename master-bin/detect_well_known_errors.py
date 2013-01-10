#!/usr/bin/python

import ConfigParser
import piupartslib
import os
import time

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
            }, "" )

def get_where( logpath ):
    """Convert a path to a log file to the 'where' component (e.g. 'pass')"""
    return( logpath.split('/')[-2] )

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

def process_section( section, config ):
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

def detect_well_known_errors( config ):

    for section in config['sections'].split(" "):
        print time.strftime( "%a %b %2d %H:%M:%S %Z %Y", time.localtime() )
        print "%s:" % section

        process_section( section, config )

    print time.strftime( "%a %b %2d %H:%M:%S %Z %Y", time.localtime() )

if __name__ == '__main__':

    conf = WKE_Config()
    conf.read( CONFIG_FILE )

    detect_well_known_errors( conf )
