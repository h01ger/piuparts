# -*- coding: utf-8 -*-

# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# Copyright © 2012-2013 Andreas Beckmann (anbe@debian.org)
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
import collections
import re
import distro_info


class MissingSection(Exception):

    def __init__(self, filename, section):
        self.args = "Section %s not defined in configuration file %s" % \
            (section, filename),


class MissingMandatorySetting(Exception):

    def __init__(self, filename, key):
        self.args = "Value for %s not set in configuration file %s" % \
            (key, filename),


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
        if not cp.has_section(self._section):
            raise MissingSection(filename, self._section)
        for key in self.keys():
            if cp.has_option(self._section, key):
                self[key] = cp.get(self._section, key)
            elif self._defaults_section and cp.has_option(self._defaults_section, key):
                self[key] = cp.get(self._defaults_section, key)
            elif key in self._mandatory:
                raise MissingMandatorySetting(filename, key)

    def get_mirror(self, distro=None):
        if self["mirror"] is not None:
            return self["mirror"]
        return "http://http.debian.net/debian"

    def get_distros(self):
        if self["upgrade-test-distros"] is not None:
            return self["upgrade-test-distros"].split()
        return []

    def get_distro(self):
        if self["distro"]:
            return self["distro"]
        distros = self.get_distros()
        if distros:
            return distros[-1]
        return None

    def get_start_distro(self):
        distros = self.get_distros()
        if distros:
            return distros[0]
        return self["distro"]

    def get_final_distro(self):
        distros = self.get_distros()
        if distros:
            return distros[-1]
        return self["distro"]

    def _get_distmap(self):
        debdist = distro_info.DebianDistroInfo()

        # start with e.g. "sid" -> "unstable"
        distmap = collections.defaultdict(lambda: "unknown", [
            (debdist.old(), "oldstable"),
                              (debdist.devel(), "unstable"),
                              (debdist.stable(), "stable"),
                              (debdist.testing(), "testing"),
                              ("experimental", "experimental"),
                              ("rc", "experimental"),
        ])

        # add mappings for e.g. "oldstable" -> "oldstable"
        distmap.update(dict([(val, val) for key, val in distmap.iteritems()]))

        # map e.g. "Debian6" -> "oldstable" where debdist.old(result="fullname")
        # currently returns 'Debian 6.0 "Squeeze"'
        dkey = lambda x: "Debian" + re.split('[ \.]', x(result="fullname"))[1]
        dfuncs = [debdist.old, debdist.stable, debdist.testing]
        distmap.update(dict([(dkey(x), distmap[x()]) for x in dfuncs]))

        return distmap

    def _map_distro(self, distro):
        distro_root = re.split("[\-\.]", distro)[0]
        distmap = self._get_distmap()
        return distmap[distro_root]

    def get_std_distro(self, distrolist=[]):
        if not distrolist:
            distrolist = [self.get_distro()] + self.get_distros()
        mappedlist = [self._map_distro(x) for x in distrolist]
        return reduce(lambda x, y: y if y != "unknown" else x, mappedlist)

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


class DistroConfig(UserDict.UserDict):

    def __init__(self, filename, mirror):
        UserDict.UserDict.__init__(self)
        self._mirror = mirror
        self._defaults = {
            "uri": None,
                "distribution": None,
                "components": None,
                "target-release": None,
                "depends": None,
                "candidates": None,
        }
        cp = ConfigParser.SafeConfigParser()
        cp.read(filename)
        for section in cp.sections():
            self[section] = dict(self._defaults)
            for key in self._defaults.keys():
                if cp.has_option(section, key):
                    self[section][key] = cp.get(section, key)

    def get(self, section, key=None):
        if not section in self.keys():
            self[section] = dict(self._defaults, distribution=section)
        if not key is None:
            return self[section][key]
        return self[section]

    def _is_virtual(self, distro):
        uri = self.get(distro, "uri")
        return uri is not None and uri == "None"

    def get_mirror(self, distro):
        if self._is_virtual(distro):
            distro = self._expand_depends(distro)[0]
        return self.get(distro, "uri") or self._mirror

    def get_distribution(self, distro):
        if self._is_virtual(distro):
            distro = self._expand_depends(distro)[0]
        return self.get(distro, "distribution") or distro

    def get_candidates(self, distro):
        return (self.get(distro, "candidates") or "").split() or [distro]

    def _get_packages_url(self, distro, area, arch):
        return "%s/dists/%s/%s/binary-%s/Packages" % (
            self.get_mirror(distro),
                self.get_distribution(distro),
                area, arch)

    def get_packages_urls(self, distro, area, arch):
        return [self._get_packages_url(d, area, arch)
                for d in self.get_candidates(distro)]

    def _get_sources_url(self, distro, area):
        return "%s/dists/%s/%s/source/Sources" % (
            self.get_mirror(distro),
                self.get_distribution(distro),
                area)

    def get_sources_urls(self, distro, area):
        return [self._get_sources_url(d, area)
                for d in self.get_candidates(distro)]

    def get_target_flags(self, distro):
        tr = self.get(distro, "target-release")
        if tr:
            return ["-t", tr]
        return []

    def _expand_depends(self, distro, include_virtual=False):
        todo = [distro]
        done = []
        seen = []
        while todo:
            curr = todo[0]
            todo = todo[1:]
            if not curr in seen:
                seen.append(curr)
                todo = (self.get(curr, "depends") or "").split() + [curr] + todo
            elif not curr in done:
                if include_virtual or not self._is_virtual(curr):
                    done.append(curr)
        assert(len(done) > 0)
        return done

    def get_deb_lines(self, distro, components):
        lines = []
        for d in self._expand_depends(distro):
            for c in components:
                if self[d]["components"] is None or c in self[d]["components"].split():
                    lines.append("deb %s %s %s" % (
                        self.get_mirror(d),
                        self.get_distribution(d),
                        c))
        return lines

    def get_basetgz(self, distro, arch):
        # look for the first base distribution
        for d in self._expand_depends(distro):
            if self.get(d, "depends"):
                next  # skip partial distro
            return "%s_%s.tar.gz" % (self.get_distribution(d), arch)
        return None


# vi:set et ts=4 sw=4 :
