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
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA


#
# NOTA BENE: This module MUST NOT use the logging module, since it can and
# will be used before logging is set up (because logging can be configured
# in a configuration file, that's why).
#

import ConfigParser
import UserDict
import subprocess


class MissingMandatorySetting(Exception):

    def __init__(self, filename, key):
        self.args = "Value for %s not set in configuration file %s" % \
            (key, filename)


class Config(UserDict.UserDict):

    def __init__(self, section, defaults, mandatory=[], defaults_section=None):
        UserDict.UserDict.__init__(self)
        self._section = section
        self._defaults_section = defaults_section
        for key, value in defaults.iteritems():
            self[key] = value
        self._mandatory = mandatory

    def read(self, filename):
        cp = ConfigParser.ConfigParser()
        cp.read(filename)
        for key in self.keys():
            if cp.has_option(self._section, key):
                self[key] = cp.get(self._section, key)
            elif self._defaults_section and cp.has_option(self._defaults_section, key):
                self[key] = cp.get(self._defaults_section, key)
            elif key in self._mandatory:
                raise MissingMandatorySetting(filename, key)

    def get_mirror(self):
        if self["mirror"] is not None:
            return self["mirror"]
        return "http://cdn.debian.net/debian"

    def get_distro(self):
        if self["distro"] is not None:
            return self["distro"]
        if self["upgrade-test-distros"] is not None:
            distros = self["upgrade-test-distros"].split()
            if distros:
                return distros[-1]
        return None

    def get_area(self):
        if self["area"] is not None:
            return self["area"]
        return "main"

    def get_arch(self):
        if not self["arch"]:
            # Try to figure it out ourselves, using dpkg
            p = subprocess.Popen(["dpkg", "--print-architecture"],
                                 stdout=subprocess.PIPE)
            self["arch"] = p.stdout.read().rstrip()
        return self["arch"]

    def get_packages_url(self, distro=None):
        if distro is None:
            distro = self.get_distro()
        return "%s/dists/%s/%s/binary-%s/Packages.bz2" % \
                (self.get_mirror(), distro, self.get_area(), self.get_arch())

    def get_sources_url(self):
        return "%s/dists/%s/%s/source/Sources.bz2" % \
                (self.get_mirror(), self.get_distro(), self.get_area())

# vi:set et ts=4 sw=4 :
