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


CONFIG_FILE = "/etc/piuparts/piuparts.conf"


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
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
            {
                "sections": "slave",
                "slave-directory": section,
                "idle-sleep": "300",
                "master-host": None,
                "master-user": None,
                "master-directory": ".",
                "master-command": None,
                "log-file": "piuparts-master.log",
                "mirror": None,
                "piuparts-cmd": "sudo piuparts",
                "distro": "sid",
                "chroot-tgz": None,
                "upgrade-test-distros": None,
                "upgrade-test-chroot-tgz": None,
                "max-reserved": "1",
                "debug": "no",
                "keep-sources-list": "no",
                "arch": None,
            }, "")


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
    
    def connect_to_master(self, log_file):
        logging.info("Connecting to %s" % self._master_host)
        if self._master_user:
            user = "-l " + self._master_user
        else:
            user = ""
        (self._to_master, self._from_master) = \
            os.popen2("ssh %s %s 'cd %s; %s 2> %s.$$ && rm %s.$$'" %
                                    (self._master_host,
                                     user,
                                     self._master_directory or ".",
                                     self._master_command,
                                     log_file,
                                     log_file))

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

    def send_log(self, section, pass_or_fail, filename):
        logging.info("Sending log file %s/%s" % (section, filename))
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


class Section:

    def __init__(self, section):
        self._config = Config(section=section)
        self._config.read(CONFIG_FILE)
        self._slave_directory = os.path.abspath(self._config["slave-directory"])
        if not os.path.exists(self._slave_directory):
            os.mkdir(self._slave_directory)

    def setup(self, master_host, master_user, master_directory, idle_sleep):
        if self._config["debug"] in ["yes", "true"]:
            self._logger = logging.getLogger()
            self._logger.setLevel(logging.DEBUG)

        oldcwd = os.getcwd()
        os.chdir(self._slave_directory)

        if self._config["chroot-tgz"] and not os.path.exists(self._config["chroot-tgz"]):
            create_chroot(self._config, self._config["chroot-tgz"], self._config["distro"])

        if (self._config["upgrade-test-distros"] and self._config["upgrade-test-chroot-tgz"]
            and not os.path.exists(self._config["upgrade-test-chroot-tgz"])):
            create_chroot(self._config, self._config["upgrade-test-chroot-tgz"], 
                        self._config["upgrade-test-distros"].split()[0])
    
        for dir in ["new", "pass", "fail"]:
            dir = os.path.join(self._slave_directory, dir)
            if not os.path.exists(os.path.join(self._slave_directory, dir)):
                os.mkdir(dir)

        self._slave = Slave()
        self._slave.set_master_host(master_host)
        self._slave.set_master_user(master_user)
        self._slave.set_master_directory(master_directory)
        self._slave.set_master_command(self._config["master-command"])
        self._idle_sleep=idle_sleep
        self._log_file=self._config["log-file"]

        for dir in ["pass", "fail", "untestable", "reserved"]:
            dir = os.path.join(self._slave_directory, dir)
            if not os.path.exists(dir):
                os.makedirs(dir)
        os.chdir(oldcwd)

    def run(self):
        logging.info("-------------------------------------------")
        logging.info("Running section " + self._config.section)
        self._slave.connect_to_master(self._log_file)

        oldcwd = os.getcwd()
        os.chdir(self._slave_directory)

        for logdir in ["pass", "fail", "untestable"]:
            for basename in os.listdir(logdir):
                if basename.endswith(".log"):
                    fullname = os.path.join(logdir, basename)
                    self._slave.send_log(self._config.section, logdir, fullname)
                    os.remove(fullname)

        if not self._slave.get_reserved():
            max_reserved = int(self._config["max-reserved"])
            while len(self._slave.get_reserved()) < max_reserved and self._slave.reserve():
                pass

        self._slave.close()

        if self._slave.get_reserved():
            packages_files = {}
            if self._config["upgrade-test-distros"]:
                distros = [self._config["distro"]] + self._config["upgrade-test-distros"].split()
            else:
                distros = [self._config["distro"]]

            for distro in distros:
                if distro not in packages_files:
                    packages_files[distro] = fetch_packages_file(self._config, distro)
            packages_file = packages_files[self._config["distro"]]

            for package_name, version in self._slave.get_reserved():
                if package_name in packages_file:
                    package = packages_file[package_name]
                    if version == package["Version"]:
                        test_package(self._config, package, packages_files)
                    else:
                        create_file(os.path.join("untestable", 
                                    log_name(package_name, version)),
                                    "%s %s not found" % (package_name, version))
                else:
                    create_file(os.path.join("untestable", 
                                log_name(package_name, version)),
                                "Package %s not found" % package_name)
                self._slave.forget_reserved(package_name, version)
            os.chdir(oldcwd)


def log_name(package, version):
    return "%s_%s.log" % (package, version)


def upgrade_testable(config, package, packages_files):
    if config["upgrade-test-distros"]:
        distros = config["upgrade-test-distros"].split()
        if not distros:
            return False

        for distro in distros:
            if not package["Package"] in packages_files[distro]:
                return False
        return True
    else:
        return False

def test_package(config, package, packages_files):
    logging.info("Testing package %s/%s %s" % (config.section, package["Package"], package["Version"]))

    output_name = log_name(package["Package"], package["Version"])
    logging.debug("Opening log file %s" % output_name)
    new_name = os.path.join("new", output_name)
    output = file(new_name, "w")
    output.write(time.strftime("Start: %Y-%m-%d %H:%M:%S %Z\n", 
                               time.gmtime()))
    output.write("\n")
    package.dump(output)
    output.write("\n")
    
    command = "%(piuparts-cmd)s -ad %(distro)s -b %(chroot-tgz)s " % \
                config
    if config["keep-sources-list"] in ["yes", "true"]:
        command += "--keep-sources-list "
    
    if config["mirror"]:
        command += "--mirror %s " % config["mirror"]
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
    output.write(time.strftime("End: %Y-%m-%d %H:%M:%S %Z\n", 
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
    
    # For supporting multiple architectures and suites, we take a command-line
    # argument referring to a section in configuration file.  
    # If no argument is given, the "global" section is assumed.
    section_names = []
    if len(sys.argv) > 1:
        section_names = sys.argv[1:]
    else:
        global_config = Config(section="global")
        global_config.read(CONFIG_FILE)
        section_names = global_config["sections"].split()

    sections = []
    for section_name in section_names:
        section = Section(section_name)
        section.setup(master_host=global_config["master-host"],master_user=global_config["master-user"],master_directory=global_config["master-directory"],idle_sleep=global_config["idle-sleep"])
        sections.append(section)

    while True:
        for section in sections:
            section.run()
        idle = True
        for section_name in section_names:
          if os.listdir(os.path.join(global_config["master-directory"],section_name,"reserved")):
            idle = False
        if idle:
          logging.info("Nothing to do, sleeping for %s seconds." % global_config["idle-sleep"])
          time.sleep(int(global_config["idle-sleep"]))


if __name__ == "__main__":
  try:
     main()
  except KeyboardInterrupt:
     print ''
     print 'Slave interrupted by the user, exiting... manual cleanup still neccessary.'
     sys.exit(1)  
