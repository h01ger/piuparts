#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# Copyright © 2011-2017 Andreas Beckmann (anbe@debian.org)
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


"""Distributed piuparts processing, slave program

Lars Wirzenius <liw@iki.fi>
"""
from __future__ import print_function  # Requires Py 2.6 or later

import os
import sys
import stat
import time
import logging
from signal import alarm, signal, SIGALRM, SIGINT, SIGKILL, SIGHUP
import subprocess
import fcntl
import random
import apt_pkg
import pipes

import piupartslib.conf
import piupartslib.packagesdb
from piupartslib.conf import MissingSection

apt_pkg.init_system()


CONFIG_FILE = "/etc/piuparts/piuparts.conf"
DISTRO_CONFIG_FILE = "/etc/piuparts/distros.conf"
MAX_WAIT_TEST_RUN = 90 * 60

interrupted = False
old_sigint_handler = None
got_sighup = False


def setup_logging(log_level, log_file_name):
    logger = logging.getLogger()
    logger.setLevel(log_level)

    formatter = logging.Formatter(fmt="%(asctime)s %(message)s",
                                  datefmt="%H:%M:%S")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if log_file_name:
        handler = logging.FileHandler(log_file_name)
        logger.addHandler(handler)


class Config(piupartslib.conf.Config):

    def __init__(self, section="slave", defaults_section=None):
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
                                         {
                                         "sections": "slave",
                                         "basetgz-sections": "",
                                         "idle-sleep": 300,
                                         "max-tgz-age": 2592000,
                                         "min-tgz-retry-delay": 21600,
                                         "master-host": None,
                                         "master-user": None,
                                         "master-command": None,
                                         "proxy": None,
                                         "mirror": None,
                                         "piuparts-command": "sudo piuparts",
                                         "piuparts-flags": "",
                                         "tmpdir": None,
                                         "distro": None,
                                         "area": None,
                                         "components": None,
                                         "chroot-tgz": None,
                                         "upgrade-test-distros": None,
                                         "basetgz-directory": ".",
                                         "chroot-meta-auto": None,
                                         "max-reserved": 1,
                                         "debug": "no",
                                         "keep-sources-list": "no",
                                         "arch": None,
                                         "precedence": "1",
                                         "slave-load-max": None,
                                         },
                                         defaults_section=defaults_section)


class Alarm(Exception):
    pass


def alarm_handler(signum, frame):
    raise Alarm


def sigint_handler(signum, frame):
    global interrupted
    interrupted = True
    print('\nSlave interrupted by the user, waiting for the current test to finish.')
    print('Press Ctrl-C again to abort now.')
    signal(SIGINT, old_sigint_handler)


def sighup_handler(signum, frame):
    global got_sighup
    got_sighup = True
    print('SIGHUP: Will flush finished logs.')


class MasterIsBusy(Exception):

    def __init__(self):
        self.args = "Master is busy, retry later",


class MasterNotOK(Exception):

    def __init__(self):
        self.args = "Master did not respond with 'ok'",


class MasterDidNotGreet(Exception):

    def __init__(self):
        self.args = "Master did not start with 'hello'",


class MasterCommunicationFailed(Exception):

    def __init__(self):
        self.args = "Communication with master failed",


class MasterIsCrazy(Exception):

    def __init__(self):
        self.args = "Master said something unexpected",


class MasterCantRecycle(Exception):

    def __init__(self):
        self.args = "Master has nothing to recycle",


