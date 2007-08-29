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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA


"""Debian package installation and uninstallation tester.

This program sets up a minimal Debian system in a chroot, and installs
and uninstalls packages and their dependencies therein, looking for
problems.

See the manual page (piuparts.1, generated from piuparts.docbook) for
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
import sets
import subprocess
import unittest


class Settings:

    """Global settings for this program."""
    
    def __init__(self):
        self.tmpdir = None
        self.scriptsdir = None
        self.keep_tmpdir = False
        self.max_command_output_size = 1024 * 1024
        self.args_are_package_files = True
        self.debian_mirrors = []
        self.debian_distros = []
        self.basetgz = None
        self.savetgz = None
        self.endmeta = None
        self.saveendmeta = None
        self.warn_on_others = False
        self.keep_sources_list = False
        self.skip_minimize = False
        self.list_installed_files = False
        self.no_upgrade_test = False
        self.skip_cronfiles_test = False
        self.check_broken_symlinks = True
        self.ignored_files = [
            "/dev/MAKEDEV",
            "/etc/aliases",
            "/etc/apt/apt.conf",
            "/etc/apt/secring.gpg",
            "/etc/apt/trustdb.gpg",
            "/etc/crypttab",
            "/etc/exports",
            "/etc/group",
            "/etc/group-",
            "/etc/gshadow",
            "/etc/gshadow-",
            "/etc/hosts.allow.bak",
            "/etc/inetd.conf",
            "/etc/init.d/gnocatan-meta-server",
            "/etc/inittab",
            "/etc/inputrc",
            "/etc/keys",
            "/etc/ld.so.cache",
            "/etc/ld.so.conf",
            "/etc/ld.so.conf.old",
            "/etc/mailname",
            "/etc/modprobe.d",
            "/etc/modules.conf",
            "/etc/modules.conf.old",
            "/etc/mtab",
            "/etc/news",
            "/etc/news/organization",
            "/etc/news/server",
            "/etc/news/servers",
            "/etc/nologin",
            "/etc/passwd",
            "/etc/passwd-",
            "/etc/printcap",
            "/etc/shells",
            "/etc/skel/.zshrc",
            "/home/ftp",
            "/usr/sbin/policy-rc.d",
            "/usr/share/doc/base-config",
            "/usr/share/doc/base-config/README.Debian",
            "/usr/share/doc/base-config/changelog.gz",
            "/usr/share/doc/base-config/copyright",
            "/usr/share/info/dir",
            "/usr/share/info/dir.old",
            "/var/backups/infodir.bak",
            "/var/cache/apt/archives/lock",
            "/var/cache/apt/pkgcache.bin", 
            "/var/cache/apt/srcpkgcache.bin",
            "/var/cache/debconf",
            "/var/cache/debconf/config.dat",
            "/var/cache/debconf/config.dat-old",
            "/var/cache/debconf/passwords.dat",
            "/var/cache/debconf/templates.dat",
            "/var/cache/debconf/templates.dat-old",
            "/var/cache/man/index.db",
            "/var/lib/apt/extended_states",
            "/var/lib/dpkg/available",
            "/var/lib/dpkg/available-old", 
            "/var/lib/dpkg/diversions",
            "/var/lib/dpkg/diversions-old",
            "/var/lib/dpkg/info/base-config.conffiles",
            "/var/lib/dpkg/info/base-config.list",
            "/var/lib/dpkg/info/base-config.md5sums",
            "/var/lib/dpkg/info/base-config.postinst",
            "/var/lib/dpkg/lock", 
            "/var/lib/dpkg/status", 
            "/var/lib/dpkg/status-old", 
            "/var/lib/dpkg/statoverride",
            "/var/lib/dpkg/statoverride-old",
            "/var/lib/dpkg/firebird",
            "/var/lib/logrotate/status",
            "/var/lib/rbldns",
            "/var/log/dpkg.log",
            "/var/log/faillog",
            "/var/log/lastlog",
            "/",
            ]
        self.ignored_patterns = [
            "/dev/",
            "/etc/ssl/certs(/.*)?",
            "/lib/modules/.*/modules.*",
            "/usr/lib/python2\../site-packages/debconf.py[co]",
            "/var/lib/cvs(/.*)?",
            "/var/lib/dpkg/alternatives",
            "/var/lib/maxdb(/.*)?",
            "/var/lib/onak(/.*)?",
            "/var/lib/papercut(/.*)?",
            "/var/log/exim/.*",
            "/var/log/exim4/.*",
            "/var/mail/.*",
            "/var/spool/exim/.*",
            "/var/spool/exim4/.*",
            "/var/spool/news(/.*)?",
            "/var/spool/squid(/.*)?",
            "/var/run/.*",
            "/var/www(/.*)?",
            "/tmp/scripts(/.*)?"
            ]


settings = Settings()


on_panic_hooks = {}
counter = 0


def do_on_panic(hook):
    global counter
    id = counter
    counter += 1
    on_panic_hooks[id] = hook
    return id


def dont_do_on_panic(id):
    del on_panic_hooks[id]


class TimeOffsetFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None):
        self.startup_time = time.time()
        logging.Formatter.__init__(self, fmt, datefmt)

    def formatTime(self, record, datefmt):
        t = time.time() - self.startup_time
        min = int(t / 60)
        s = t % 60.0
        return "%dm%.1fs" % (min, s)


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


def panic():
    for i in range(counter):
        if i in on_panic_hooks:
            on_panic_hooks[i]()
    sys.exit(1)
    

def indent_string(str):
    """Indent all lines in a string with two spaces and return result."""
    return "\n".join(["  " + line for line in str.split("\n")])


safechars = ("abcdefghijklmnopqrstuvwxyz" +
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
             "0123456789" +
             ",.-_!%/=+:")

def shellquote(str):
    if str == "":
        return "''"

    result = []
    for c in str:
        if c == "'":
            result.append("\"'\"")
        elif c in safechars:
            result.append(c)
        else:
            result.append("\\" + c)
    return "".join(result)


def run(command, ignore_errors=False):
    """Run an external command and die with error message if it fails."""
    assert type(command) == type([])
    logging.debug("Starting command: %s" % command)
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANGUAGES"] = ""
    p = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, 
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output, _) = p.communicate()

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


def is_broken_symlink(root, dirpath, filename):
    """Is symlink dirpath+filename broken?
    
    When resolving the symlink, pretend (similar to chroot) that root is
    the root of the filesystem. Note that this does NOT work completely
    correctly if the symlink target contains .. path components. This is
    good enough for my immediate purposes, but nowhere near good enough
    for anything that needs to be secure. For that, use chroot and have
    the kernel resolve symlinks instead.

    """

    pathname = os.path.join(dirpath, filename)
    i = 0
    while os.path.islink(pathname):
        if i >= 10: # let's avoid infinite loops...
            return True
        i += 1
        target = os.readlink(pathname)
        if os.path.isabs(target):
            pathname = os.path.join(root, target[1:]) # Assume Unix filenames
        else:
            pathname = os.path.join(dirpath, target)

    # The symlink chain, if any, has now been resolved. Does the target
    # exist?
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
        
    def tearDown(self):
        for symlink in self.symlinks:
            os.remove(symlink)
        os.rmdir(self.testdir)
        
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


class Chroot:

    """A chroot for testing things in."""
    
    def __init__(self):
        self.name = None
        
    def create_temp_dir(self):
        """Create a temporary directory for the chroot."""
        self.name = tempfile.mkdtemp(dir=settings.tmpdir)
        os.chmod(self.name, 0755)
        logging.debug("Created temporary directory %s" % self.name)

    def create(self):
        """Create a chroot according to user's wishes."""
        self.create_temp_dir()
        id = do_on_panic(self.remove)
        if settings.basetgz:
            self.unpack_from_tgz(settings.basetgz)
            self.configure_chroot()
            self.run(["apt-get", "update"])
            self.run(["apt-get", "-yf", "upgrade"])
            self.minimize()
            self.run(["apt-get", "clean"])
        else:
            self.setup_minimal_chroot()
            self.run(["apt-get", "update"])
            self.run(["apt-get", "clean"])
            if settings.savetgz:
                self.pack_into_tgz(settings.savetgz)
        dont_do_on_panic(id)

    def remove(self):
        """Remove a chroot and all its contents."""
        if not settings.keep_tmpdir and os.path.exists(self.name):
            self.unmount_proc()
            shutil.rmtree(self.name)
            logging.debug("Removed directory tree at %s" % self.name)

    def pack_into_tgz(self, result):
        """Tar and compress all files in the chroot."""
        logging.debug("Saving %s to %s." % (self.name, result))
        try:
            tf = tarfile.open(result, "w:gz")
            tf.add(self.name, arcname=".")
            tf.close()
        except tarfile.TarError, detail:
            logging.error("Couldn't create tar file %s: %s" % 
                          (result, detail))
            panic()

    def unpack_from_tgz(self, tarball):
        """Unpack a tarball to a chroot."""
        logging.debug("Unpacking %s into %s" % (tarball, self.name))
        run(["tar", "-C", self.name, "-zxf", tarball])

    def run(self, command, ignore_errors=False):
        return run(["chroot", self.name] + command,
                   ignore_errors=ignore_errors)

    def create_apt_sources(self, distro):
        """Create an /etc/apt/sources.list with a given distro."""
        lines = []
        for mirror, components in settings.debian_mirrors:
            lines.append("deb %s %s %s\n" % 
                         (mirror, distro, " ".join(components)))
        create_file(os.path.join(self.name, "etc/apt/sources.list"), 
                    "".join(lines))

    def create_apt_conf(self):
        """Create /etc/apt/apt.conf inside the chroot."""
        create_file(self.relative("etc/apt/apt.conf"),
                    'APT::Get::AllowUnauthenticated "yes";\n' + 
                    'APT::Get::Assume-Yes "yes";\n')

    def create_policy_rc_d(self):
        """Create a policy-rc.d that prevents daemons from running."""
	full_name = os.path.join(self.name, "usr/sbin/policy-rc.d")
        create_file(full_name, "#!/bin/sh\nexit 101\n")
	os.chmod(full_name, 0777)
	logging.debug("Created policy-rc.d and chmodded it.")

    def setup_minimal_chroot(self):
        """Set up a minimal Debian system in a chroot."""
        logging.debug("Setting up minimal chroot for %s at %s." % 
              (settings.debian_distros[0], self.name))
        run(["debootstrap", "--resolve-deps", settings.debian_distros[0], 
             self.name, settings.debian_mirrors[0][0]])
        self.configure_chroot()
        self.minimize()

    def minimize(self):
        """Minimize a chroot by removing (almost all) unnecessary packages"""
        if False:
            logging.debug("NOT minimizing chroot because of dpkg bug")
            return

        if settings.skip_minimize:
             return

        self.run(["apt-get", "install", "debfoster"])
        self.run(["debfoster", "-o", "MaxPriority=required", "-o",
                  "UseRecommends=no", "-f", "-n", "apt", "debfoster"])
        remove_files([self.relative("var/lib/debfoster/keepers")])
        self.run(["dpkg", "--purge", "debfoster"])

    def configure_chroot(self):
        """Configure a chroot according to current settings"""
        if not settings.keep_sources_list:
            self.create_apt_sources(settings.debian_distros[0])
        self.create_apt_conf()
        self.create_policy_rc_d()

    def upgrade_to_distros(self, distros, packages):
        """Upgrade a chroot installation to each successive distro."""
        for distro in distros:
            logging.debug("Upgrading %s to %s" % (self.name, distro))
            self.create_apt_sources(distro)
            self.run(["apt-get", "update"])
            self.run(["apt-get", "-yf", "dist-upgrade"])
            # Sometimes dist-upgrade won't upgrade the packages we want
            # to test because the new version depends on a newer library,
            # and installing that would require removing the old version
            # of the library, and we've told apt-get not to remove
            # packages. So, we force the installation like this.
            self.install_packages_by_name(packages)
            self.check_for_no_processes()
    
    def apt_get_knows(self, package_names):
        """Does apt-get (or apt-cache) know about a set of packages?"""
        for name in package_names:
            (status, output) = self.run(["apt-cache", "show", name],
                                        ignore_errors=True)
            if not os.WIFEXITED(status):
                logging.error("Error occurred when running apt-cache " +
                              " in chroot:\n" + output)
                panic()
            if os.WEXITSTATUS(status) != 0 or not output.strip():
                return False
        return True

    def copy_files(self, source_names, target_name):
        """Copy files in 'source_name' to file/dir 'target_name', relative
        to the root of the chroot."""
        target_name = os.path.join(self.name, target_name)
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


    def install_package_files(self, filenames):
        if filenames:
            self.copy_files(filenames, "tmp")
            tmp_files = [os.path.basename(a) for a in filenames]
            tmp_files = [os.path.join("tmp", name) for name in tmp_files]

            self.run_scripts("pre_install")

            if settings.list_installed_files:
                pre_info = self.save_meta_data()

                self.run(["dpkg", "-i"] + tmp_files, ignore_errors=True)
                self.list_installed_files (pre_info, self.save_meta_data())

                self.run(["apt-get", "-yf", "--no-remove", "install"])
                self.list_installed_files (pre_info, self.save_meta_data())

            else:
                self.run(["dpkg", "-i"] + tmp_files, ignore_errors=True)
                self.run(["apt-get", "-yf", "--no-remove", "install"])

            self.run_scripts("post_install")

            self.run(["apt-get", "clean"])
            remove_files([os.path.join(self.name, name) 
                            for name in tmp_files])

    def get_selections(self):
        """Get current package selections in a chroot."""
        (status, output) = self.run(["dpkg", "--get-selections", "*"])
        list = [line.split() for line in output.split("\n") if line.strip()]
        dict = {}
        for name, status in list:
            dict[name] = status
        return dict

    def remove_or_purge(self, operation, packages):
        """Remove or purge packages in a chroot."""
        for name in packages:
            self.run(["dpkg", "--" + operation, name], ignore_errors=True)
        self.run(["dpkg", "--remove", "--pending"], ignore_errors=True)

 
    def restore_selections(self, changes, packages):
        """Restore package selections in a chroot by applying 'changes'.
           'changes' is a return value from diff_selections."""
 
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
    
        # First remove all packages.
        self.remove_or_purge("remove", deps_to_remove + deps_to_purge +
                                        nondeps_to_remove + nondeps_to_purge)
        # Run custom scripts after remove all packages. 
	if settings.scriptsdir is not None:
            self.run_scripts("post_remove")	

        if not settings.skip_cronfiles_test:
            cronfiles, cronfiles_list = self.check_if_cronfiles(packages)
	
        if not settings.skip_cronfiles_test and cronfiles:
            self.check_output_cronfiles(cronfiles_list)

        # Then purge all packages being depended on.
        self.remove_or_purge("purge", deps_to_purge)

        # Finally, purge actual packages.
        self.remove_or_purge("purge", nondeps_to_purge)

        # Run custom scripts after purge all packages.
        if settings.scriptsdir is not None: 
            self.run_scripts("post_purge")

        # Now do a final run to see that everything worked.
        self.run(["dpkg", "--purge", "--pending"])
        self.run(["dpkg", "--remove", "--pending"])

    def save_meta_data(self):
        """Return the filesystem meta data for all objects in the chroot."""
        root = os.path.join(self.name, ".")
        dict = {}
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
                dict[name[len(root):]] = (st, target)
        return dict

    def relative(self, pathname):
        return os.path.join(self.name, pathname)

    def get_files_owned_by_packages(self):
        """Return dict[filename] = [packagenamelist]."""
        dir = self.relative("var/lib/dpkg/info")
        dict = {}
        for basename in os.listdir(dir):
            if basename.endswith(".list"):
                pkg = basename[:-len(".list")]
                f = file(os.path.join(dir, basename), "r")
                for line in f:
                    pathname = line.strip()
                    if pathname in dict:
                        dict[pathname].append(pkg)
                    else:
                        dict[pathname] = [pkg]
                f.close()
        return dict

    def install_packages_by_name(self, packages):
        if packages:
	    if settings.list_installed_files:
                pre_info = self.save_meta_data()
                self.run(["apt-get", "-y", "install"] + packages)
                self.list_installed_files (pre_info, self.save_meta_data())
            else:
                self.run(["apt-get", "-y", "install"] + packages)
	    
	    
    def check_for_no_processes(self):
        """Check there are no processes running inside the chroot."""
        (status, output) = run(["lsof", "+D", self.name], ignore_errors=True)
        count = len(output.split("\n")) - 1
        if count > 0:
            logging.error("Processes are running inside chroot:\n%s" % 
                          indent_string(output))
            panic()

    def mount_proc(self):
        """Mount /proc inside chroot."""
        self.run(["mount", "-t", "proc", "proc", "/proc"])

    def unmount_proc(self):
        """Unmount /proc inside chroot."""
        self.run(["umount", "/proc"], ignore_errors=True)

    def is_ignored(self, pathname):
        """Is a file (or dir or whatever) to be ignored?"""
        if pathname in settings.ignored_files:
            return True
        for pattern in settings.ignored_patterns:
            if re.search(pattern, pathname):
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
                name = os.path.join(dirpath, filename)
                if name.startswith(self.name):
                    name = name[len(self.name):]
                ret = is_broken_symlink(self.name, dirpath, filename)
                if ret and not self.is_ignored(name):
                    broken.append("%s -> %s" % (name, ret))
        if broken:
            logging.error("Broken symlinks:\n%s" % 
                          indent_string("\n".join(broken)))
	    panic()
        else:
            logging.debug("No broken symlinks as far as we can find.")
	    
    def check_if_cronfiles(self, packages):
        """Check if the packages have cron files under /etc/cron.d and in case positive, 
        it returns the list of files. """

        dir = self.relative("var/lib/dpkg/info")
        list = []
        has_cronfiles  = False
        for p in packages:
            basename = p + ".list"

	    if not os.path.exists(os.path.join(dir,basename)):
                continue

            f = file(os.path.join(dir,basename), "r")
            for line in f:
                pathname = line.strip()
                if pathname.startswith("/etc/cron."):
                    if os.path.isfile(self.relative(pathname.strip("/"))):
                        if not has_cronfiles:
                            has_cronfiles = True
                        list.append(pathname)
                        logging.info("Package " + p + " contains cron file: " + pathname)
            f.close()

        return has_cronfiles, list

    def check_output_cronfiles (self, list):
        """Check if a given list of cronfiles has any output. Executes 
	cron file as cron would do (except for SHELL)"""
        for file in list:

            if not os.path.exists(self.relative(file.strip("/"))):
                continue 

            self.run([file])

    def run_scripts (self, step):
        """ Run custom scripts to given step post-install|remove|purge"""

        if settings.scriptsdir is None:
            exit
        logging.info("Running scripts post "+ step)
        basepath = self.relative("tmp/scripts/")
        list_scripts = os.listdir(basepath)
        list_scripts.sort()
        for file in list_scripts:
            if file.startswith(step):
                script = os.path.join("tmp/scripts", file)
                self.run([script]) 



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

    return new, removed, modified


