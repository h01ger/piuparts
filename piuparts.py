#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# Copyright © 2007-2018 Holger Levsen (holger@layer-acht.org)
# Copyright © 2010-2018 Andreas Beckmann (anbe@debian.org)
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


"""Debian package installation and uninstallation tester.

This program sets up a minimal Debian system in a chroot, and installs
and uninstalls packages and their dependencies therein, looking for
problems.

See the manual page (piuparts.1, generated from piuparts.1.txt) for
more usage information.

Lars Wirzenius <liw@iki.fi>
"""
from __future__ import print_function  # Requires Py 2.6 or later

VERSION = "__PIUPARTS_VERSION__"


import distro_info
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
import json
import pickle
import subprocess
import traceback
import urllib
import uuid
import apt_pkg
import pipes
from collections import namedtuple
from signal import alarm, signal, SIGALRM, SIGTERM, SIGKILL

try:
    from debian import deb822
except ImportError:
    from debian_bundle import deb822

import piupartslib.conf

apt_pkg.init_system()

DISTRO_CONFIG_FILE = "/etc/piuparts/distros.conf"


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

    def get_keyring(self):
        """Return default keyring."""


class DebianDefaults(Defaults):

    def get_components(self):
        return ["main", "contrib", "non-free"]

    def get_mirror(self):
        return [("http://deb.debian.org/debian", self.get_components())]

    def get_distribution(self):
        return [distro_info.DebianDistroInfo().devel()]

    def get_keyring(self):
        return "/usr/share/keyrings/debian-archive-keyring.gpg"


