# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA


#
# NOTA BENE: This module MUST NOT use the logging module, since it can and
# will be used before logging is set up (because logging can be configured
# in a configuration file, that's why).
#

import ConfigParser
import UserDict


class MissingMandatorySetting(Exception):

    def __init__(self, filename, key):
        self.args = "Value for %s not set in configuration file %s" % \
            (key, filename)


class Config(UserDict.UserDict):

    def __init__(self, section, defaults, mandatory):
        UserDict.UserDict.__init__(self)
        self._section = section
        for key, value in defaults.iteritems():
            self[key] = value
        self._mandatory = mandatory
    
    def read(self, filename):
        cp = ConfigParser.ConfigParser()
        cp.read(filename)
        for key in self.keys():
            if cp.has_option(self._section, key):
                self[key] = cp.get(self._section, key)
            elif key in self._mandatory:
                raise MissingMandatorySetting(filename, key)