def file_list(meta_infos, file_owners):
    """Return list of indented filenames."""
    meta_infos = meta_infos[:]
    meta_infos.sort()
    list = []
    for name, data in meta_infos:
        list.append("  %s\t" % name)
        if name in file_owners:
            list.append(" owned by: %s\n" % ", ".join(file_owners[name]))
	else:
            list.append(" not owned\n")	

    return "".join(list)


def offending_packages(meta_infos, file_owners):
    """Return a Set of offending packages."""
    pkgset = sets.Set()
    for name, data in meta_infos:
        if name in file_owners:
            for pkg in file_owners[name]:
                pkgset.add(pkg)
    return pkgset


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
             selections[name] == "purge":
            changes[name] = selections[name]
    return changes


def get_package_names_from_package_files(filenames):
    """Return list of package names given list of package file names."""
    list = []
    for filename in filenames:
        (status, output) = run(["dpkg", "--info", filename])
        for line in [line.lstrip() for line in output.split("\n")]:
            if line[:len("Package:")] == "Package:":
                list.append(line.split(":", 1)[1].strip())
    return list


def check_results(chroot, root_info, file_owners, packages=[]):
    """Check that current chroot state matches 'root_info'."""
    if settings.warn_on_others:
        pkgset = sets.Set(packages)
    else:
        pkgset = sets.Set()
    current_info = chroot.save_meta_data()
    (new, removed, modified) = diff_meta_data(root_info, current_info)
    ok = True
    if new:
        msg = "Package purging left files on system:\n" + \
              file_list(new, file_owners)
        offendingset = offending_packages(new, file_owners)
        if settings.warn_on_others and not offendingset.intersection(pkgset):
            # Just print a warning since none of our packages caused the error
            logging.info("Warning: " + msg)
        else:
            logging.error(msg)
            ok = False
    if removed:
        logging.error("After purging files have disappeared:\n" +
                      file_list(removed, file_owners))
        ok = False
    if modified:
        logging.error("After purging files have been modified:\n" +
                      file_list(modified, file_owners))
        ok = False

    return ok


