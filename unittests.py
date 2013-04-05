# -*- coding: utf-8 -*-

import os
import StringIO
import unittest


import piupartslib.packagesdb
import piupartslib.dependencyparser


class DependencyParserTests(unittest.TestCase):

    """Tests for module dependencyparser."""

    def parse(self, str):
        parser = piupartslib.dependencyparser.DependencyParser(str)
        deps = parser.get_dependencies()
        names = []
        for dep in deps:
            names.append([])
            for simpledep in dep:
                names[-1].append(simpledep.name)
        return deps, names

    def testEmpty(self):
        deps, names = self.parse("")
        self.failUnlessEqual(deps, [])

    def testSingle(self):
        deps, names = self.parse("foo")
        self.failUnlessEqual(names, [["foo"]])

    def testTwo(self):
        deps, names = self.parse("foo, bar")
        self.failUnlessEqual(names, [["foo"], ["bar"]])

    def testAlternatives(self):
        deps, names = self.parse("foo, bar | foobar")
        self.failUnlessEqual(names, [["foo"], ["bar", "foobar"]])


class FakeLogDB(piupartslib.packagesdb.LogDB):

    """A fake version of the LogDB class, for testing

    This version simulates filesystem actions so that there is no need
    to do actual I/O. Cleaner, although not quite as thorough.

    """

    def __init__(self):
        self.dict = {
            "pass": [],
            "fail": [],
            "untestable": [],
            "reserved": [],
            "bugged": [],
            "affected": [],
        }

    def listdir(self, dirname):
        return self.dict[dirname]

    def _parse(self, pathname):
        return os.path.dirname(pathname), os.path.basename(pathname)

    def exists(self, pathname):
        vdir, base = self._parse(pathname)
        return base in self.dict[vdir]

    def open_file(self, pathname, mode):
        vdir, base = self._parse(pathname)
        self.dict[vdir].append(base)
        return StringIO.StringIO()

    def remove_file(self, pathname):
        vdir, base = self._parse(pathname)
        if base in self.dict[vdir]:
            del self.dict[vdir]

    def create(self, subdir, package, version, contents):
        return True


class PackagesDbTests(unittest.TestCase):

    def new_db(self, packages_file_contents):
        db = piupartslib.packagesdb.PackagesDB(FakeLogDB())
        db.read_packages_file(StringIO.StringIO(packages_file_contents))
        return db

    def reserve(self, packages_file_contents):
        db = self.new_db(packages_file_contents)
        return db.reserve_package()

    def testNoPackages(self):
        p = self.reserve("")
        self.failUnlessEqual(p, None)

    def testNoDeps(self):
        p = self.reserve("""\
Package: foo
Version: 1.0-1
""")
        self.failIfEqual(p, None)
        self.failUnlessEqual(p["Package"], "foo")


if __name__ == "__main__":
    unittest.main()

# vi:set et ts=4 sw=4 :
