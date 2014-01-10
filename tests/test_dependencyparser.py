import unittest
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
