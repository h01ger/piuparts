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


"""Packages database for distributed piuparts processing

This module contains tools for keeping track of which packages have
been tested, the test results, and for determining what to test next.

Lars Wirzenius <liw@iki.fi>
"""


import dircache
import os
import tempfile
import UserDict
import apt_pkg

from piupartslib.dependencyparser import DependencyParser

apt_pkg.init_system()


def rfc822_like_header_parse(input):
    headers = []
    while 1:
        line = input.readline()
        if not line or line in ["\r\n", "\n"]:
            break
        if headers and line and line[0].isspace():
            headers[-1] = headers[-1] + line
        else:
            headers.append(line)
    return headers

class Package(UserDict.UserDict):

    def __init__(self, headers):
        UserDict.UserDict.__init__(self)
        self.headers = headers
        for header in headers:
            name, value = header.split(":", 1)
            self[name.strip()] = value.strip()
        self._parsed_deps = {}
        self._parsed_alt_deps = {}

    def _parse_dependencies(self, header_name):
        if header_name in self._parsed_deps:
            depends = self._parsed_deps[header_name]
        else:
            parser = DependencyParser(self[header_name])
            depends = parser.get_dependencies()
            depends = [alternatives[0].name for alternatives in depends]
            self._parsed_deps[header_name] = depends
        return depends

    def _parse_alternative_dependencies(self, header_name):
        if header_name in self._parsed_alt_deps:
            depends = self._parsed_alt_deps[header_name]
        else:
            parser = DependencyParser(self[header_name])
            depends = parser.get_dependencies()
            depends = [[alt.name for alt in alternatives] for alternatives in depends]
            self._parsed_alt_deps[header_name] = depends
        return depends

    # first alternative only - [package_name...]
    def dependencies(self):
        vlist = []
        for header in ["Depends", "Pre-Depends"]:
            if header in self:
                vlist += self._parse_dependencies(header)
        return vlist

    # all alternatives - [[package_name...]...]
    def all_dependencies(self):
        vlist = []
        for header in ["Depends", "Pre-Depends"]:
            if header in self:
                vlist += self._parse_alternative_dependencies(header)
        return vlist

    def depends_with_alts(self, header_name):
        vlist = []
        if header_name in self:
            parser = DependencyParser(self[header_name])
            vlist += parser.get_dependencies()
        return vlist

    def prefer_alt_depends(self, header_name,dep_idx,dep):
        if header_name in self:
            if header_name not in self._parsed_deps:
                  self._parse_dependencies(header_name)
            if self._parsed_deps[header_name][dep_idx]:
                self._parsed_deps[header_name][dep_idx] = dep.name

    def provides(self):
        vlist = []
        for header in ["Provides"]:
            if header in self:
                vlist += self._parse_dependencies(header)
        return vlist

    def is_testable(self):
        """Are we testable at all? Required aren't."""
        return self.get("Priority", "") != "required"

    def dump(self, output_file):
        output_file.write("".join(self.headers))


class PackagesFile(UserDict.UserDict):

    def __init__(self, input):
        UserDict.UserDict.__init__(self)
        self._read_file(input)

    def _read_file(self, input):
        """Parse a Packages file and add its packages to us-the-dict"""
        while True:
            headers = rfc822_like_header_parse(input)
            if not headers:
                break
            p = Package(headers)
            if p["Package"] in self:
                q = self[p["Package"]]
                if apt_pkg.version_compare(p["Version"], q["Version"]) <= 0:
                    # there is already a newer version
                    continue
            self[p["Package"]] = p


class LogDB:

    def listdir(self, dirname):
        return dircache.listdir(dirname)

    def exists(self, pathname):
        try:
            cache = self.exists_cache
        except AttributeError:
            self.exists_cache = {}
            cache = self.exists_cache
        if pathname not in cache:
            cache[pathname] = os.path.exists(pathname)
        return cache[pathname]

    def open_file(self, pathname, mode):
        return file(pathname, mode)

    def remove_file(self, pathname):
        os.remove(pathname)

    def _log_name(self, package, version):
        return "%s_%s.log" % (package, version)

    def log_exists(self, package, subdirs):
        log_name = self._log_name(package["Package"], package["Version"])
        for subdir in subdirs:
            if self.exists(os.path.join(subdir, log_name)):
                return True
        return False

    def create(self, subdir, package, version, contents):
        (fd, temp_name) = tempfile.mkstemp(dir=subdir)
        os.close(fd)

        # tempfile.mkstemp sets the file mode to be readable only by owner.
        # Let's make it follow the umask.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp_name, 0666 & ~umask)

        full_name = os.path.join(subdir, self._log_name(package, version))
        try:
            os.link(temp_name, full_name)
        except OSError, detail:
            os.remove(temp_name)
            return False
        os.remove(temp_name)
        f = self.open_file(full_name, "w")
        f.write(contents)
        f.close()
        return True

    def remove(self, subdir, package, version):
        full_name = os.path.join(subdir, self._log_name(package, version))
        if self.exists(full_name):
            self.remove_file(full_name)


