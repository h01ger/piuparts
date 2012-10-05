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
import stat
import time
import logging
from signal import alarm, signal, SIGALRM, SIGINT, SIGKILL, SIGHUP
import subprocess
import fcntl
import random
import ConfigParser

import piupartslib.conf
import piupartslib.packagesdb


CONFIG_FILE = "/etc/piuparts/piuparts.conf"
MAX_WAIT_TEST_RUN = 45*60

interrupted = False
old_sigint_handler = None
got_sighup = False

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

    def __init__(self, section="slave", defaults_section=None):
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
            {
                "sections": "slave",
                "slave-directory": section,
                "idle-sleep": 300,
                "max-tgz-age": 2592000,
                "min-tgz-retry-delay": 21600,
                "master-host": None,
                "master-user": None,
                "master-directory": ".",
                "master-command": None,
                "log-file": "piuparts-master.log",
                "mirror": None,
                "piuparts-command": "sudo piuparts",
                "piuparts-flags": "",
                "distro": None,
                "area": None,
                "chroot-tgz": None,
                "upgrade-test-distros": None,
                "upgrade-test-chroot-tgz": None,
                "max-reserved": 1,
                "debug": "no",
                "keep-sources-list": "no",
                "arch": None,
                "precedence": "1",
            },
            defaults_section=defaults_section)


class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

def sigint_handler(signum, frame):
    global interrupted
    interrupted = True
    print '\nSlave interrupted by the user, waiting for the current test to finish.'
    print 'Press Ctrl-C again to abort now.'
    signal(SIGINT, old_sigint_handler)

def sighup_handler(signum, frame):
    global got_sighup
    got_sighup = True
    print 'SIGHUP: Will flush finished logs.'


class MasterIsBusy(Exception):

    def __init__(self):
        self.args = "Master is busy, retry later"


class MasterNotOK(Exception):

    def __init__(self):
        self.args = "Master did not respond with 'ok'"


class MasterDidNotGreet(Exception):

    def __init__(self):
        self.args = "Master did not start with 'hello'"


class MasterCommunicationFailed(Exception):

    def __init__(self):
        self.args = "Communication with master failed"


class MasterIsCrazy(Exception):

    def __init__(self):
        self.args = "Master said something unexpected"


class MasterCantRecycle(Exception):

    def __init__(self):
        self.args = "Master has nothing to recycle"


