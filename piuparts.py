#!/usr/bin/python
#
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


"""Debian package installation and uninstallation tester.

This program sets up a minimal Debian system in a chroot, and installs
and uninstalls packages and their dependencies therein, looking for
problems.

See the manual page (piuparts.1, generated from piuparts.1.txt) for 
more usage information.

Lars Wirzenius <liw@iki.fi>
"""


VERSION = "__PIUPARTS_VERSION__"


import time
import logging
import optparse
import sys
import commands
import tempfile
import shutil
import os
import tarfile
import stat
import re
import pickle
import subprocess
import unittest
import urllib
import uuid
from signal import alarm, signal, SIGALRM, SIGTERM, SIGKILL

try:
    from debian import deb822
except ImportError:
    from debian_bundle import deb822

class Defaults:

    """Default settings which depend on flavor of Debian.

    Some settings, such as the default mirror and distribution, depend on
    which flavor of Debian we run under: Debian itself, or a derived
    distribution such as Ubuntu. This class abstracts away the defaults
    so that the rest of the code can just refer to the values defined
    herein.

    """

    def get_components(self):
        """Return list of default components for a mirror."""

    def get_mirror(self):
        """Return default mirror."""

    def get_distribution(self):
        """Return default distribution."""


class DebianDefaults(Defaults):

    def get_components(self):
        return ["main", "contrib", "non-free"]

    def get_mirror(self):
        return [("http://ftp.debian.org/debian", self.get_components())]

    def get_distribution(self):
        return ["sid"]


class UbuntuDefaults(Defaults):

    def get_components(self):
        return ["main", "universe", "restricted", "multiverse"]

    def get_mirror(self):
        return [("http://archive.ubuntu.com/ubuntu", self.get_components())]

    def get_distribution(self):
        return ["natty"]


class DefaultsFactory:

    """Instantiate the right defaults class."""

    def guess_flavor(self):
        p = subprocess.Popen(["lsb_release", "-i", "-s"], 
                             stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return stdout.strip().lower()

    def new_defaults(self):
        if not settings.defaults:
            settings.defaults = self.guess_flavor()
            print "Guessed:", settings.defaults
        if settings.defaults.lower() == "debian":
            return DebianDefaults()
        if settings.defaults.lower() == "ubuntu":
            return UbuntuDefaults()
        logging.error("Unknown set of defaults: %s" % settings.defaults)
        panic()


class Settings:

    """Global settings for this program."""

    def __init__(self):
        self.defaults = None
        self.tmpdir = None
        self.keep_tmpdir = False
        self.max_command_output_size = 3 * 1024 * 1024  # 3 MB (daptup on dist-upgrade)
        self.max_command_runtime = 30 * 60  # 30 minutes (texlive-full on dist-upgrade)
        self.single_changes_list = False
        self.args_are_package_files = True
        # distro setup
        self.debian_mirrors = []
        self.debian_distros = []
        self.keep_sources_list = False
        self.do_not_verify_signatures = False
        self.scriptsdirs = []
        self.bindmounts = []
        # chroot setup
        self.basetgz = None
        self.savetgz = None
        self.lvm_volume = None
        self.existing_chroot = None
        self.schroot = None
        self.end_meta = None
        self.save_end_meta = None
        self.skip_minimize = True
        self.debfoster_options = None
        # tests and checks
        self.no_install_purge_test = False
        self.no_upgrade_test = False
        self.install_remove_install = False
        self.list_installed_files = False
        self.extra_old_packages = []
        self.skip_cronfiles_test = False
        self.skip_logrotatefiles_test = False
        self.check_broken_diversions = True
        self.check_broken_symlinks = True
        self.warn_broken_symlinks = True
        self.warn_on_others = False
        self.warn_on_leftovers_after_purge = False
        self.ignored_files = [
            # piuparts state
            "/usr/sbin/policy-rc.d",
            # system state
            "/boot/grub/",
            "/etc/X11/",
            "/etc/X11/default-display-manager",
            "/etc/aliases",
            "/etc/aliases.db",
            "/etc/crypttab",
            "/etc/group",
            "/etc/group-",
            "/etc/gshadow",
            "/etc/gshadow-",
            "/etc/inetd.conf",
            "/etc/inittab",
            "/etc/ld.so.cache",
            "/etc/mailname",
            "/etc/mtab",
            "/etc/network/interfaces",
            "/etc/news/",
            "/etc/news/organization",
            "/etc/news/server",
            "/etc/news/servers",
            "/etc/news/whoami",
            "/etc/nologin",
            "/etc/passwd",
            "/etc/passwd-",
            "/etc/shadow",
            "/etc/shadow-",
            "/usr/share/info/dir",
            "/usr/share/info/dir.old",
            "/var/cache/ldconfig/aux-cache",
            "/var/crash/",
            "/var/games/",
            # package management
            "/etc/apt/secring.gpg",
            "/etc/apt/trustdb.gpg",
            "/etc/apt/trusted.gpg",
            "/etc/apt/trusted.gpg~",
            "/usr/share/keyrings/debian-archive-removed-keys.gpg~",
            "/var/cache/apt/archives/lock",
            "/var/cache/apt/pkgcache.bin", 
            "/var/cache/apt/srcpkgcache.bin",
            "/var/cache/debconf/",
            "/var/cache/debconf/config.dat",
            "/var/cache/debconf/config.dat.old",
            "/var/cache/debconf/config.dat-old",
            "/var/cache/debconf/passwords.dat",
            "/var/cache/debconf/passwords.dat.old",
            "/var/cache/debconf/templates.dat",
            "/var/cache/debconf/templates.dat.old",
            "/var/cache/debconf/templates.dat-old",
            "/var/lib/apt/extended_states",
            "/var/lib/cdebconf/",
            "/var/lib/cdebconf/passwords.dat",
            "/var/lib/cdebconf/questions.dat",
            "/var/lib/cdebconf/templates.dat",
            "/var/lib/dpkg/available",
            "/var/lib/dpkg/available-old", 
            "/var/lib/dpkg/diversions",
            "/var/lib/dpkg/diversions-old",
            "/var/lib/dpkg/lock", 
            "/var/lib/dpkg/status", 
            "/var/lib/dpkg/status-old", 
            "/var/lib/dpkg/statoverride",
            "/var/lib/dpkg/statoverride-old",
            "/var/log/alternatives.log",
            "/var/log/apt/history.log",
            "/var/log/apt/term.log",
            "/var/log/bootstrap.log",
            "/var/log/dpkg.log",
            # system logfiles
            "/var/log/auth.log",
            "/var/log/daemon.log",
            "/var/log/debug",
            "/var/log/faillog",
            "/var/log/kern.log",
            "/var/log/lastlog",
            "/var/log/lpr.log",
            "/var/log/mail.err",
            "/var/log/mail.info",
            "/var/log/mail.log",
            "/var/log/mail.warn",
            "/var/log/messages",
            "/var/log/news/",
            "/var/log/news/news.crit",
            "/var/log/news/news.err",
            "/var/log/news/news.notice",
            "/var/log/secure",
            "/var/log/syslog",
            "/var/log/user.log",
            # home directories of system accounts
            "/var/lib/gozerbot/",
            "/var/lib/nagios/",         # nagios* (#668756)
            "/var/lib/rbldns/",
            "/var/spool/powerdns/",     # pdns-server (#531134), pdns-recursor (#531135)
            # work around #316521 dpkg: incomplete cleanup of empty directories
            "/etc/apache2/",
            "/etc/apache2/conf.d/",
            "/etc/cron.d/",
            "/etc/nagios-plugins/config/",
            "/etc/php5/",
            "/etc/php5/conf.d/",
            "/etc/php5/mods-available/",
            "/etc/sgml/",
            "/etc/ssl/",
            "/etc/ssl/private/",
            "/etc/xml/",
            # HACKS
            ]
        self.ignored_patterns = [
            # system state
            "/dev/.*",
            "/etc/init.d/\.depend.*",
            "/run/.*",
            "/var/backups/.*",
            "/var/cache/man/.*",
            "/var/mail/.*",
            "/var/run/.*",
            # package management
            "/var/lib/apt/lists/.*",
            "/var/lib/dpkg/alternatives/.*",
            "/var/lib/dpkg/triggers/.*",
            "/var/lib/insserv/run.*.log",
            "/var/lib/ucf/.*",
            "/var/lib/update-rc.d/.*",
            # application data
            "/var/lib/citadel/(data/.*)?",
            "/var/lib/mercurial-server/.*",
            "/var/lib/onak/.*",
            "/var/lib/openvswitch/(pki/.*)?",
            "/var/log/exim/.*",
            "/var/log/exim4/.*",
            "/var/spool/exim/.*",
            "/var/spool/exim4/.*",
            "/var/spool/news/.*",
            "/var/spool/squid/(../.*)?",
            "/var/www/.*",
            # HACKS
            "/lib/modules/.*/modules.*",
            ]
        self.non_pedantic_ignore_patterns = [
            "/tmp/.*"
            ]


settings = Settings()


on_panic_hooks = {}
counter = 0


def do_on_panic(hook):
    global counter
    cid = counter
    counter += 1
    on_panic_hooks[cid] = hook
    return cid


def dont_do_on_panic(id):
    del on_panic_hooks[id]


class TimeOffsetFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None):
        self.startup_time = time.time()
        logging.Formatter.__init__(self, fmt, datefmt)

    def formatTime(self, record, datefmt):
        t = time.time() - self.startup_time
        t_min = int(t / 60)
        t_sec = t % 60.0
        return "%dm%.1fs" % (t_min, t_sec)


DUMP = logging.DEBUG - 1
HANDLERS = []