def install_purge_test(chroot, root_info, selections, args, packages):
    """Do an install-purge test. Return True if successful, False if not.
       Assume 'root' is a directory already populated with a working
       chroot, with packages in states given by 'selections'."""

    # Install packages into the chroot.
    chroot.mount_proc()
    if args:
        chroot.install_package_files(args)
    else:
        chroot.install_packages_by_name(packages)
        chroot.run(["apt-get", "clean"])


    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    file_owners = chroot.get_files_owned_by_packages()

    # Remove all packages from the chroot that weren't there initially.    
    changes = diff_selections(chroot, selections)
    chroot.restore_selections(changes, packages)
    
    chroot.check_for_broken_symlinks()
    chroot.unmount_proc()

    return check_results(chroot, root_info, file_owners, packages=packages)


def install_upgrade_test(chroot, root_info, selections, args, package_names):
    """Install package via apt-get, then upgrade from package files.
    Return True if successful, False if not."""

    chroot.mount_proc()

    # First install via apt-get.
    chroot.install_packages_by_name(package_names)

    chroot.run_scripts("pre_upgrade")

    chroot.check_for_broken_symlinks()

    # Then from the package files.
    chroot.install_package_files(args)
    
    file_owners = chroot.get_files_owned_by_packages()

    # Remove all packages from the chroot that weren't there
    # initially.
    changes = diff_selections(chroot, selections)
    chroot.restore_selections(changes, package_names)
    
    chroot.check_for_no_processes()
    chroot.check_for_broken_symlinks()

    chroot.unmount_proc()

    return check_results(chroot, root_info, file_owners)


