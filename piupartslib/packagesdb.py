# -*- coding: utf-8 -*-

# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# Copyright © 2011-2018 Andreas Beckmann (anbe@debian.org)
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
# this program. If not, see <https://www.gnu.org/licenses/>


"""Packages database for distributed piuparts processing

This module contains tools for keeping track of which packages have
been tested, the test results, and for determining what to test next.

Lars Wirzenius <liw@iki.fi>
"""


import logging
import os
import random
import stat
import tempfile
import time
import UserDict
import apt_pkg

import piupartslib
from piupartslib.dependencyparser import DependencyParser

apt_pkg.init_system()


def rfc822_like_header_parse(input):
    headers = []
    while True:
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
        self.rrdep_cnt = None
        self.block_cnt = None
        self.waiting_cnt = None
        self.rdep_chain_len = None

    def name(self):
        return self["Package"]

    def version(self):
        return self["Version"]

    def source(self):
        # Binary packages built from the source package with the same name
        # and version don't have a Source header.
        if "Source" in self:
            # If source and binary version differ (e.g. for binNMUs), the
            # source version is given as the second element in the "Source"
            # entry. Strip off the optional source version.
            return self["Source"].split(" ")[0]
        return self["Package"]

    def source_version(self):
        # Binary packages built from the source package with the same name
        # and version don't have a Source header.
        if "Source" in self:
            # If source and binary version differ (e.g. for binNMUs), the
            # source version is given as the second element in the "Source"
            # entry. Strip off the parentheses around the source version.
            if " " in self["Source"]:
                return self["Source"].split(" ")[1][1:-1]
        return self["Version"]

    def set_test_versions(self, tv):
        self["TestVersions"] = tv

    def test_versions(self):
        """ToDo: for distupgrade tests test_versions() should return a list
           of versions in all distros in the upgrade path"""
        if "TestVersions" in self:
            return self["TestVersions"]
        return self.version()

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
    def all_dependencies(self, header_name=None):
        headers = ["Depends", "Pre-Depends"]
        if header_name is not None:
            headers = [header_name]
        vlist = []
        for header in headers:
            if header in self:
                vlist += self._parse_alternative_dependencies(header)
        return vlist

    def prefer_alt_depends(self, header_name, dep_idx, dep):
        if header_name in self:
            if header_name not in self._parsed_deps:
                self._parse_dependencies(header_name)
            if self._parsed_deps[header_name][dep_idx]:
                self._parsed_deps[header_name][dep_idx] = dep

    def provides(self):
        vlist = []
        for header in ["Provides"]:
            if header in self:
                vlist += self._parse_dependencies(header)
        return vlist

    def dump(self, output_file):
        output_file.write("".join(self.headers))


class PackagesFile(UserDict.UserDict):

    def __init__(self):
        UserDict.UserDict.__init__(self)
        self._urllist = []

    def load_packages_urls(self, urls, restrict_packages=None):
        for url in urls:
            logging.debug("Opening %s.*" % url)
            (url, stream) = piupartslib.open_packages_url(url)
            logging.debug("Fetching %s" % url)
            self._read_file(stream, restrict_packages=restrict_packages)
            stream.close()
            self._urllist.append(url)

    def _read_file(self, input, restrict_packages=None):
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
            if restrict_packages is not None:
                if p["Package"] not in restrict_packages:
                    # unwanted package
                    continue
            self[p["Package"]] = p

    def get_urls(self):
        return self._urllist