class Slave:

    def __init__(self):
        self._to_master = None
        self._from_master = None
        self._master_host = None
        self._master_user = None
        self._master_directory = "."
        self._master_command = None

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
            user = self._master_user + "@"
        else:
            user = ""
        ssh_cmdline = "cd %s; %s 2> %s.$$ && rm %s.$$" % \
                      (self._master_directory or ".",
                      self._master_command, log_file, log_file)
        p = subprocess.Popen(["ssh", user + self._master_host, ssh_cmdline],
                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._to_master = p.stdin
        self._from_master = p.stdout
        line = self._readline()
        if line == "busy\n":
            raise MasterIsBusy()
        if line != "hello\n":
            raise MasterDidNotGreet()
        logging.debug("Connected to master")

    def close(self):
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
        if words and words[0] == "ok":
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
        return os.path.join("reserved",  "%s_%s.log" % (name, version))

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

    def __init__(self, section):
        self._config = Config(section=section, defaults_section="global")
        self._config.read(CONFIG_FILE)
        self._error_wait_until = 0
        self._idle_wait_until = 0
        self._recycle_wait_until = 0
        self._slave_directory = os.path.abspath(self._config["slave-directory"])
        if not os.path.exists(self._slave_directory):
            os.makedirs(self._slave_directory)

        if self._config["debug"] in ["yes", "true"]:
            self._logger = logging.getLogger()
            self._logger.setLevel(logging.DEBUG)

        if self._config["chroot-tgz"] and not self._config["distro"]:
          logging.info("The option --chroot-tgz needs --distro.")

        if int(self._config["max-reserved"]) > 0:
            self._check_tarball()

        for rdir in ["new", "pass", "fail", "untestable", "reserved"]:
            rdir = os.path.join(self._slave_directory, rdir)
            if not os.path.exists(rdir):
                os.mkdir(rdir)

        self._slave = Slave()

    def _connect_to_master(self, recycle=False):
        self._slave.set_master_host(self._config["master-host"])
        self._slave.set_master_user(self._config["master-user"])
        self._slave.set_master_directory(self._config["master-directory"])
        self._slave.set_master_command(self._config["master-command"] + " " + self._config.section)
        self._slave.connect_to_master(self._config["log-file"])
        if recycle:
            self._slave.enable_recycling()

    def _check_tarball(self):
        oldcwd = os.getcwd()
        os.chdir(self._slave_directory)

        tarball = self._config["chroot-tgz"]
        if tarball:
            create_or_replace_chroot_tgz(self._config, tarball,
                                         self._config["distro"])

        tarball = self._config["upgrade-test-chroot-tgz"]
        if self._config["upgrade-test-distros"] and tarball:
            create_or_replace_chroot_tgz(self._config, tarball,
                                         self._config["upgrade-test-distros"].split()[0])

        os.chdir(oldcwd)

    def _count_submittable_logs(self):
        files = 0
        for logdir in ["pass", "fail", "untestable"]:
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

        if not do_processing and self._count_submittable_logs() == 0:
            return 0

        logging.info("-------------------------------------------")
        action = "Running"
        if recycle:
            action = "Recycling"
        if not do_processing:
            action = "Flushing"
        logging.info("%s section %s (precedence=%d)" \
                     % (action, self._config.section, self.precedence()))
        self._config = Config(section=self._config.section, defaults_section="global")
        self._config.read(CONFIG_FILE)

        if int(self._config["max-reserved"]) == 0:
            logging.info("disabled")
            self._error_wait_until = time.time() + 12 * 3600
            return 0

        if not self._config["distro"] and (not self._config["upgrade-test-distros"] \
                                           or not self._config["upgrade-test-distros"].split()):
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
                if self._talk_to_master(fetch=do_processing, recycle=recycle):
                    if do_processing:
                        if not self._slave.get_reserved():
                            self._idle_wait_until = time.time() + int(self._config["idle-sleep"])
                            if recycle:
                                self._recycle_wait_until = self._idle_wait_until + 3600
                        else:
                            processed = self._process()
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
        except (MasterDidNotGreet, MasterIsCrazy, MasterCommunicationFailed):
            logging.error("connection to master failed")
            self._error_wait_until = time.time() + 900
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
            except (MasterIsCrazy, MasterCommunicationFailed):
                logging.error("communication with master failed")
                self._error_wait_until = time.time() + 900
            else:
                return True
        finally:
            self._slave.close()
        return False


    def _process(self):
        if self._config["distro"]:
            distros = [self._config["distro"]]
        else:
            distros = []

        if self._config["upgrade-test-distros"]:
            distros += self._config["upgrade-test-distros"].split()

        packages_files = {}
        for distro in distros:
            if distro not in packages_files:
                try:
                    packages_files[distro] = fetch_packages_file(self._config, distro)
                except IOError:
                    logging.error("failed to fetch packages file for %s" % distro)
                    self._error_wait_until = time.time() + 900
                    return 0
        if self._config["distro"]:
            packages_file = packages_files[self._config["distro"]]
        else:
            packages_file = packages_files[distro]

        test_count = 0
        self._check_tarball()
        for package_name, version in self._slave.get_reserved():
            if got_sighup:
                break
            test_count += 1
            if package_name in packages_file:
                package = packages_file[package_name]
                if version == package["Version"]:
                    test_package(self._config, package, packages_files)
                else:
                    logging.info("Cannot test %s/%s %s" % (self._config.section, package_name, version))
                    create_file(os.path.join("untestable",
                                log_name(package_name, version)),
                                "%s %s not found, %s is available\n" \
                                    % (package_name, version, package["Version"]))
            else:
                logging.info("Cannot test %s/%s %s" % (self._config.section, package_name, version))
                create_file(os.path.join("untestable",
                            log_name(package_name, version)),
                            "Package %s not found\n" % package_name)
            self._slave.forget_reserved(package_name, version)
            if interrupted:
                break
        self._talk_to_master(unreserve=interrupted)
        if interrupted:
            raise KeyboardInterrupt
        return test_count


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


def run_test_with_timeout(cmd, maxwait, kill_all=True):

    def terminate_subprocess(p, kill_all):
        pids = [p.pid]
        if kill_all:
            ps = subprocess.Popen(["ps", "--no-headers", "-o", "pid", "--ppid", "%d" % p.pid],
                                  stdout = subprocess.PIPE)
            stdout, stderr = ps.communicate()
            pids.extend([int(pid) for pid in stdout.split()])
        if p.poll() is None:
            print 'Sending SIGINT...'
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
            print 'Sending SIGTERM...'
            p.terminate()
            # piuparts has 5 seconds to clean up after SIGTERM
            for i in range(10):
                time.sleep(0.5)
                if p.poll() is not None:
                    break
        if p.poll() is None:
            print 'Sending SIGKILL...'
            p.kill()
        for pid in pids:
            if pid > 0:
                try:
                    os.kill(pid, SIGKILL)
                    print "Killed %d" % pid
                except OSError:
                    pass

    logging.debug("Executing: %s" % " ".join(cmd))

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
        return -1,stdout
    except KeyboardInterrupt:
        print '\nSlave interrupted by the user, cleaning up...'
        try:
            terminate_subprocess(p, kill_all)
        except KeyboardInterrupt:
            print '\nTerminating piuparts was interrupted... manual cleanup still neccessary.'
            raise
        raise

    return p.returncode,stdout


def test_package(config, package, packages_files):
    global old_sigint_handler
    old_sigint_handler = signal(SIGINT, sigint_handler)

    pname = package["Package"]
    pvers = package["Version"]
    logging.info("Testing package %s/%s %s" % (config.section, pname, pvers))

    output_name = log_name(pname, pvers)
    logging.debug("Opening log file %s" % output_name)
    new_name = os.path.join("new", output_name)
    output = file(new_name, "we")
    output.write(time.strftime("Start: %Y-%m-%d %H:%M:%S %Z\n",
                               time.gmtime()))
    output.write("\n")
    package.dump(output)
    output.write("\n")

    base_command = config["piuparts-command"].split()
    if config["piuparts-flags"]:
        base_command.extend(config["piuparts-flags"].split())
    if config["mirror"]:
        base_command.extend(["--mirror", config["mirror"]])

    ret = 0
    if config["chroot-tgz"]:
        command = base_command[:]
        command.extend(["-b", config["chroot-tgz"]])
        command.extend(["-d", config["distro"]])
        command.append("--no-upgrade-test")
        if config["keep-sources-list"] in ["yes", "true"]:
            command.append("--keep-sources-list")
        command.extend(["--apt", "%s=%s" % (pname, pvers)])

        output.write("Executing: %s\n" % " ".join(command))
        ret,f = run_test_with_timeout(command, MAX_WAIT_TEST_RUN)
        if not f or f[-1] != '\n':
            f += '\n'
        output.write(f)
        lastline = f.split('\n')[-2]
        if ret < 0:
            output.write(" *** Process KILLED - exceed maximum run time ***\n")
        elif not "piuparts run ends" in lastline:
            ret += 1024
            output.write(" *** PIUPARTS OUTPUT INCOMPLETE ***\n");

    if ret == 0 and config["upgrade-test-chroot-tgz"] and upgrade_testable(config, package, packages_files):
        command = base_command[:]
        command.extend(["-b", config["upgrade-test-chroot-tgz"]])
        for distro in config["upgrade-test-distros"].split():
            command.extend(["-d", distro])
        command.extend(["--apt", "%s=%s" % (pname, pvers)])

        output.write("Executing: %s\n" % " ".join(command))
        ret,f = run_test_with_timeout(command, MAX_WAIT_TEST_RUN)
        if not f or f[-1] != '\n':
            f += '\n'
        output.write(f)
        lastline = f.split('\n')[-2]
        if ret < 0:
            output.write(" *** Process KILLED - exceed maximum run time ***\n")
        elif not "piuparts run ends" in lastline:
            ret += 1024
            output.write(" *** PIUPARTS OUTPUT INCOMPLETE ***\n");

    output.write("\n")
    output.write("ret=%d\n" % ret)
    output.write(time.strftime("End: %Y-%m-%d %H:%M:%S %Z\n",
                               time.gmtime()))
    output.close()
    if ret != 0:
        subdir = "fail"
    else:
        subdir = "pass"
    os.rename(new_name, os.path.join(subdir, output_name))
    logging.debug("Done with %s: %s (%d)" % (output_name, subdir, ret))
    signal(SIGINT, old_sigint_handler)


def create_chroot(config, tarball, distro):
    output_name = tarball + ".log"
    logging.debug("Opening log file %s" % output_name)
    logging.info("Creating new tarball %s" % tarball)
    command = config["piuparts-command"].split()
    if config["piuparts-flags"]:
        command.extend(config["piuparts-flags"].split())
    if config["mirror"]:
        command.extend(["--mirror", config["mirror"]])
    command.extend(["-d", distro])
    command.extend(["-s", tarball + ".new"])
    command.extend(["--apt", "dpkg"])
    output = file(output_name, "w")
    output.write(time.strftime("Start: %Y-%m-%d %H:%M:%S %Z\n\n",
                               time.gmtime()))
    output.write("Executing: " + " ".join(command) + "\n\n")
    logging.debug("Executing: " + " ".join(command))
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in p.stdout:
        output.write(line)
        logging.debug(">> " + line.rstrip())
    p.wait()
    output.write(time.strftime("\nEnd: %Y-%m-%d %H:%M:%S %Z\n",
                               time.gmtime()))
    output.close()
    if os.path.exists(tarball + ".new"):
        os.rename(tarball + ".new", tarball)

def create_or_replace_chroot_tgz(config, tgz, distro):
    forced = 0
    if os.path.exists(tgz):
        max_tgz_age = int(config["max-tgz-age"])
        min_tgz_retry_delay = int(config["min-tgz-retry-delay"])
        now = time.time()
        statobj = os.stat(tgz)
        # stat.ST_MTIME is actually time file was initially created
        age = now - statobj[stat.ST_MTIME]
        logging.info("Check-replace %s: age=%d vs. max=%d" % (tgz, age, max_tgz_age))
        if age > max_tgz_age:
            logging.info("Limit-replace %s: last-retry=%d vs. min=%d" % (tgz, now - statobj[stat.ST_CTIME], min_tgz_retry_delay))
            # stat.ST_CTIME is time created OR last renamed
            if min_tgz_retry_delay is None or now - statobj[stat.ST_CTIME] > min_tgz_retry_delay:
                os.rename(tgz, tgz + ".old")
                forced = 1
                logging.info("%s too old.  Renaming to force re-creation" % tgz)
    if not os.path.exists(tgz):
        create_chroot(config, tgz, distro)
        if forced:
            if not os.path.exists(tgz):
                os.rename(tgz + ".old", tgz)
                logging.info("Failed to create ... reverting to old %s" % tgz)
            else:
                os.unlink(tgz + ".old")

def fetch_packages_file(config, distro):
    packages_url = config.get_packages_url(distro)
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
    signal(SIGHUP, sighup_handler)

    # For supporting multiple architectures and suites, we take command-line
    # argument(s) referring to section(s) in the configuration file.
    # If no argument is given, the "sections" entry from the "global" section
    # is used.
    section_names = []
    global_config = Config(section="global")
    global_config.read(CONFIG_FILE)
    if len(sys.argv) > 1:
        section_names = sys.argv[1:]
    else:
        section_names = global_config["sections"].split()

    sections = [Section(section_name)
                for section_name in section_names]

    while True:
        global got_sighup
        test_count = 0

        for section in sorted(sections, key=lambda section: (section.precedence(), section.sleep_until())):
            test_count += section.run(do_processing=(test_count == 0 and not got_sighup))

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

        if test_count == 0:
            now = time.time()
            sleep_until = min([now + int(global_config["idle-sleep"])] + [section.sleep_until() for section in sections])
            if (sleep_until > now):
                to_sleep = max(60, sleep_until - now)
                logging.info("Nothing to do, sleeping for %d seconds." % to_sleep)
                time.sleep(to_sleep)


if __name__ == "__main__":
  try:
     main()
  except KeyboardInterrupt:
     print ''
     print 'Slave interrupted by the user, exiting...'
     sys.exit(1)

# vi:set et ts=4 sw=4 :