def save_meta_data(filename, root_info, selections):
    """Save directory tree meta data into a file for fast access later."""
    logging.debug("Saving chroot meta data to %s" % filename)
    f = file(filename, "w")
    pickle.dump((root_info, selections), f)
    f.close()


def load_meta_data(filename):
    """Load meta data saved by 'save_meta_data'."""
    logging.debug("Loading chroot meta data from %s" % filename)
    f = file(filename, "r")
    (root_info, selections) = pickle.load(f)
    f.close()
    return root_info, selections


def install_and_upgrade_between_distros(filenames, packages):
    """Install package and upgrade it between distributions, then remove.
       Return True if successful, False if not."""

    chroot = Chroot()
    chroot.create()
    id = do_on_panic(chroot.remove)

    if settings.basetgz:
        root_tgz = settings.basetgz
    else:
        (fd, root_tgz) = create_temp_file()
        chroot.pack_into_tgz(root_tgz)
        
    if settings.endmeta:
        root_info, selections = load_meta_data(settings.endmeta)
    else:
        chroot.mount_proc()
        chroot.upgrade_to_distros(settings.debian_distros[1:], [])
        chroot.unmount_proc()
        chroot.run(["apt-get", "clean"])

        root_info = chroot.save_meta_data()
        selections = chroot.get_selections()
        
        if settings.saveendmeta:
            save_meta_data(settings.saveendmeta, root_info, selections)
    
        chroot.remove()
        dont_do_on_panic(id)
        chroot = Chroot()
        chroot.create_temp_dir()
        id = do_on_panic(chroot.remove)
        chroot.unpack_from_tgz(root_tgz)

    chroot.check_for_no_processes()
    
    chroot.mount_proc()

    chroot.run(["apt-get", "update"])
    chroot.install_packages_by_name(packages)

    chroot.check_for_no_processes()

    chroot.upgrade_to_distros(settings.debian_distros[1:], packages)

    chroot.check_for_no_processes()

    chroot.install_package_files(filenames)
    chroot.run(["apt-get", "clean"])
    
    chroot.check_for_no_processes()

    file_owners = chroot.get_files_owned_by_packages()

    changes = diff_selections(chroot, selections)
    chroot.restore_selections(changes, packages)
    result = check_results(chroot, root_info, file_owners)

    chroot.check_for_no_processes()
    
    chroot.unmount_proc()

    if root_tgz != settings.basetgz:
        remove_files([root_tgz])
    chroot.remove()
    dont_do_on_panic(id)

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
    
    parser.add_option("-b", "--basetgz", metavar="TARBALL",
                      help="Use TARBALL as the contents of the initial " +
                           "chroot, instead of building a new one with " +
                           "debootstrap.")
    
    parser.add_option("-B", "--end-meta", metavar="FILE",
                      help="XXX")
    
    parser.add_option("-d", "--distribution", action="append", metavar="NAME",
                      help="Which Debian distribution to use: a code name " +
                           "(sarge, etch, sid) or experimental. The " +
                           "default is sid (i.e., unstable).")
    
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
    
    parser.add_option("--keep-sources-list", 
                      action="store_true", default=False,
                      help="Don't modify the chroot's " +
                           "etc/apt/sources.list (only makes sense " +
                           "with --basetgz).")
    
    parser.add_option("--warn-on-others",
                      action="store_true", default=False,
                      help="Print a warning rather than failing if "
                           "files are left behind by a package that "
                           "was not given on the command-line.")
			   
    parser.add_option("--skip-minimize", 
                      action="store_true", default=False,
                      help="Skip minimize chroot step.")
    
    parser.add_option("--list-installed-files", 
                      action="store_true", default=False,
                      help="List files added to the chroot after the " +
		      "installation of the package.")
    
    parser.add_option("--no-upgrade-test", 
                      action="store_true", default=False,
                      help="Skip testing the upgrade from an existing version " +
		      "in the archive.")

    parser.add_option("--skip-cronfiles-test", 
                      action="store_true", default=False,
                      help="Skip testing the output from the cron files.")

    parser.add_option("--scriptsdir", metavar="DIR",
                      help="Directory where are placed the custom scripts.")
    
    parser.add_option("-l", "--log-file", metavar="FILENAME",
                      help="Write log file to FILENAME in addition to " +
                           "the standard output.")
    
    parser.add_option("-m", "--mirror", action="append", metavar="URL",
                      default=[],
                      help="Which Debian mirror to use.")
    
    parser.add_option("-n", "--no-ignores", action="callback",
                      callback=forget_ignores,
                      help="Forget all ignores set so far, including " +
                           "built-in ones.")
    
    parser.add_option("-N", "--no-symlinks", action="store_true",
                      default=False,
                      help="Don't check for broken symlinks.")
    
    parser.add_option("-p", "--pbuilder", action="callback",
                      callback=set_basetgz_to_pbuilder,
                      help="Use /var/cache/pbuilder/base.tgz as the base " +
                           "tarball.")
    
    parser.add_option("-s", "--save", metavar="FILENAME",
                      help="Save the chroot into FILENAME.")

    parser.add_option("-S", "--save-end-meta", metavar="FILE",
                      help="XXX")

    parser.add_option("-t", "--tmpdir", metavar="DIR",
                      help="Use DIR for temporary storage. Default is " +
                           "$TMPDIR or /tmp.")
    
    parser.add_option("-v", "--verbose", 
                      action="store_true", default=False,
                      help="No meaning anymore.")
    
    (opts, args) = parser.parse_args()
    
    settings.args_are_package_files = not opts.apt
    settings.basetgz = opts.basetgz
    settings.debian_distros = opts.distribution
    settings.ignored_files += opts.ignore
    settings.ignored_patterns += opts.ignore_regex
    settings.keep_tmpdir = opts.keep_tmpdir
    settings.keep_sources_list = opts.keep_sources_list
    settings.skip_minimize = opts.skip_minimize
    settings.list_installed_files = opts.list_installed_files
    settings.no_upgrade_test = opts.no_upgrade_test
    settings.skip_cronfiles_test = opts.skip_cronfiles_test
    log_file_name = opts.log_file
    settings.debian_mirrors = [parse_mirror_spec(x, 
                                                 ["main", 
                                                  "contrib", 
                                                  "non-free"]) 
                               for x in opts.mirror]
    settings.check_broken_symlinks = not opts.no_symlinks
    settings.savetgz = opts.save
    settings.warn_on_others = opts.warn_on_others

    if opts.tmpdir is not None:
        settings.tmpdir = opts.tmpdir
        if not os.path.isdir(settings.tmpdir):
            logging.error("Temporary directory is not a directory: %s" % 
                          settings.tmpdir)
            panic()

    setup_logging(DUMP, log_file_name)

    exit = None

    if not settings.tmpdir:
        if "TMPDIR" in os.environ:
            settings.tmpdir = os.environ["TMPDIR"]
        else:
            settings.tmpdir = "/tmp"

    if opts.scriptsdir is not None:
        settings.scriptsdir = opts.scriptsdir
	if not os.path.isdir(settings.scriptsdir):
            logging.error("Scripts directory is not a directory: %s" % 
                          settings.scriptsdir)
            panic()

    if not settings.debian_distros:
        settings.debian_distros = ["sid"]

    if not settings.debian_mirrors:
        settings.debian_mirrors = find_default_debian_mirrors()
        if not settings.debian_mirrors:
            settings.debian_mirrors = [("http://ftp.debian.org/",
                                        ["main", "contrib", "non-free"])]

    if settings.keep_sources_list and \
       (not settings.basetgz or len(settings.debian_distros) > 1):
        logging.error("--keep-sources-list only makes sense with --basetgz "
                      "and only one distribution")
        exit = 1
    
    if not args:
        logging.error("Need command line arguments: " +
                      "names of packages or package files")
        exit = 1

    if exit is not None:
        sys.exit(exit)

    return args
    