def setup_logging(log_level, log_file_name):
    logging.addLevelName(DUMP, "DUMP")

    logger = logging.getLogger()
    logger.setLevel(log_level)
    formatter = TimeOffsetFormatter("%(asctime)s %(levelname)s: %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    HANDLERS.append(handler)

    if log_file_name:
        handler = logging.FileHandler(log_file_name)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        HANDLERS.append(handler)


def dump(msg):
    logger = logging.getLogger()
    logger.log(DUMP, msg)
    for handler in HANDLERS:
        handler.flush()


def panic(exit=1):
    for i in range(counter):
        if i in on_panic_hooks:
            on_panic_hooks[i]()
    sys.exit(exit)


def indent_string(str):
    """Indent all lines in a string with two spaces and return result."""
    return "\n".join(["  " + line for line in str.split("\n")])


class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm


def run(command, ignore_errors=False, timeout=0):
    """Run an external command and die with error message if it fails."""

    def kill_subprocess(p, reason):
        logging.error("Terminating command due to %s" % reason)
        p.terminate()
        for i in range(10):
            time.sleep(0.5)
            if p.poll() is not None:
                break
        else:
            logging.error("Killing command due to %s" % reason)
            p.kill()
        p.wait()

    assert type(command) == type([])
    command = [x for x in command if x] # Delete any empty argument
    logging.debug("Starting command: %s" % command)
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANGUAGES"] = ""
    env["PIUPARTS_OBJECTS"] = ' '.join(str(vobject) for vobject in settings.testobjects )
    devnull = open('/dev/null', 'r')
    p = subprocess.Popen(command, env=env, stdin=devnull, 
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = ""
    excessive_output = False
    if timeout > 0:
        signal(SIGALRM, alarm_handler)
        alarm(timeout)
    try:
        while p.poll() is None:
            """Read 64 KB chunks, but depending on the output buffering behavior
            of the command we may get less even if more output is coming later.
            Abort after reading max_command_output_size bytes."""
            output += p.stdout.read(1 << 16)
            if (len(output) > settings.max_command_output_size):
                excessive_output = True
                ignore_errors = False
                alarm(0)
                kill_subprocess(p, "excessive output")
                output += "\n\n***** Command was terminated after exceeding output limit (%.2f MB) *****\n" \
                          % (settings.max_command_output_size / 1024. / 1024.)
                break
        if not excessive_output:
            output += p.stdout.read(settings.max_command_output_size)
        alarm(0)
    except Alarm:
        ignore_errors = False
        kill_subprocess(p, "excessive runtime")
        output += "\n\n***** Command was terminated after exceeding runtime limit (%s s) *****\n" % timeout
    devnull.close()

    if output:
        dump("\n" + indent_string(output.rstrip("\n")))

    if p.returncode == 0:
        logging.debug("Command ok: %s" % repr(command))
    elif ignore_errors:
        logging.debug("Command failed (status=%d), but ignoring error: %s" % 
              (p.returncode, repr(command)))
    else:
        logging.error("Command failed (status=%d): %s\n%s" % 
              (p.returncode, repr(command), indent_string(output)))
        panic()
    return p.returncode, output


def create_temp_file():
    """Create a temporary file and return its full path."""
    (fd, path) = tempfile.mkstemp(dir=settings.tmpdir)
    logging.debug("Created temporary file %s" % path)
    return (fd, path)


def create_file(name, contents):
    """Create a new file with the desired name and contents."""
    try:
        f = file(name, "w")
        f.write(contents)
        f.close()
    except IOError, detail:
        logging.error("Couldn't create file %s: %s" % (name, detail))
        panic()


def remove_files(filenames):
    """Remove some files."""
    for filename in filenames:
        logging.debug("Removing %s" % filename)
        try:
            os.remove(filename)
        except OSError, detail:
            logging.error("Couldn't remove %s: %s" % (filename, detail))
            panic()


def make_metapackage(name, depends, conflicts):
    """Return the path to a .deb created just for satisfying dependencies

    Caller is responsible for removing the temporary directory containing the
    .deb when finished.
    """
    # Inspired by pbuilder's pbuilder-satisfydepends-aptitude

    tmpdir = tempfile.mkdtemp(dir=settings.tmpdir)
    old_umask = os.umask(0)
    os.makedirs(os.path.join(tmpdir, name, 'DEBIAN'), mode = 0755)
    os.umask(old_umask)
    control = deb822.Deb822()
    control['Package'] = name
    control['Version'] = '0.invalid.0'
    control['Architecture'] = 'all'
    control['Maintainer'] = ('piuparts developers team '
                             '<piuparts-devel@lists.alioth.debian.org>')
    control['Description'] = ('Dummy package to satisfy dependencies - '
                              'created by piuparts\n'
                              ' This package was created automatically by '
                              'piuparts and can safely be removed')
    if depends:
        control['Depends'] = depends
    if conflicts:
        control['Conflicts'] = conflicts

    create_file(os.path.join(tmpdir, name, 'DEBIAN', 'control'),
                control.dump())

    run(['dpkg-deb', '-b', os.path.join(tmpdir, name)])
    return os.path.join(tmpdir, name) + '.deb'


def split_path(pathname):
    parts = []
    while pathname:
        (head, tail) = os.path.split(pathname)
        #print "split '%s' => '%s' + '%s'" % (pathname, head, tail)
        if tail:
            parts.append(tail)
        elif not head:
            break
        elif head == pathname:
            parts.append(head)
            break
        pathname = head
    return parts

def canonicalize_path(root, pathname):
    """Canonicalize a path name, simulating chroot at 'root'.

    When resolving the symlink, pretend (similar to chroot) that
    'root' is the root of the filesystem.  Also resolve '..' and
    '.' components.  This should not escape the chroot below
    'root', but for security concerns, use chroot and have the
    kernel resolve symlinks instead.

    """
    #print "\nCANONICALIZE %s %s" % (root, pathname)
    seen = []
    parts = split_path(pathname)
    #print "PARTS ", list(reversed(parts))
    path = "/"
    while parts:
        tag = "\n".join(parts + [path])
        #print "TEST '%s' + " % path, list(reversed(parts))
        if tag in seen or len(seen) > 1024:
            fullpath = os.path.join(path, *reversed(parts))
            #print "LOOP %s" % fullpath
            path = fullpath
            logging.error("ELOOP: Too many symbolic links in '%s'" % path)
            break
        seen.append(tag)
        part = parts.pop()
        # Using normpath() to cleanup '.', '..' and multiple slashes.
        # Removing a suffix 'foo/..' is safe here since it can't change the
        # meaning of 'path' because it contains no symlinks - they have been
        # resolved already.
        newpath = os.path.normpath(os.path.join(path, part))
        rootedpath = os.path.join(root, newpath[1:])
        if newpath == "/":
            path = "/"
        elif os.path.islink(rootedpath):
            target = os.readlink(rootedpath)
            #print "LINK to '%s'" % target
            if os.path.isabs(target):
                path = "/"
            parts.extend(split_path(target))
        else:
            path = newpath
    #print "FINAL '%s'" % path
    return path


def is_broken_symlink(root, dirpath, filename):
    """Is symlink dirpath+filename broken?"""

    if dirpath[:len(root)] == root:
        dirpath = dirpath[len(root):]
    pathname = canonicalize_path(root, os.path.join(dirpath, filename))
    pathname = os.path.join(root, pathname[1:])

    # The symlink chain, if any, has now been resolved. Does the target
    # exist?
    #print "EXISTS ", pathname, os.path.exists(pathname)
    return not os.path.exists(pathname)


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


class Chroot:

    """A chroot for testing things in."""

    def __init__(self):
        self.name = None

    def create_temp_dir(self):
        """Create a temporary directory for the chroot."""
        self.name = tempfile.mkdtemp(dir=settings.tmpdir)
        os.chmod(self.name, 0755)
        logging.debug("Created temporary directory %s" % self.name)

    def create(self, temp_tgz = None):
        """Create a chroot according to user's wishes."""
        if not settings.schroot:
            self.create_temp_dir()
        cid = do_on_panic(self.remove)

        if temp_tgz:
            self.unpack_from_tgz(temp_tgz)
        elif settings.basetgz:
            self.unpack_from_tgz(settings.basetgz)
        elif settings.lvm_volume:
            self.setup_from_lvm(settings.lvm_volume)
        elif settings.existing_chroot:
            self.setup_from_dir(settings.existing_chroot)
        elif settings.schroot:
            self.setup_from_schroot(settings.schroot)
        else:
            self.setup_minimal_chroot()

        if not settings.schroot:
            self.mount_proc()
            self.mount_selinux()
        self.configure_chroot()
        if settings.basetgz or settings.schroot:
            self.run(["apt-get", "-yf", "dist-upgrade"])
        self.minimize()

        # Copy scripts dirs into the chroot, merging all dirs together,
        # later files overwriting earlier ones.
        if settings.scriptsdirs:
            dest = self.relative("tmp/scripts/")
            if not os.path.exists(self.relative("tmp/scripts/")):
                os.mkdir(dest)
            for sdir in settings.scriptsdirs:
                logging.debug("Copying scriptsdir %s to %s" % (sdir, dest))
                for sfile in os.listdir(sdir):
                    if (sfile.startswith("post_") or sfile.startswith("pre_")) and os.path.isfile(os.path.join(sdir, sfile)):
                        shutil.copy(os.path.join(sdir, sfile), dest)

        # Run custom scripts after creating the chroot.
        self.run_scripts("post_setup")

        if settings.savetgz and not temp_tgz:
            self.pack_into_tgz(settings.savetgz)

        dont_do_on_panic(cid)

    def remove(self):
        """Remove a chroot and all its contents."""
        if not settings.keep_tmpdir and os.path.exists(self.name):
            self.terminate_running_processes()
            if not settings.schroot:
                self.unmount_selinux()
                self.unmount_proc()
            if settings.lvm_volume:
                logging.debug('Unmounting and removing LVM snapshot %s' % self.lvm_snapshot_name)
                run(['umount', self.name])
                run(['lvremove', '-f', self.lvm_snapshot])
            if settings.schroot:
                logging.debug("Terminate schroot session '%s'" % self.name)
                run(['schroot', '--end-session', '--chroot', self.schroot_session])
            if not settings.schroot:
                shutil.rmtree(self.name)
                logging.debug("Removed directory tree at %s" % self.name)
        elif settings.keep_tmpdir:
            if settings.schroot:
                logging.debug("Keeping schroot session %s at %s" % (self.schroot_session, self.name))
            else:
                logging.debug("Keeping directory tree at %s" % self.name)   

    def create_temp_tgz_file(self):
        """Return the path to a file to be used as a temporary tgz file"""
        # Yes, create_temp_file() would work just as well, but putting it in
        # the interface for Chroot allows the VirtServ hack to work.
        (fd, temp_tgz) = create_temp_file()
        return temp_tgz

    def remove_temp_tgz_file(self, temp_tgz):
        """Remove the file that was used as a temporary tgz file"""
        # Yes, remove_files() would work just as well, but putting it in
        # the interface for Chroot allows the VirtServ hack to work.
        remove_files([temp_tgz])

    def pack_into_tgz(self, result):
        """Tar and compress all files in the chroot."""
        self.run(["apt-get", "clean"])
        logging.debug("Saving %s to %s." % (self.name, result))

        run(['tar', '-czf', result, '--one-file-system', '--exclude', 'tmp/scripts', '-C', self.name, './'])

    def unpack_from_tgz(self, tarball):
        """Unpack a tarball to a chroot."""
        logging.debug("Unpacking %s into %s" % (tarball, self.name))
        prefix = []
        if settings.eatmydata and os.path.isfile('/usr/bin/eatmydata'):
            prefix.append('eatmydata')
        run(prefix + ["tar", "-C", self.name, "-zxf", tarball])

    def setup_from_schroot(self, schroot):
        self.schroot_session = schroot.split(":")[1] + "-" + str(uuid.uuid1()) + "-piuparts"
        run(['schroot', '--begin-session', '--chroot', schroot , '--session-name', self.schroot_session])
        ret_code, output = run(['schroot', '--chroot', self.schroot_session, '--location'])
        self.name = output.strip()
        logging.info("New schroot session in '%s'" % self.name);

    def setup_from_lvm(self, lvm_volume):
        """Create a chroot by creating an LVM snapshot."""
        self.lvm_base = os.path.dirname(lvm_volume)
        self.lvm_vol_name = os.path.basename(lvm_volume)
        self.lvm_snapshot_name = self.lvm_vol_name + "-" + str(uuid.uuid1());
        self.lvm_snapshot = os.path.join(self.lvm_base, self.lvm_snapshot_name)

        logging.debug("Creating LVM snapshot %s from %s" % (self.lvm_snapshot, lvm_volume))
        run(['lvcreate', '-n', self.lvm_snapshot, '-s', lvm_volume, '-L', settings.lvm_snapshot_size])
        logging.info("Mounting LVM snapshot to %s" % self.name); 
        run(['mount', self.lvm_snapshot, self.name])

    def setup_from_dir(self, dirname):
        """Create chroot from an existing one."""
        logging.debug("Copying %s into %s" % (dirname, self.name))
        for name in os.listdir(dirname):
            src = os.path.join(dirname, name)
            dst = os.path.join(self.name, name)
            run(["cp", "-ax", src, dst])

    def run(self, command, ignore_errors=False):
        prefix = []
        if settings.eatmydata and os.path.isfile(os.path.join(self.name,
                                                 'usr/bin/eatmydata')):
            prefix.append('eatmydata')
        if settings.schroot:
            return run(["schroot", "--preserve-environment", "--run-session", "--chroot", self.schroot_session, "--directory", "/", "-u", "root", "--"] + prefix + command,
                   ignore_errors=ignore_errors, timeout=settings.max_command_runtime)
        else:
            return run(["chroot", self.name] + prefix + command,
                   ignore_errors=ignore_errors, timeout=settings.max_command_runtime)

    def create_apt_sources(self, distro):
        """Create an /etc/apt/sources.list with a given distro."""
        lines = []
        for mirror, components in settings.debian_mirrors:
            lines.append("deb %s %s %s\n" % 
                         (mirror, distro, " ".join(components)))
        create_file(self.relative("etc/apt/sources.list"), 
                    "".join(lines))

    def create_apt_conf(self):
        """Create /etc/apt/apt.conf.d/piuparts inside the chroot."""
        lines = [
            'APT::Get::Assume-Yes "yes";\n',
            'APT::Install-Recommends "0";\n',
            'APT::Install-Suggests "0";\n',
            ]
        lines.append('APT::Get::AllowUnauthenticated "%s";\n' % settings.apt_unauthenticated) 
        if "HTTP_PROXY" in os.environ:
            proxy = os.environ["HTTP_PROXY"]
        else:
            proxy = None;
            pat = re.compile(r"^Acquire::http::Proxy\s+\"([^\"]+)\"", re.I);
            p = subprocess.Popen(["apt-config", "dump"], 
                             stdout=subprocess.PIPE)
            stdout, _ = p.communicate()
            if stdout:
                for line in stdout.split("\n"):
                    m = re.match(pat, line)
                    if proxy is None and m:
                        proxy = m.group(1)
        if proxy:
            lines.append('Acquire::http::Proxy "%s";\n' % proxy)
        if settings.dpkg_force_unsafe_io:
            lines.append('Dpkg::Options {"--force-unsafe-io";};\n')
        if settings.dpkg_force_confdef:
            lines.append('Dpkg::Options {"--force-confdef";};\n')

        create_file(self.relative("etc/apt/apt.conf.d/piuparts"),
            "".join(lines))

    def create_dpkg_conf(self):
        """Create /etc/dpkg/dpkg.cfg.d/piuparts inside the chroot."""
        lines = []
        if settings.dpkg_force_unsafe_io:
            lines.append('force-unsafe-io\n')
        if settings.dpkg_force_confdef:
            lines.append('force-confdef\n')
            logging.info("Warning: dpkg has been configured to use the force-confdef option. This will hide problems, see #466118.")
        if lines:
          if not os.path.exists(self.relative("etc/dpkg/dpkg.cfg.d")):
              os.mkdir(self.relative("etc/dpkg/dpkg.cfg.d"))
          create_file(self.relative("etc/dpkg/dpkg.cfg.d/piuparts"),
            "".join(lines))

    def create_policy_rc_d(self):
        """Create a policy-rc.d that prevents daemons from running."""
        full_name = self.relative("usr/sbin/policy-rc.d")
        create_file(full_name, "#!/bin/sh\nexit 101\n")
        os.chmod(full_name, 0777)
        logging.debug("Created policy-rc.d and chmodded it.")

    def setup_minimal_chroot(self):
        """Set up a minimal Debian system in a chroot."""
        logging.debug("Setting up minimal chroot for %s at %s." % 
              (settings.debian_distros[0], self.name))
        prefix = []
        if settings.eatmydata and os.path.isfile('/usr/bin/eatmydata'):
            prefix.append('eatmydata')
        if settings.do_not_verify_signatures:
          logging.info("Warning: not using --keyring option when running debootstrap!")
        options = [settings.keyringoption]
        if settings.eatmydata:
            options.append('--include=eatmydata')
            options.append('--components=%s' % ','.join(settings.debian_mirrors[0][1]))
        run(prefix + ["debootstrap", "--variant=minbase"] + options +
            [settings.debian_distros[0], self.name, settings.debian_mirrors[0][0]])

    def minimize(self):
        """Minimize a chroot by removing (almost all) unnecessary packages"""
        if settings.skip_minimize or not settings.minimize:
             return
        self.run(["apt-get", "install", "debfoster"])
        self.run(["debfoster"] + settings.debfoster_options)
        remove_files([self.relative("var/lib/debfoster/keepers")])
        self.run(["dpkg", "--purge", "debfoster"])

    def configure_chroot(self):
        """Configure a chroot according to current settings"""
        os.environ["PIUPARTS_DISTRIBUTION"] = settings.debian_distros[0]
        if not settings.keep_sources_list:
            self.create_apt_sources(settings.debian_distros[0])
        self.create_apt_conf()
        self.create_dpkg_conf()
        self.create_policy_rc_d()
        for bindmount in settings.bindmounts:
            run(["mkdir", "-p", self.relative(bindmount)])
            run(["mount", "-obind", bindmount, self.relative(bindmount)])
        self.run(["apt-get", "update"])

    def upgrade_to_distros(self, distros, packages):
        """Upgrade a chroot installation to each successive distro."""
        for distro in distros:
            logging.debug("Upgrading %s to %s" % (self.name, distro))
            os.environ["PIUPARTS_DISTRIBUTION_NEXT"] = distro
            self.create_apt_sources(distro)
            # Run custom scripts before upgrade
            self.run_scripts("pre_distupgrade")
            self.run(["apt-get", "update"])
            self.run(["apt-get", "-yf", "dist-upgrade"])
            os.environ["PIUPARTS_DISTRIBUTION_PREV"] = os.environ["PIUPARTS_DISTRIBUTION"]
            os.environ["PIUPARTS_DISTRIBUTION"] = distro
            # Sometimes dist-upgrade won't upgrade the packages we want
            # to test because the new version depends on a newer library,
            # and installing that would require removing the old version
            # of the library, and we've told apt-get not to remove
            # packages. So, we force the installation like this.
            if packages:
                known_packages = self.get_known_packages(packages + settings.extra_old_packages)
                self.install_packages_by_name(known_packages)
            # Run custom scripts after upgrade
            self.run_scripts("post_distupgrade")
            self.check_for_no_processes()

    def get_known_packages(self, packages):
        """Does apt-get (or apt-cache) know about a set of packages?"""
        known_packages = []
        new_packages = []
        for name in packages:
            (status, output) = self.run(["apt-cache", "show", name],
                                        ignore_errors=True)
            # apt-cache reports status for some virtual packages and packages
            # in status config-files-remaining state without installation
            # candidate -- but only real packages have Filename/MD5sum/SHA*
            if status != 0 or re.search(r'^(Filename|MD5sum|SHA1|SHA256):', output, re.M) is None:
                new_packages.append(name)
            else:
                known_packages.append(name)
        if not known_packages:
            logging.info("apt-cache does not know about any of the requested packages")
        else:
            logging.info("apt-cache knows about the following packages: " +
                    ", ".join(known_packages))
            if new_packages:
                logging.info("the following packages are not in the archive: " +
                        ", ".join(new_packages))
        return known_packages

    def copy_files(self, source_names, target_name):
        """Copy files in 'source_name' to file/dir 'target_name', relative
        to the root of the chroot."""
        target_name = self.relative(target_name)
        logging.debug("Copying %s to %s" % 
                      (", ".join(source_names), target_name))
        for source_name in source_names:
            try:
                shutil.copy(source_name, target_name)
            except IOError, detail:
                logging.error("Error copying %s to %s: %s" % 
                      (source_name, target_name, detail))
                panic()

    def list_installed_files (self, pre_info, post_info):
        """List the new files installed, removed and modified between two dir trees.
        Actually, it is a nice output of the funcion diff_meta_dat."""
        (new, removed, modified) = diff_meta_data(pre_info, post_info)
        file_owners = self.get_files_owned_by_packages()

        if new:
            logging.debug("New installed files on system:\n" + file_list(new, file_owners))
        else:
            logging.debug("The package did not install any new file.\n")                    

        if removed:
            logging.debug("The following files have disappeared:\n" +
                          file_list(removed, file_owners))

        if modified:
            logging.debug("The following files have been modified:\n" +
                          file_list(modified, file_owners))
        else:
            logging.debug("The package did not modify any file.\n")     


    def install_package_files(self, package_files, packages = None):
        if package_files:
            self.copy_files(package_files, "tmp")
            tmp_files = [os.path.basename(a) for a in package_files]
            tmp_files = [os.path.join("tmp", name) for name in tmp_files]

            self.run_scripts("pre_install")

            if settings.list_installed_files:
                pre_info = self.save_meta_data()

                self.run(["dpkg", "-i"] + tmp_files, ignore_errors=True)
                self.list_installed_files (pre_info, self.save_meta_data())

                self.run(["apt-get", "-yf", "install"])
                self.list_installed_files (pre_info, self.save_meta_data())

            else:
                self.run(["dpkg", "-i"] + tmp_files, ignore_errors=True)
                self.run(["apt-get", "-yf", "install"])

            logging.info ("Installation of %s ok", tmp_files)

            self.run_scripts("post_install")

            remove_files([self.relative(name) for name in tmp_files])

    def get_selections(self):
        """Get current package selections in a chroot."""
        (status, output) = self.run(["dpkg", "--get-selections", "*"])
        vlist = [line.split() for line in output.split("\n") if line.strip()]
        vdict = {}
        for name, status in vlist:
            vdict[name] = status
        return vdict

    def get_diversions(self):
        """Get current dpkg-divert --list in a chroot."""
        if not settings.check_broken_diversions:
            return
        (status, output) = self.run(["dpkg-divert", "--list"])
        return output.split("\n")

    def get_modified_diversions(self, pre_install_diversions, post_install_diversions = None):
        """Check that diversions in chroot are identical (though potentially reordered)."""
        if post_install_diversions is None:
            post_install_diversions = self.get_diversions()
        removed = [ln for ln in pre_install_diversions if not ln in post_install_diversions]
        added = [ln for ln in post_install_diversions if not ln in pre_install_diversions]
        return (removed, added)

    def remove_packages(self, packages):
        """Remove packages in a chroot."""
        if packages:
            self.run(["apt-get", "remove"] + packages, ignore_errors=True)

    def purge_packages(self, packages):
        """Purge packages in a chroot."""
        if packages:
            self.run(["dpkg", "--purge"] + packages, ignore_errors=True)

    def restore_selections(self, selections, packages):
        """Restore package selections in a chroot to the state in
        'selections'."""

        changes = diff_selections(self, selections)
        deps = {}
        nondeps = {}
        for name, state in changes.iteritems():
            if name in packages:
                nondeps[name] = state
            else:
                deps[name] = state

        deps_to_remove = [name for name, state in deps.iteritems()
                          if state == "remove"]
        deps_to_purge = [name for name, state in deps.iteritems()
                         if state == "purge"]
        nondeps_to_remove = [name for name, state in nondeps.iteritems()
                             if state == "remove"]
        nondeps_to_purge = [name for name, state in nondeps.iteritems()
                            if state == "purge"]
        deps_to_install = [name for name, state in deps.iteritems()
                          if state == "install"]

        # Run custom scripts before removing all packages. 
        self.run_scripts("pre_remove")

        # First remove all packages (and reinstall missing ones).
        self.remove_packages(deps_to_remove + deps_to_purge +
                             nondeps_to_remove + nondeps_to_purge +
                             ["%s+" % x for x in deps_to_install])

        # Run custom scripts after removing all packages. 
        self.run_scripts("post_remove")

        if not settings.skip_cronfiles_test:
            cronfiles, cronfiles_list = self.check_if_cronfiles(packages)

        if not settings.skip_cronfiles_test and cronfiles:
            self.check_output_cronfiles(cronfiles_list)

        if not settings.skip_logrotatefiles_test:
            logrotatefiles, logrotatefiles_list = self.check_if_logrotatefiles(packages)

        if not settings.skip_logrotatefiles_test and logrotatefiles:
            installed = self.install_logrotate()
            self.check_output_logrotatefiles(logrotatefiles_list)
            self.purge_packages(installed)

        # Then purge all packages being depended on.
        self.purge_packages(deps_to_purge)

        # Finally, purge actual packages.
        self.purge_packages(nondeps_to_purge)

        # Run custom scripts after purge all packages.
        self.run_scripts("post_purge")

        # Now do a final run to see that everything worked.
        self.run(["dpkg", "--purge", "--pending"])
        self.run(["dpkg", "--remove", "--pending"])
        self.run(["apt-get", "clean"])

    def save_meta_data(self):
        """Return the filesystem meta data for all objects in the chroot."""
        self.run(["apt-get", "clean"])
        root = self.relative(".")
        vdict = {}
        proc = os.path.join(root, "proc")
        for dirpath, dirnames, filenames in os.walk(root):
            assert dirpath[:len(root)] == root
            if dirpath[:len(proc) + 1] in [proc, proc + "/"]:
                continue
            for name in [dirpath] + \
                        [os.path.join(dirpath, f) for f in filenames]:
                st = os.lstat(name)
                if stat.S_ISLNK(st.st_mode):
                    target = os.readlink(name)
                else:
                    target = None
                    if stat.S_ISDIR(st.st_mode):
                        name += "/"
                vdict[name[len(root):]] = (st, target)
        return vdict

    def relative(self, pathname):
        if pathname.startswith('/'):
            return os.path.join(self.name, pathname[1:])
        return os.path.join(self.name, pathname)

    def get_files_owned_by_packages(self):
        """Return dict[filename] = [packagenamelist]."""
        vdir = self.relative("var/lib/dpkg/info")
        vdict = {}
        for basename in os.listdir(vdir):
            if basename.endswith(".list"):
                pkg = basename[:-len(".list")]
                f = file(os.path.join(vdir, basename), "r")
                for line in f:
                    pathname = line.strip()
                    if pathname in vdict:
                        vdict[pathname].append(pkg)
                    else:
                        vdict[pathname] = [pkg]
                f.close()
        return vdict

    def install_packages_by_name(self, packages):
        if packages:
            self.run_scripts("pre_install")

            self.run(["apt-cache", "policy"])
            self.run(["apt-cache", "policy"] + packages)

            if settings.list_installed_files:
                pre_info = self.save_meta_data()
                self.run(["apt-get", "-y", "install"] + packages)
                self.list_installed_files (pre_info, self.save_meta_data())
            else:
                self.run(["apt-get", "-y", "install"] + packages)

            self.run_scripts("post_install")


    def check_for_no_processes(self):
        """Check there are no processes running inside the chroot."""
        (status, output) = run(["lsof", "-w", "+D", self.name], ignore_errors=True)
        count = len(output.split("\n")) - 1
        if count > 0:
            logging.error("FAIL: Processes are running inside chroot:\n%s" % 
                          indent_string(output))
            self.terminate_running_processes()
            panic()


    def terminate_running_processes(self):
        """Terminate all processes running in the chroot."""
        seen = []
        while True:
            p = subprocess.Popen(["lsof", "-t", "+D", self.name],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            stdout, _ = p.communicate()
            if not stdout:
                break

            pidlist = reversed([int(pidstr) for pidstr in stdout.split("\n") if len(pidstr) and int(pidstr) > 0])
            if not pidlist:
                break

            for pid in pidlist:
                try:
                    signo = (SIGTERM, SIGKILL)[pid in seen]
                    os.kill(pid, signo)
                    seen.append(pid)
                    logging.debug("kill -%d %d" % (signo, pid))
                    time.sleep(0.25)
                except OSError:
                    pass

            time.sleep(5)


    def mount_selinux(self):
        if selinux_enabled():
            run(["mkdir", "-p", self.relative("/selinux")])
            run(["mount", "-t", "selinuxfs", "/selinux", self.relative("/selinux")])
            logging.info("SElinux mounted into chroot")

    def unmount_selinux(self):
        if selinux_enabled():
            run(["umount", self.relative("/selinux")])
            logging.info("SElinux unmounted from chroot")

    def mount_proc(self):
        """Mount /proc inside chroot."""
        self.run(["mount", "-t", "proc", "proc", "/proc"])

    def unmount_proc(self):
        """Unmount /proc inside chroot."""
        self.run(["umount", "/proc"], ignore_errors=True)
        for bindmount in settings.bindmounts:
            run(["umount", self.relative(bindmount)], ignore_errors=True)

    def is_ignored(self, pathname):
        """Is a file (or dir or whatever) to be ignored?"""
        if pathname in settings.ignored_files:
            return True
        for pattern in settings.ignored_patterns:
            if re.search('^' + pattern + '$', pathname):
                return True
        return False

    def check_for_broken_symlinks(self):
        """Check that all symlinks in chroot are non-broken."""
        if not settings.check_broken_symlinks:
            return
        broken = []
        for dirpath, dirnames, filenames in os.walk(self.name):
            # Remove /proc within chroot to avoid lots of spurious errors.
            if dirpath == self.name and "proc" in dirnames:
                dirnames.remove("proc")
            for filename in filenames:
                full_name = name = os.path.join(dirpath, filename)
                if name.startswith(self.name):
                    name = name[len(self.name):]
                ret = is_broken_symlink(self.name, dirpath, filename)
                if ret and not self.is_ignored(name):
                    try:
                        target = os.readlink(full_name)
                    except os.error:
                        target = "<unknown>"
                    broken.append("%s -> %s" % (name, target))
        if broken:
            if settings.warn_broken_symlinks:
                logging.error("WARN: Broken symlinks:\n%s" %
                              indent_string("\n".join(broken)))
            else:
                logging.error("FAIL: Broken symlinks:\n%s" %
                              indent_string("\n".join(broken)))
                panic()
        else:
            logging.debug("No broken symlinks as far as we can find.")

    def check_if_cronfiles(self, packages):
        """Check if the packages have cron files under /etc/cron.d and in case positive, 
        it returns the list of files. """

        vdir = self.relative("var/lib/dpkg/info")
        vlist = []
        has_cronfiles  = False
        for p in packages:
            basename = p + ".list"

            if not os.path.exists(os.path.join(vdir,basename)):
                continue

            f = file(os.path.join(vdir,basename), "r")
            for line in f:
                pathname = line.strip()
                if pathname.startswith("/etc/cron."):
                    if os.path.isfile(self.relative(pathname.strip("/"))):
                        st = os.lstat(self.relative(pathname.strip("/")))
                        mode = st[stat.ST_MODE]
                        # XXX /etc/cron.d/ files are NOT executables
                        if (mode & stat.S_IEXEC): 
                            if not has_cronfiles:
                                has_cronfiles = True
                            vlist.append(pathname)
                            logging.info("Package " + p + " contains cron file: " + pathname)
            f.close()

        return has_cronfiles, vlist

    def check_output_cronfiles (self, list):
        """Check if a given list of cronfiles has any output. Executes 
        cron file as cron would do (except for SHELL)"""
        failed = False
        for vfile in list:

            if not os.path.exists(self.relative(vfile.strip("/"))):
                continue 

            (retval, output) = self.run([vfile])
            if output:
                failed = True
                logging.error("FAIL: Cron file %s has output with package removed" % vfile)

        if failed:
            panic()

    def check_if_logrotatefiles(self, packages):
        """Check if the packages have logrotate files under /etc/logrotate.d and in case positive, 
        it returns the list of files. """

        vdir = self.relative("var/lib/dpkg/info")
        vlist = []
        has_logrotatefiles  = False
        for p in packages:
            basename = p + ".list"

            if not os.path.exists(os.path.join(vdir,basename)):
                continue

            f = file(os.path.join(vdir,basename), "r")
            for line in f:
                pathname = line.strip()
                if pathname.startswith("/etc/logrotate.d/"):
                    if os.path.isfile(self.relative(pathname.strip("/"))):
                        if not has_logrotatefiles:
                            has_logrotatefiles = True
                        vlist.append(pathname)
                        logging.info("Package " + p + " contains logrotate file: " + pathname)
            f.close()

        return has_logrotatefiles, vlist

    def install_logrotate(self):
        """Install logrotate for check_output_logrotatefiles, and return the
        list of packages that were installed"""
        old_selections = self.get_selections()
        self.run(['apt-get', 'install', '-y', 'logrotate'])
        diff = diff_selections(self, old_selections)
        return diff.keys()

    def check_output_logrotatefiles (self, list):
        """Check if a given list of logrotatefiles has any output. Executes 
        logrotate file as logrotate would do from cron (except for SHELL)"""
        failed = False
        for vfile in list:

            if not os.path.exists(self.relative(vfile.strip("/"))):
                continue 

            (retval, output) = self.run(['/usr/sbin/logrotate', vfile])
            if output or retval != 0:
                failed = True
                logging.error("FAIL: Logrotate file %s exits with error or has output with package removed" % file)

        if failed:
            panic()

    def run_scripts (self, step):
        """ Run custom scripts to given step post-install|remove|purge"""

        if not settings.scriptsdirs:
            return
        logging.info("Running scripts "+ step)
        basepath = self.relative("tmp/scripts/")
        if not os.path.exists(basepath):
            logging.error("Scripts directory %s does not exist" % basepath)
            panic()
        list_scripts = os.listdir(basepath)
        list_scripts.sort()
        for vfile in list_scripts:
            if vfile.startswith(step):
                script = os.path.join("tmp/scripts", vfile)
                self.run([script]) 


class VirtServ(Chroot):
    # Provides a thing that looks to the rest of piuparts much like
    # a chroot but is actually provided by an adt virtualisation server.
    # See /usr/share/doc/autopkgtest/README.virtualisation-server.

    def __init__(self, cmdline):
        self._cmdline = cmdline
        self.name = '/ADT-VIRT'
        self._vs = None

    def _awaitok(self, cmd):
        r = self._vs.stdout.readline().rstrip('\n')
        l = r.split(' ')
        if l[0] != 'ok': self._fail('virtserver response to %s: %s' % (cmd,r))
        logging.debug('adt-virt << %s', r)
        return l[1:]

    def _vs_send(self, cmd):
        if type(cmd) == type([]):
                def maybe_quote(a):
                    if type(a) != type(()): return a
                    (a,) = a
                    return urllib.quote(a)
                cmd = ' '.join(map(maybe_quote,cmd))
        logging.debug('adt-virt >> %s', cmd)
        print >>self._vs.stdin, cmd
        return cmd.split(' ')[0]

    def _command(self, cmd):
        # argument forms:   complete-command-string
        #                   [arg, ...]    where arg may be (arg,) to quote it
        cmdp = self._vs_send(cmd)
        self._vs.stdin.flush()
        return self._awaitok(cmdp)

    def _getfilecontents(self, filename):
        try:
            (_,tf) = create_temp_file()
            self._command(['copyup',(filename,),(tf,)])
            f = file(tf)
            d = f.read()
            f.close()
        finally:
            os.remove(tf)
        return d

    def create_temp_dir(self):
        if self._vs is None:
            logging.debug('adt-virt || %s' % self._cmdline)
            self._vs = subprocess.Popen(self._cmdline, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None)
            self._awaitok('banner')
            self._caps = self._command('capabilities')

    def shutdown(self):
        if self._vs is None: return
        self._vs_send('quit')
        self._vs.stdin.close()
        self._vs.stdout.close()
        self._vs.wait()
        self._vs = None

    def remove(self):
        self._command('close')

    def _fail(self,m):
        logging.error("adt-virt-* error: "+m)
        panic()

    def _open(self):
        self._scratch = self._command('open')[0]

    # this is a hack to make install_and_upgrade_between distros
    #  work; we pretend to save the chroot to a tarball but in
    #  fact we do nothing and then we can `restore' the `tarball' with
    #  adt-virt revert
    def create_temp_tgz_file(self):
        return self
    def remove_temp_tgz_file(self, tgz):
        if tgz is not self: self._fail('removing a tgz not supported')
        # FIXME: anything else to do here?
    def pack_into_tgz(self, tgz):
        if tgz is not self: self._fail('packing into tgz not supported')
        if not 'revert' in self._caps: self._fail('testbed cannot revert')
    def unpack_from_tgz(self, tgz):
        if tgz is not self: self._fail('unpacking from tgz not supported')
        self._open()

    def _execute(self, cmdl, tolerate_errors=False):
        assert type(cmdl) == type([])
        prefix = ['sh','-ec','''
            LC_ALL=C
            unset LANGUAGES
            export LC_ALL
            exec 2>&1
            exec "$@"
                ''','<command>']
        ca = ','.join(map(urllib.quote, prefix + cmdl))
        stdout = '%s/cmd-stdout' % self._scratch
        stderr = '%s/cmd-stderr-base' % self._scratch
        cmd = ['execute',ca,
               '/dev/null',(stdout,),(stderr,),
               '/root','timeout=600']
        es = int(self._command(cmd)[0])
        if es and not tolerate_errors:
            stderr_data = self._getfilecontents(stderr)
            logging.error("Execution failed (status=%d): %s\n%s" %
                (es, `cmdl`, indent_string(stderr_data)))
            panic()
        return (es, stdout, stderr)

    def _execute_getoutput(self, cmdl):
        (es,stdout,stderr) = self._execute(cmdl)
        stderr_data = self._getfilecontents(stderr)
        if es or stderr_data:
            logging.error('Internal command failed (status=%d): %s\n%s' %
                (es, `cmdl`, indent_string(stderr_data)))
            panic()
        (_,tf) = create_temp_file()
        try:
            self._command(['copyup',(stdout,),(tf,)])
        except:
            os.remove(tf)
            raise
        return tf

    def run(self, command, ignore_errors=False):
        cmdl = ['sh','-ec','cd /\n' + ' '.join(command)]
        (es,stdout,stderr) = self._execute(cmdl, tolerate_errors=True)
        stdout_data = self._getfilecontents(stdout)
        print >>sys.stderr, "VirtServ run", `command`,`cmdl`, '==>', `es`,`stdout`,`stderr`, '|', stdout_data
        if es == 0 or ignore_errors: return (es, stdout_data)
        stderr_data = self._getfilecontents(stderr)
        logging.error('Command failed (status=%d): %s\n%s' %
                    (es, `command`, indent_string(stdout_data + stderr_data)))
        panic()

    def setup_minimal_chroot(self):
        self._open()

    def _tbpath(self, with_junk):
        if not with_junk.startswith(self.name):
            logging.error("Un-mangling testbed path `%s' but it does not"
                        "start with expected manglement `%s'" %
                        (with_junk, self.name))
            panic()
        return with_junk[len(self.name):]

    def chmod(self, path, mode):
        self._execute(['chmod', ('0%o' % mode), self._tbpath(path)])
    def remove_files(self, paths):
        self._execute(['rm','--'] + map(self._tbpath, paths))
    def copy_file(self, our_src, tb_dest):
        self._command(['copydown',(our_src,),
                (self._tbpath(tb_dest)+'/'+os.path.basename(our_src),)])
    def create_file(self, path, data):
        path = self._tbpath(path)
        try:
            (_,tf) = create_temp_file()
            f = file(tf,'w')
            f.write(tf)
            f.close()
            self._command(['copydown',(tf,),(path,)])
        finally:
            os.remove(tf)

    class DummyStat: pass

    def save_meta_data(self):
        mode_map = {
            's': stat.S_IFSOCK,
            'l': stat.S_IFLNK,
            'f': stat.S_IFREG,
            'b': stat.S_IFBLK,
            'd': stat.S_IFDIR,
            'c': stat.S_IFCHR,
            'p': stat.S_IFIFO,
        }

        vdict = {}

        tf = self._execute_getoutput(['find','/','-xdev','-printf',
                "%y %m %U %G %s %p %l \\n".replace(' ','\\0')])
        try:
            f = file(tf)

            while 1:
                line = ''
                while 1:
                    splut = line.split('\0')
                    if len(splut) == 8 and splut[7] == '\n': break
                    if len(splut) >= 8:
                        self._fail('aaargh wrong output from find: %s' %
                                    urllib.quote(line), `splut`)
                    l = f.readline()
                    if not l:
                        if not line: break
                        self._fail('aargh missing final newline from find'
                                    ': %s, %s' % (`l`[0:200], `splut`[0:200]))
                    line += l
                if not line: break

                st = VirtServ.DummyStat()
                st.st_mode = mode_map[splut[0]] | int(splut[1],8)
                (st.st_uid, st.st_gid, st.st_size) = map(int, splut[2:5])

                vdict[splut[5]] = (st, splut[6])

            f.close()
        finally:
            os.remove(tf)

        return vdict     

    def get_files_owned_by_packages(self):
        tf = self._execute_getoutput(['bash','-ec','''
                cd /var/lib/dpkg/info
                find . -name "*.list" -type f -print0 | \\
                    xargs -r0 egrep . /dev/null
                test "${PIPESTATUS[*]}" = "0 0"
            '''])
        vdict = {}
        try:
            f = file(tf)
            for l in f:
                (lf,pathname) = l.rstrip('\n').split(':',1)
                assert lf.endswith('.list')
                pkg = lf[:-5]
                if pathname in vdict:
                    vdict[pathname].append(pkg)
                else:
                    vdict[pathname] = [pkg]

            f.close()
        finally:
            os.remove(tf)
        return vdict

    def check_for_broken_symlinks(self):
        if not settings.check_broken_symlinks:
            return
        tf = self._execute_getoutput(['bash','-ec','''
                find / -xdev -type l -print0 | \\
                    xargs -r0 -i'{}' \\
                    find '{}' -maxdepth 0 -follow -type l -ls
                test "${PIPESTATUS[*]}" = "0 0"
            '''])
        try:
            f = file(tf)
            broken = False
            for l in f:
                logging.error("FAIL: Broken symlink: " + l)
                broken = True
            if broken: panic()
            logging.debug("No broken symlinks found.")
        finally:
            os.remove(tf)

    def check_for_no_processes(self): pass # ?!
    def mount_proc(self): pass
    def unmount_proc(self): pass

def selinux_enabled(enabled_test="/usr/sbin/selinuxenabled"):
    if os.access(enabled_test, os.X_OK):
        retval, output = run([enabled_test], ignore_errors=True)
        if retval == 0:
            return True
        else:
            return False

def objects_are_different(pair1, pair2):
    """Are filesystem objects different based on their meta data?"""
    (m1, target1) = pair1
    (m2, target2) = pair2
    if (m1.st_mode != m2.st_mode or 
        m1.st_uid != m2.st_uid or 
        m1.st_gid != m2.st_gid or
        target1 != target2):
        return True
    if stat.S_ISREG(m1.st_mode):
        return m1.st_size != m2.st_size # or m1.st_mtime != m2.st_mtime
    return False


def diff_meta_data(tree1, tree2):
    """Compare two dir trees and return list of new files (only in 'tree2'),
       removed files (only in 'tree1'), and modified files."""

    tree1 = tree1.copy()
    tree2 = tree2.copy()

    for name in settings.ignored_files:
        if name in tree1:
            del tree1[name]
        if name in tree2:
            del tree2[name]

    for pattern in settings.ignored_patterns:
        pat = re.compile(pattern)
        for name in tree1.keys():
            m = pat.search(name)
            if m:
                del tree1[name]
        for name in tree2.keys():
            m = pat.search(name)
            if m:
                del tree2[name]

    modified = []
    for name in tree1.keys()[:]:
        if name in tree2:
            if objects_are_different(tree1[name], tree2[name]):
                modified.append((name, tree1[name]))
            del tree1[name]
            del tree2[name]

    removed = [x for x in tree1.iteritems()]
    new = [x for x in tree2.iteritems()]

    # fix for #586793 by Andreas Beckmann <debian@abeckmann.de>
    # prune rc?.d symlinks renamed by insserv
    pat1 = re.compile(r"^(/etc/rc.\.d/)[SK][0-9]{2}(.*)$")
    for name1, data1 in removed[:]:
        m = pat1.search(name1)
        if m:
            pat2 = re.compile(r"^" + m.group(1) + r"[SK][0-9]{2}" + m.group(2) + r"$")
            for name2, data2 in new[:]:
                m = pat2.search(name2)
                if m:
                    logging.debug("File was renamed: %s\t=> %s" % (name1, name2))
                    removed.remove((name1, data1))
                    new.remove((name2, data2))
    # this is again special casing due to the behaviour of a single package :(
    # general tracking of moved files would be the better approach, probably.

    return new, removed, modified


def file_list(meta_infos, file_owners):
    """Return list of indented filenames."""
    meta_infos = meta_infos[:]
    meta_infos.sort()
    vlist = []
    for name, data in meta_infos:
        (st, target) = data
        info = ""
        if target is not None:
            info = " -> %s" % target
        vlist.append("  %s%s\t" % (name, info))
        key = name
        if key.endswith('/'):
            key = key[:-1]
        if key in file_owners:
            vlist.append(" owned by: %s\n" % ", ".join(file_owners[key]))
        else:
            vlist.append(" not owned\n")        

    return "".join(vlist)


def offending_packages(meta_infos, file_owners):
    """Return a Set of offending packages."""
    pkgset = set()
    for name, data in meta_infos:
        if name in file_owners:
            for pkg in file_owners[name]:
                pkgset.add(pkg)
    return pkgset


def prune_files_list(files, depsfiles):
    """Remove elements from 'files' that are in 'depsfiles', and return the
    list of removed elements.
    """
    warn = []
    for vfile in depsfiles:
        if vfile in files:
            files.remove(vfile)
            warn.append(vfile)
    return warn


def diff_selections(chroot, selections):
    """Compare original and current package selection.
       Return dict where dict[package_name] = original_status, that is,
       the value in the dict is the state that the package needs to be
       set to to restore original selections."""
    changes = {}
    current = chroot.get_selections()
    for name, value in current.iteritems():
        if name not in selections:
            changes[name] = "purge"
        elif selections[name] != current[name] and \
             selections[name] in ["purge", "install"]:
            changes[name] = selections[name]
    for name, value in selections.iteritems():
        if name not in current:
            changes[name] = "install"
    return changes


def get_package_names_from_package_files(package_files):
    """Return list of package names given list of package file names."""
    vlist = []
    for filename in package_files:
        (status, output) = run(["dpkg", "--info", filename])
        for line in [line.lstrip() for line in output.split("\n")]:
            if line[:len("Package:")] == "Package:":
                vlist.append(line.split(":", 1)[1].strip())
    return vlist

# Method to process a changes file, returning a list of all the .deb packages
# from the 'Files' stanza.
def process_changes(changes):
    # Determine the path to the changes file, then check if it's readable.
    dir_path = ""
    changes_path = ""
    if not os.path.dirname(changes):
        changes_path = os.path.basename(changes)
    else:
        dir_path = os.path.dirname(changes) + "/"
        changes_path = os.path.abspath(changes)
    if not os.access(changes_path, os.R_OK):
        logging.warn(changes_path + " is not readable. Skipping.")
        return

    # Determine the packages in the changes file through the 'Files' stanza.
    field = 'Files'
    pattern = re.compile(\
        r'^'+field+r':' + r'''  # The field we want the contents from
        (.*?)                   # The contents of the field
        \n([^ ]|$)              # Start of a new field or EOF
        ''',
        re.MULTILINE | re.DOTALL | re.VERBOSE)
    f = open(changes_path)
    file_text = f.read()
    f.close()
    matches = pattern.split(file_text)

    # Append all the packages found in the changes file to a package list.
    package_list = []
    newline_p = re.compile('\n')
    package_p = re.compile('.*?([^ ]+\.deb)$')
    for line in newline_p.split(matches[1]):
        if package_p.match(line):
            package = dir_path + package_p.split(line)[1]
            package_list.append(package)

    # Return the list.
    return package_list


def check_results(chroot, chroot_state, file_owners, deps_info=None):
    """Check that current chroot state matches 'chroot_state'.

    If settings.warn_on_others is True and deps_info is not None, then only
    print a warning rather than failing if the current chroot contains files
    that are in deps_info but not in root_info.  (In this case, deps_info
    should be the result of chroot.save_meta_data() right after the
    dependencies are installed, but before the actual packages to test are
    installed.)
    """

    root_info = chroot_state["tree"]
    ok = True
    if settings.check_broken_diversions:
        (removed, added) = chroot.get_modified_diversions(chroot_state["diversions"])
        if added:
            logging.error("FAIL: Installed diversions (dpkg-divert) not removed by purge:\n%s" %
                          indent_string("\n".join(added)))
            ok = False
        if removed:
            logging.error("FAIL: Existing diversions (dpkg-divert) removed/modified:\n%s" %
                          indent_string("\n".join(removed)))
            ok = False

    current_info = chroot.save_meta_data()
    if settings.warn_on_others and deps_info is not None:
        (new, removed, modified) = diff_meta_data(root_info, current_info)
        (depsnew, depsremoved, depsmodified) = diff_meta_data(root_info,
                                                              deps_info)

        warnnew = prune_files_list(new, depsnew)
        warnremoved = prune_files_list(removed, depsremoved)
        warnmodified = prune_files_list(modified, depsmodified)

    else:
        (new, removed, modified) = diff_meta_data(root_info, current_info)

    if new:
        if settings.warn_on_leftovers_after_purge:
          logging.info("Warning: Package purging left files on system:\n" +
                       file_list(new, file_owners))
        else:
          logging.error("FAIL: Package purging left files on system:\n" +
                       file_list(new, file_owners))
          ok = False
    if removed:
        logging.error("FAIL: After purging files have disappeared:\n" +
                      file_list(removed, file_owners))
        ok = False
    if modified:
        logging.error("FAIL: After purging files have been modified:\n" +
                      file_list(modified, file_owners))
        ok = False

    if ok and settings.warn_on_others and deps_info is not None:
        if warnnew:
            msg = ("Warning: Package purging left files on system:\n" +
                   file_list(warnnew, file_owners) + \
                   "These files seem to have been left by dependencies rather "
                   "than by packages\nbeing explicitly tested.\n")
            logging.info(msg)
        if warnremoved:
            msg = ("After purging files have dissappeared:\n" +
                   file_list(warnremoved, file_owners) +
                   "This seems to have been caused by dependencies rather "
                   "than by packages\nbbeing explicitly tested.\n")
            logging.info(msg)
        if warnmodified:
            msg = ("After purging files have been modified:\n" +
                   file_list(warnmodified, file_owners) +
                   "This seems to have been caused by dependencies rather "
                   "than by packages\nbbeing explicitly tested.\n")
            logging.info(msg)

    return ok


def install_purge_test(chroot, chroot_state, package_files, packages):
    """Do an install-purge test. Return True if successful, False if not.
       Assume 'root' is a directory already populated with a working
       chroot, with packages in states given by 'selections'."""

    os.environ["PIUPARTS_TEST"] = "install"
    chroot.run_scripts("pre_test")

    # Install packages into the chroot.
    os.environ["PIUPARTS_PHASE"] = "install"

    if settings.warn_on_others:
        # Create a metapackage with dependencies from the given packages
        if package_files:
            control_infos = []
            # We were given package files, so let's get the Depends and
            # Conflicts directly from the .debs
            for deb in package_files:
                returncode, output = run(["dpkg", "-f", deb])
                control = deb822.Deb822(output)
                control_infos.append(control)
        else:
            # We have package names.  Use apt to get all their control
            # information.
            apt_cache_args = ["apt-cache", "show"]
            apt_cache_args.extend(packages)
            returncode, output = chroot.run(apt_cache_args)
            control_infos = deb822.Deb822.iter_paragraphs(output.splitlines())

        depends = []
        conflicts = []
        for control in control_infos:
            if control.get("pre-depends"):
                depends.append(control["pre-depends"])
            if control.get("depends"):
                depends.append(control["depends"])
            if control.get("conflicts"):
                conflicts.append(control["conflicts"])
        all_depends = ", ".join(depends)
        all_conflicts = ", ".join(conflicts)
        metapackage = make_metapackage("piuparts-depends-dummy",
                                       all_depends, all_conflicts)

        # Install the metapackage
        chroot.install_package_files([metapackage])
        # Now remove it
        metapackagename = os.path.basename(metapackage)[:-4]
        chroot.purge_packages([metapackagename])
        shutil.rmtree(os.path.dirname(metapackage))

        # Save the file ownership information so we can tell which
        # modifications were caused by the actual packages we are testing,
        # rather than by their dependencies.
        deps_info = chroot.save_meta_data()
    else:
        deps_info = None

    if package_files:
        chroot.install_package_files(package_files, packages)
    else:
        chroot.install_packages_by_name(packages)

    if settings.install_remove_install:
        chroot.remove_packages(packages)
        if package_files:
            chroot.install_package_files(package_files)
        else:
            chroot.install_packages_by_name(packages)

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    file_owners = chroot.get_files_owned_by_packages()

    # Remove all packages from the chroot that weren't there initially.    
    chroot.restore_selections(chroot_state["selections"], packages)

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    return check_results(chroot, chroot_state, file_owners, deps_info=deps_info)


def install_upgrade_test(chroot, chroot_state, package_files, packages, old_packages):
    """Install old_packages via apt-get, then upgrade from package files.
    Return True if successful, False if not."""

    os.environ["PIUPARTS_TEST"] = "upgrade"
    chroot.run_scripts("pre_test")

    # First install via apt-get.
    os.environ["PIUPARTS_PHASE"] = "install"
    chroot.install_packages_by_name(old_packages)

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    if settings.install_remove_install:
        chroot.remove_packages(packages)

    # Then from the package files.
    os.environ["PIUPARTS_PHASE"] = "upgrade"
    chroot.install_package_files(package_files, packages)

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    file_owners = chroot.get_files_owned_by_packages()

    # Remove all packages from the chroot that weren't there initially.
    chroot.restore_selections(chroot_state["selections"], packages)

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    return check_results(chroot, chroot_state, file_owners)


def save_meta_data(filename, chroot_state):
    """Save directory tree meta data into a file for fast access later."""
    logging.debug("Saving chroot meta data to %s" % filename)
    f = file(filename, "w")
    pickle.dump(chroot_state, f)
    f.close()


def load_meta_data(filename):
    """Load meta data saved by 'save_meta_data'."""
    logging.debug("Loading chroot meta data from %s" % filename)
    f = file(filename, "r")
    chroot_state = pickle.load(f)
    f.close()
    return chroot_state


def install_and_upgrade_between_distros(package_files, packages):
    """Install package and upgrade it between distributions, then remove.
       Return True if successful, False if not."""

    # this function is a bit confusing at first, because of what it does by default:
    # 1. create chroot with source distro
    # 2. upgrade chroot to target distro
    # 3. remove chroot and recreate chroot with source distro
    # 4. install depends in chroot
    # 5. install package in chroot
    # 6. upgrade chroot to target distro
    # 7. remove package and depends
    # 8. compare results
    #
    # sounds silly, or?
    # well, it is is a reasonable default (see below for why), but 
    #
    # step 2+3 can be done differently by using --save-end-meta once and 
    # then --end-meta for all following runs - until the target distro
    # changes again... 
    # 
    # Under normal circumstances the target distro can change anytime, ie. at
    # the next mirror pulse, so unless the target distro is frozen, this is
    # a reasonable default behaviour for distro upgrade tests, which are not 
    # done by default anyway.

    os.environ["PIUPARTS_TEST"] = "distupgrade"

    chroot = get_chroot()
    chroot.create()
    cid = do_on_panic(chroot.remove)

    if settings.end_meta:
        # load root_info and selections
        chroot_state = load_meta_data(settings.end_meta)
    else:
        if not settings.basetgz and not settings.schroot:
            temp_tgz = chroot.create_temp_tgz_file()
            # FIXME: on panic remove temp_tgz
            chroot.pack_into_tgz(temp_tgz)

        chroot.upgrade_to_distros(settings.debian_distros[1:], [])

        chroot.check_for_no_processes()

        # set root_info and selections
        chroot_state = {}
        chroot_state["tree"] = chroot.save_meta_data()
        chroot_state["selections"] = chroot.get_selections()
        chroot_state["diversions"] = chroot.get_diversions()

        if settings.save_end_meta:
            # save root_info and selections
            save_meta_data(settings.save_end_meta, chroot_state)

        chroot.remove()
        dont_do_on_panic(cid)

        # leave indication in logfile why we do what we do
        logging.info("Notice: package selections and meta data from target distro saved, now starting over from source distro. See the description of --save-end-meta and --end-meta to learn why this is neccessary and how to possibly avoid it.")

        chroot = get_chroot()
        if settings.basetgz or settings.schroot:
            chroot.create()
        else:
            chroot.create(temp_tgz)
            chroot.remove_temp_tgz_file(temp_tgz)
        cid = do_on_panic(chroot.remove)

    chroot.check_for_no_processes()

    chroot.run_scripts("pre_test")

    os.environ["PIUPARTS_PHASE"] = "install"

    known_packages = chroot.get_known_packages(packages + settings.extra_old_packages)
    chroot.install_packages_by_name(known_packages)

    if settings.install_remove_install:
        chroot.remove_packages(packages)

    chroot.check_for_no_processes()

    os.environ["PIUPARTS_PHASE"] = "distupgrade"

    if not settings.install_remove_install:
        chroot.upgrade_to_distros(settings.debian_distros[1:], packages)
    else:
        chroot.upgrade_to_distros(settings.debian_distros[1:], [])

    chroot.check_for_no_processes()

    os.environ["PIUPARTS_PHASE"] = "upgrade"

    if settings.install_remove_install:
        chroot.install_packages_by_name(packages)

    chroot.install_package_files(package_files, packages)

    chroot.check_for_no_processes()

    file_owners = chroot.get_files_owned_by_packages()

    chroot.restore_selections(chroot_state["selections"], packages)
    result = check_results(chroot, chroot_state, file_owners)

    chroot.check_for_no_processes()

    chroot.remove()
    dont_do_on_panic(cid)

    return result


def parse_mirror_spec(str, defaultcomponents=[]):
    """Parse a mirror specification from the --mirror option argument.
       Return (mirror, componentslist)."""
    parts = str.split()
    return parts[0], parts[1:] or defaultcomponents[:]


def find_default_debian_mirrors():
    """Find the default Debian mirrors."""
    mirrors = []
    try:
        f = file("/etc/apt/sources.list", "r")
        for line in f:
            parts = line.split()
            if len(parts) > 2 and parts[0] == "deb":
                mirrors.append((parts[1], parts[3:]))
                break # Only use the first one, at least for now.
        f.close()
    except IOError:
        return None
    return mirrors


def forget_ignores(option, opt, value, parser, *args, **kwargs):
    settings.bindmounts = []
    parser.values.ignore = []
    parser.values.ignore_regex = []
    settings.ignored_files = []
    settings.ignored_patterns = []


def set_basetgz_to_pbuilder(option, opt, value, parser, *args, **kwargs):
    parser.values.basetgz = "/var/cache/pbuilder/base.tgz"

def parse_command_line():
    """Parse the command line, change global settings, return non-options."""

    parser = optparse.OptionParser(usage="%prog [options] package ...",
                                   version="piuparts %s" % VERSION)


    parser.add_option("-a", "--apt", action="store_true", default=False,
                      help="Command line arguments are package names " +
                           "to be installed via apt.")

    parser.add_option("--adt-virt",
                      metavar='CMDLINE', default=None,
                      help="Use CMDLINE via autopkgtest (adt-virt-*)"
                           " protocol instead of managing a chroot.")

    parser.add_option("-b", "--basetgz", metavar="TARBALL",
                      help="Use TARBALL as the contents of the initial " +
                           "chroot, instead of building a new one with " +
                           "debootstrap.")

    parser.add_option("--bindmount", action="append", metavar="DIR",
                      default=[],
                      help="Directory to be bind-mounted inside the chroot.")

    parser.add_option("-d", "--distribution", action="append", metavar="NAME",
                      help="Which Debian distribution to use: a code name " +
                           "(for example lenny, squeeze, sid) or experimental. The " +
                           "default is sid (=unstable).")

    parser.add_option("-D", "--defaults", action="store",
                      help="Choose which set of defaults to use "
                           "(debian/ubuntu).")

    parser.add_option("--debfoster-options",
                      default="-o MaxPriority=required -o UseRecommends=no -f -n apt debfoster",
                      help="Run debfoster with different parameters (default: -o MaxPriority=required -o UseRecommends=no -f -n apt debfoster).")

    parser.add_option("--no-eatmydata",
                      default=False,
                      action='store_true',
                      help="Default is to use libeatmydata in the chroot")

    parser.add_option("--dpkg-noforce-unsafe-io",
                      default=False,
                      action='store_true',
                      help="Default is to run dpkg with --force-unsafe-io option, which causes dpkg to skip certain file system syncs known to cause substantial performance degradation on some filesystems.  This option turns that off and dpkg will use safe I/O operations.")

    parser.add_option("--dpkg-force-confdef",
                      default=False,
                      action='store_true',
                      help="Make dpkg use --force-confdef, which lets dpkg always choose the default action when a modified conffile is found. This option will make piuparts ignore errors it was designed to report and therefore should only be used to hide problems in depending packages.  (See #466118.)")

    parser.add_option("--do-not-verify-signatures", default=False,
                      action='store_true',
                      help="Do not verify signatures from the Release files when running debootstrap.")

    parser.add_option("-e", "--existing-chroot", metavar="DIR",
                      help="Use DIR as the contents of the initial " +
                           "chroot, instead of building a new one with " +
                           "debootstrap")

    parser.add_option("-i", "--ignore", action="append", metavar="FILENAME",
                      default=[],
                      help="Add FILENAME to list of filenames to be " +
                           "ignored when comparing changes to chroot.")

    parser.add_option("-I", "--ignore-regex", action="append", 
                      metavar="REGEX", default=[],
                      help="Add REGEX to list of Perl compatible regular " +
                           "expressions for filenames to be " +
                           "ignored when comparing changes to chroot.")

    parser.add_option("-k", "--keep-tmpdir", 
                      action="store_true", default=False,
                      help="Don't remove the temporary directory for the " +
                           "chroot when the program ends.")

    parser.add_option("-K", "--keyring", metavar="FILE",  
                      default = "/usr/share/keyrings/debian-archive-keyring.gpg", 
                      help="Use FILE as the keyring to use with debootstrap when creating chroots.")

    parser.add_option("--keep-sources-list", 
                      action="store_true", default=False,
                      help="Don't modify the chroot's " +
                           "etc/apt/sources.list (only makes sense " +
                           "with --basetgz).")

    parser.add_option("-l", "--log-file", metavar="FILENAME",
                      help="Write log file to FILENAME in addition to " +
                           "the standard output.")

    parser.add_option("--list-installed-files", 
                      action="store_true", default=False,
                      help="List files added to the chroot after the " +
                      "installation of the package.")

    parser.add_option("--lvm-volume", metavar="LVM-VOL", action="store",
                      help="Use LVM-VOL as source for the chroot, instead of building " +
                           "a new one with debootstrap. This creates a snapshot of the " +
                           "given LVM volume and mounts it to the chroot path")

    parser.add_option("--lvm-snapshot-size", metavar="SNAPSHOT-SIZE", action="store",
                      default="1G", help="Use SNAPSHOT-SIZE as snapshot size when creating " +
                      "a new LVM snapshot (default: 1G)")

    parser.add_option("--schroot", metavar="SCHROOT-NAME", action="store",
                      help="Use schroot session named SCHROOT-NAME for the chroot, instead of building " +
                           "a new one with debootstrap.")

    parser.add_option("-m", "--mirror", action="append", metavar="URL",
                      default=[],
                      help="Which Debian mirror to use.")

    parser.add_option("--no-diversions", action="store_true",
                      default=False,
                      help="Don't check for broken diversions.")

    parser.add_option("-n", "--no-ignores", action="callback",
                      callback=forget_ignores,
                      help="Forget all ignores set so far, including " +
                           "built-in ones.")

    parser.add_option("-N", "--no-symlinks", action="store_true",
                      default=False,
                      help="Don't check for broken symlinks.")

    parser.add_option("--no-upgrade-test", 
                      action="store_true", default=False,
                      help="Skip testing the upgrade from an existing version " +
                      "in the archive.")

    parser.add_option("--no-install-purge-test", 
                      action="store_true", default=False,
                      help="Skip install and purge test.")

    parser.add_option("--install-remove-install",
                      action="store_true", default=False,
                      help="Remove package after installation and reinstall. For testing installation in config-files-remaining state.")

    parser.add_option("--extra-old-packages",
                      action="append", default=[],
                      help="Install these additional packages along with the old packages from the archive. " +
                      "Useful to test Conflicts/Replaces of packages that will disappear during the update. " +
                      "Takes a comma separated list of package names and can be given multiple times.")

    parser.add_option("-p", "--pbuilder", action="callback",
                      callback=set_basetgz_to_pbuilder,
                      help="Use /var/cache/pbuilder/base.tgz as the base " +
                           "tarball.")

    parser.add_option("--pedantic-purge-test", 
                      action="store_true", default=False,
                      help="Be pedantic when checking if a purged package leaves files behind. If this option is not set, files left in /tmp are ignored.")

    parser.add_option("-s", "--save", metavar="FILENAME",
                      help="Save the chroot into FILENAME.")

    parser.add_option("-B", "--end-meta", metavar="FILE",
                      help="Load chroot package selection and file meta data from FILE. See the function install_and_upgrade_between_distros() in piuparts.py for defaults. Mostly useful for large scale distro upgrade tests.")

    parser.add_option("-S", "--save-end-meta", metavar="FILE",
                      help="Save chroot package selection and file meta data in FILE for later use. See the function install_and_upgrade_between_distros() in piuparts.py for defaults. Mostly useful for large scale distro upgrade tests.")

    parser.add_option("--single-changes-list", default=False,
                      action="store_true",
                      help="test all packages from all changes files together.")

    parser.add_option("--skip-cronfiles-test", 
                      action="store_true", default=False,
                      help="Skip testing the output from the cron files.")

    parser.add_option("--skip-logrotatefiles-test", 
                      action="store_true", default=False,
                      help="Skip testing the output from the logrotate files.")

    parser.add_option("--skip-minimize", 
                      action="store_true", default=True,
                      help="Skip minimize chroot step. This is the default now.")

    parser.add_option("--minimize", 
                      action="store_true", default=False,
                      help="Minimize chroot with debfoster. This used to be the default until #539142 was fixed.")

    parser.add_option("--scriptsdir", metavar="DIR",
                      action="append", default=[],
                      help="Directory where are placed the custom scripts. Can be given multiple times.")

    parser.add_option("-t", "--tmpdir", metavar="DIR",
                      help="Use DIR for temporary storage. Default is " +
                           "$TMPDIR or /tmp.")

    parser.add_option("-v", "--verbose", 
                      action="store_true", default=False,
                      help="No meaning anymore.")

    parser.add_option("--warn-on-others",
                      action="store_true", default=False,
                      help="Print a warning rather than failing if "
                           "files are left behind, modified, or removed "
                           "by a package that was not given on the "
                           "command-line.  Behavior with multiple packages "
                           "given could be problematic, particularly if the "
                           "dependency tree of one package in the list "
                           "includes another in the list.  Therefore, it is "
                           "recommended to use this option with one package "
                           "at a time.")

    parser.add_option("--warn-on-leftovers-after-purge",
                      action="store_true", default=False,
                      help="Print a warning rather than failing if "
                           "files are left behind after purge.")

    parser.add_option("--fail-on-broken-symlinks", action="store_true",
                      default=False,
                      help="Fail if broken symlinks are detected.")

    parser.add_option("--log-level", action="store",metavar='LEVEL',
                      default="dump",
                      help="Displays messages from LEVEL level, possible values are: error, info, dump, debug. The default is dump.")

    (opts, args) = parser.parse_args()

    settings.defaults = opts.defaults
    settings.keep_tmpdir = opts.keep_tmpdir
    settings.single_changes_list = opts.single_changes_list
    settings.args_are_package_files = not opts.apt
    # distro setup
    settings.debian_distros = opts.distribution
    settings.keep_sources_list = opts.keep_sources_list
    settings.keyring = opts.keyring
    settings.do_not_verify_signatures = opts.do_not_verify_signatures
    if settings.do_not_verify_signatures:
      settings.keyringoption=""
      settings.apt_unauthenticated="Yes"
    else:
      settings.keyringoption="--keyring=%s" % settings.keyring
      settings.apt_unauthenticated="No"
    settings.eatmydata = not opts.no_eatmydata
    settings.dpkg_force_unsafe_io = not opts.dpkg_noforce_unsafe_io
    settings.dpkg_force_confdef = opts.dpkg_force_confdef
    settings.bindmounts += opts.bindmount
    # chroot setup
    settings.basetgz = opts.basetgz
    settings.savetgz = opts.save
    settings.lvm_volume = opts.lvm_volume
    settings.lvm_snapshot_size = opts.lvm_snapshot_size
    settings.existing_chroot = opts.existing_chroot
    settings.schroot = opts.schroot
    settings.end_meta = opts.end_meta
    settings.save_end_meta = opts.save_end_meta
    settings.skip_minimize = opts.skip_minimize
    settings.minimize = opts.minimize
    if settings.minimize:
      settings.skip_minimize = False
    settings.debfoster_options = opts.debfoster_options.split()
    # tests and checks
    settings.no_install_purge_test = opts.no_install_purge_test
    settings.no_upgrade_test = opts.no_upgrade_test
    settings.install_remove_install = opts.install_remove_install
    settings.list_installed_files = opts.list_installed_files
    [settings.extra_old_packages.extend([i.strip() for i in csv.split(",")]) for csv in opts.extra_old_packages]
    settings.skip_cronfiles_test = opts.skip_cronfiles_test
    settings.skip_logrotatefiles_test = opts.skip_logrotatefiles_test
    settings.check_broken_diversions = not opts.no_diversions
    settings.check_broken_symlinks = not opts.no_symlinks
    settings.warn_broken_symlinks = not opts.fail_on_broken_symlinks
    settings.warn_on_others = opts.warn_on_others
    settings.warn_on_leftovers_after_purge = opts.warn_on_leftovers_after_purge
    settings.ignored_files += opts.ignore
    settings.ignored_patterns += opts.ignore_regex
    settings.pedantic_purge_test = opts.pedantic_purge_test
    if not settings.pedantic_purge_test:
      settings.ignored_patterns += settings.non_pedantic_ignore_patterns

    log_file_name = opts.log_file

    defaults = DefaultsFactory().new_defaults()

    settings.debian_mirrors = [parse_mirror_spec(x, defaults.get_components())
                               for x in opts.mirror]

    if opts.adt_virt is None:
        settings.adt_virt = None
    else:
        settings.adt_virt = VirtServ(opts.adt_virt)

    if opts.tmpdir is not None:
        settings.tmpdir = opts.tmpdir
        if not os.path.isdir(settings.tmpdir):
            logging.error("Temporary directory is not a directory: %s" % 
                          settings.tmpdir)
            panic()

    if opts.log_level == "error":
        setup_logging(logging.ERROR, log_file_name)
    elif opts.log_level == "info":
        setup_logging(logging.INFO, log_file_name)
    elif opts.log_level == "debug":
        setup_logging(logging.DEBUG, log_file_name)
    else:
        setup_logging(DUMP, log_file_name)

    exitcode = None

    if not settings.tmpdir:
        if "TMPDIR" in os.environ:
            settings.tmpdir = os.environ["TMPDIR"]
        else:
            settings.tmpdir = "/tmp"

    settings.scriptsdirs = opts.scriptsdir
    for sdir in settings.scriptsdirs:
        if not os.path.isdir(sdir):
            logging.error("Scripts directory is not a directory: %s" % sdir)
            panic()

    if not settings.debian_distros:
        settings.debian_distros = defaults.get_distribution()

    if not settings.debian_mirrors:
        settings.debian_mirrors = find_default_debian_mirrors()
        if not settings.debian_mirrors:
            settings.debian_mirrors = defaults.get_mirror()

    if settings.keep_sources_list and \
       (not settings.basetgz or len(settings.debian_distros) > 1):
        logging.error("--keep-sources-list only makes sense with --basetgz "
                      "and only one distribution")
        exitcode = 1

    if not args:
        logging.error("Need command line arguments: " +
                      "names of packages or package files")
        exitcode = 1
    settings.testobjects = args

    if exitcode is not None:
        sys.exit(exitcode)

    return args


def get_chroot():
    if settings.adt_virt is None: return Chroot()
    return settings.adt_virt

# Process the packages given in a list
def process_packages(package_list):
    # Find the names of packages.
    if settings.args_are_package_files:
        packages = get_package_names_from_package_files(package_list)
        package_files = package_list
    else:
        packages = package_list
        package_files = []

    if len(settings.debian_distros) == 1:
        chroot = get_chroot()
        chroot.create()
        cid = do_on_panic(chroot.remove)

        chroot_state = {}
        chroot_state["tree"] = chroot.save_meta_data()
        chroot_state["selections"] = chroot.get_selections()
        chroot_state["diversions"] = chroot.get_diversions()

        if not settings.no_install_purge_test:
            if not install_purge_test(chroot, chroot_state,
                      package_files, packages):
                logging.error("FAIL: Installation and purging test.")
                panic()
            logging.info("PASS: Installation and purging test.")

        if not settings.no_upgrade_test:
            if not settings.args_are_package_files:
                logging.info("Can't test upgrades: -a or --apt option used.")
            else:
                packages_to_query = packages[:]
                packages_to_query.extend(settings.extra_old_packages)
                known_packages = chroot.get_known_packages(packages_to_query)
                if not known_packages:
                    logging.info("Can't test upgrade: packages not known by apt-get.")
                elif install_upgrade_test(chroot, chroot_state, package_files,
                        packages, known_packages):
                    logging.info("PASS: Installation, upgrade and purging tests.")
                else:
                    logging.error("FAIL: Installation, upgrade and purging tests.")
                    panic()

        chroot.remove()
        dont_do_on_panic(cid)
    else:
        if install_and_upgrade_between_distros(package_files, packages):
            logging.info("PASS: Upgrading between Debian distributions.")
        else:
            logging.error("FAIL: Upgrading between Debian distributions.")
            panic()

    if settings.adt_virt is not None: settings.adt_virt.shutdown()

def main():
    """Main program. But you knew that."""

    args = parse_command_line()

    # check if user has root privileges
    if os.getuid():
        print 'You need to be root to use piuparts.'
        sys.exit(1)

    logging.info("-" * 78)
    logging.info("To quickly glance what went wrong, scroll down to the bottom of this logfile.")
    logging.info("FAQ available at http://wiki.debian.org/piuparts/FAQ")
    logging.info("-" * 78)
    logging.info("piuparts version %s starting up." % VERSION)
    logging.info("Command line arguments: %s" % " ".join(sys.argv))
    logging.info("Running on: %s %s %s %s %s" % os.uname())

    # Make sure debconf does not ask questions and stop everything.
    # Packages that don't use debconf will lose.
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    if "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]


    changes_packages_list = []
    regular_packages_list = []
    changes_p = re.compile('.*\.changes$')
    for arg in args:
        if changes_p.match(arg):
            package_list = process_changes(arg)
            if settings.single_changes_list:
                for package in package_list:
                    regular_packages_list.append(package)
            else:
                changes_packages_list.append(package_list)
        else:
            regular_packages_list.append(arg)

    if changes_packages_list:
        for package_list in changes_packages_list:
            process_packages(package_list)

    if regular_packages_list:
        process_packages(regular_packages_list)

    logging.info("PASS: All tests.")
    logging.info("piuparts run ends.")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["unittest"]:
            del sys.argv[1]
            unittest.main()
        else:
            main()
    except KeyboardInterrupt:
        print ''
        print 'Piuparts interrupted by the user, exiting...'
        sys.exit(1)

# vi:set et ts=4 sw=4 :