class UbuntuDefaults(Defaults):

    def get_components(self):
        return ["main", "universe", "restricted", "multiverse"]

    def get_mirror(self):
        return [("http://archive.ubuntu.com/ubuntu", self.get_components())]

    def get_distribution(self):
        return [distro_info.UbuntuDistroInfo().devel()]

    def get_keyring(self):
        return "/usr/share/keyrings/ubuntu-archive-keyring.gpg"


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
        self.keep_env = False
        self.shell_on_error = False
        self.max_command_output_size = 8 * 1024 * 1024  # 8 MB (google-android-ndk-installer on install) (daptup on dist-upgrade)
        self.max_command_runtime = 60 * 60  # 60 minutes (texlive-full and blends metapackages on dist-upgrade)
        self.single_changes_list = False
        self.single_packages = False
        self.args_are_package_files = True
        # distro setup
        self.proxy = None
        self.debian_mirrors = []
        self.extra_repos = []
        self.testdebs_repo = None
        self.debian_distros = []
        self.keep_sources_list = False
        self.keyring = None
        self.do_not_verify_signatures = False
        self.no_check_valid_until = False
        self.install_recommends = False
        self.install_suggests = False
        self.eatmydata = True
        self.dpkg_force_unsafe_io = True
        self.dpkg_force_confdef = False
        self.scriptsdirs = []
        self.bindmounts = []
        self.allow_database = False
        # chroot setup
        self.arch = None
        self.basetgz = None
        self.savetgz = None
        self.lvm_volume = None
        self.lvm_snapshot_size = "1G"
        self.existing_chroot = None
        self.hard_link = False
        self.schroot = None
        self.end_meta = None
        self.save_end_meta = None
        self.skip_minimize = True
        self.minimize = False
        self.debfoster_options = None
        self.docker_image = None
        # tests and checks
        self.no_install_purge_test = False
        self.no_upgrade_test = False
        self.upgrade_before_dist_upgrade = False
        self.distupgrade_to_testdebs = False
        self.install_remove_install = False
        self.install_purge_install = False
        self.list_installed_files = False
        self.fake_essential_packages = []
        self.extra_old_packages = []
        self.skip_cronfiles_test = False
        self.skip_logrotatefiles_test = False
        self.adequate = True
        self.check_broken_diversions = True
        self.check_broken_symlinks = True
        self.warn_broken_symlinks = True
        self.warn_on_others = False
        self.warn_on_leftovers_after_purge = False
        self.warn_on_debsums_errors = False
        self.warn_on_install_over_symlink = False
        self.warn_if_inadequate = True
        self.pedantic_purge_test = False
        self.ignored_files = [
            # /root/.rnd should *not* be listed here, see #750099
            # piuparts state
            "/usr/sbin/policy-rc.d",
            # system state
            "/boot/grub/",
            "/etc/X11/",
            "/etc/X11/Xwrapper.config",         #859929
            "/etc/X11/default-display-manager",
            "/etc/aliases",
            "/etc/aliases.db",
            "/etc/crypttab",
            "/etc/group",
            "/etc/group-",
            "/etc/group.org",
            "/etc/gshadow",
            "/etc/gshadow-",
            "/etc/hosts",
            "/etc/inetd.conf",
            "/etc/inittab",
            "/etc/ld.so.cache",
            "/etc/machine-id",
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
            "/etc/passwd.org",
            "/etc/rc.local",
            "/etc/shadow",
            "/etc/shadow-",
            "/etc/shadow.org",
            "/etc/subgid",
            "/etc/subgid-",
            "/etc/subuid",
            "/etc/subuid-",
            "/usr/share/info/dir",
            "/usr/share/info/dir.old",
            "/var/cache/ldconfig/aux-cache",
            "/var/crash/",
            "/var/games/",
            # package management
            "/etc/apt/apt.conf.d/01autoremove-kernels",
            "/etc/apt/secring.gpg",
            "/etc/apt/trustdb.gpg",
            "/etc/apt/trusted.gpg",
            "/etc/apt/trusted.gpg~",
            "/var/cache/apt/archives/lock",
            "/var/cache/apt/archives/partial/",
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
            "/var/lib/apt/daily_lock",
            "/var/lib/apt/extended_states",
            "/var/lib/cdebconf/",
            "/var/lib/cdebconf/passwords.dat",
            "/var/lib/cdebconf/questions.dat",
            "/var/lib/cdebconf/questions.dat-old",
            "/var/lib/cdebconf/templates.dat",
            "/var/lib/cdebconf/templates.dat-old",
            "/var/lib/dpkg/arch",
            "/var/lib/dpkg/available",
            "/var/lib/dpkg/available-old",
            "/var/lib/dpkg/diversions",
            "/var/lib/dpkg/diversions-old",
            "/var/lib/dpkg/lock",
            "/var/lib/dpkg/lock-frontend",
            "/var/lib/dpkg/status",
            "/var/lib/dpkg/status-old",
            "/var/lib/dpkg/statoverride",
            "/var/lib/dpkg/statoverride-old",
            "/var/log/alternatives.log",
            "/var/log/apt/eipp.log.xz",
            "/var/log/apt/history.log",
            "/var/log/apt/term.log",
            "/var/log/bootstrap.log",
            "/var/log/dbconfig-common/dbc.log",
            "/var/log/dpkg.log",
            # system logfiles
            "/var/log/auth.log",
            "/var/log/btmp",
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
            "/var/log/tallylog",
            "/var/log/user.log",
            # application logfiles
            # actually, only modification should be permitted here, but not creation/removal
            "/var/log/fontconfig.log",
            # home directories of system accounts
            "/var/lib/debian-security-support/",    # #749317
            "/var/lib/gozerbot/",
            "/var/lib/nagios/",         # nagios* (#668756)
            "/var/lib/onioncat/",       # onioncat
            "/var/lib/pkcs11proxyd/",   # caml-crush-server (#810703)
            "/var/lib/rbldns/",
            "/var/lib/sreview/",        # sreview (#905500)
            "/var/spool/powerdns/",     # pdns-server (#531134), pdns-recursor (#531135)
            # work around broken symlinks
            "/etc/modules-load.d/modules.conf",  # -> ../modules (target obsoleted by modules-load.d)
            "/etc/sysctl.d/99-sysctl.conf",  # -> ../sysctl.conf (target obsoleted by sysctl.d)
            "/usr/lib/python2.6/dist-packages/python-support.pth",  # 635493 and #385775
            "/usr/lib/python2.7/dist-packages/python-support.pth",
            "/usr/share/texmf/ls-R",  # -> /var/lib/texmf/ls-R-TEXMFMAIN (link owned by tex-common, target created with mktexlsr from texlive-binaries)
            # work around #316521 dpkg: incomplete cleanup of empty directories
            "/etc/apache2/",
            "/etc/apache2/conf.d/",
            "/etc/clamav/",
            "/etc/cron.d/",
            "/etc/lighttpd/",
            "/etc/lighttpd/conf-available/",
            "/etc/modprobe.d/",
            "/etc/nagios-plugins/config/",
            "/etc/network/",
            "/etc/php/",
            "/etc/php/7.0/",
            "/etc/php/7.0/apache2/",
            "/etc/php/7.0/apache2/conf.d/",
            "/etc/php/7.0/cli/",
            "/etc/php/7.0/cli/conf.d/",
            "/etc/php/7.0/mods-available/",
            "/etc/php/7.0/phpdbg/",
            "/etc/php/7.0/phpdbg/conf.d/",
            "/etc/php5/",
            "/etc/php5/conf.d/",
            "/etc/php5/mods-available/",
            "/etc/sgml/",
            "/etc/ssl/",
            "/etc/ssl/certs/",
            "/etc/ssl/private/",
            "/etc/xml/",
            "/usr/share/dh-python/",
            "/usr/share/dh-python/dhpython/",
            "/usr/share/dh-python/dhpython/build/",
            "/usr/share/python3/",
            "/usr/share/python3/debpython/",
            "/var/lib/apache2/",
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
            "/etc/apt/trusted.gpg.d/.*.gpg~",
            "/var/lib/apt/lists/.*",
            "/var/lib/dpkg/alternatives/.*",
            "/var/lib/dpkg/triggers/.*",
            "/var/lib/insserv/run.*.log",
            "/var/lib/ucf/.*",
            "/var/lib/update-rc.d/.*",
            # application data
            "/srv/.*",  # 848186
            "/var/lib/citadel/(data/.*)?",
            "/var/lib/mercurial-server/.*",
            "/var/lib/onak/.*",
            "/var/lib/openvswitch/(pki/.*)?",
            "/var/lib/vmm/(./.*)?",  # 682184
            "/var/log/exim/.*",
            "/var/log/exim4/.*",
            "/var/spool/exim/.*",
            "/var/spool/exim4/.*",
            "/var/spool/news/.*",
            "/var/spool/squid/(../.*)?",
            "/var/www/.*",
            # HACKS
            ":/lib/modules/([^/]*/(modules.*)?)?",
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
    for i in reversed(range(counter)):
        if i in on_panic_hooks:
            on_panic_hooks[i]()
    logging.error("piuparts run ends.")
    sys.exit(exit)


def indent_string(str):
    """Indent all lines in a string with two spaces and return result."""
    return "\n".join(["  " + line for line in str.split("\n")])


def command2string(command):
    """Quote s.t. copy+paste from the logfile gives a runnable command in the shell."""
    return " ".join([pipes.quote(arg) for arg in command])


def unqualify(packages):
    if packages:
        return [p.split("=", 1)[0].strip() for p in packages]
    return packages


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

    assert isinstance(command, type([]))
    logging.debug("Starting command: %s" % command)
    env = os.environ.copy()
    for var in ["LANG",
            "LANGUAGE",
            "LC_CTYPE",
            "LC_NUMERIC",
            "LC_TIME",
            "LC_COLLATE",
            "LC_MONETARY",
            "LC_MESSAGES",
            "LC_PAPER",
            "LC_NAME",
            "LC_ADDRESS",
            "LC_TELEPHONE",
            "LC_MEASUREMENT",
            "LC_IDENTIFICATION",
            "LC_ALL"]:
        if var in env:
            del env[var]
    env["PIUPARTS_OBJECTS"] = ' '.join(str(vobject) for vobject in settings.testobjects)
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


def create_file(filename, contents):
    """Create a new file with the desired name and contents."""
    try:
        with open(filename, "w") as f:
            f.write(contents)
    except IOError as detail:
        logging.error("Couldn't create file %s: %s" % (filename, detail))
        panic()


def readlines_file(filename):
    with open(filename, "r") as f:
        return f.readlines()


def remove_files(filenames):
    """Remove some files."""
    for filename in filenames:
        logging.debug("Removing %s" % filename)
        try:
            os.remove(filename)
        except OSError as detail:
            logging.error("Couldn't remove %s: %s" % (filename, detail))
            panic()


def make_metapackage(name, depends, conflicts, arch='all'):
    """Return the path to a .deb created just for satisfying dependencies

    Caller is responsible for removing the temporary directory containing the
    .deb when finished.
    """
    # Inspired by pbuilder's pbuilder-satisfydepends-aptitude

    tmpdir = tempfile.mkdtemp(dir=settings.tmpdir)
    panic_handler_id = do_on_panic(lambda: shutil.rmtree(tmpdir))
    create_file(os.path.join(tmpdir, ".piuparts.tmpdir"), "metapackage creation")
    old_umask = os.umask(0)
    os.makedirs(os.path.join(tmpdir, name, 'DEBIAN'), mode=0o755)
    os.umask(old_umask)
    control = deb822.Deb822()
    control['Package'] = name
    control['Version'] = '0.invalid.0'
    control['Architecture'] = arch
    control['Maintainer'] = ('piuparts developers team '
                             '<piuparts-devel@alioth-lists.debian.net>')
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

    logging.debug("metapackage:\n" + indent_string(control.dump()))
    run(['dpkg-deb', '-b', '-Zgzip', '--nocheck', os.path.join(tmpdir, name)])
    dont_do_on_panic(panic_handler_id)
    return os.path.join(tmpdir, name + '.deb')


def split_path(pathname):
    parts = []
    while pathname:
        (head, tail) = os.path.split(pathname)
        # print "split '%s' => '%s' + '%s'" % (pathname, head, tail)
        if tail:
            parts.append(tail)
        elif not head:
            break
        elif head == pathname:
            parts.append(head)
            break
        pathname = head
    return parts


def canonicalize_path(root, pathname, report_links=False):
    """Canonicalize a path name, simulating chroot at 'root'.

    When resolving the symlink, pretend (similar to chroot) that
    'root' is the root of the filesystem.  Also resolve '..' and
    '.' components.  This should not escape the chroot below
    'root', but for security concerns, use chroot and have the
    kernel resolve symlinks instead.

    Returns the final canonical path or a list of (path, target) tuples,
    one for each symlink encountered.

    """
    # print "\nCANONICALIZE %s %s" % (root, pathname)
    links = []
    seen = []
    parts = split_path(pathname)
    # print "PARTS ", list(reversed(parts))
    path = "/"
    while parts:
        tag = "\n".join(parts + [path])
        # print "TEST '%s' + " % path, list(reversed(parts))
        if tag in seen or len(seen) > 1024:
            fullpath = os.path.join(path, *reversed(parts))
            # print "LOOP %s" % fullpath
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
            # print "LINK to '%s'" % target
            links.append((newpath, target))
            if os.path.isabs(target):
                path = "/"
            parts.extend(split_path(target))
        else:
            path = newpath
    # print "FINAL '%s'" % path
    if report_links:
        return links
    return path


def is_broken_symlink(root, dirpath, filename):
    """Is symlink dirpath+filename broken?"""

    if dirpath[:len(root)] == root:
        dirpath = dirpath[len(root):]
    pathname = canonicalize_path(root, os.path.join(dirpath, filename))
    pathname = os.path.join(root, pathname[1:])

    # The symlink chain, if any, has now been resolved. Does the target
    # exist?
    # print "EXISTS ", pathname, os.path.exists(pathname)
    return not os.path.exists(pathname)


FileInfo = namedtuple('FileInfo', ['st', 'target', 'user', 'group'])

class Chroot:

    """A chroot for testing things in."""

    def __init__(self):
        self.name = None
        self.bootstrapped = False
        self.mounts = []
        self.initial_selections = None
        self.avail_md5_history = []

    def create_temp_dir(self):
        """Create a temporary directory for the chroot."""
        self.name = tempfile.mkdtemp(dir=settings.tmpdir)
        create_file(os.path.join(self.name, ".piuparts.tmpdir"), "chroot")
        os.chmod(self.name, 0o755)
        logging.debug("Created temporary directory %s" % self.name)

    def create(self, temp_tgz=None):
        """Create a chroot according to user's wishes."""
        self.panic_handler_id = do_on_panic(self.remove)
        if not settings.schroot and not settings.docker_image:
            self.create_temp_dir()

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
        elif settings.docker_image:
            self.setup_from_docker(settings.docker_image)
        else:
            self.setup_minimal_chroot()

        if not settings.schroot and not settings.docker_image:
            self.mount_proc()
        self.configure_chroot()

        # Copy scripts dirs into the chroot, merging all dirs together,
        # later files overwriting earlier ones.
        if settings.scriptsdirs:
            self.mkdir_p("tmp/scripts/")
            dest = self.relative("tmp/scripts/")
            for sdir in settings.scriptsdirs:
                logging.debug("Copying scriptsdir %s to %s" % (sdir, dest))
                for sfile in os.listdir(sdir):
                    if (sfile.startswith("post_") or sfile.startswith("pre_") or sfile.startswith("is_testable_")) \
                            and not ".dpkg-" in sfile \
                            and os.path.isfile(os.path.join(sdir, sfile)):
                        shutil.copy(os.path.join(sdir, sfile), dest)

        # Run custom scripts after chroot has been unpacked/debootstrapped
        # Useful for adjusting apt configuration e.g. for internal mirror usage
        self.run_scripts("post_chroot_unpack")

        self.run(["apt-get", "update"])
        if settings.basetgz or settings.docker_image or settings.schroot or settings.existing_chroot:
            self.run(["apt-get", "-yf", "dist-upgrade"])
        self.minimize()
        self.remember_available_md5()

        # Run custom scripts after creating the chroot.
        self.run_scripts("post_setup")

        self.install_packages_by_name(settings.fake_essential_packages, with_scripts=False)

        if settings.savetgz and not temp_tgz:
            self.pack_into_tgz(settings.savetgz)

    def remove(self):
        """Remove a chroot and all its contents."""
        if not settings.keep_env and os.path.exists(self.name):
            self.terminate_running_processes()
            self.unmount_all()
            if settings.lvm_volume:
                logging.debug('Unmounting and removing LVM snapshot %s' % self.lvm_snapshot_name)
                run(['umount', self.name])
                run(['lvremove', '-f', self.lvm_snapshot])
            if settings.schroot:
                logging.debug("Terminate schroot session '%s'" % self.name)
                run(['schroot', '--end-session', '--chroot', "session:" + self.schroot_session])
            if settings.docker_image:
                logging.debug("Destroy docker container '%s'" % self.docker_container)
                run(['docker', 'rm', '-f', self.docker_container])
            if not settings.schroot and not settings.docker_image:
                run(['rm', '-rf', '--one-file-system', self.name])
                if os.path.exists(self.name):
                    create_file(os.path.join(self.name, ".piuparts.tmpdir"), "removal failed")
                logging.debug("Removed directory tree at %s" % self.name)
        elif settings.keep_env:
            if settings.schroot:
                logging.debug("Keeping schroot session %s at %s" % (self.schroot_session, self.name))
            elif settings.docker_image:
                logging.debug("Keeping container %s" % self.docker_container)
            else:
                logging.debug("Keeping directory tree at %s" % self.name)
        dont_do_on_panic(self.panic_handler_id)

    def was_bootstrapped(self):
        return self.bootstrapped

    def create_temp_tgz_file(self):
        """Return the path to a file to be used as a temporary tgz file"""
        # Yes, create_temp_file() would work just as well, but putting it in
        # the interface for Chroot allows the VirtServ hack to work.
        (fd, temp_tgz) = create_temp_file()
        os.close(fd)
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

        (fd, tmpfile) = tempfile.mkstemp(dir=os.path.dirname(result))
        os.close(fd)
        cleanup_tmpfile = lambda: os.remove(tmpfile)
        panic_handler_id = do_on_panic(cleanup_tmpfile)

        run(['tar', '-czf', tmpfile, '--one-file-system', '--exclude', 'tmp/scripts', '-C', self.name, './'])

        os.chmod(tmpfile, 0o644)
        os.rename(tmpfile, result)
        dont_do_on_panic(panic_handler_id)

    def unpack_from_tgz(self, tarball):
        """Unpack a tarball to a chroot."""
        logging.debug("Unpacking %s into %s" % (tarball, self.name))
        prefix = []
        if settings.eatmydata and os.path.isfile('/usr/bin/eatmydata'):
            prefix.append('eatmydata')
        run(prefix + ["tar", "-C", self.name, "-zxf", tarball])

    def setup_from_schroot(self, schroot):
        self.schroot_session = schroot.split(":", 1)[-1] + "-" + str(uuid.uuid1()) + "-piuparts"
        run(['schroot', '--begin-session', '--chroot', schroot, '--session-name', self.schroot_session])
        ret_code, output = run(['schroot', '--chroot', "session:" + self.schroot_session, '--location'])
        self.name = output.strip()
        logging.info("New schroot session in '%s'" % self.name)

    @staticmethod
    def check_if_docker_storage_driver_is_supported():
        ret_code, output = run(['docker', 'info'])
        if 'overlay2' not in output:
            logging.error('Only overlay2 storage driver is supported')
            panic()

    def setup_from_docker(self, docker_image):
        self.check_if_docker_storage_driver_is_supported()
        ret_code, output = run(['docker', 'run', '-d', '-it', docker_image, 'bash'])
        if ret_code != 0:
            logging.error("Couldn't start the container from '%s'" % docker_image)
            panic()
        self.docker_container = output.strip()
        ret_code, output = run(['docker', 'inspect', self.docker_container])
        container_data = json.loads(output)[0]
        self.name = container_data['GraphDriver']['Data']['MergedDir']
        logging.info("New container created '%s'" % self.docker_container)

    def setup_from_lvm(self, lvm_volume):
        """Create a chroot by creating an LVM snapshot."""
        self.lvm_base = os.path.dirname(lvm_volume)
        self.lvm_vol_name = os.path.basename(lvm_volume)
        self.lvm_snapshot_name = self.lvm_vol_name + "-" + str(uuid.uuid1())
        self.lvm_snapshot = os.path.join(self.lvm_base, self.lvm_snapshot_name)

        logging.debug("Creating LVM snapshot %s from %s" % (self.lvm_snapshot, lvm_volume))
        run(['lvcreate', '-n', self.lvm_snapshot, '-s', lvm_volume, '-L', settings.lvm_snapshot_size])
        logging.info("Mounting LVM snapshot to %s" % self.name)
        run(['mount', self.lvm_snapshot, self.name])

    def setup_from_dir(self, dirname):
        """Create chroot from an existing one."""
        # if on same device, make hard link
        cmd = ["cp"]
        if settings.hard_link and os.stat(dirname).st_dev == os.stat(self.name).st_dev:
            cmd += ["-al"]
            logging.debug("Hard linking %s to %s" % (dirname, self.name))
        else:
            cmd += ["-ax"]
            logging.debug("Copying %s into %s" % (dirname, self.name))
        for name in os.listdir(dirname):
            src = os.path.join(dirname, name)
            dst = os.path.join(self.name, name)
            run(cmd + [src, dst])

    def interactive_shell(self):
        logging.info("Entering interactive shell in %s" % self.name)
        env = os.environ.copy()
        env['debian_chroot'] = "piuparts:%s" % self.name
        try:
            subprocess.call(['chroot', self.name, 'bash', '-l'], env=env)
        except:
            pass

    def run(self, command, ignore_errors=False):
        prefix = []
        if settings.eatmydata and os.path.isfile(os.path.join(self.name,
                                                 'usr/bin/eatmydata')):
            prefix.append('eatmydata')
        if settings.schroot:
            return run(
                ["schroot", "--preserve-environment", "--run-session", "--chroot", "session:" +
                    self.schroot_session, "--directory", "/", "-u", "root", "--"] + prefix + command,
                   ignore_errors=ignore_errors, timeout=settings.max_command_runtime)
        elif settings.docker_image:
            return run(
                ['docker', 'exec', self.docker_container,] + prefix + command,
                ignore_errors=ignore_errors,
                timeout=settings.max_command_runtime,
            )
        else:
            return run(["chroot", self.name] + prefix + command,
                       ignore_errors=ignore_errors, timeout=settings.max_command_runtime)

    def mkdir_p(self, path):
        fullpath = self.relative(path)
        if not os.path.isdir(fullpath):
            os.makedirs(fullpath)

    def create_apt_sources(self, distro):
        """Create an /etc/apt/sources.list with a given distro."""
        lines = []
        lines.extend(settings.distro_config.get_deb_lines(
            distro, settings.debian_mirrors[0][1]))
        for mirror, components in settings.debian_mirrors[1:]:
            lines.append("deb %s %s %s" %
                         (mirror, distro, " ".join(components)))
        for repo in settings.extra_repos:
            lines.append(repo)
        create_file(self.relative("etc/apt/sources.list"),
                    "\n".join(lines) + "\n")
        logging.debug("sources.list:\n" + indent_string("\n".join(lines)))

    def enable_testdebs_repo(self, update=True):
        if settings.testdebs_repo:
            if settings.testdebs_repo.startswith("deb"):
                debline = settings.testdebs_repo
            elif settings.testdebs_repo.startswith("/"):
                debline = "deb [ trusted=yes ] file://%s ./" % settings.testdebs_repo
            else:
                debline = "deb [ trusted=yes ] %s ./" % settings.testdebs_repo
            logging.debug("enabling testdebs repository '%s'" % debline)
            create_file(self.relative("etc/apt/sources.list.d/piuparts-testdebs-repo.list"), debline + "\n")
            if update:
                self.run(["apt-get", "update"])

    def disable_testdebs_repo(self):
        if settings.testdebs_repo:
            logging.debug("disabling testdebs repository")
            remove_files([self.relative("etc/apt/sources.list.d/piuparts-testdebs-repo.list")])

    def create_apt_conf(self):
        """Create /etc/apt/apt.conf.d/piuparts inside the chroot."""
        lines = ['APT::Get::Assume-Yes "yes";\n']
        lines.append('APT::Install-Recommends "%d";\n' % int(settings.install_recommends))
        lines.append('APT::Install-Suggests "%d";\n' % int(settings.install_suggests))
        lines.append('APT::Get::AllowUnauthenticated "%s";\n' % settings.apt_unauthenticated)
        lines.append('Acquire::PDiffs "false";\n')
        if settings.no_check_valid_until:
            lines.append('Acquire::Check-Valid-Until "false";\n')
        if settings.proxy:
            proxy = settings.proxy
        elif "http_proxy" in os.environ:
            proxy = os.environ["http_proxy"]
        else:
            proxy = None
            pat = re.compile(r"^Acquire::http::Proxy\s+\"([^\"]+)\"", re.I)
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
            self.mkdir_p("etc/dpkg/dpkg.cfg.d")
            create_file(self.relative("etc/dpkg/dpkg.cfg.d/piuparts"),
                        "".join(lines))

    def create_policy_rc_d(self):
        """Create a policy-rc.d that prevents daemons from running."""
        full_name = self.relative("usr/sbin/policy-rc.d")
        policy = "#!/bin/sh\n"
        if settings.allow_database:
            policy += 'test "$1" = "mysql" && exit 0\n'
            policy += 'test "$1" = "postgresql" && exit 0\n'
            policy += 'test "$1" = "postgresql-8.3" && exit 0\n'
            policy += 'test "$1" = "firebird2.5-super" && exit 0\n'
            policy += 'test "$1" = "firebird3.0" && exit 0\n'
        policy += "exit 101\n"
        create_file(full_name, policy)
        os.chmod(full_name, 0o755)
        logging.debug("Created policy-rc.d and chmodded it.")

    def create_resolv_conf(self):
        """Update resolv.conf based on the current configuration in the host system. Strip comments and whitespace."""
        if settings.docker_image:
            # Docker takes care of this
            return
        full_name = self.relative("etc/resolv.conf")
        resolvconf = ""
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if line.strip() and not line.startswith(('#', ';')):
                    resolvconf += line.strip() + '\n'
        create_file(full_name, resolvconf)
        os.chmod(full_name, 0o644)
        logging.debug("Created resolv.conf.")

    def setup_minimal_chroot(self):
        """Set up a minimal Debian system in a chroot."""
        logging.debug("Setting up minimal chroot for %s at %s." %
                      (settings.debian_distros[0], self.name))
        prefix = []
        if settings.eatmydata and os.path.isfile('/usr/bin/eatmydata'):
            prefix.append('eatmydata')
        options = []
        if settings.do_not_verify_signatures:
            logging.info("Warning: not using --keyring option when running debootstrap!")
        else:
            options.append("--keyring=%s" % settings.keyring)
        if settings.eatmydata:
            options.append('--include=eatmydata')
        options.append('--no-merged-usr')
        options.append('--components=%s' % ','.join(settings.debian_mirrors[0][1]))
        if settings.arch:
            options.append('--arch=%s' % settings.arch)
        run(prefix + ["debootstrap", "--variant=minbase"] + options +
            [settings.debian_distros[0], self.name, settings.distro_config.get_mirror(settings.debian_distros[0])])
        self.bootstrapped = True

    def minimize(self):
        """Minimize a chroot by removing (almost all) unnecessary packages"""
        if settings.skip_minimize or not settings.minimize:
            return
        self.run(["apt-get", "install", "debfoster"])
        debfoster_command = ["debfoster"] + settings.debfoster_options
        if settings.eatmydata:
            debfoster_command.append("eatmydata")
        self.run(debfoster_command)
        remove_files([self.relative("var/lib/debfoster/keepers")])
        self.run(["dpkg", "--purge", "debfoster"])

    def configure_chroot(self):
        """Configure a chroot according to current settings"""
        os.environ["PIUPARTS_DISTRIBUTION"] = settings.distro_config.get_distribution(settings.debian_distros[0])
        if not settings.keep_sources_list:
            self.create_apt_sources(settings.debian_distros[0])
        self.create_apt_conf()
        self.create_dpkg_conf()
        self.create_policy_rc_d()
        self.create_resolv_conf()
        for bindmount in settings.bindmounts:
            self.mount(bindmount, bindmount, opts="bind")
        if not os.path.exists(self.name + '/dev/null'):
            run(['mknod', '-m' ,'666', self.name + '/dev/null', 'c', '1', '3'])

    def remember_available_md5(self):
        """Keep a history of 'apt-cache dumpavail | md5sum' after initial
           setup and each dist-upgrade step to notice outdated reference
           chroot metadata"""
        errorcode, avail_md5 = self.run(["sh", "-c", "apt-cache dumpavail | md5sum"])
        self.avail_md5_history.append(avail_md5.split()[0])

    def remember_initial_selections(self):
        """Remember initial selections to easily recognize mismatching chroot metadata"""
        self.initial_selections = self.get_selections()

    def upgrade_to_distros(self, distros, packages, apt_get_upgrade=False):
        """Upgrade a chroot installation to each successive distro."""
        for distro in distros:
            logging.debug("Upgrading %s to %s" % (self.name, distro))
            os.environ["PIUPARTS_DISTRIBUTION_NEXT"] = settings.distro_config.get_distribution(distro)
            self.create_apt_sources(distro)
            # Run custom scripts before upgrade
            self.run_scripts("pre_distupgrade")
            self.run(["apt-get", "update"])
            if apt_get_upgrade:
                self.run(["apt-get", "-y", "upgrade"])
            self.run(["apt-get", "-yf", "dist-upgrade"])
            self.remember_available_md5()
            os.environ["PIUPARTS_DISTRIBUTION_PREV"] = os.environ["PIUPARTS_DISTRIBUTION"]
            os.environ["PIUPARTS_DISTRIBUTION"] = settings.distro_config.get_distribution(distro)
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
            (status, output) = self.run(["apt-cache", "show", "--no-all-versions", name],
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
            except IOError as detail:
                logging.error("Error copying %s to %s: %s" %
                              (source_name, target_name, detail))
                panic()

    def list_installed_files(self, pre_info, post_info):
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

    def is_installed(self, packages):
        if not packages:
            return True
        retcode, output = self.run(["dpkg-query", "-f", "${Package} ${Status}\n", "-W"] + packages, ignore_errors=True)
        if retcode != 0:
            return False
        installed = True
        for line in output.splitlines():
            pkg, desired, whatever, status = line.split()
            if status != 'installed':
                logging.error("Installation of %s failed", pkg)
                installed = False
        return installed

    def install_packages(self, package_files, packages, with_scripts=True, reinstall=False):
        if package_files:
            self.install_package_files(package_files, packages, with_scripts=with_scripts)
        else:
            self.install_packages_by_name(packages, with_scripts=with_scripts, reinstall=reinstall)

    def install_package_files(self, package_files, packages=None, with_scripts=False):
        if packages and settings.testdebs_repo:
            self.install_packages_by_name(packages, with_scripts=with_scripts)
            return
        if package_files:
            # Check whether apt-get can install debs (supported since apt 1.1)
            #
            # If it can, this is preferable to the traditional
            #   `dpkg -i foo.deb && apt-get -yf install`
            # approach since 'apt-get -yf install' can 'resolve' dependency
            # problems by removing the package we are trying to install
            (status, output) = self.run(["dpkg-query", "-f", "${Version}\n", "-W", "apt"], ignore_errors=True)
            apt_can_install_debs = apt_pkg.version_compare(output.strip(), "1.1") >= 0

            # This must look like a local path so that apt-get can
            # distinguish it from a 'package/suite' request.
            self.copy_files(package_files, "tmp")
            tmp_files = [os.path.join("./tmp", os.path.basename(a)) for a in package_files]

            if with_scripts:
                self.run_scripts("pre_install")

            if apt_can_install_debs:
                # --allow-downgrades is also required in order to permit
                # installing a deb with the same version as that already
                # installed
                apt_get_install = ["apt-get", "-y", "--allow-downgrades"]
            else:
                apt_get_install = ["apt-get", "-yf"]

            apt_get_install.extend(settings.distro_config.get_target_flags(
                os.environ["PIUPARTS_DISTRIBUTION"]))
            apt_get_install.append("install")

            if settings.list_installed_files:
                pre_info = self.get_tree_meta_data()

            if apt_can_install_debs:
                self.run(apt_get_install + tmp_files)
            else:
                (ret, out) = self.run(["dpkg", "-i"] + tmp_files, ignore_errors=True)
                if ret != 0:
                    if "dependency problems - leaving unconfigured" in out:
                        pass
                    else:
                        logging.error("Installation failed")
                        panic()

                if settings.list_installed_files:
                    self.list_installed_files(pre_info, self.get_tree_meta_data())

                self.run(apt_get_install)

            if settings.list_installed_files:
                self.list_installed_files(pre_info, self.get_tree_meta_data())

            if not self.is_installed(unqualify(packages)):
                logging.error("Could not install %s.", " ".join(unqualify(packages)))
                panic()

            logging.info("Installation of %s ok", tmp_files)

            if with_scripts:
                self.run_scripts("post_install")

            remove_files([self.relative(name) for name in tmp_files])

    def install_packages_by_name(self, packages, with_scripts=True, reinstall=False):
        if packages:
            if with_scripts:
                self.run_scripts("pre_install")

            self.run(["apt-cache", "policy"])
            self.run(["apt-cache", "policy"] + unqualify(packages))

            if settings.list_installed_files:
                pre_info = self.get_tree_meta_data()

            target_flags = settings.distro_config.get_target_flags(os.environ["PIUPARTS_DISTRIBUTION"])
            self.apt_get_install(to_install=packages, flags=target_flags, reinstall=reinstall)

            if settings.list_installed_files:
                self.list_installed_files(pre_info, self.get_tree_meta_data())

            if with_scripts:
                self.run_scripts("post_install")

    def apt_get_install(self, to_install=[], to_remove=[], to_purge=[], flags=[], reinstall=False):
        command = ["apt-get", "-y"] + flags + ["install"]
        if reinstall:
            command.append("--reinstall")
        command.extend(to_install)
        command.extend(["%s-" % x for x in unqualify(to_remove)])
        command.extend(["%s_" % x for x in unqualify(to_purge)])
        self.run(command)

    def get_selections(self):
        """Get current package selections in a chroot."""
        # "${Status}" emits three columns, e.g. "install ok installed"
        # "${binary:Package}" requires a multi-arch dpkg, so fall back to "${Package}" on older versions
        (status, output) = self.run(["dpkg-query", "-W", "-f", "${Status}\\t${binary:Package}\\t${Package}\\t${Version}\\n"])
        vdict = {}
        for line in [line for line in output.split("\n") if line.strip()]:
            token = line.split()
            status = token[0]
            name = token[3]
            if status == "install":
                version = token[-1]
            else:
                version = None
            vdict[name] = (status, version)
        return vdict

    def get_diversions(self):
        """Get current dpkg-divert --list in a chroot."""
        if not settings.check_broken_diversions:
            return
        (status, output) = self.run(["dpkg-divert", "--list"])
        return output.split("\n")

    def get_modified_diversions(self, pre_install_diversions, post_install_diversions=None):
        """Check that diversions in chroot are identical (though potentially reordered)."""
        if post_install_diversions is None:
            post_install_diversions = self.get_diversions()
        removed = [ln for ln in pre_install_diversions if not ln in post_install_diversions]
        added = [ln for ln in post_install_diversions if not ln in pre_install_diversions]
        return (removed, added)

    def check_debsums(self):
        (status, output) = run(["debsums", "--root", self.name, "-ac", "--ignore-obsolete"], ignore_errors=True)
        if status != 0:
            logging.error("FAIL: debsums reports modifications inside the chroot:\n%s" %
                          indent_string(output.replace(self.name, "")))
            if not settings.warn_on_debsums_errors:
                panic()

    def check_adequate(self, packages):
        """Run adequate and categorize output according to our needs. """
        packages = unqualify([p for p in packages if not p.endswith("=None")])
        if packages and settings.adequate and os.path.isfile('/usr/bin/adequate'):
            (status, output) = run(["dpkg-query", "-f", "${Version}\n", "-W", "adequate"], ignore_errors=True)
            logging.info("Running adequate version %s now." % output.strip())
            adequate_tags = [
                'bin-or-sbin-binary-requires-usr-lib-library',
                    'broken-binfmt-detector',
                    'broken-binfmt-interpreter',
                    'incompatible-licenses',
                    'ldd-failure',
                    'library-not-found',
                    'missing-alternative',
                    'missing-copyright-file',
                    'missing-pkgconfig-dependency',
                    'missing-symbol-version-information',
                    'program-name-collision',
                    'py-file-not-bytecompiled',
                    'pyshared-file-not-bytecompiled',
                    'symbol-size-mismatch',
                    'undefined-symbol',
            ]
            boring_tags = [
                'obsolete-conffile',
                    'broken-symlink',
            ]
            ignored_tags = []
            (status, output) = run(["adequate", "--root", self.name] + packages, ignore_errors=True)
            for tag in ignored_tags:
                # ignore some tags
                _regex = '^[^:]+: ' + tag + ' .*\n'
                output = re.compile(_regex, re.MULTILINE).sub('', output)
            if output:
                inadequate_results = ''
                boring_results = ''
                for tag in adequate_tags:
                    if ' ' + tag + ' ' in output:
                        inadequate_results += ' ' + tag + ' '
                for tag in boring_tags:
                    if ' ' + tag + ' ' in output:
                        boring_results += ' ' + tag + ' '
                if settings.warn_if_inadequate:
                    error_code = 'WARN'
                else:
                    error_code = 'FAIL'
                logging.error("%s: Inadequate results from running adequate!\n%s" %
                              (error_code, indent_string(output.replace(self.name, ""))))
                if inadequate_results:
                    logging.error("%s: Running adequate resulted in inadequate tags found: %s" % (error_code, inadequate_results))
                if boring_results:
                    logging.error("%s: Running adequate resulted in less interesting tags found: %s" % (error_code, boring_results))
                if not boring_results and not inadequate_results:
                    logging.error("%s: Found unknown tags running adequate." % error_code)
                if status != 0:
                    logging.error("%s: Exit code from adequate was %s!" % (error_code, status))
                if not settings.warn_if_inadequate:
                    panic()

    def list_paths_with_symlinks(self):
        file_owners = self.get_files_owned_by_packages()
        bad = []
        overwrites = False
        usrmerge = set()
        for f in sorted(file_owners.keys()):
            dn, fn = os.path.split(f)
            dc = canonicalize_path(self.name, dn)
            if dn != dc:
                # Allow the /usr merge to have taken place. For example, if
                # f (the file recorded in the dpkg database) is /bin/cat,
                # then dn is /bin, and it's OK for /bin to have become a
                # symlink to /usr/bin. Similarly /sbin, /lib, /libQUAL
                # (/lib32 etc.) or any subdirectory of /lib or /libQUAL
                # can be /usr-merged.
                if dc == '/usr' + dn and (dn in ('/bin', '/sbin') or
                                          dn.startswith('/lib')):
                    # Only report each directory once
                    if dn not in usrmerge:
                        usrmerge.add(dn)
                        logging.info('%s converted to %s by /usr merge', dn, dc)

                    continue

                fc = os.path.join(dc, fn)
                of = ", ".join(file_owners[f])
                if fc in file_owners:
                    overwrites = True
                    ofc = ", ".join(file_owners[fc])
                else:
                    ofc = "?"
                bad.append("%s (%s) != %s (%s)" % (f, of, fc, ofc))
                for (link, target) in canonicalize_path(self.name, dn, report_links=True):
                    bad.append("  %s -> %s" % (link, target))
        if bad:
            if overwrites:
                msg = "FAIL: silently overwrites files via directory symlinks:\n"
            else:
                msg = "installs objects over existing directory symlinks:\n"
            msg += indent_string("\n".join(bad))
            if not settings.warn_on_install_over_symlink:
                logging.error(msg)
                panic()
            else:
                logging.info(msg)

    def remove_packages(self, packages, ignore_errors=False):
        """Remove packages in a chroot."""
        if packages:
            self.run(["apt-get", "remove"] + unqualify(packages), ignore_errors=ignore_errors)

    def purge_packages(self, packages, ignore_errors=False):
        """Purge packages in a chroot."""
        if packages:
            self.run(["dpkg", "--purge"] + unqualify(packages), ignore_errors=ignore_errors)

    def restore_selections(self, reference_chroot_state, packages_qualified):
        """Restore package selections in a chroot to the state in
        'reference_chroot_state'."""

        if reference_chroot_state["avail_md5"] != self.avail_md5_history:
            logging.warn("History of available packages does not match - reference chroot may be outdated")
            logging.debug(" reference: %s" % " ".join(reference_chroot_state["avail_md5"]))
            logging.debug(" current  : %s" % " ".join(self.avail_md5_history))

        selections = reference_chroot_state["selections"]
        packages = unqualify(packages_qualified)

        changes = diff_selections(self, selections)
        deps = {}
        nondeps = {}
        for name, state_version in changes.iteritems():
            if name in packages:
                nondeps[name] = state_version
            else:
                deps[name] = state_version

        deps_to_remove = [name for name, (state, version) in deps.iteritems()
                          if state == "remove"]
        deps_to_purge = [name for name, (state, version) in deps.iteritems()
                         if state == "purge"]
        nondeps_to_remove = [name for name, (state, version) in nondeps.iteritems()
                             if state == "remove"]
        nondeps_to_purge = [name for name, (state, version) in nondeps.iteritems()
                            if state == "purge"]
        all_to_remove = deps_to_remove + deps_to_purge + nondeps_to_remove + nondeps_to_purge
        all_to_install = [(name, version) for name, (state, version) in deps.iteritems()
                          if state == "install"]
        all_to_install += [(name, version) for name, (state, version) in nondeps.iteritems()
                           if state == "install"]

        self.list_paths_with_symlinks()
        self.check_debsums()
        self.check_adequate(packages_qualified)

        # Run custom scripts before removing all packages.
        self.run_scripts("pre_remove")

        # First remove all packages (and reinstall missing ones).
        self.remove_packages(deps_to_remove)
        if all_to_install:
            version_qualified = [name for (name, version) in all_to_install
                                 if version is None]
            version_qualified += ["%s=%s" % (name, version) for (name, version) in all_to_install
                                  if version is not None]
            self.apt_get_install(to_remove=all_to_remove,
                                 to_install=version_qualified,
                                 flags=["--no-install-recommends", "--force-yes"])
        else:
            self.remove_packages(all_to_remove)

        # Run custom scripts after removing all packages.
        self.run_scripts("post_remove")

        if not settings.skip_cronfiles_test:
            cronfiles = self.check_if_cronfiles(packages)
            if cronfiles:
                self.check_output_cronfiles(cronfiles)

        if not settings.skip_logrotatefiles_test:
            logrotatefiles = self.check_if_logrotatefiles(packages)
            if logrotatefiles:
                installed = self.install_logrotate()
                self.check_output_logrotatefiles(logrotatefiles)
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

    def get_tree_meta_data(self):
        """Return the filesystem meta data for all objects in the chroot."""
        self.run(["apt-get", "clean"])
        logging.debug("Recording chroot state")
        root = self.relative(".")
        uidmap = {}
        with open(self.relative("etc/passwd"), "r") as passwd:
            for line in passwd:
                (usr, x, uid) = line.split(":")[0:3]
                uidmap[int(uid)] = usr
        gidmap = {}
        with open(self.relative("etc/group"), "r") as group:
            for line in group:
                (grp, x, gid) = line.split(":")[0:3]
                gidmap[int(gid)] = grp
        vdict = {}
        proc = os.path.join(root, "proc")
        devpts = os.path.join(root, "dev/pts")
        for dirpath, dirnames, filenames in os.walk(root):
            assert dirpath[:len(root)] == root
            if dirpath[:len(proc) + 1] in [proc, proc + "/"]:
                continue
            if dirpath[:len(devpts) + 1] in [devpts, devpts + "/"]:
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
                if st.st_uid in uidmap:
                    user = uidmap[st.st_uid]
                else:
                    user = "#%d" % st.st_uid
                if st.st_gid in gidmap:
                    group = gidmap[st.st_gid]
                else:
                    group = "#%d" % st.st_gid
                vdict[name[len(root):]] = FileInfo(st, target, user, group)
        return vdict

    def get_state_meta_data(self):
        chroot_state = {}
        chroot_state["initial_selections"] = self.initial_selections
        chroot_state["avail_md5"] = self.avail_md5_history
        chroot_state["tree"] = self.get_tree_meta_data()
        chroot_state["selections"] = self.get_selections()
        chroot_state["diversions"] = self.get_diversions()
        return chroot_state

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
                for line in readlines_file(os.path.join(vdir, basename)):
                    pathname = line.strip()
                    if pathname in vdict:
                        vdict[pathname].append(pkg)
                    else:
                        vdict[pathname] = [pkg]
        return vdict

    def check_for_no_processes(self, fail=None):
        """Check there are no processes running inside the chroot."""
        if settings.docker_image:
            (status, output) = run(["docker", "top", self.docker_container])
            count = len(output.strip().split("\n")) - 2 # header + bash launched on container creation
        else:
            (status, output) = run(["lsof", "-w", "+D", self.name], ignore_errors=True)
            count = len(output.split("\n")) - 1
        if count > 0:
            if fail is None:
                fail = not settings.allow_database
            logging.error("%s: Processes are running inside chroot:\n%s" %
                          ("FAIL" if fail else "WARN", indent_string(output)))
            if fail:
                self.terminate_running_processes()
                panic()

    def terminate_running_processes(self):
        """Terminate all processes running in the chroot."""
        if settings.docker_image:
            # Docker takes care of this
            return
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

    # If /selinux is present, assume that this is the only supported
    # location by libselinux. Otherwise use the new location.
    # /selinux was shipped by the libselinux package until wheezy.
    def selinuxfs_path(self):
        if os.path.isdir(self.relative('/selinux')):
            return '/selinux'
        else:
            return '/sys/fs/selinux'

    def mount(self, source, path, fstype=None, opts=None, no_mkdir=False):
        """Mount something into the chroot and remember it for unmount_all()."""
        path = canonicalize_path(self.name, path)
        if not no_mkdir:
            self.mkdir_p(path)
        fullpath = self.relative(path)
        command = ["mount"]
        if fstype is not None:
            command.extend(["-t", fstype])
        if opts is not None:
            command.extend(["-o", opts])
        command.extend([source, fullpath])
        run(command)
        self.mounts.append(fullpath)

    def unmount_all(self):
        """Unmount everything we mount()ed into the chroot."""

        # Workaround to unmount /proc/sys/fs/binfmt_misc which is mounted by
        # update-binfmts but never unmounted
        # This workaround can be removed once #847788 is fixed
        binfmt_misc = self.relative("/proc/sys/fs/binfmt_misc")
        if os.path.ismount(binfmt_misc):
            self.mounts.append(binfmt_misc)

        for mountpoint in reversed(self.mounts):
            run(["umount", mountpoint], ignore_errors=True)

    def mount_proc(self):
        """Mount /proc etc. inside chroot."""
        self.mount("proc", "/proc", fstype="proc")
        etcmtab = self.relative("etc/mtab")
        if not os.path.lexists(etcmtab):
            os.symlink("../proc/mounts", etcmtab)
        self.mount("devpts", "/dev/pts", fstype="devpts", opts="newinstance,noexec,nosuid,gid=5,mode=0620,ptmxmode=0666")
        dev_ptmx_rel_path = self.relative("dev/ptmx")
        if not os.path.islink(dev_ptmx_rel_path):
            if not os.path.exists(dev_ptmx_rel_path):
                os.mknod(dev_ptmx_rel_path, 0666 | stat.S_IFCHR, os.makedev(5, 2))
            self.mount(self.relative("dev/pts/ptmx"), "/dev/ptmx", opts="bind", no_mkdir=True)
        p = subprocess.Popen(["tty"], stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        current_tty = stdout.strip()
        if p.returncode == 0 and os.path.exists(current_tty):
            dev_console = self.relative("/dev/console")
            if not os.path.exists(dev_console):
                os.mknod(dev_console, 0600, os.makedev(5, 1))
            self.mount(current_tty, "/dev/console", opts="bind", no_mkdir=True)
        self.mount("tmpfs", "/dev/shm", fstype="tmpfs", opts="size=65536k")
        if selinux_enabled():
            self.mount("/sys/fs/selinux", self.selinuxfs_path(), opts="bind,ro")

    def is_ignored(self, pathname, info="PATH"):
        """Is a file (or dir or whatever) to be ignored?"""
        if pathname in settings.ignored_files:
            return True
        if ':' + pathname in settings.ignored_files:
            logging.info("IGNORED %s: %s" % (info, pathname))
            return True
        for pattern in settings.ignored_patterns:
            if pattern[0] == ':':
                verbose = True
                pattern = pattern[1:]
            else:
                verbose = False
            if re.search('^' + pattern + '$', pathname):
                if verbose:
                    logging.info("IGNORED %s: %s" % (info, pathname))
                return True
        return False

    def check_for_broken_symlinks(self, warn_only=None, file_owners={}):
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
                if ret and not self.is_ignored(name, info="broken symlink"):
                    try:
                        target = os.readlink(full_name)
                    except os.error:
                        target = "<unknown>"
                    entry = "%s -> %s" % (name, target)
                    if name in file_owners:
                        entry += " (%s)" % ", ".join(file_owners[name])
                    broken.append(entry)
        if broken:
            if settings.warn_broken_symlinks or warn_only:
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

        # FIXME! Does not work for M-A: same packages
        vdir = self.relative("var/lib/dpkg/info")
        vlist = []
        for p in packages:
            basename = p + ".list"

            if not os.path.exists(os.path.join(vdir, basename)):
                continue

            for line in readlines_file(os.path.join(vdir, basename)):
                pathname = line.strip()
                if pathname.startswith("/etc/cron."):
                    if os.path.isfile(self.relative(pathname.strip("/"))):
                        st = os.lstat(self.relative(pathname.strip("/")))
                        mode = st[stat.ST_MODE]
                        # XXX /etc/cron.d/ files are NOT executables
                        if (mode & stat.S_IEXEC):
                            vlist.append(pathname)
                            logging.info("Package " + p + " contains cron file: " + pathname)

        return vlist

    def check_output_cronfiles(self, list):
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

        # FIXME! Does not work for M-A: same packages
        vdir = self.relative("var/lib/dpkg/info")
        vlist = []
        for p in packages:
            basename = p + ".list"

            if not os.path.exists(os.path.join(vdir, basename)):
                continue

            for line in readlines_file(os.path.join(vdir, basename)):
                pathname = line.strip()
                if os.path.dirname(pathname) == "/etc/logrotate.d":
                    if os.path.isfile(self.relative(pathname.strip("/"))):
                        vlist.append(pathname)
                        logging.info("Package " + p + " contains logrotate file: " + pathname)

        return vlist

    def install_logrotate(self):
        """Install logrotate for check_output_logrotatefiles, and return the
        list of packages that were installed"""
        old_selections = self.get_selections()
        self.run(['apt-get', 'install', '-y', 'logrotate'])
        diff = diff_selections(self, old_selections)
        return diff.keys()

    def check_output_logrotatefiles(self, list):
        """Check if a given list of logrotatefiles has any output. Executes
        logrotate file as logrotate would do from cron (except for SHELL)"""
        failed = False
        for vfile in list:

            if not os.path.exists(self.relative(vfile.strip("/"))):
                continue

            (retval, output) = self.run(['/usr/sbin/logrotate', vfile])
            if output or retval != 0:
                failed = True
                logging.error("FAIL: Logrotate file %s exits with error or has output with package removed" % vfile)

        if failed:
            panic()

    def run_scripts(self, step, ignore_errors=False):
        """ Run custom scripts to given step post-install|remove|purge"""

        errorcodes = 0
        if not settings.scriptsdirs:
            return errorcodes
        logging.info("Running scripts " + step)
        basepath = self.relative("tmp/scripts/")
        if not os.path.exists(basepath):
            logging.error("Scripts directory %s does not exist" % basepath)
            panic()
        list_scripts = sorted(os.listdir(basepath))
        for vfile in list_scripts:
            if vfile.startswith(step):
                script = os.path.join("tmp/scripts", vfile)
                errorcode, output = self.run([script], ignore_errors=ignore_errors)
                errorcodes = errorcodes | errorcode
        return errorcodes


def selinux_enabled(enabled_test="/usr/sbin/selinuxenabled"):
    if os.access(enabled_test, os.X_OK):
        retval, output = run([enabled_test], ignore_errors=True)
        if retval == 0:
            return True
        else:
            return False


def objects_are_different(obj1, obj2):
    """Are filesystem objects different based on their meta data?"""
    if (obj1.st.st_mode != obj2.st.st_mode or
            obj1.user != obj2.user or
            obj1.group != obj2.group or
            obj1.target != obj2.target):
        return True
    if stat.S_ISREG(obj1.st.st_mode):
        return obj1.st.st_size != obj2.st.st_size  # or obj1.st.st_mtime != obj2.st.st_mtime
    return False


def format_object_attributes(obj):
    st = obj.st
    ft = ""
    if stat.S_ISDIR(st.st_mode):
        ft += "d"
    if stat.S_ISCHR(st.st_mode):
        ft += "c"
    if stat.S_ISBLK(st.st_mode):
        ft += "b"
    if stat.S_ISREG(st.st_mode):
        ft += "-"
    if stat.S_ISFIFO(st.st_mode):
        ft += "p"
    if stat.S_ISLNK(st.st_mode):
        ft += "l"
    if stat.S_ISSOCK(st.st_mode):
        ft += "s"
    res = "(%s, %s, %s %o, %d, %s)" % (
            obj.user,
            obj.group,
            ft,
            st.st_mode,
            st.st_size,
            obj.target)
    return res


def diff_meta_data(tree1, tree2, quiet=False):
    """Compare two dir trees and return list of new files (only in 'tree2'),
       removed files (only in 'tree1'), and modified files."""

    tree1 = tree1.copy()
    tree2 = tree2.copy()

    for name in settings.ignored_files:
        if name[0] == ':':
            verbose = not quiet
            name = name[1:]
        else:
            verbose = False
        if name in tree1:
            if verbose:
                logging.info("IGNORED PATH@1: %s" % name)
            del tree1[name]
        if name in tree2:
            if verbose:
                logging.info("IGNORED PATH@2: %s" % name)
            del tree2[name]

    for pattern in settings.ignored_patterns:
        if pattern[0] == ':':
            verbose = not quiet
            pattern = pattern[1:]
        else:
            verbose = False
        pat = re.compile(pattern)
        for name in tree1.keys():
            m = pat.search(name)
            if m:
                if verbose:
                    logging.info("IGNORED PATH@1: %s" % name)
                del tree1[name]
        for name in tree2.keys():
            m = pat.search(name)
            if m:
                if verbose:
                    logging.info("IGNORED PATH@2: %s" % name)
                del tree2[name]

    modified = []
    for name in tree1.keys()[:]:
        if name in tree2:
            if objects_are_different(tree1[name], tree2[name]):
                if not quiet:
                    logging.debug("Modified(user, group, mode, size, target): %s expected%s != found%s" %
                                  (name, format_object_attributes(tree1[name]), format_object_attributes(tree2[name])))
                modified.append((name, tree1[name]))
            del tree1[name]
            del tree2[name]

    removed = [x for x in tree1.iteritems()]
    new = [x for x in tree2.iteritems()]

    # fix for #586793
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
    meta_infos = sorted(meta_infos[:])
    vlist = []
    for name, obj in meta_infos:
        info = ""
        if obj.target is not None:
            info = " -> %s" % obj.target
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
    depfiles_names = [x[0] for x in depsfiles]
    for vfile in files[:]:
        if vfile[0] in depfiles_names:
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
    for name, (value, version) in current.iteritems():
        if name not in selections:
            changes[name] = ("purge", None)
        elif selections[name][0] != value and \
                selections[name][0] in ["purge", "install"]:
            changes[name] = selections[name]
    for name, (value, version) in selections.iteritems():
        if name not in current or \
            current[name][1] != version:
                changes[name] = selections[name]
    return changes


def get_package_names_from_package_files(package_files):
    """Return list of package names given list of package file names."""
    vlist = []
    for filename in package_files:
        (status, output) = run(["dpkg", "--info", filename])
        p = None
        v = None
        for line in [line.lstrip() for line in output.split("\n")]:
            if line.startswith("Package:"):
                p = line.split(":", 1)[1].strip()
            if line.startswith("Version:"):
                v = line.split(":", 1)[1].strip()
        if p is not None:
            if v is not None:
                vlist.append(p + "=" + v)
            else:
                vlist.append(p)
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
    pattern = re.compile(
        r'^' + field + r':' + r'''  # The field we want the contents from
        (.*?)                   # The contents of the field
        \n([^ ]|$)              # Start of a new field or EOF
        ''',
        re.MULTILINE | re.DOTALL | re.VERBOSE)
    with open(changes_path, "r") as f:
        file_text = f.read()
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
    that are in deps_info but not in chroot_state["tree"].  (In this case, deps_info
    should be the result of chroot.get_tree_meta_data() right after the
    dependencies are installed, but before the actual packages to test are
    installed.)
    """

    reference_info = chroot_state["tree"]
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

    current_info = chroot.get_tree_meta_data()
    if settings.warn_on_others and deps_info is not None:
        (new, removed, modified) = diff_meta_data(reference_info, current_info)
        (depsnew, depsremoved, depsmodified) = diff_meta_data(reference_info,
                                                              deps_info, quiet=True)

        warnnew = prune_files_list(new, depsnew)
        warnremoved = prune_files_list(removed, depsremoved)
        warnmodified = prune_files_list(modified, depsmodified)

    else:
        (new, removed, modified) = diff_meta_data(reference_info, current_info)

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

    if settings.warn_on_others and deps_info is not None:
        if warnnew:
            msg = ("Warning: Package purging left files on system:\n" +
                   file_list(warnnew, file_owners) +
                   "These files seem to have been left by dependencies rather "
                   "than by packages\nbeing explicitly tested.\n")
            logging.info(msg)
        if warnremoved:
            msg = ("After purging files have disappeared:\n" +
                   file_list(warnremoved, file_owners) +
                   "This seems to have been caused by dependencies rather "
                   "than by packages\nbeing explicitly tested.\n")
            logging.info(msg)
        if warnmodified:
            msg = ("After purging files have been modified:\n" +
                   file_list(warnmodified, file_owners) +
                   "This seems to have been caused by dependencies rather "
                   "than by packages\nbeing explicitly tested.\n")
            logging.info(msg)

    return ok


def install_purge_test(chroot, chroot_state, package_files, packages, extra_packages):
    """Do an install-purge test. Return True if successful, False if not.
       Assume 'root' is a directory already populated with a working
       chroot, with packages in states given by 'selections'."""

    deps_info = None

    os.environ["PIUPARTS_TEST"] = "install"
    chroot.run_scripts("pre_test")

    # Install packages into the chroot.
    os.environ["PIUPARTS_PHASE"] = "install"

    chroot.enable_testdebs_repo()

    chroot.check_for_no_processes(fail=True)
    chroot.check_for_broken_symlinks()

    chroot.run_scripts("pre_install")

    chroot.install_packages([], extra_packages, with_scripts=False)

    if settings.warn_on_others or settings.install_purge_install:
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
            apt_cache_args = ["apt-cache", "show", "--no-all-versions"]
            if os.environ["PIUPARTS_DISTRIBUTION"] in ["lenny"]:
                # apt-cache in lenny does not accept version-qualified packages
                apt_cache_args.extend(unqualify(packages))
            else:
                apt_cache_args.extend(packages)
            returncode, output = chroot.run(apt_cache_args)
            control_infos = deb822.Deb822.iter_paragraphs(output.splitlines())

        depends = []
        conflicts = []
        provides = []
        arch = 'all'
        for control in control_infos:
            if control.get("pre-depends"):
                depends.extend([x.strip() for x in control["pre-depends"].split(',')])
            if control.get("depends"):
                depends.extend([x.strip() for x in control["depends"].split(',')])
            if control.get("conflicts"):
                conflicts.extend([x.strip() for x in control["conflicts"].split(',')])
            if control.get("provides"):
                provides.extend([x.strip() for x in control["provides"].split(',')])
            if control.get("architecture"):
                a = control["architecture"]
                if arch == 'all':
                    arch = a
                if arch != a:
                    logging.info("architecture mismatch: %s != %s)" % (arch, a))
        for provided in provides:
            if provided in conflicts:
                conflicts.remove(provided)
        all_depends = ", ".join(depends)
        all_conflicts = ", ".join(conflicts)
        metapackage = make_metapackage("piuparts-depends-dummy",
                                       depends=all_depends, conflicts=all_conflicts, arch=arch)
        cleanup_metapackage = lambda: shutil.rmtree(os.path.dirname(metapackage))
        panic_handler_id = do_on_panic(cleanup_metapackage)

        # Install the metapackage
        chroot.install_package_files([metapackage], with_scripts=False)

        # Check whether it got installed, the 'dpkg -i p-d-d.deb && apt-get -yf install' approach
        # may not have installed it, cannot happen with 'apt-get install p-d-d.deb' (since stretch)
        if not chroot.is_installed(["piuparts-depends-dummy"]):
            logging.error("Installation of piuparts-depends-dummy FAILED")
            # don't panic(), too many problems on old distros

        # Now remove it
        metapackagename = os.path.basename(metapackage)[:-4]
        chroot.purge_packages([metapackagename])
        cleanup_metapackage()
        dont_do_on_panic(panic_handler_id)

        # Save the file ownership information so we can tell which
        # modifications were caused by the actual packages we are testing,
        # rather than by their dependencies.
        deps_info = chroot.get_tree_meta_data()

        if settings.install_purge_install:
            # save chroot state with all deps installed
            chroot_state_with_deps = chroot.get_state_meta_data()

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks(warn_only=True)  # warn only since no scripts could fix up things after installing the dependencies

    chroot.install_packages(package_files, packages, with_scripts=False)

    chroot.run_scripts("post_install")

    if settings.install_purge_install:
        file_owners = chroot.get_files_owned_by_packages()
        chroot.restore_selections(chroot_state_with_deps, packages)
        logging.info("Validating chroot after purge")
        chroot.check_debsums()
        chroot.check_for_no_processes()
        chroot.check_for_broken_symlinks(file_owners=file_owners)
        if not check_results(chroot, chroot_state_with_deps, file_owners, deps_info=deps_info):
            return False
        logging.info("Reinstalling after purge")
        chroot.install_packages(package_files, packages, with_scripts=True)

    if settings.install_remove_install:
        chroot.remove_packages(packages, ignore_errors=True)
        logging.info("Reinstalling after remove")
        chroot.install_packages(package_files, packages, with_scripts=True)
        chroot.install_packages(package_files, packages, with_scripts=True, reinstall=True)

    chroot.disable_testdebs_repo()

    file_owners = chroot.get_files_owned_by_packages()

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks(file_owners=file_owners)

    # Remove all packages from the chroot that weren't there initially.
    chroot.restore_selections(chroot_state, packages)

    chroot.run_scripts("post_test")

    chroot.check_for_no_processes(fail=True)
    chroot.check_for_broken_symlinks(file_owners=file_owners)

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
        chroot.remove_packages(packages, ignore_errors=True)

    # Then from the package files.
    os.environ["PIUPARTS_PHASE"] = "upgrade"

    chroot.enable_testdebs_repo()

    chroot.install_packages(package_files, packages)

    chroot.disable_testdebs_repo()

    file_owners = chroot.get_files_owned_by_packages()

    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks(file_owners=file_owners)

    # Remove all packages from the chroot that weren't there initially.
    chroot.restore_selections(chroot_state, packages)

    chroot.run_scripts("post_test")

    chroot.check_for_no_processes(fail=True)
    chroot.check_for_broken_symlinks(file_owners=file_owners)

    return check_results(chroot, chroot_state, file_owners)


def save_meta_data(filename, chroot_state):
    """Save directory tree meta data into a file for fast access later."""
    logging.debug("Saving chroot meta data to %s" % filename)
    with open(filename, "w") as f:
        pickle.dump(chroot_state, f)


def load_meta_data(filename):
    """Load meta data saved by 'save_meta_data'."""
    logging.debug("Loading chroot meta data from %s" % filename)
    with open(filename, "r") as f:
        return pickle.load(f)


def install_and_upgrade_between_distros(package_files, packages_qualified):
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
    # well, it is a reasonable default (see below for why), but
    # step 2+3 can be done differently by using --save-end-meta once and
    # then --end-meta for all following runs - until the target distro
    # changes again...
    #
    # Under normal circumstances the target distro can change anytime, ie. at
    # the next mirror pulse, so unless the target distro is frozen, this is
    # a reasonable default behaviour for distro upgrade tests, which are not
    # done by default anyway.

    os.environ["PIUPARTS_TEST"] = "distupgrade"

    packages = unqualify(packages_qualified)

    chroot = get_chroot()
    chroot.create()
    chroot.remember_initial_selections()

    chroot_state = None
    if settings.end_meta:
        if os.path.exists(settings.end_meta):
            chroot_state = load_meta_data(settings.end_meta)
        else:
            logging.info("Cannot load chroot state from %s - generating it on-the-fly." % settings.end_meta)

    if chroot_state is not None:
        if chroot.initial_selections != chroot_state["initial_selections"]:
            logging.warn("Initial package selections do not match - ignoring loaded reference chroot state")
            refsel = [(s, p, v) for p, (s, v) in chroot_state["initial_selections"].iteritems()]
            cursel = [(s, p, v) for p, (s, v) in chroot.initial_selections.iteritems()]
            rsel = [x for x in refsel if not x in cursel]
            csel = [x for x in cursel if not x in refsel]
            [logging.debug("  -%s" % " ".join(x)) for x in rsel]
            [logging.debug("  +%s" % " ".join(x)) for x in csel]
            chroot_state = None

    if chroot_state is None:
        temp_tgz = None
        if chroot.was_bootstrapped():
            temp_tgz = chroot.create_temp_tgz_file()
            panic_handler_id = do_on_panic(lambda: chroot.remove_temp_tgz_file(temp_tgz))
            chroot.pack_into_tgz(temp_tgz)

        chroot.upgrade_to_distros(settings.debian_distros[1:], [])

        chroot.check_for_no_processes(fail=True)

        chroot_state = chroot.get_state_meta_data()

        if settings.save_end_meta:
            save_meta_data(settings.save_end_meta, chroot_state)

        chroot.remove()

        # leave indication in logfile why we do what we do
        logging.info(
            "Notice: package selections and meta data from target distro saved, now starting over from source distro. See the description of --save-end-meta and --end-meta to learn why this is neccessary and how to possibly avoid it.")

        chroot = get_chroot()
        if temp_tgz is None:
            chroot.create()
        else:
            chroot.create(temp_tgz)
            chroot.remove_temp_tgz_file(temp_tgz)
            dont_do_on_panic(panic_handler_id)

    chroot.check_for_no_processes(fail=True)

    cannot_test = chroot.run_scripts("is_testable", ignore_errors=True)
    if cannot_test != 0:
        if cannot_test & 2:
            logging.info("FAIL: All tests. Package cannot be tested with piuparts: %s.", " ".join(packages))
            retval = False
        else:
            logging.info("SKIP: All tests. Package cannot be tested with piuparts: %s.", " ".join(packages))
            retval = True
        testable = False
        chroot.remove()
        return retval

    if settings.shell_on_error:
        panic_handler_id = do_on_panic(lambda: chroot.interactive_shell())

    chroot.run_scripts("pre_test")

    os.environ["PIUPARTS_PHASE"] = "install"

    distupgrade_packages = packages
    known_packages = chroot.get_known_packages(packages + settings.extra_old_packages)
    chroot.install_packages_by_name(known_packages)

    if settings.install_remove_install:
        chroot.remove_packages(packages, ignore_errors=True)
        distupgrade_packages = []

    chroot.check_for_no_processes()

    os.environ["PIUPARTS_PHASE"] = "distupgrade"

    chroot.upgrade_to_distros(settings.debian_distros[1:-1], distupgrade_packages, settings.upgrade_before_dist_upgrade)

    if settings.distupgrade_to_testdebs:
        chroot.enable_testdebs_repo(update=False)

    chroot.upgrade_to_distros(settings.debian_distros[-1:], distupgrade_packages, settings.upgrade_before_dist_upgrade)

    chroot.check_for_no_processes()

    os.environ["PIUPARTS_PHASE"] = "upgrade"

    if not settings.distupgrade_to_testdebs:
        chroot.enable_testdebs_repo()

    chroot.install_packages(package_files, [p for p in packages_qualified if not p.endswith("=None")])

    chroot.disable_testdebs_repo()

    file_owners = chroot.get_files_owned_by_packages()

    chroot.check_for_no_processes()

    # Remove all packages from the chroot that weren't in the reference chroot.
    chroot.restore_selections(chroot_state, packages_qualified)

    chroot.run_scripts("post_test")

    chroot.check_for_no_processes(fail=True)

    result = check_results(chroot, chroot_state, file_owners)

    if settings.shell_on_error:
        dont_do_on_panic(panic_handler_id)
        if not result:
            chroot.interactive_shell()

    chroot.remove()

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
        for line in readlines_file("/etc/apt/sources.list"):
            line = re.sub('\[arch=.*\]', '', line)
            parts = line.split()
            if len(parts) > 2 and parts[0] == "deb":
                mirrors.append((parts[1], parts[3:]))
                break  # Only use the first one, at least for now.
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

    parser.add_option("--arch", metavar="ARCH", action="store",
                      help="Create chroot and run tests for (non-default) architecture ARCH.")

    parser.add_option("-b", "--basetgz", metavar="TARBALL",
                      help="Use TARBALL as the contents of the initial " +
                           "chroot, instead of building a new one with " +
                           "debootstrap.")

    parser.add_option("--bindmount", action="append", metavar="DIR",
                      default=[],
                      help="Directory to be bind-mounted inside the chroot.")

    parser.add_option("-d", "--distribution", action="append", metavar="NAME",
                      help="Which Debian distribution to use: a code name " +
                           "(for example jessie, stretch, sid) or experimental. The " +
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

    parser.add_option("--no-check-valid-until",
                      default=False,
                      action='store_true',
                      help="Set apt option Acquire::Check-Valid-Until=false for testing archived releases.")

    parser.add_option("--allow-database", default=False,
                      action='store_true',
                      help="Allow database servers (MySQL, PostgreSQL) to be started in the chroot.")

    parser.add_option("--distupgrade-to-testdebs", default=False,
                      action='store_true',
                      help="Use the testdebs repository as distupgrade target.")

    parser.add_option("-e", "--existing-chroot", metavar="DIR",
                      help="Use DIR as the contents of the initial " +
                           "chroot, instead of building a new one with " +
                           "debootstrap")

    parser.add_option("--hard-link", default=False,
                      action='store_true',
                      help="When using --existing-chroot, and the source dir is on the same"
                           "filesystem, hard-link files instead of copying them.")

    parser.add_option("-i", "--ignore", action="append", metavar="FILENAME",
                      default=[],
                      help="Add FILENAME to list of filenames to be " +
                           "ignored when comparing changes to chroot."
                           "FILENAMES prefixed with ':' will be reported verbosely.")

    parser.add_option("-I", "--ignore-regex", "--ignore-regexp", action="append",
                      metavar="REGEX", default=[],
                      help="Add REGEX to list of Perl compatible regular " +
                           "expressions for filenames to be " +
                           "ignored when comparing changes to chroot."
                           "Patterns prefixed with ':' will report all matches verbosely.")

    parser.add_option("--install-recommends",
                      action="store_true", default=False,
                      help="Enable the installation of Recommends.")

    parser.add_option("--install-suggests",
                      action="store_true", default=False,
                      help="Enable the installation of Suggests.")

    def keep_env_parser(option, opt_str, value, parser):
        setattr(parser.values, option.dest, True)
        if "--keep-tmpdir" == opt_str:
            print('WARNING `--keep-tmpdir` is deprecated, use `--keep-env` '
                  'instead')

    parser.add_option("-k", "--keep-env", "--keep-tmpdir", action="callback",
                      callback=keep_env_parser, default=False, dest='keep_env',
                      help="Keep the environment used for testing after "
                      "the program ends.")

    parser.add_option("-K", "--keyring", action="store", metavar="FILE",
                      help="Use FILE as the keyring to use with debootstrap when creating chroots.")

    parser.add_option("--keep-sources-list",
                      action="store_true", default=False,
                      help="Don't modify the chroot's " +
                           "etc/apt/sources.list.")

    parser.add_option("-l", "--log-file", "--logfile", metavar="FILENAME",
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
                      help="Use schroot session named SCHROOT-NAME for the "
                      "testing environment, instead of building a new one "
                      "with debootstrap.")

    parser.add_option("--docker-image", metavar="DOCKER-IMAGE", action="store",
                      help="Use a container created from the docker image "
                      "DOCKER-IMAGE for the testing environment, instead of "
                      "building a new one with debootstrap.")

    parser.add_option("-m", "--mirror", action="append", metavar="URL",
                      default=[],
                      help="Which Debian mirror to use.")

    parser.add_option("--extra-repo", action="append",
                      default=[],
                      help="Additional (unparsed) lines to be appended to sources.list, e.g. " +
                      "'deb <URL> <distrib> <components>' or 'deb file://</bind/mount> ./'")

    parser.add_option("--testdebs-repo",
                      help="A repository that contains the packages to be tested, e.g. " +
                      "'deb <URL> <distrib> <components>...' or 'deb file://</bind/mount> ./'," +
                      "plain URLs or local paths are permitted, too.")

    parser.add_option("--no-adequate",
                      default=False,
                      action='store_true',
                      help="Don't run adequate after installation.")

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

    parser.add_option("--upgrade-before-dist-upgrade",
                      action="store_true", default=False,
                      help="Perform two-stage upgrades: 'apt-get upgrade && apt-get dist-upgrade'")

    parser.add_option("--no-upgrade-test",
                      action="store_true", default=False,
                      help="Skip testing the upgrade from an existing version " +
                      "in the archive.")

    parser.add_option("--no-install-purge-test",
                      action="store_true", default=False,
                      help="Skip install and purge test.")

    parser.add_option("--install-purge-install",
                      action="store_true", default=False,
                      help="Purge package after installation and reinstall.")

    parser.add_option("--install-remove-install",
                      action="store_true", default=False,
                      help="Remove package after installation and reinstall. For testing installation in config-files-remaining state.")

    parser.add_option("--fake-essential-packages",
                      action="append", default=[],
                      help="Install additional packages in the base chroot that are not removed after the test. " +
                      "Takes a comma separated list of package names and can be given multiple times. " +
                      "Useful for packages that can be used during purge of the package to be tested " +
                      "or to test whether the package to be tested mishandles these packages.")

    parser.add_option("--extra-old-packages",
                      action="append", default=[],
                      help="Install these additional packages along with the old packages from the archive. " +
                      "Useful to test Conflicts/Replaces of packages that will disappear during the update. " +
                      "Takes a comma separated list of package names and can be given multiple times. " +
                      "For install/purge tests these packages will be installed before the package that is to be tested.")

    parser.add_option("-p", "--pbuilder", action="callback",
                      callback=set_basetgz_to_pbuilder,
                      help="Use /var/cache/pbuilder/base.tgz as the base " +
                           "tarball.")

    parser.add_option("--pedantic-purge-test",
                      action="store_true", default=False,
                      help="Be pedantic when checking if a purged package leaves files behind. If this option is not set, files left in /tmp are ignored.")

    parser.add_option("--proxy", metavar="URL",
                      help="Use the proxy at URL for accessing the mirrors.")

    parser.add_option("-s", "--save", metavar="FILENAME",
                      help="Save the chroot into FILENAME.")

    parser.add_option("-B", "--end-meta", metavar="FILE",
                      help="Load chroot package selection and file meta data from FILE. See the function install_and_upgrade_between_distros() in piuparts.py for defaults. Mostly useful for large scale distro upgrade tests.")

    parser.add_option("-S", "--save-end-meta", metavar="FILE",
                      help="Save chroot package selection and file meta data in FILE for later use. See the function install_and_upgrade_between_distros() in piuparts.py for defaults. Mostly useful for large scale distro upgrade tests.")

    parser.add_option("--single-changes-list", default=False,
                      action="store_true",
                      help="test all packages from all changes files together.")

    parser.add_option("--single-packages", default=False,
                      action="store_true",
                      help="test all packages from the command line individually.")

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

    parser.add_option("--shell-on-error", default=False,
                      action='store_true',
                      help="Execute an interactive shell in the chroot if an error occurred.")

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

    parser.add_option("--warn-on-debsums-errors",
                      action="store_true", default=False,
                      help="Print a warning rather than failing if "
                           "debsums reports modified files.")

    parser.add_option("--warn-on-install-over-symlink",
                      action="store_true", default=False,
                      help="Print a warning rather than failing if "
                           "files are installed over existing symlinks.")

    parser.add_option("--fail-if-inadequate",
                      action="store_true", default=False,
                      help="Fail on inadequate results from running adequate.")

    parser.add_option("--fail-on-broken-symlinks", action="store_true",
                      default=False,
                      help="Fail if broken symlinks are detected.")

    parser.add_option("--log-level", action="store", metavar='LEVEL',
                      default="dump",
                      help="Displays messages from LEVEL level, possible values are: error, info, dump, debug. The default is dump.")

    (opts, args) = parser.parse_args()

    settings.defaults = opts.defaults
    defaults = DefaultsFactory().new_defaults()

    settings.tmpdir = opts.tmpdir
    settings.keep_env = opts.keep_env
    settings.shell_on_error = opts.shell_on_error
    settings.single_changes_list = opts.single_changes_list
    settings.single_packages = opts.single_packages
    settings.args_are_package_files = not opts.apt
    # distro setup
    settings.proxy = opts.proxy
    if settings.proxy:
        os.environ["http_proxy"] = settings.proxy
    settings.debian_mirrors = [parse_mirror_spec(x, defaults.get_components())
                               for x in opts.mirror]
    settings.extra_repos = opts.extra_repo
    settings.testdebs_repo = opts.testdebs_repo
    settings.debian_distros = opts.distribution
    settings.keep_sources_list = opts.keep_sources_list
    if opts.keyring:
        settings.keyring = opts.keyring
    else:
        settings.keyring = defaults.get_keyring()
    settings.do_not_verify_signatures = opts.do_not_verify_signatures
    if settings.do_not_verify_signatures:
        settings.apt_unauthenticated = "Yes"
    else:
        settings.apt_unauthenticated = "No"
    settings.no_check_valid_until = opts.no_check_valid_until
    settings.install_recommends = opts.install_recommends
    settings.install_suggests = opts.install_suggests
    settings.eatmydata = not opts.no_eatmydata
    settings.dpkg_force_unsafe_io = not opts.dpkg_noforce_unsafe_io
    settings.dpkg_force_confdef = opts.dpkg_force_confdef
    settings.scriptsdirs = opts.scriptsdir
    settings.bindmounts += opts.bindmount
    settings.allow_database = opts.allow_database
    # chroot setup
    settings.arch = opts.arch
    settings.basetgz = opts.basetgz
    settings.savetgz = opts.save
    settings.lvm_volume = opts.lvm_volume
    settings.lvm_snapshot_size = opts.lvm_snapshot_size
    settings.existing_chroot = opts.existing_chroot
    settings.hard_link = opts.hard_link
    settings.schroot = opts.schroot
    settings.end_meta = opts.end_meta
    settings.save_end_meta = opts.save_end_meta
    settings.skip_minimize = opts.skip_minimize
    settings.minimize = opts.minimize
    if settings.minimize:
        settings.skip_minimize = False
    settings.debfoster_options = opts.debfoster_options.split()
    settings.docker_image = opts.docker_image
    # tests and checks
    settings.no_install_purge_test = opts.no_install_purge_test
    settings.no_upgrade_test = opts.no_upgrade_test
    settings.upgrade_before_dist_upgrade = opts.upgrade_before_dist_upgrade
    settings.distupgrade_to_testdebs = opts.distupgrade_to_testdebs
    settings.install_purge_install = opts.install_purge_install
    settings.install_remove_install = opts.install_remove_install
    settings.list_installed_files = opts.list_installed_files
    [settings.fake_essential_packages.extend([i.strip() for i in csv.split(",")]) for csv in opts.fake_essential_packages]
    [settings.extra_old_packages.extend([i.strip() for i in csv.split(",")]) for csv in opts.extra_old_packages]
    settings.skip_cronfiles_test = opts.skip_cronfiles_test
    settings.skip_logrotatefiles_test = opts.skip_logrotatefiles_test
    settings.adequate = not opts.no_adequate
    settings.check_broken_diversions = not opts.no_diversions
    settings.check_broken_symlinks = not opts.no_symlinks
    settings.warn_broken_symlinks = not opts.fail_on_broken_symlinks
    settings.warn_on_others = opts.warn_on_others
    settings.warn_on_leftovers_after_purge = opts.warn_on_leftovers_after_purge
    settings.warn_on_debsums_errors = opts.warn_on_debsums_errors
    settings.warn_on_install_over_symlink = opts.warn_on_install_over_symlink
    settings.warn_if_inadequate = not opts.fail_if_inadequate
    settings.pedantic_purge_test = opts.pedantic_purge_test
    settings.ignored_files += opts.ignore
    settings.ignored_patterns += opts.ignore_regex
    if not settings.pedantic_purge_test:
        settings.ignored_patterns += settings.non_pedantic_ignore_patterns

    log_file_name = opts.log_file

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

    if not os.path.isdir(settings.tmpdir):
        logging.error("Temporary directory is not a directory: %s" %
                      settings.tmpdir)
        panic()

    for sdir in settings.scriptsdirs:
        if not os.path.isdir(sdir):
            logging.error("Scripts directory is not a directory: %s" % sdir)
            panic()

    if not settings.debian_distros:
        settings.debian_distros = defaults.get_distribution()

    if not settings.debian_mirrors:
        if opts.defaults:
            settings.debian_mirrors = defaults.get_mirror()
        else:
            settings.debian_mirrors = find_default_debian_mirrors()
        if not settings.debian_mirrors:
            settings.debian_mirrors = defaults.get_mirror()

    settings.distro_config = piupartslib.conf.DistroConfig(
        DISTRO_CONFIG_FILE, settings.debian_mirrors[0][0])

    if settings.keep_sources_list and len(settings.debian_distros) > 1:
        logging.error("--keep-sources-list only makes sense "
                      "with only one distribution")
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
    return Chroot()

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

        if settings.shell_on_error:
            panic_handler_id = do_on_panic(lambda: chroot.interactive_shell())

        chroot_state = chroot.get_state_meta_data()

        testable = True
        cannot_test = chroot.run_scripts("is_testable", ignore_errors=True)
        if cannot_test != 0:
            testable = False
            if cannot_test & 2:
                logging.info("FAIL: All tests. Package cannot be tested with piuparts: %s.", " ".join(packages))
                panic()
            else:
                logging.info("SKIP: All tests. Package cannot be tested with piuparts: %s.", " ".join(packages))

        if testable and not settings.no_install_purge_test:
            extra_packages = chroot.get_known_packages(settings.extra_old_packages)
            if not install_purge_test(chroot, chroot_state,
                                      package_files, packages, extra_packages):
                logging.error("FAIL: Installation and purging test.")
                panic()
            logging.info("PASS: Installation and purging test.")

        if testable and not settings.no_upgrade_test:
            if not settings.args_are_package_files and not settings.testdebs_repo:
                logging.info("Can't test upgrades: -a or --apt option used.")
            else:
                packages_to_query = unqualify(packages)
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

        if settings.shell_on_error:
            dont_do_on_panic(panic_handler_id)

        chroot.remove()
    else:
        if install_and_upgrade_between_distros(package_files, packages):
            logging.info("PASS: Upgrading between Debian distributions.")
        else:
            logging.error("FAIL: Upgrading between Debian distributions.")
            panic()


def main():
    """Main program. But you knew that."""

    args = parse_command_line()

    # check if user has root privileges
    if os.getuid():
        print('You need to be root to use piuparts.')
        sys.exit(1)

    logging.info("-" * 78)
    logging.info("To quickly glance what went wrong, scroll down to the bottom of this logfile.")
    logging.info("FAQ available at https://wiki.debian.org/piuparts/FAQ")
    logging.info("The FAQ also explains how to contact us in case you think piuparts is wrong.")
    logging.info("-" * 78)
    logging.info("piuparts version %s starting up." % VERSION)
    logging.info("Command line arguments: %s" % command2string(sys.argv))
    logging.info("Running on: %s %s %s %s %s" % os.uname())

    # Make sure debconf does not ask questions and stop everything.
    # Packages that don't use debconf will lose.
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    # Reduce the amount of ESC-codes in the logfile.
    os.environ["DPKG_COLORS"] = "never"

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
        if settings.single_packages:
            for package in regular_packages_list:
                process_packages([package])
        else:
            process_packages(regular_packages_list)

    logging.info("PASS: All tests.")
    logging.info("piuparts run ends.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('')
        print('Piuparts interrupted by the user, exiting...')
        panic(1)
        sys.exit(1)
    except SystemExit:
        raise
    except:
        print('')
        print('Piuparts caught exception, exiting...')
        print('-'*60)
        traceback.print_exc(file=sys.stdout)
        print('-'*60)
        panic(1)
        raise

# vi:set et ts=4 sw=4 :
