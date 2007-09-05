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


"""Distributed piuparts processing, slave program

Lars Wirzenius <liw@iki.fi>
"""


import os
import sys
import time
import logging
import ConfigParser
import urllib


import piupartslib.conf
import piupartslib.packagesdb


CONFIG_FILE = "piuparts-slave.conf"


def setup_logging(log_level, log_file_name):
    logger = logging.getLogger()
    logger.setLevel(log_level)

    formatter = logging.Formatter(fmt="%(asctime)s %(message)s",
                                  datefmt="%H:%M")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    if log_file_name:
        handler = logging.FileHandler(log_file_name)
        logger.addHandler(handler)


class Config(piupartslib.conf.Config):

    def __init__(self, section="slave"):
        piupartslib.conf.Config.__init__(self, section,
            {
                "idle-sleep": "10",
                "master-host": None,
                "master-user": None,
                "master-directory": ".",
                "master-command": None,
                "mirror": None,
                "piuparts-cmd": "python piuparts.py",
                "distro": "sid",
                "chroot-tgz": None,
                "upgrade-test-distros": None,
                "upgrade-test-chroot-tgz": None,
                "max-reserved": "1",
                "debug": "no",
                "keep-sources-list": "no",
                "arch": None,
            },
            ["master-host", "master-user", "master-command"])


class MasterNotOK(Exception):

    def __init__(self):
        self.args = "Master did not responed with 'ok'"


class MasterDidNotGreet(Exception):

    def __init__(self):
        self.args = "Master did not start with 'hello'"


class MasterIsCrazy(Exception):

    def __init__(self):
        self.args = "Master said something unexpected"


class Slave:

    def __init__(self):
        self._to_master = None
        self._from_master = None
        self._master_host = None
        self._master_user = None
        self._master_directory = "."
        self._master_command = None
        
    def _readline(self):
        line = self._from_master.readline()
        logging.debug("<< " + line.rstrip())
        return line
        
    def _writeline(self, *words):
        line = " ".join(words)
        logging.debug(">> " + line)
        self._to_master.write(line + "\n")
        self._to_master.flush()

    def set_master_host(self, host):
        logging.debug("Setting master host to %s" % host)
        self._master_host = host
        
    def set_master_user(self, user):
        logging.debug("Setting master user to %s" % user)
        self._master_user = user
        
    def set_master_directory(self, dir):
        logging.debug("Setting master directory to %s" % dir)
        self._master_directory = dir
        
    def set_master_command(self, cmd):
        logging.debug("Setting master command to %s" % cmd)
        self._master_command = cmd
    
    def connect_to_master(self):
        logging.info("Connecting to %s" % self._master_host)
        if self._master_user:
            user = "-l " + self._master_user
        else:
            user = ""
        (self._to_master, self._from_master) = \
            os.popen2("ssh %s %s 'cd %s; %s 2> master.log.$$ && rm master.log.$$'" %
                                    (self._master_host,
                                     user,
                                     self._master_directory or ".",
                                     self._master_command))
        line = self._readline()
        if line != "hello\n":
            raise MasterDidNotGreet()
        logging.debug("Connected to master")

    def close(self):
        logging.debug("Closing connection to master")
        self._from_master.close()
        self._to_master.close()
        self._from_master = self._to_master = None
        logging.info("Connection to master closed")

    def send_log(self, pass_or_fail, filename):
        logging.info("Sending log file %s" % filename)
        basename = os.path.basename(filename)
        package, rest = basename.split("_", 1)
        version = rest[:-len(".log")]
        self._writeline(pass_or_fail, package, version)
        f = file(filename, "r")
        for line in f:
            if line.endswith("\n"):
                line = line[:-1]
            self._writeline(" " + line)
        f.close()
        self._writeline(".")
        line = self._readline()
        if line != "ok\n":
            raise MasterNotOK()

    def reserve(self):
        self._writeline("reserve")
        line = self._readline()
        words = line.split()
        if words and words[0] == "ok":
            logging.info("Reserved for us: %s %s" % (words[1], words[2]))
            self.remember_reservation(words[1], words[2])
            return True
        elif words and words[0] == "error":
            logging.info("Master didn't reserve anything (more) for us")
            return False
        else:
            raise MasterIsCrazy()

    def _reserved_filename(self, name, version):
        return os.path.join("reserved",  "%s_%s.log" % (name, version))

    def remember_reservation(self, name, version):
        create_file(self._reserved_filename(name, version), "")

    def get_reserved(self):
        list = []
        for basename in os.listdir("reserved"):
            if "_" in basename and basename.endswith(".log"):
                name, version = basename[:-len(".log")].split("_", 1)
                list.append((name, version))
        return list

    def forget_reserved(self, name, version):
        try:
            os.remove(self._reserved_filename(name, version))
        except os.error:
            pass


def log_name(package, version):
    return "%s_%s.log" % (package, version)


def upgrade_testable(config, package, packages_files):
    distros = config["upgrade-test-distros"].split()
    if not distros:
        return False
    for distro in distros:
        if not package["Package"] in packages_files[distro]:
            return False
    return True