class LogDB:

    def exists(self, pathname):
        try:
            cache = self.exists_cache
        except AttributeError:
            self.exists_cache = {}
            cache = self.exists_cache
        if pathname not in cache:
            cache[pathname] = os.path.exists(pathname)
        return cache[pathname]

    def _evict(self, pathname):
        try:
            cache = self.exists_cache
            if pathname in cache:
                del cache[pathname]
        except AttributeError:
            pass

    def bulk_load_dir(self, dirname):
        try:
            cache = self.exists_cache
        except AttributeError:
            self.exists_cache = {}
            cache = self.exists_cache
        for basename in os.listdir(dirname):
            if basename.endswith(".log"):
                cache[os.path.join(dirname, basename)] = True

    def remove_file(self, pathname):
        os.remove(pathname)

    def _log_name(self, package, version):
        return "%s_%s.log" % (package, version)

    def log_exists2(self, package, version, subdirs):
        log_name = self._log_name(package, version)
        for subdir in subdirs:
            if self.exists(os.path.join(subdir, log_name)):
                return True
        return False

    def log_exists(self, package, subdirs):
        return self.log_exists2(package.name(), package.test_versions(), subdirs)

    def create(self, subdir, package, version, contents):
        (fd, temp_name) = tempfile.mkstemp(dir=subdir)
        if os.write(fd, contents) != len(contents):
            raise Exception("Partial write?")
        os.close(fd)

        # tempfile.mkstemp sets the file mode to be readable only by owner.
        # Let's make it follow the umask.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp_name, 0o666 & ~umask)

        full_name = os.path.join(subdir, self._log_name(package, version))
        try:
            os.link(temp_name, full_name)
        except OSError:
            return False
        finally:
            os.remove(temp_name)
        self._evict(full_name)
        return True

    def remove(self, subdir, package, version):
        full_name = os.path.join(subdir, self._log_name(package, version))
        if self.exists(full_name):
            self.remove_file(full_name)
        self._evict(full_name)

    def stat(self, subdir, package, version):
        full_name = os.path.join(subdir, self._log_name(package, version))
        return os.stat(full_name)


class LogfileExists(Exception):

    def __init__(self, path, package, version):
        self.args = (path, package, version)