class Slave:

    def __init__(self):
        self._to_master = None
        self._from_master = None
        self._master_host = None
        self._master_user = None
        self._master_command = None
        self._section = None

    def _readline(self):
        try:
            line = self._from_master.readline()
        except IOError:
            raise MasterCommunicationFailed()
        logging.debug("<< " + line.rstrip())
        return line

    def _writeline(self, *words):
        line = " ".join(words)
        logging.debug(">> " + line)
        try:
            self._to_master.write(line + "\n")
            self._to_master.flush()
        except IOError:
            raise MasterCommunicationFailed()

    def set_master_host(self, host):
        logging.debug("Setting master host to %s" % host)
        if self._master_host != host:
            self.close()
            self._master_host = host

    def set_master_user(self, user):
        logging.debug("Setting master user to %s" % user)
        if self._master_user != user:
            self.close()
            self._master_user = user

    def set_master_command(self, cmd):
        logging.debug("Setting master command to %s" % cmd)
        if self._master_command != cmd:
            self.close()
            self._master_command = cmd

    def set_section(self, section):
        logging.debug("Setting section to %s" % section)
        self._section = section

    def connect_to_master(self):
        if not self._is_connected():
            self._initial_connect()
        self._select_section()

    def _is_connected(self):
        return self._to_master and self._from_master

    def _initial_connect(self):
        logging.info("Connecting to %s" % self._master_host)
        ssh_command = ["ssh", "-x"]
        if self._master_user:
            ssh_command.extend(["-l", self._master_user])
        ssh_command.append(self._master_host)
        ssh_command.append(self._master_command or "command-is-set-in-authorized_keys")
        p = subprocess.Popen(ssh_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._to_master = p.stdin
        self._from_master = p.stdout
        line = self._readline()
        if line != "hello\n":
            raise MasterDidNotGreet()

    def _select_section(self):
        self._writeline("section", self._section)
        line = self._readline()
        if line == "busy\n":
            raise MasterIsBusy()
        elif line != "ok\n":
            raise MasterNotOK()
        logging.debug("Connected to master")

    def close(self):
        if self._from_master is None and self._to_master is None:
            return
        logging.debug("Closing connection to master")
        if self._from_master is not None:
            self._from_master.close()
        if self._to_master is not None:
            self._to_master.close()
        self._from_master = self._to_master = None
        logging.info("Connection to master closed")

    def send_log(self, section, pass_or_fail, filename):
        logging.info("Sending log file %s/%s" % (section, filename))
        basename = os.path.basename(filename)
        package, rest = basename.split("_", 1)
        version = rest[:-len(".log")]
        self._writeline(pass_or_fail, package, version)
        with open(filename, "r") as f:
            for line in f:
                if line.endswith("\n"):
                    line = line[:-1]
                self._writeline(" " + line)
        self._writeline(".")
        line = self._readline()
        if line != "ok\n":
            raise MasterNotOK()

    def get_status(self, section):
        self._writeline("status")
        line = self._readline()
        words = line.split()
        if words and words[0] == "ok":
            logging.info("Master " + section + " status: " + " ".join(words[1:]))
        else:
            raise MasterIsCrazy()

    def enable_recycling(self):
        self._writeline("recycle")
        line = self._readline()
        words = line.split()
        if line != "ok\n":
            raise MasterCantRecycle()

    def get_idle(self):
        self._writeline("idle")
        line = self._readline()
        words = line.split()
        if words and words[0] == "ok" and len(words) == 2:
            return int(words[1])
        else:
            raise MasterIsCrazy()

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

    def unreserve(self, filename):
        basename = os.path.basename(filename)
        package, rest = basename.split("_", 1)
        version = rest[:-len(".log")]
        logging.info("Unreserve: %s %s" % (package, version))
        self._writeline("unreserve", package, version)
        line = self._readline()
        if line != "ok\n":
            raise MasterNotOK()

    def _reserved_filename(self, name, version):
        return os.path.join("reserved", "%s_%s.log" % (name, version))

    def remember_reservation(self, name, version):
        create_file(self._reserved_filename(name, version), "")

    def get_reserved(self):
        vlist = []
        for basename in os.listdir("reserved"):
            if "_" in basename and basename.endswith(".log"):
                name, version = basename[:-len(".log")].split("_", 1)
                vlist.append((name, version))
        return vlist

    def forget_reserved(self, name, version):
        try:
            os.remove(self._reserved_filename(name, version))
        except os.error:
            pass


class Section:

    def __init__(self, section, slave=None):
        self._config = Config(section=section, defaults_section="global")
        self._config.read(CONFIG_FILE)
        self._distro_config = piupartslib.conf.DistroConfig(
            DISTRO_CONFIG_FILE, self._config["mirror"])
        self._error_wait_until = 0
        self._idle_wait_until = 0
        self._recycle_wait_until = 0
        self._tarball_wait_until = 0
        self._slave_directory = os.path.abspath(section)
        if not os.path.exists(self._slave_directory):
            os.makedirs(self._slave_directory)

        if self._config["debug"] in ["yes", "true"]:
            self._logger = logging.getLogger()
            self._logger.setLevel(logging.DEBUG)

        if int(self._config["max-reserved"]) > 0:
            self._check_tarball()

        for rdir in ["new", "pass", "fail", "untestable", "reserved"]:
            rdir = os.path.join(self._slave_directory, rdir)
            if not os.path.exists(rdir):
                os.mkdir(rdir)

        self._slave = slave or Slave()

    def _throttle_if_overloaded(self):
        global interrupted
        if interrupted or got_sighup:
            return
        if self._config["slave-load-max"] is None:
            return
        load_max = float(self._config["slave-load-max"])
        if load_max < 1.0:
            return
        if os.getloadavg()[0] <= load_max:
            return
        load_resume = max(load_max - 1.0, 0.9)
        secs = random.randrange(30, 90)
        self._slave.close()
        while True:
            load = os.getloadavg()[0]
            if load <= load_resume:
                break
            logging.info("Sleeping due to high load (%.2f)" % load)
            try:
                time.sleep(secs)
            except KeyboardInterrupt:
                interrupted = True
            if interrupted or got_sighup:
                break
            if secs < 300:
                secs += random.randrange(30, 90)

    def _connect_to_master(self, recycle=False):
        self._slave.set_master_host(self._config["master-host"])
        self._slave.set_master_user(self._config["master-user"])
        self._slave.set_master_command(self._config["master-command"])
        self._slave.set_section(self._config.section)
        self._slave.connect_to_master()
        if recycle:
            self._slave.enable_recycling()

    def _get_tarball(self):
        basetgz = self._config["chroot-tgz"] or \
            self._distro_config.get_basetgz(self._config.get_start_distro(),
                                            self._config.get_arch())
        return os.path.join(self._config["basetgz-directory"], basetgz)

    def _check_tarball(self):
        if int(self._config["max-tgz-age"]) < 0:
            return

        oldcwd = os.getcwd()
        os.chdir(self._slave_directory)

        tgz = self._get_tarball()
        max_tgz_age = int(self._config["max-tgz-age"])
        min_tgz_retry_delay = int(self._config["min-tgz-retry-delay"])
        ttl = 0
        needs_update = not os.path.exists(tgz)
        if not needs_update and max_tgz_age > 0:
            # tgz exists and age is limited, so check age
            now = time.time()
            age = now - os.path.getmtime(tgz)
            ttl = max_tgz_age - age
            logging.info("Check-replace %s: age=%d vs. max=%d" % (tgz, age, max_tgz_age))
            if ttl < 0:
                if os.path.exists(tgz + ".log"):
                    age = now - os.path.getmtime(tgz + ".log")
                ttl = min_tgz_retry_delay - age
                logging.info("Limit-replace %s: last-retry=%d vs. min=%d" % (tgz, age, min_tgz_retry_delay))
                if ttl < 0:
                    needs_update = True
                    logging.info("%s too old.  Forcing re-creation" % tgz)
        if needs_update:
            create_chroot(self._config, tgz, self._config.get_start_distro())
            ttl = min_tgz_retry_delay
        self._tarball_wait_until = time.time() + ttl

        os.chdir(oldcwd)

    def _count_submittable_logs(self):
        files = 0
        subdirs = ["pass", "fail", "untestable"]
        if interrupted:
            subdirs += ["reserved", "new"]
        for logdir in subdirs:
            for basename in os.listdir(os.path.join(self._slave_directory, logdir)):
                if basename.endswith(".log"):
                    files += 1
        return files

    def precedence(self):
        return int(self._config["precedence"])

    def sleep_until(self, recycle=False):
        if recycle:
            return max(self._error_wait_until, self._recycle_wait_until)
        return max(self._error_wait_until, self._idle_wait_until)

    def run(self, do_processing=True, recycle=False):
        if time.time() < self.sleep_until(recycle=recycle):
            return 0

        self._throttle_if_overloaded()

        self._config = Config(section=self._config.section, defaults_section="global")
        try:
            self._config.read(CONFIG_FILE)
        except MissingSection:
            logging.info("unknown section " + self._config.section)
            self._error_wait_until = time.time() + 3600
            return 0
        self._distro_config = piupartslib.conf.DistroConfig(
                DISTRO_CONFIG_FILE, self._config["mirror"])

        if interrupted or got_sighup:
            do_processing = False

        if do_processing and time.time() > self._tarball_wait_until:
            self._check_tarball()

        if self._config.get_distro() == "None":
            # section is for tarball creation only
            self._idle_wait_until = self._tarball_wait_until + 60
            self._recycle_wait_until = self._tarball_wait_until + 3600
            return 0

        if interrupted or got_sighup:
            do_processing = False

        if not do_processing and self._count_submittable_logs() == 0:
            return 0

        logging.info("-------------------------------------------")
        action = "Running"
        if recycle:
            action = "Recycling"
        if not do_processing:
            action = "Flushing"
        logging.info("%s section %s (precedence=%d)"
                     % (action, self._config.section, self.precedence()))

        if int(self._config["max-reserved"]) == 0:
            logging.info("disabled")
            self._error_wait_until = time.time() + 12 * 3600
            return 0

        if not self._config.get_distro() and not self._config.get_distros():
            logging.error("neither 'distro' nor 'upgrade-test-distros' configured")
            self._error_wait_until = time.time() + 3600
            return 0

        with open(os.path.join(self._slave_directory, "slave.lock"), "we") as lock:
            oldcwd = os.getcwd()
            os.chdir(self._slave_directory)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                logging.info("busy")
                self._error_wait_until = time.time() + 900
            else:
                if self._talk_to_master(fetch=do_processing, recycle=recycle, unreserve=interrupted):
                    if do_processing:
                        if not self._slave.get_reserved():
                            self._idle_wait_until = time.time() + int(self._config["idle-sleep"])
                            if recycle:
                                self._recycle_wait_until = self._idle_wait_until + 3600
                        else:
                            processed = self._process()
                            if got_sighup and self._slave.get_reserved():
                                # keep this section at the front of the round-robin runnable queue
                                self._idle_wait_until = 0
                                self._recycle_wait_until = 0
                            else:
                                # put this section at the end of the round-robin runnable queue
                                self._idle_wait_until = time.time()
                                self._recycle_wait_until = time.time()
                            return processed
            finally:
                os.chdir(oldcwd)
        return 0

    def _talk_to_master(self, fetch=False, unreserve=False, recycle=False):
        flush = self._count_submittable_logs() > 0
        fetch = fetch and not self._slave.get_reserved()
        if not flush and not fetch:
            return True

        try:
            self._connect_to_master(recycle=recycle)
        except KeyboardInterrupt:
            raise
        except MasterIsBusy:
            logging.error("master is busy")
            self._error_wait_until = time.time() + random.randrange(60, 180)
        except MasterCantRecycle:
            logging.error("master has nothing to recycle")
            self._recycle_wait_until = max(time.time(), self._idle_wait_until) + 3600
        except (MasterDidNotGreet, MasterIsCrazy, MasterCommunicationFailed, MasterNotOK):
            logging.error("connection to master failed")
            self._error_wait_until = time.time() + 900
            self._slave.close()
        else:
            try:
                for logdir in ["pass", "fail", "untestable"]:
                    for basename in os.listdir(logdir):
                        if basename.endswith(".log"):
                            fullname = os.path.join(logdir, basename)
                            self._slave.send_log(self._config.section, logdir, fullname)
                            os.remove(fullname)

                if unreserve:
                    for logdir in ["new", "reserved"]:
                        for basename in os.listdir(logdir):
                            if basename.endswith(".log"):
                                fullname = os.path.join(logdir, basename)
                                self._slave.unreserve(fullname)
                                os.remove(fullname)

                if fetch:
                    max_reserved = int(self._config["max-reserved"])
                    idle = self._slave.get_idle()
                    if idle > 0:
                        idle = min(idle, int(self._config["idle-sleep"]))
                        logging.info("idle (%d)" % idle)
                        if not recycle:
                            self._idle_wait_until = time.time() + idle
                        else:
                            self._recycle_wait_until = time.time() + idle
                        return 0
                    while len(self._slave.get_reserved()) < max_reserved and self._slave.reserve():
                        pass
                    self._slave.get_status(self._config.section)
            except MasterNotOK:
                logging.error("master did not respond with 'ok'")
                self._error_wait_until = time.time() + 900
                self._slave.close()
            except (MasterIsCrazy, MasterCommunicationFailed):
                logging.error("communication with master failed")
                self._error_wait_until = time.time() + 900
                self._slave.close()
            else:
                return True
        return False

    def _process(self):
        global interrupted
        self._slave.close()

        packagenames = set([x[0] for x in self._slave.get_reserved()])
        packages_files = {}
        for distro in [self._config.get_distro()] + self._config.get_distros():
            if distro not in packages_files:
                try:
                    pf = piupartslib.packagesdb.PackagesFile()
                    pf.load_packages_urls(
                        self._distro_config.get_packages_urls(
                            distro,
                                self._config.get_area(),
                                self._config.get_arch()),
                            packagenames)
                    packages_files[distro] = pf
                except IOError:
                    logging.error("failed to fetch packages file for %s" % distro)
                    self._error_wait_until = time.time() + 900
                    return 0
                except KeyboardInterrupt:
                    interrupted = True
        del packagenames

        test_count = 0
        self._check_tarball()
        if not os.path.exists(self._get_tarball()):
            self._error_wait_until = time.time() + 300
        if self._config["chroot-meta-auto"]:
            if os.path.exists(self._config["chroot-meta-auto"]):
                try:
                    age = time.time() - os.path.getmtime(self._config["chroot-meta-auto"])
                    if age > 6 * 3600:
                        os.unlink(self._config["chroot-meta-auto"])
                        logging.info("Deleting old %s" % self._config["chroot-meta-auto"])
                except OSError:
                    pass
        for package_name, version in self._slave.get_reserved():
            self._throttle_if_overloaded()
            if interrupted or got_sighup:
                break
            if not os.path.exists(self._get_tarball()):
                logging.error("Missing chroot-tgz %s" % self._get_tarball())
                break
            test_count += 1
            self._test_package(package_name, version, packages_files)
            self._slave.forget_reserved(package_name, version)
        self._talk_to_master(unreserve=interrupted)
        return test_count

    def _test_package(self, pname, pvers, packages_files):
        global old_sigint_handler
        old_sigint_handler = signal(SIGINT, sigint_handler)

        logging.info("Testing package %s/%s %s" % (self._config.section, pname, pvers))

        output_name = log_name(pname, pvers)
        logging.debug("Opening log file %s" % output_name)
        new_name = os.path.join("new", output_name)
        output = open(new_name, "we")
        output.write(time.strftime("Start: %Y-%m-%d %H:%M:%S %Z\n",
                                   time.gmtime()))

        distupgrade = len(self._config.get_distros()) > 1

        command = self._config["piuparts-command"].split()
        if self._config["piuparts-flags"]:
            command.extend(self._config["piuparts-flags"].split())
        if "http_proxy" in os.environ:
            command.extend(["--proxy", os.environ["http_proxy"]])
        if self._config["mirror"]:
            mirror = self._config["mirror"]
            if self._config["components"]:
                mirror += " " + self._config["components"]
            command.extend(["--mirror", mirror])
        if self._config["tmpdir"]:
            command.extend(["--tmpdir", self._config["tmpdir"]])
        command.extend(["--arch", self._config.get_arch()])
        command.extend(["-b", self._get_tarball()])
        if not distupgrade:
            command.extend(["-d", self._config.get_distro()])
            command.append("--no-upgrade-test")
        else:
            for distro in self._config.get_distros():
                command.extend(["-d", distro])
        if self._config["keep-sources-list"] in ["yes", "true"]:
            command.append("--keep-sources-list")
        if distupgrade and self._config["chroot-meta-auto"]:
            if not os.path.exists(self._config["chroot-meta-auto"]):
                command.extend(["-S", self._config["chroot-meta-auto"]])
            else:
                command.extend(["-B", self._config["chroot-meta-auto"]])
        command.extend(["--apt", "%s=%s" % (pname, pvers)])

        subdir = "fail"
        ret = 0

        if not distupgrade:
            distro = self._config.get_distro()
            if not pname in packages_files[distro]:
                output.write("Package %s not found in %s\n" % (pname, distro))
                ret = -10001
            else:
                package = packages_files[distro][pname]
                if pvers != package["Version"]:
                    output.write("Package %s %s not found in %s, %s is available\n" % (pname, pvers, distro, package["Version"]))
                    ret = -10002
                output.write("\n")
                package.dump(output)
                output.write("\n")
        else:
            distros = self._config.get_distros()
            if distros:
                # the package must exist somewhere
                for distro in distros:
                    if pname in packages_files[distro]:
                        break
                else:
                    output.write("Package %s not found in any distribution\n" % pname)
                    ret = -10003

                # the package must have the correct version in the distupgrade target distro
                distro = distros[-1]
                if not pname in packages_files[distro]:
                    # the package may "disappear" in the distupgrade target distro
                    if pvers == "None":
                        pass
                    else:
                        output.write("Package %s not found in %s\n" % (pname, distro))
                        ret = -10004
                else:
                    package = packages_files[distro][pname]
                    if pvers != package["Version"]:
                        output.write("Package %s %s not found in %s, %s is available\n" % (pname, pvers, distro, package["Version"]))
                        ret = -10005

                for distro in distros:
                    output.write("\n[%s]\n" % distro)
                    if pname in packages_files[distro]:
                        packages_files[distro][pname].dump(output)
                output.write("\n")

                if ret == 0:
                    prev = "~"
                    for distro in distros:
                        if pname in packages_files[distro]:
                            v = packages_files[distro][pname]["Version"]
                            if not apt_pkg.version_compare(prev, v) <= 0:
                                output.write("Upgrade to %s requires downgrade: %s > %s\n" % (distro, prev, v))
                                ret = -10006
                            prev = v
            else:
                ret = -10010
        if ret != 0:
            subdir = "untestable"

        if ret == 0:
            output.write("Executing: %s\n" % command2string(command))
            ret, f = run_test_with_timeout(command, MAX_WAIT_TEST_RUN)
            if not f or f[-1] != '\n':
                f += '\n'
            output.write(f.replace('\033', '[ESC]'))
            lastline = f.split('\n')[-2]
            if ret < 0:
                output.write(" *** Process KILLED - exceed maximum run time ***\n")
            elif not "piuparts run ends" in lastline:
                ret += 1024
                output.write(" *** PIUPARTS OUTPUT INCOMPLETE ***\n")
            elif distupgrade and self._config["chroot-meta-auto"]:
                try:
                    if "History of available packages does not match - reference chroot may be outdated" in f:
                        os.unlink(self._config["chroot-meta-auto"])
                        logging.info("Deleting outdated %s" % self._config["chroot-meta-auto"])
                    elif "Initial package selections do not match - ignoring loaded reference chroot state" in f:
                        os.unlink(self._config["chroot-meta-auto"])
                        logging.info("Deleting mismatching %s" % self._config["chroot-meta-auto"])
                except OSError:
                    pass

        output.write("\n")
        output.write("ret=%d\n" % ret)
        output.write(time.strftime("End: %Y-%m-%d %H:%M:%S %Z\n",
                                   time.gmtime()))
        output.close()
        if ret == 0:
            subdir = "pass"
        os.rename(new_name, os.path.join(subdir, output_name))
        logging.debug("Done with %s: %s (%d)" % (output_name, subdir, ret))
        signal(SIGINT, old_sigint_handler)


def log_name(package, version):
    return "%s_%s.log" % (package, version)


def command2string(command):
    """Quote s.t. copy+paste from the logfile gives a runnable command in the shell."""
    return " ".join([pipes.quote(arg) for arg in command])


def run_test_with_timeout(cmd, maxwait, kill_all=True):

    def terminate_subprocess(p, kill_all):
        pids = [p.pid]
        if kill_all:
            ps = subprocess.Popen(["ps", "--no-headers", "-o", "pid", "--ppid", "%d" % p.pid],
                                  stdout=subprocess.PIPE)
            stdout, stderr = ps.communicate()
            pids.extend([int(pid) for pid in stdout.split()])
        if p.poll() is None:
            print('Sending SIGINT...')
            try:
                os.killpg(os.getpgid(p.pid), SIGINT)
            except OSError:
                pass
            # piuparts has 30 seconds to clean up after Ctrl-C
            for i in range(60):
                time.sleep(0.5)
                if p.poll() is not None:
                    break
        if p.poll() is None:
            print('Sending SIGTERM...')
            p.terminate()
            # piuparts has 5 seconds to clean up after SIGTERM
            for i in range(10):
                time.sleep(0.5)
                if p.poll() is not None:
                    break
        if p.poll() is None:
            print('Sending SIGKILL...')
            p.kill()
        for pid in pids:
            if pid > 0:
                try:
                    os.kill(pid, SIGKILL)
                    print("Killed %d" % pid)
                except OSError:
                    pass

    logging.debug("Executing: %s" % command2string(cmd))

    stdout = ""
    p = subprocess.Popen(cmd, preexec_fn=os.setpgrp,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if maxwait > 0:
        signal(SIGALRM, alarm_handler)
        alarm(maxwait)
    try:
        stdout, stderr = p.communicate()
        alarm(0)
    except Alarm:
        terminate_subprocess(p, kill_all)
        return -1, stdout
    except KeyboardInterrupt:
        print('\nSlave interrupted by the user, cleaning up...')
        try:
            terminate_subprocess(p, kill_all)
        except KeyboardInterrupt:
            print('\nTerminating piuparts was interrupted... manual cleanup still neccessary.')
            raise
        raise

    ret = p.returncode
    if ret in [124, 137]:
        # process was terminated by the timeout command
        ret = -ret
    return ret, stdout


def create_chroot(config, tarball, distro):
    command = config["piuparts-command"].split()
    if config["piuparts-flags"]:
        command.extend(config["piuparts-flags"].split())
    if "http_proxy" in os.environ:
        command.extend(["--proxy", os.environ["http_proxy"]])
    if config["mirror"]:
        mirror = config["mirror"]
        if config["components"]:
            mirror += " " + config["components"]
        command.extend(["--mirror", mirror])
    if config["tmpdir"]:
        command.extend(["--tmpdir", config["tmpdir"]])
    command.extend(["--arch", config.get_arch()])
    command.extend(["-d", distro])
    command.extend(["-s", tarball + ".new"])
    command.extend(['--no-install-purge-test', '--no-upgrade-test'])
    command.extend(["--apt", "TARBALL"])  # dummy package name

    output_name = tarball + ".log"
    with open(output_name, "we") as output:
        try:
            fcntl.flock(output, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            logging.info("Creation of tarball %s already in progress." % tarball)
        else:
            logging.info("Creating new tarball %s" % tarball)
            output.write(time.strftime("Start: %Y-%m-%d %H:%M:%S %Z\n\n",
                                       time.gmtime()))
            output.write("Executing: " + command2string(command) + "\n\n")
            logging.debug("Executing: " + command2string(command))
            p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in p.stdout:
                output.write(line)
                logging.debug(">> " + line.rstrip())
            p.wait()
            output.write(time.strftime("\nEnd: %Y-%m-%d %H:%M:%S %Z\n",
                                       time.gmtime()))
            if os.path.exists(tarball + ".new"):
                os.rename(tarball + ".new", tarball)
            else:
                logging.error("Tarball creation failed, see %s" % output_name)


def create_file(filename, contents):
    with open(filename, "w") as f:
        f.write(contents)


def main():
    setup_logging(logging.INFO, None)
    signal(SIGHUP, sighup_handler)

    # For supporting multiple architectures and suites, we take command-line
    # argument(s) referring to section(s) in the configuration file.
    # If no argument is given, the "sections" entry from the "global" section
    # is used.
    section_names = []
    global_config = Config(section="global")
    global_config.read(CONFIG_FILE)
    if global_config["proxy"]:
        os.environ["http_proxy"] = global_config["proxy"]
    if len(sys.argv) > 1:
        section_names = sys.argv[1:]
    else:
        section_names = global_config["sections"].split()
        section_names += global_config["basetgz-sections"].split()

    persistent_connection = Slave()
    sections = []
    for section_name in section_names:
        try:
            sections.append(Section(section_name, persistent_connection))
        except MissingSection:
            # ignore unknown sections
            pass

    if not sections:
        logging.error("no sections found")
        return

    # flush logs from previous run
    for section in sections:
        section.run(do_processing=False)

    while True:
        global got_sighup
        test_count = 0

        for section in sorted(sections, key=lambda section: (section.precedence(), section.sleep_until())):
            test_count += section.run(do_processing=(test_count == 0))

        if test_count == 0 and got_sighup:
            # clear SIGHUP state after flushing all sections
            got_sighup = False
            continue

        if test_count == 0:
            # try to recycle old logs
            # round robin recycling of all sections is ensured by the recycle_wait_until timestamps
            idle_until = min([section.sleep_until() for section in sections])
            for section in sorted(sections, key=lambda section: section.sleep_until(recycle=True)):
                test_count += section.run(recycle=True)
                if test_count > 0 and idle_until < time.time():
                    break

        if interrupted:
            raise KeyboardInterrupt

        if test_count == 0 and not got_sighup:
            now = time.time()
            sleep_until = min([now + int(global_config["idle-sleep"])] + [section.sleep_until() for section in sections])
            if (sleep_until > now):
                to_sleep = max(60, sleep_until - now)
                persistent_connection.close()
                logging.info("Nothing to do, sleeping for %d seconds." % to_sleep)
                time.sleep(to_sleep)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('')
        print('Slave interrupted by the user, exiting...')
        sys.exit(1)

# vi:set et ts=4 sw=4 :