class PackagesDB:

    # keep in sync with piuparts-report.py: emphasize_reason()
    # FIXME: can we reorder this list or remove entries without breaking the counts.txt for the plot?
    _states = [
        "successfully-tested",
        "failed-testing",
        "cannot-be-tested",
        "essential-required",
        "waiting-to-be-tested",
        "waiting-for-dependency-to-be-tested",
        "dependency-failed-testing",
        "dependency-cannot-be-tested",
        "dependency-does-not-exist",
        "circular-dependency",
        "unknown",
        "unknown-preferred-alternative",
        "no-dependency-from-alternatives-exists",
        #"does-not-exist",  # can only happen as query result for a dependency
    ]

    _dep_state_to_state = {
        "failed-testing": "dependency-failed-testing",
        "cannot-be-tested": "dependency-cannot-be-tested",
        "waiting-to-be-tested": "waiting-for-dependency-to-be-tested",
        "waiting-for-dependency-to-be-tested": "waiting-for-dependency-to-be-tested",
        "dependency-failed-testing": "dependency-failed-testing",
        "dependency-cannot-be-tested": "dependency-cannot-be-tested",
        "dependency-does-not-exist": "dependency-does-not-exist",
        "unknown-preferred-alternative": "unknown-preferred-alternative",
        "no-dependency-from-alternatives-exists": "dependency-cannot-be-tested",
        "does-not-exist": "dependency-does-not-exist",
    }

    def __init__(self, logdb=None, prefix=None):
        self.prefix = prefix
        self._packages_files = []
        self._ready_for_testing = None
        self._logdb = logdb or LogDB()
        self._packages = None
        self._in_state = None
        self._package_state = {}
        self.set_subdirs(ok="pass", fail="fail", evil="untestable",
                         reserved="reserved", morefail=["bugged"])

    def set_subdirs(self, ok=None, fail=None, evil=None, reserved=None, morefail=None):
        # Prefix all the subdirs with the prefix
        if self.prefix:
            pformat = self.prefix + "/%s"
        else:
            pformat = "%s"
        if ok:
            self._ok = pformat % ok
        if fail:
            self._fail = pformat % fail
        if evil:
            self._evil = pformat % evil
        if reserved:
            self._reserved = pformat % reserved
        if morefail:
            self._morefail = [pformat % s for s in morefail]
        self._all = [self._ok, self._fail, self._evil, self._reserved] + self._morefail

    def create_subdirs(self):
        for sdir in self._all:
            if not os.path.exists(sdir):
                os.makedirs(sdir)

    def read_packages_file(self, input):
        self._packages_files.append(PackagesFile(input))
        self._packages = None

    def set_known_circular_depends(self, known_circular_depends=[]):
        self._known_circular_depends = []
        self._known_circular_depends = list(known_circular_depends)

    def _find_all_packages(self):
        if self._packages is None:
            self._packages = {}
            self._virtual_packages = {}
            for pf in self._packages_files:
                for p in pf.values():
                    self._packages[p["Package"]] = p
            for p in self._packages.values():
                for provided in p.provides():
                    if provided != p["Package"]:
                        if provided not in self._virtual_packages:
                            self._virtual_packages[provided] = []
                        self._virtual_packages[provided].append(p["Package"])

    def _get_recursive_dependencies(self, package, break_circles=True):
        assert self._packages is not None
        deps = []
        more = package.dependencies()
        while more:
            dep = more[0]
            more = more[1:]
            if dep not in deps:
                deps.append(dep)
                if dep in self._packages:
                    more += self._packages[dep].dependencies()
                elif dep in self._virtual_packages:
                    more += self._packages[self._virtual_packages[dep][0]].dependencies()

        # Break circular dependencies
        if break_circles and package["Package"] in deps:
            deps.remove(package["Package"])

        return deps

    def _compute_package_state(self, package):
        if self._logdb.log_exists(package, [self._ok]):
            return "successfully-tested"
        if self._logdb.log_exists(package, [self._fail] + self._morefail):
            return "failed-testing"
        if self._logdb.log_exists(package, [self._evil]):
            return "cannot-be-tested"
        if not package.is_testable():
            return "essential-required"

        # First attempt to resolve (still-unresolved) multiple alternative depends
        # Definitely sub-optimal, but improvement over blindly selecting first one
        # 1) Prefer first alternative = "essential-required", prefer it
        # 2) If no "essential-required", prefer first alternative = "successfully-tested"
        # 3) Otherwise, prefer first alternative =  "waiting-to-be-tested" IF NO REMAINING
        #    are "unknown/fail"
        #
        # Problems:
        #   a) We will test and fail when >=1 "successfully-tested" but another
        #      that failed is selected by apt during test run
        #   b) False positive "Dependency failed/cannot be tested"; however
        #       more accurately "waiting-for-dependency-to-be-tested"

        state = None
        for header in ["Depends", "Pre-Depends"]:
            alt_deps=package.depends_with_alts(header)
            for d in range(len(alt_deps)):
                if len(alt_deps[d]) > 1:
                    alt_found = 0
                    alt_fails = 0
                    alt_unknowns = 0
                    alt_state = None
                    prefer_alt_score = 0
                    prefer_alt_idx = 0
                    prefer_alt = None
                    for alternative in alt_deps[d]:
                        dep = alternative.name
                        altdep_state = self.get_package_state(dep)
                        if altdep_state != "does-not-exist":
                            alt_found += 1
                            if prefer_alt_score < 3 and altdep_state == "essential-required":
                                prefer_alt = alternative
                                prefer_alt_idx = d
                                prefer_alt_score = 3
                            elif prefer_alt_score < 2 and altdep_state == "successfully-tested":
                                prefer_alt = alternative
                                prefer_alt_idx = d
                                prefer_alt_score = 2
                            elif prefer_alt_score < 1 and \
                                 altdep_state in ["waiting-to-be-tested", "waiting-for-dependency-to-be-tested"]:
                                prefer_alt = alternative
                                prefer_alt_idx = d
                                prefer_alt_score = 1
                            elif altdep_state == "unknown":
                                alt_unknowns += 1
                            else:
                                alt_fails += 1
                                if alt_state is None:
                                    alt_state = altdep_state

                    if prefer_alt_score >= 2:
                        package.prefer_alt_depends(header,prefer_alt_idx,prefer_alt)
                    elif prefer_alt_score == 1 and ((alt_unknowns + alt_fails) == 0):
                        package.prefer_alt_depends(header,prefer_alt_idx,prefer_alt)
                    elif alt_found == 0:
                        return "no-dependency-from-alternatives-exists"
                    else:
                        if alt_state is not None and alt_unknowns == 0:
                            state = alt_state
                        elif state is None:
                            state = "unknown-preferred-alternative"

        if state is not None:
             return state

        for dep in package.dependencies():
            dep_state = self.get_package_state(dep)
            if dep_state in self._dep_state_to_state:
                return self._dep_state_to_state[dep_state]

        state = "waiting-to-be-tested"
        for dep in package.dependencies():
            dep_state = self.get_package_state(dep)
            if dep_state not in \
                    ["successfully-tested", "essential-required"]:
                state = "unknown"
                break
        if state == "waiting-to-be-tested":
            return state

        deps = self._get_recursive_dependencies(package, break_circles=False)
        # ignore those packages:
        for pkg in self._known_circular_depends:
            if pkg in deps:
                deps.remove(pkg)
        if package["Package"] in deps:
            return "circular-dependency"  # actually, it's an unknown circular-dependency

        # treat circular-dependencies as testable (for the part of the circle)
        state = "unknown" 
        if package["Package"] in self._known_circular_depends:
            for dep in package.dependencies():
                dep_state = self.get_package_state(dep)
                if dep not in self._known_circular_depends and dep_state not in \
                        ["successfully-tested", "essential-required"]:
                    state = "unknown"
                    break
                if dep in self._known_circular_depends and dep_state not in \
                        ["failed-testing", "dependency-failed-testing"]:
                    state = "waiting-to-be-tested"
                    continue
        return state

    def _compute_package_states(self):
        if self._in_state is not None:
            return

        todo = []
        unpreferred_alt = []

        self._find_all_packages()
        package_names = self._packages.keys()

        self._package_state = {}
        for package_name in package_names:
            self._package_state[package_name] = "unknown"

        self._in_state = {}
        for state in self._states:
            self._in_state[state] = []

        while package_names:
            todo = []
            done = []
            unpreferred_alt = []
            for package_name in package_names:
                package = self._packages[package_name]
                if self._package_state[package_name] in \
                   [ "unknown", "unknown-preferred-alternative" ]:
                    state = self._compute_package_state(package)
                    assert state in self._states
                    if state == "unknown":
                        todo.append(package_name)
                    elif state == "unknown-preferred-alternative":
                        unpreferred_alt.append(package_name)
                    else:
                        self._in_state[state].append(package_name)
                        self._package_state[package_name] = state
                        done.append(package)
            if not done:
                # If we didn't do anything this time, we sure aren't going
                # to do anything the next time either.
                break
            package_names = todo
            package_names.extend(unpreferred_alt)

        self._in_state["unknown"] = todo
        self._in_state["unknown-preferred-alternative"] = unpreferred_alt
        for package_name in unpreferred_alt:
            self._package_state[package_name] = "unknown-preferred-alternative"

        for state in self._states:
            self._in_state[state].sort()

    def get_states(self):
        return self._states

    def get_pkg_names_in_state(self, state):
        self._compute_package_states()
        return set(self._in_state[state])

    def has_package(self, name):
        self._find_all_packages()
        return name in self._packages

    def get_package(self, name):
        return self._packages[name]

    def get_providers(self, name):
        if name in self._virtual_packages:
            return self._virtual_packages[name]
        return []

    def get_all_packages(self):
        self._find_all_packages()
        return self._packages

    def get_control_header(self, package_name, header):
        if header == "Source":
          # binary packages build from the source package with the same name
          # don't have a Source header, so let's try:
          try:
            _source = self._packages[package_name][header]
            # for binNMU the Source header in Packages files holds the version 
            # too, so we need to chop it of:
            if " " in _source:
              source, version = _source.split(" ")
            else:
              source = _source
          except:
            source = self._packages[package_name]["Package"]
          return source
        elif header == "Uploaders":
          # not all (source) packages have an Uploaders header
          uploaders = ""
          try:
            uploaders = self._packages[package_name][header]
          except:
            pass
          return uploaders
        else:
          return self._packages[package_name][header]

    def get_package_state(self, package_name, resolve_virtual=True):
        if package_name in self._package_state:
            return self._package_state[package_name]
        if package_name in self._virtual_packages:
            if resolve_virtual:
                provider = self._virtual_packages[package_name][0]
                return self._package_state[provider]
            else:
                return "virtual"
        return "does-not-exist"

    def _find_packages_ready_for_testing(self):
        return self.get_pkg_names_in_state("waiting-to-be-tested")

    def reserve_package(self):
        pset = self._find_packages_ready_for_testing()
        while (len(pset)):
            p = self.get_package(pset.pop())
            if self._logdb.create(self._reserved, p["Package"], p["Version"], ""):
                return p
        return None

    def _check_for_acceptability_as_filename(self, str):
        if "/" in str:
            raise Exception("'/' in (partial) filename: %s" % str)

    def unreserve_package(self, package, version):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        self._logdb.remove(self._reserved, package, version)

    def pass_package(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.create(self._ok, package, version, log):
            self._logdb.remove(self._reserved, package, version)
        else:
            raise Exception("Log file exists already: %s (%s)" %
                                (package, version))

    def fail_package(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.create(self._fail, package, version, log):
            self._logdb.remove(self._reserved, package, version)
        else:
            raise Exception("Log file exists already: %s (%s)" %
                                (package, version))

    def make_package_untestable(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.create(self._evil, package, version, log):
            self._logdb.remove(self._reserved, package, version)
        else:
            raise Exception("Log file exists already: %s (%s)" %
                                (package, version))

# vi:set et ts=4 sw=4 :