class PackagesDB:

    # these packages are uses as dependencies but are only available
    # from foreign architectures
    # HACK: this hardcoded list should be moved to some data file
    _foreign_packages = {
        "ia32-libs-i386": "i386",
        "ia32-libs-gtk-i386": "i386",
        "libnss-mdns-i386": "i386",
    }

    # these packages are used as dependencies but are only available on
    # some architectures or from third-party repositories
    # HACK: this hardcoded list should be moved to some data file
    _ignored_missing_dependencies = [
        "kbdcontrol",
        "vidcontrol",
    ]

    # keep in sync with piuparts-report.py: emphasize_reason()
    # FIXME: can we reorder this list or remove entries without breaking the counts.txt for the plot?
    _states = [
        "successfully-tested",
        "failed-testing",
        "cannot-be-tested",
        "essential-required",  # obsolete
        "waiting-to-be-tested",
        "waiting-for-dependency-to-be-tested",
        "dependency-failed-testing",
        "dependency-cannot-be-tested",
        "dependency-does-not-exist",
        "circular-dependency",  # obsolete
        "unknown",
        "unknown-preferred-alternative",  # obsolete
        "no-dependency-from-alternatives-exists",  # obsolete
        "outdated",
        # "foreign:*",  # can only happen as query result for a dependency
        # "does-not-exist",  # can only happen as query result for a dependency
        # "ignore-does-not-exist",  # can only happen as query result for a dependency
    ]

    _good_states = [
        "successfully-tested",
        "essential-required",
        "ignore-does-not-exist",
    ] + ["foreign:%s" % arch for arch in set(_foreign_packages.values())]

    _obsolete_states = [
        "essential-required",
        "circular-dependency",
        "unknown-preferred-alternative",
        "no-dependency-from-alternatives-exists",
    ]

    _propagate_error_state = {
        "failed-testing": "dependency-failed-testing",
        "cannot-be-tested": "dependency-cannot-be-tested",
        "dependency-failed-testing": "dependency-failed-testing",
        "dependency-cannot-be-tested": "dependency-cannot-be-tested",
        "dependency-does-not-exist": "dependency-cannot-be-tested",
        "does-not-exist": "dependency-does-not-exist",
    }

    _propagate_waiting_state = {
        "waiting-to-be-tested": "waiting-for-dependency-to-be-tested",
        "waiting-for-dependency-to-be-tested": "waiting-for-dependency-to-be-tested",
    }

    def __init__(self, logdb=None, prefix=None):
        self.prefix = prefix
        self._packages_files = []
        self._ready_for_testing = None
        self._logdb = logdb or LogDB()
        self._packages = None
        self._in_state = None
        self._package_state = {}
        self._dependency_databases = []
        self._recycle_mode = False
        self._candidates_for_testing = None
        self._rdeps = None
        self.set_subdirs(ok="pass", fail="fail", evil="untestable",
                         reserved="reserved", morefail=["bugged", "affected"],
                         recycle="recycle")
        self.create_subdirs()

    def set_subdirs(self, ok=None, fail=None, evil=None, reserved=None, morefail=None, recycle=None):
        # Prefix all the subdirs with the prefix
        if self.prefix:
            pformat = self.prefix + "/%s"
        else:
            pformat = "%s"
        self._submissions = pformat % "submissions.txt"
        self._all = []
        if ok:
            self._ok = pformat % ok
            self._all.append(self._ok)
        if fail:
            self._fail = pformat % fail
            self._all.append(self._fail)
        if evil:
            self._evil = pformat % evil
            self._all.append(self._evil)
        if reserved:
            self._reserved = pformat % reserved
            self._all.append(self._reserved)
        if morefail:
            self._morefail = [pformat % s for s in morefail]
            self._all.extend(self._morefail)
        if recycle:
            self._recycle = pformat % recycle
            self._all.append(self._recycle)
        self._most = [x for x in self._all if x not in [self._reserved, self._recycle]]

    def create_subdirs(self):
        for sdir in self._all:
            if not os.path.exists(sdir):
                os.makedirs(sdir)

    def enable_recycling(self):
        if self._recycle_mode:
            return True
        if self._packages is not None:
            logging.info("too late for recycling")
            return False
        for basename in os.listdir(self._recycle):
            if basename.endswith(".log"):
                self._recycle_mode = True
                return True
        logging.info("nothing to recycle")
        return False

    def get_mtime(self):
        return max([os.path.getmtime(sdir) for sdir in self._all])

    def load_packages_urls(self, urls):
        pf = PackagesFile()
        pf.load_packages_urls(urls)
        self._packages_files.append(pf)
        self._packages = None

    def load_alternate_versions_from_packages_urls(self, urls):
        # take version numbers (or None) from alternate URLs
        pf2 = PackagesFile()
        pf2.load_packages_urls(urls)
        for package in self.get_all_packages():
            if package.name() in pf2:
                package.set_test_versions(pf2[package.name()].version())
            else:
                package.set_test_versions("None")

    def get_urls(self):
        urls = []
        for pf in self._packages_files:
            urls.extend(pf.get_urls())
        return urls

    def set_dependency_databases(self, dependency_databases=[]):
        self._dependency_databases = list(dependency_databases)

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

    def _get_recursive_dependencies(self, package):
        assert self._packages is not None
        deps = []
        more = package.dependencies()
        while more:
            dep = more[0]
            more = more[1:]
            if dep not in deps:
                deps.append(dep)
                dep_pkg = self.get_package(dep, recurse=True, resolve_virtual=True)
                if dep_pkg is not None:
                    more += dep_pkg.dependencies()
        return deps

    def _get_dependency_cycle(self, package_name):
        deps = []
        circular = []
        more = [package_name]
        while more:
            dep = more[0]
            more = more[1:]
            if dep not in deps:
                deps.append(dep)
                dep_pkg = self.get_package(dep, recurse=True, resolve_virtual=True)
                if dep_pkg is not None and package_name in self._get_recursive_dependencies(dep_pkg):
                    circular.append(dep)
                    more += dep_pkg.dependencies()
        return circular

    def _is_successfully_tested(self, package):
        # a pass/ log exists but no corresponding recycle/ log exists
        if self._logdb.log_exists(package, [self._ok]):
            if not (self._recycle_mode and self._logdb.log_exists(package, [self._recycle])):
                return True
        return False

    def _lookup_package_state(self, package, use_cached_success, check_outdated):
        if check_outdated:
            # Check if dependency databases have a newer version of this package.
            # Use the actual package versions, not the target versions.
            curr_ver = package.version()
            for db in self._dependency_databases:
                dep_ver = db.get_version(package.name())
                if dep_ver is not None and apt_pkg.version_compare(curr_ver, dep_ver) < 0:
                    #logging.info("[%s] outdated: %s %s < %s @[%s]" % (self.prefix, package.name(), curr_ver, dep_ver, db.prefix))
                    return "outdated";
        if self._recycle_mode:
            if self._logdb.log_exists(package, [self._reserved]):
                return "waiting-to-be-tested"
            if self._logdb.log_exists(package, [self._recycle]):
                return "unknown"
        if self._logdb.log_exists(package, [self._ok]):
            success = True
            if not use_cached_success:
                # if a pass/ log exists but any dependency may be not
                # trivially satisfiable do not skip dependency resolution
                for dep in package.dependencies():
                    if not self.get_package(dep, resolve_virtual=True):
                        success = False
                        break
            if success:
                return "successfully-tested"
        if self._logdb.log_exists(package, [self._fail] + self._morefail):
            return "failed-testing"
        if self._logdb.log_exists(package, [self._evil]):
            return "cannot-be-tested"
        if self._logdb.log_exists(package, [self._reserved]):
            return "waiting-to-be-tested"
        return "unknown"

    def _compute_package_state(self, package):
        # First attempt to resolve (still-unresolved) multiple alternative depends
        # Definitely sub-optimal, but improvement over blindly selecting first one
        # Select the first alternative in the highest of the following states:
        #   1) "essential-required"
        #   2) "successfully-tested"
        #   3) "waiting-to-be-tested" / "waiting-for-dependency-to-be-tested"
        #   4) "unknown" (retry later)
        # and update the preferred alternative of that dependency.
        # If no alternative is in any of these states we retry later ("unknown")
        # or set "dependency-does-not-exist".
        #
        # Problems:
        #   a) We will test and fail when >=1 "successfully-tested" but another
        #      that failed is selected by apt during test run
        #   b) We may report a status of "waiting-for-dependency-to-be-tested"
        #      instead of "waiting-to-be-tested" depending on the order the
        #      package states get resolved.

        for header in ["Depends", "Pre-Depends"]:
            alt_deps = package.all_dependencies(header)
            for d in range(len(alt_deps)):
                if len(alt_deps[d]) > 1:
                    alt_found = 0
                    prefer_alt_score = -1
                    prefer_alt = None
                    for alternative in alt_deps[d]:
                        altdep_state = self.get_package_state(alternative)
                        if altdep_state != "does-not-exist":
                            alt_found += 1
                            if prefer_alt_score < 3 and altdep_state == "essential-required":
                                prefer_alt = alternative
                                prefer_alt_score = 3
                            elif prefer_alt_score < 2 and altdep_state == "successfully-tested":
                                prefer_alt = alternative
                                prefer_alt_score = 2
                            elif prefer_alt_score < 1 and \
                                    altdep_state in ["waiting-to-be-tested", "waiting-for-dependency-to-be-tested"]:
                                prefer_alt = alternative
                                prefer_alt_score = 1
                            elif prefer_alt_score < 0 and altdep_state == "unknown":
                                prefer_alt = alternative
                                prefer_alt_score = 0
                    if alt_found == 0:
                        return "dependency-does-not-exist"
                    if prefer_alt_score >= 0:
                        package.prefer_alt_depends(header, d, prefer_alt)

        dep_states = [(dep, self.get_best_package_state(dep))
                      for dep in package.dependencies()]

        for dep, dep_state in dep_states:
            if dep_state in self._propagate_error_state:
                return self._propagate_error_state[dep_state]

        testable = True
        for dep, dep_state in dep_states:
            if dep_state not in self._good_states:
                testable = False
                break
        if testable:
            if self._is_successfully_tested(package):
                return "successfully-tested"
            return "waiting-to-be-tested"

        # treat circular-dependencies as testable (for the part of the circle)
        circular_deps = self._get_dependency_cycle(package["Package"])
        if package["Package"] in circular_deps:
            testable = True
            for dep, dep_state in dep_states:
                if dep in circular_deps:
                    # allow any non-error dep_state on the cycle for testing
                    # (error states are handled by the error propagation above)
                    pass
                elif dep_state not in self._good_states:
                    # non-circular deps must have passed before testing circular deps
                    testable = False
                    break
            if testable:
                if self._is_successfully_tested(package):
                    return "successfully-tested"
                return "waiting-to-be-tested"

        for dep, dep_state in dep_states:
            if dep_state in self._propagate_waiting_state:
                return self._propagate_waiting_state[dep_state]

        return "unknown"

    def _initialize_package_states(self, use_cached_success, check_outdated):
        self._find_all_packages()

        self._package_state = {}
        self._in_state = {}
        for state in self._states:
            self._in_state[state] = []
        todo = []

        for package_name, package in self._packages.iteritems():
            state = self._lookup_package_state(package, use_cached_success, check_outdated)
            assert state in self._states
            self._package_state[package_name] = state
            if state == "unknown":
                todo.append(package_name)
            else:
                self._in_state[state].append(package_name)

        return todo

    def _compute_package_states(self, use_cached_success=False):
        if self._in_state is not None:
            return

        self._stamp = time.time()

        for subdir in self._all:
            self._logdb.bulk_load_dir(subdir)

        todo = self._initialize_package_states(use_cached_success=use_cached_success, check_outdated=False)

        for db in self._dependency_databases:
            db._compute_package_states(use_cached_success=True)

        if self._dependency_databases:
            # redo the initialization to properly resolve "outdated" packages after the dependency databases have been initialized
            todo = self._initialize_package_states(use_cached_success=use_cached_success, check_outdated=True)

        while todo:
            package_names = todo
            todo = []
            done = []
            for package_name in package_names:
                if self._package_state[package_name] == "unknown":
                    state = self._compute_package_state(self._packages[package_name])
                    assert state in self._states
                    if state == "unknown":
                        todo.append(package_name)
                    else:
                        self._in_state[state].append(package_name)
                        self._package_state[package_name] = state
                        done.append(package_name)
            if not done:
                # If we didn't do anything this time, we sure aren't going
                # to do anything the next time either.
                break

        self._in_state["unknown"] = todo

        for state in self._states:
            self._in_state[state].sort()

    def get_states(self):
        return self._states

    def get_active_states(self):
        return [x for x in self._states if not x in self._obsolete_states]

    def get_error_states(self):
        return [x for x in self._propagate_error_state.keys() if x in self._states]

    def get_waiting_states(self):
        return [x for x in self._propagate_waiting_state.keys() if x in self._states]

    def get_pkg_names_in_state(self, state):
        self._compute_package_states()
        return set(self._in_state[state])

    def has_package(self, name):
        self._find_all_packages()
        return name in self._packages

    def get_package(self, name, recurse=False, resolve_virtual=False):
        self._find_all_packages()
        if name in self._packages:
            return self._packages[name]
        if recurse:
            for db in self._dependency_databases:
                if db.has_package(name):
                    return db.get_package(name)
        if resolve_virtual:
            providers = self.get_providers(name, recurse=recurse)
            if providers:
                return self.get_package(providers[0], recurse=recurse, resolve_virtual=False)
        return None

    def get_version(self, name):
        self._find_all_packages()
        if name in self._packages:
            return self._packages[name].version()
        return None

    def get_test_versions(self, name):
        self._find_all_packages()
        if name in self._packages:
            return self._packages[name].test_versions()
        return None

    def get_providers(self, name, recurse=True):
        self._find_all_packages()
        providers = []
        if name in self._virtual_packages:
            providers.extend(self._virtual_packages[name])
        if recurse:
            for db in self._dependency_databases:
                providers.extend(db.get_providers(name, recurse=False))
        return providers

    def get_all_packages(self):
        self._find_all_packages()
        return self._packages.values()

    def get_all_package_names(self):
        self._find_all_packages()
        return self._packages.keys()

    def get_control_header(self, package_name, header):
        self._find_all_packages()
        if header == "Uploaders":
            # not all (source) packages have an Uploaders header
            uploaders = ""
            try:
                uploaders = self._packages[package_name][header]
            except:
                pass
            return uploaders
        else:
            return self._packages[package_name][header]

    def get_package_state(self, package_name, resolve_virtual=True, recurse=True):
        self._compute_package_states()
        if package_name in self._package_state:
            if recurse and self._package_state[package_name] == "outdated":
                for db in self._dependency_databases:
                    state = db.get_package_state(package_name, resolve_virtual=resolve_virtual, recurse=False)
                    if state not in ["does-not-exist", "outdated"]:
                        return state
            return self._package_state[package_name]
        if package_name in self._virtual_packages:
            if resolve_virtual:
                provider = self._virtual_packages[package_name][0]
                return self._package_state[provider]
            else:
                return "virtual"
        if recurse:
            for db in self._dependency_databases:
                state = db.get_package_state(package_name, resolve_virtual=resolve_virtual, recurse=False)
                if state != "does-not-exist":
                    return state
        if package_name in self._foreign_packages:
            return "foreign:%s" % self._foreign_packages[package_name]
        if package_name in self._ignored_missing_dependencies:
            return "ignore-does-not-exist"
        return "does-not-exist"

    def get_best_package_state(self, package_name, resolve_virtual=True, recurse=True):
        package_state = self.get_package_state(package_name, resolve_virtual=resolve_virtual, recurse=recurse)
        if package_state in self._good_states:
            return package_state
        providers = []
        if resolve_virtual:
            providers = self.get_providers(package_name, recurse=recurse)
        if not providers:
            return package_state
        states = [self.get_package_state(name, resolve_virtual=False, recurse=recurse) for name in [package_name] + providers]
        for state in self._good_states + self._propagate_waiting_state.keys() + self._propagate_error_state.keys():
            if state in states:
                return state
        return package_state

    def _get_package_weight(self, p):
        # compute the priority of a package that needs testing
        # result will be used as a reverse sorting key, so higher is earlier
        waiting_count = self.waiting_count(p["Package"])
        rdep_chain_len = self.rdep_chain_len(p["Package"])

        if not self._recycle_mode:
            return (
                min(rdep_chain_len, waiting_count),
                    waiting_count,
            )

        try:
            statobj = self._logdb.stat(self._recycle, p.name(), p.test_versions())
            ctime = statobj[stat.ST_CTIME]  # last inode modification = time of linking into recycle/
            mtime = statobj[stat.ST_MTIME]
        except OSError:
            ctime = 0
            mtime = 0

        return (
            min(rdep_chain_len, waiting_count),
                waiting_count,
                not self._logdb.log_exists(p, [self._ok]),  # prefer problematic logs
                -ctime / 3600,  # prefer older, at 1 hour granularity to allow randomization
                -mtime / 3600,  # prefer older, at 1 hour granularity to allow randomization
        )

    def _find_packages_ready_for_testing(self):
        if self._candidates_for_testing is None:
            self._candidates_for_testing = [self.get_package(pn)
                                            for pn in self.get_pkg_names_in_state("waiting-to-be-tested")]
            self._candidates_for_testing = [p for p in self._candidates_for_testing
                                            if not self._logdb.log_exists(p, [self._reserved]) or
                                            self._logdb.log_exists(p, [self._recycle])]
            if len(self._candidates_for_testing) > 1:
                tuples = [(self._get_package_weight(p), random.random(), p)
                          for p in self._candidates_for_testing]
                self._candidates_for_testing = [x[-1]
                                                for x in sorted(tuples, reverse=True)]
        return self._candidates_for_testing[:]

    def _remove_unavailable_candidate(self, p):
        self._candidates_for_testing.remove(p)

    def reserve_package(self):
        for p in self._find_packages_ready_for_testing():
            if self._logdb.log_exists(p, [self._reserved]):
                self._remove_unavailable_candidate(p)
                continue
            if self._recycle_mode and self._logdb.log_exists(p, [self._recycle]):
                for vdir in [x for x in self._most if x != self._ok]:
                    if self._logdb.log_exists(p, [vdir]):
                        self._logdb.remove(vdir, p.name(), p.test_versions())
                        logging.info("Recycled %s %s %s" % (vdir, p.name(), p.test_versions()))
            elif self._logdb.log_exists(p, self._most):
                self._remove_unavailable_candidate(p)
                continue
            if self._logdb.log_exists(p, [self._recycle]):
                self._logdb.remove(self._recycle, p.name(), p.test_versions())
            if self._logdb.create(self._reserved, p.name(), p.test_versions(), ""):
                return p
        return None

    def _check_for_acceptability_as_filename(self, str):
        if "/" in str:
            raise Exception("'/' in (partial) filename: %s" % str)

    def _record_submission(self, category, package, version):
        with open(self._submissions, "a") as submissions:
            submissions.write("%d %s %s %s\n" % (time.time(), category, package, version))

    def _remove_logs_if_reserved(self, package, version):
        if self._logdb.log_exists2(package, version, [self._reserved]):
            for vdir in self._most:
                if self._logdb.log_exists2(package, version, [vdir]):
                    self._logdb.remove(vdir, package, version)
                    logging.info("Recycled %s %s %s" % (vdir, package, version))
            self._logdb.remove(self._reserved, package, version)

    def unreserve_package(self, package, version):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.log_exists2(package, version, [self._reserved]):
            if not self._logdb.log_exists2(package, version, [self._recycle]):
                # restore possible recycle marker
                if self._logdb.log_exists2(package, version, self._most):
                    self._logdb.create(self._recycle, package, version, "")
        self._logdb.remove(self._reserved, package, version)

    def pass_package(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        self._remove_logs_if_reserved(package, version)
        if self._logdb.create(self._ok, package, version, log):
            self._record_submission("pass", package, version)
        else:
            raise LogfileExists(self._ok, package, version)

    def fail_package(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        self._remove_logs_if_reserved(package, version)
        if self._logdb.create(self._fail, package, version, log):
            self._record_submission("fail", package, version)
        else:
            raise LogfileExists(self._fail, package, version)

    def make_package_untestable(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        self._remove_logs_if_reserved(package, version)
        if self._logdb.create(self._evil, package, version, log):
            self._record_submission("untestable", package, version)
        else:
            raise LogfileExists(self._evil, package, version)

    def _get_rdep_dict(self):
        """Return dict of one-level reverse dependencies by package"""

        if self._rdeps is None:

            self._rdeps = {}

            for pkg_name in self.get_all_package_names():
                for dep in self.get_package(pkg_name).dependencies():
                    dep_pkg = self.get_package(dep, recurse=True, resolve_virtual=True)

                    if dep_pkg is not None:
                        dep = dep_pkg["Package"]

                    if not dep in self._rdeps:
                        self._rdeps[dep] = set()
                    self._rdeps[dep].add(pkg_name)

        return self._rdeps

    def _calc_rrdep_pkg_counts(self, pkg):

        pkg_name = pkg['Package']
        self._compute_package_states()  # populate _package_state

        # calc full recursive reverse dependency package set
        rrdep_set = set()
        rdeps = self._get_rdep_dict()
        next_level = set([pkg_name])
        chain_len = 0

        while next_level:
            chain_len += 1
            rrdep_set |= next_level
            new_pkgs = next_level
            next_level = set([y for x in new_pkgs if x in rdeps for y in rdeps[x]])
            next_level -= rrdep_set

        rrdep_set.remove(pkg_name)

        # calculate and set the metrics
        pkg.rrdep_cnt = len(rrdep_set)

        error_states = self.get_error_states()
        if self._package_state[pkg_name] in error_states:
            block_list = [x for x in rrdep_set
                          if self._package_state[x] in error_states]
            pkg.block_cnt = len(block_list)
        else:
            pkg.block_cnt = 0

        waiting_states = self.get_waiting_states()
        if self._package_state[pkg_name] in waiting_states:
            waiting_list = [x for x in rrdep_set
                            if self._package_state[x] in waiting_states]
            pkg.waiting_cnt = len(waiting_list)
        else:
            pkg.waiting_cnt = 0

        pkg.rdep_chain_len = chain_len

    def block_count(self, name):
        pkg = self.get_package(name)
        if pkg is None:
            return -1
        if pkg.block_cnt is None:
            self._calc_rrdep_pkg_counts(pkg)

        return pkg.block_cnt

    def rrdep_count(self, name):
        pkg = self.get_package(name)
        if pkg is None:
            return -1
        if pkg.rrdep_cnt is None:
            self._calc_rrdep_pkg_counts(pkg)

        return pkg.rrdep_cnt

    def waiting_count(self, name):
        pkg = self.get_package(name)
        if pkg is None:
            return -1
        if pkg.waiting_cnt is None:
            self._calc_rrdep_pkg_counts(pkg)

        return pkg.waiting_cnt

    def rdep_chain_len(self, name):
        pkg = self.get_package(name)
        if pkg is None:
            return -1
        if pkg.rdep_chain_len is None:
            self._calc_rrdep_pkg_counts(pkg)

        return pkg.rdep_chain_len


# vi:set et ts=4 sw=4 :
