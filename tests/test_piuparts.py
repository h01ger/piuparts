import unittest
import os
import shutil
from piuparts import is_broken_symlink


class IsBrokenSymlinkTests(unittest.TestCase):

    testdir = "is-broken-symlink-testdir"

    def symlink(self, target, name):
        pathname = os.path.join(self.testdir, name)
        os.symlink(target, pathname)
        self.symlinks.append(pathname)

    def setUp(self):
        self.symlinks = []
        os.mkdir(self.testdir)
        self.symlink("notexist", "relative-broken")
        self.symlink("relative-broken", "relative-broken-to-symlink")
        self.symlink(".", "relative-works")
        self.symlink("relative-works", "relative-works-to-symlink")
        self.symlink("/etc", "absolute-broken")
        self.symlink("absolute-broken", "absolute-broken-to-symlink")
        self.symlink("/", "absolute-works")
        self.symlink("/absolute-works", "absolute-works-to-symlink")
        os.mkdir(os.path.join(self.testdir, "dir"))
        self.symlink("dir", "dir-link")
        os.mkdir(os.path.join(self.testdir, "dir/subdir"))
        self.symlink("subdir", "dir/subdir-link")
        self.symlink("notexist/", "trailing-slash-broken")
        self.symlink("dir/", "trailing-slash-works")
        self.symlink("selfloop", "selfloop")
        self.symlink("/absolute-selfloop", "absolute-selfloop")
        self.symlink("../dir/selfloop", "dir/selfloop")
        self.symlink("../dir-link/selfloop", "dir/selfloop1")
        self.symlink("../../dir/subdir/selfloop", "dir/subdir/selfloop")
        self.symlink("../../dir-link/subdir/selfloop", "dir/subdir/selfloop1")
        self.symlink("../../link/subdir-link/selfloop", "dir/subdir/selfloop2")
        self.symlink("../../dir-link/subdir-link/selfloop", "dir/subdir/selfloop3")
        self.symlink("explode/bomb", "explode")

    def tearDown(self):
        shutil.rmtree(self.testdir)

    def testRelativeBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "relative-broken"))

    def testRelativeBrokenToSymlink(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "relative-broken-to-symlink"))

    def testAbsoluteBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "absolute-broken"))

    def testAbsoluteBrokenToSymlink(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "absolute-broken-to-symlink"))

    def testTrailingSlashBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "trailing-slash-broken"))

    def testSelfLoopBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "selfloop"))

    def testExpandingSelfLoopBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "explode"))

    def testAbsoluteSelfLoopBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "absolute-selfloop"))

    def testSubdirSelfLoopBroken(self):
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "dir/selfloop"))
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "dir/selfloop1"))
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "dir/subdir/selfloop"))
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "dir/subdir/selfloop1"))
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "dir/subdir/selfloop2"))
        self.failUnless(is_broken_symlink(self.testdir, self.testdir,
                                          "dir/subdir/selfloop3"))

    def testRelativeWorks(self):
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "relative-works"))

    def testRelativeWorksToSymlink(self):
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "relative-works-to-symlink"))

    def testAbsoluteWorks(self):
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "absolute-works"))

    def testAbsoluteWorksToSymlink(self):
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "absolute-works-to-symlink"))

    def testTrailingSlashWorks(self):
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "trailing-slash-works"))

    def testMultiLevelNestedSymlinks(self):
        # target/first-link -> ../target/second-link -> ../target

        os.mkdir(os.path.join(self.testdir, "target"))
        self.symlink("../target", "target/second-link")
        self.symlink("../target/second-link", "target/first-link")
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "target/first-link"))

    def testMultiLevelNestedAbsoluteSymlinks(self):
        # first-link -> /second-link/final-target
        # second-link -> /target-dir

        os.mkdir(os.path.join(self.testdir, "final-dir"))
        os.mkdir(os.path.join(self.testdir, "final-dir/final-target"))
        self.symlink("/second-link/final-target", "first-link")
        self.symlink("/final-dir", "second-link")
        self.failIf(is_broken_symlink(self.testdir, self.testdir,
                                      "first-link"))

