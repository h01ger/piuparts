import os
import shutil
import unittest
from unittest.mock import patch

import piuparts
from piuparts import is_broken_symlink


class DefaultsFactoryTests(unittest.TestCase):
    def setUp(self):
        self.df = piuparts.DefaultsFactory()
        piuparts.settings = piuparts.Settings()

    def test_new_defaults_return_debian_defaults(self):
        # mock the guess_flavor function as it runs lsb_release in a subprocess
        with patch.object(
            self.df, "guess_flavor", return_value="debian"
        ) as guess_flavor_mock:
            defaults = self.df.new_defaults()
            guess_flavor_mock.assert_called_once()

        self.assertEqual(
            defaults.get_keyring(), "/usr/share/keyrings/debian-archive-keyring.gpg"
        )
        self.assertEqual(defaults.get_components(), ["main", "contrib", "non-free", "non-free-firmware"])
        self.assertEqual(
            defaults.get_mirror(),
            [("http://deb.debian.org/debian", ["main", "contrib", "non-free", "non-free-firmware"])],
        )
        self.assertEqual(defaults.get_distribution(), ["sid"])

    def test_new_defaults_return_ubuntu_defaults(self):
        with patch.object(
            self.df, "guess_flavor", return_value="ubuntu"
        ) as guess_flavor_mock:
            defaults = self.df.new_defaults()
            guess_flavor_mock.assert_called_once()

        self.assertEqual(
            defaults.get_keyring(), "/usr/share/keyrings/ubuntu-archive-keyring.gpg"
        )
        self.assertEqual(
            defaults.get_components(), ["main", "universe", "restricted", "multiverse"]
        )
        self.assertEqual(
            defaults.get_mirror(),
            [
                (
                    "http://archive.ubuntu.com/ubuntu",
                    ["main", "universe", "restricted", "multiverse"],
                )
            ],
        )

    def test_new_defaults_panics_with_unknown_flavor(self):
        with patch.object(
            self.df, "guess_flavor", return_value="centos"
        ) as guess_flavor_mock, patch.object(
            piuparts, "panic", side_effect=SystemExit
        ) as panic_mock:
            with self.assertRaises(SystemExit):
                self.df.new_defaults()

            guess_flavor_mock.assert_called_once()
            panic_mock.assert_called_once()


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
