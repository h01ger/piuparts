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

class WKE_Config( piupartslib.conf.Config ):
    """Configuration parameters for Well Known Errors"""

    def __init__( self ):
        self.section = 'global'

        piupartslib.conf.Config.__init__( self, self.section,
            {
                "sections": "sid",
                "master-directory": "/var/lib/piuparts/master/",
            }, "" )

def process_section( section, config ):
    """ Update .bug and .kpr files for logs in this section """

    sectiondir = os.path.join( config['master-directory'], section )
    workdirs = [ os.path.join(sectiondir,x) for x in KPR_DIRS ]

    if not os.access( sectiondir, os.F_OK ):
        return

    [os.mkdir(x) for x in workdirs if not os.path.exists(x)]

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