def test_package(config, package, packages_files):
    logging.info("Testing package %(Package)s %(Version)s" % package)

    output_name = log_name(package["Package"], package["Version"])
    logging.debug("Opening log file %s" % output_name)
    new_name = os.path.join("new", output_name)
    output = file(new_name, "w")
    output.write(time.strftime("Start: %Y-%m-%d %H:%M:%S UTC\n", 
                               time.gmtime()))
    output.write("\n")
    package.dump(output)
    output.write("\n")
    
    command = "%(piuparts-cmd)s -ad %(distro)s -b %(chroot-tgz)s " % \
                config
    if config["keep-sources-list"] in ["yes", "true"]:
        command += "--keep-sources-list "
    command += package["Package"]
    
    logging.debug("Executing: %s" % command)
    output.write("Executing: %s\n" % command)
    f = os.popen("{ %s; } 2>&1" % command, "r")
    for line in f:
        output.write(line)
    status = f.close()
    if status is None:
        status = 0

    if status == 0 and upgrade_testable(config, package, packages_files):
        distros = config["upgrade-test-distros"].split()
        distros = ["-d " + distro.strip() for distro in distros]
        distros = " ".join(distros)
        command = "%(piuparts-cmd)s -ab %(upgrade-test-chroot-tgz)s " % config
        command += distros + " " + package["Package"]

        logging.debug("Executing: %s" % command)
        output.write("\nExecuting: %s\n" % command)
        f = os.popen("{ %s; } 2>&1" % command, "r")
        for line in f:
            output.write(line)
            output.flush()
        status = f.close()
        if status is None:
            status = 0

    output.write("\n")
    output.write(time.strftime("End: %Y-%m-%d %H:%M:%S UTC\n", 
                               time.gmtime()))
    output.close()
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        subdir = "fail"
    else:
        subdir = "pass"
    os.rename(new_name, os.path.join(subdir, output_name))
    logging.debug("Done with %s" % output_name)


def create_chroot(config, tarball, distro):
    logging.info("Creating new tarball %s" % tarball)
    command = "%s -ad %s -s %s.new -m %s hello" % \
                (config["piuparts-cmd"], distro, tarball, config["mirror"])
    logging.debug("Executing: " + command)
    f = os.popen("{ %s; } 2>&1" % command, "r")
    for line in f:
        logging.debug(">> " + line.rstrip())
    f.close()
    os.rename(tarball + ".new", tarball)


def fetch_packages_file(config, distro):
    mirror = config["mirror"]
    arch = config["arch"]
    if not arch:
        # Try to figure it out ourselves, using dpkg
        input, output = os.popen2("dpkg --print-architecture")
        arch = output.read().rstrip()
    packages_url = \
        "%s/dists/%s/main/binary-%s/Packages.bz2" % (mirror, distro, arch)

    logging.debug("Fetching %s" % packages_url)
    f = piupartslib.open_packages_url(packages_url)
    packages_file = piupartslib.packagesdb.PackagesFile(f)
    f.close()
    
    return packages_file


def create_file(filename, contents):
    f = file(filename, "w")
    f.write(contents)
    f.close()


def main():
    setup_logging(logging.INFO, None)
    
    # For supporting multiple piuparts-slave configurations on a particular
    # machine (e.g. for testing multiple suites), we take a command-line
    # argument referring to a section in the slave configuration file.  For
    # backwards compatibility, if no argument is given, the "slave" section is
    # assumed.
    if len(sys.argv) == 2:
        section = sys.argv[1]
        config = Config(section=section)
    else:
        section = None
        config = Config()
    config.read(CONFIG_FILE)
    
    if config["debug"] in ["yes", "true"]:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
    
    if not os.path.exists(config["chroot-tgz"]):
        create_chroot(config, config["chroot-tgz"], config["distro"])

    if (config["upgrade-test-distros"] and not
        os.path.exists(config["upgrade-test-chroot-tgz"])):
        create_chroot(config, config["upgrade-test-chroot-tgz"], 
                      config["upgrade-test-distros"].split()[0])

    for dir in ["new", "pass", "fail"]:
        if not os.path.exists(dir):
            os.mkdir(dir)

    s = Slave()
    s.set_master_host(config["master-host"])
    s.set_master_user(config["master-user"])
    s.set_master_directory(config["master-directory"])
    s.set_master_command(config["master-command"])

    for dir in ["pass", "fail", "untestable", "reserved"]:
        if not os.path.exists(dir):
            os.makedirs(dir)

    while True:
        logging.info("-------------------------------------------")
        s.connect_to_master()
    
        for logdir in ["pass", "fail", "untestable"]:
            for basename in os.listdir(logdir):
                if basename.endswith(".log"):
                    fullname = os.path.join(logdir, basename)
                    s.send_log(logdir, fullname)
                    os.remove(fullname)

        if not s.get_reserved():
            max_reserved = int(config["max-reserved"])
            while len(s.get_reserved()) < max_reserved and s.reserve():
                pass

        s.close()

        if not s.get_reserved():
            logging.debug("Nothing to do, sleeping for a bit")
            time.sleep(int(config["idle-sleep"]))
            continue
        
        packages_files = {}
        distros = [config["distro"]] + config["upgrade-test-distros"].split()
        for distro in distros:
            if distro not in packages_files:
                packages_files[distro] = fetch_packages_file(config, distro)
        packages_file = packages_files[config["distro"]]
        
        for package_name, version in s.get_reserved():
            if package_name in packages_file:
                package = packages_file[package_name]
                if version == package["Version"]:
                    test_package(config, package, packages_files)
                else:
                    create_file(os.path.join("untestable", 
                                             log_name(package_name, version)),
                                "%s %s not found" % (package_name, version))
            else:
                create_file(os.path.join("untestable", 
                                         log_name(package_name, version)),
                            "Package %s not found" % package_name)
            s.forget_reserved(package_name, version)
        

if __name__ == "__main__":
    main()