def main():
    """Main program. But you knew that."""

    args = parse_command_line()

    logging.info("-" * 78)
    logging.info("piuparts version %s starting up." % VERSION)
    logging.info("Command line arguments: %s" % " ".join(sys.argv))
    logging.info("Running on: %s %s %s %s %s" % os.uname())

    # Make sure debconf does not ask questions and stop everything.
    # Packages that don't use debconf will lose.
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    # Find the names of packages.
    if settings.args_are_package_files:
        packages = get_package_names_from_package_files(args)
    else:
        packages = args
        args = []

    if len(settings.debian_distros) == 1:
        chroot = Chroot()
        chroot.create()
        id = do_on_panic(chroot.remove)

        root_info = chroot.save_meta_data()
        selections = chroot.get_selections()
    
        #copy scripts dir into the chroot
        if settings.scriptsdir is not None:
            dest = chroot.relative("tmp/scripts/")
            os.mkdir(dest)
            for file in os.listdir(settings.scriptsdir):
                if (file.startswith("post_") or file.startswith("pre_")) and os.path.isfile(os.path.join((settings.scriptsdir), file)):
                    shutil.copy(os.path.join((settings.scriptsdir), file), dest) 

        if not install_purge_test(chroot, root_info, selections,
				  args, packages):
            logging.error("FAIL: Installation and purging test.")
            panic()
        logging.info("PASS: Installation and purging test.")

        if not settings.no_upgrade_test:
            if not settings.args_are_package_files:
                logging.info("Can't test upgrades: -a or --apt option used.")
            elif not chroot.apt_get_knows(packages):
                logging.info("Can't test upgrade: packages not known by apt-get.")
            elif install_upgrade_test(chroot, root_info, selections, args, 
                                  packages):
                logging.info("PASS: Installation, upgrade and purging tests.")
            else:
                logging.error("FAIL: Installation, upgrade and purging tests.")
                panic()
    
        chroot.remove()
        dont_do_on_panic(id)
    else:
        if install_and_upgrade_between_distros(args, packages):
            logging.info("PASS: Upgrading between Debian distributions.")
        else:
            logging.error("FAIL: Upgrading between Debian distributions.")
            panic()

    logging.info("PASS: All tests.")
    logging.info("piuparts run ends.")


if __name__ == "__main__":
    if sys.argv[1:] == ["unittest"]:
        del sys.argv[1]
        unittest.main()
    else:
        main()
