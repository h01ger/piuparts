#!/usr/bin/python3
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


"""Distributed piuparts processing, master program

Lars Wirzenius <liw@iki.fi>
"""


import sys
import logging
import os
import fcntl
import time
import random

import piupartslib
from piupartslib.packagesdb import LogfileExists
from piupartslib.conf import MissingSection

from six.moves.urllib.error import URLError


CONFIG_FILE = "/etc/piuparts/piuparts.conf"
DISTRO_CONFIG_FILE = "/etc/piuparts/distros.conf"


log_handler = None


def setup_logging(log_level, log_file_name):
    logger = logging.getLogger()

    global log_handler
    logger.removeHandler(log_handler)

    if log_file_name:
        log_handler = logging.FileHandler(log_file_name)
    else:
        log_handler = logging.StreamHandler(sys.stderr)

    logger.addHandler(log_handler)
    logger.setLevel(log_level)


def timestamp():
    return time.strftime("[%Y-%m-%d %H:%M:%S]")


class Config(piupartslib.conf.Config):

    def __init__(self, section="master", defaults_section=None):
        piupartslib.conf.Config.__init__(self, section,
                                         {
                                         "log-file": None,
                                         "master-directory": ".",
                                         "proxy": None,
                                         "mirror": None,
                                         "distro": None,
                                         "area": None,
                                         "arch": None,
                                         "upgrade-test-distros": None,
                                         "depends-sections": None,
                                         },
                                         defaults_section=defaults_section)


class CommandSyntaxError(Exception):

    def __init__(self, msg):
        self.args = msg,


class ProtocolError(Exception):

    def __init__(self):
        self.args = "EOF, missing space in long part, or other protocol error",


class Protocol:

    def __init__(self, myinput, output):
        self._input = myinput
        self._output = output

    def _readline(self):
        line = self._input.readline()
        logging.debug(">> " + line.rstrip())
        return line

    def _writeline(self, line):
        logging.debug("<< " + line)
        self._output.write(line + "\n")
        self._output.flush()

    def _short_response(self, *words):
        self._writeline(" ".join(words))

    def _read_long_part(self):
        lines = []
        while True:
            line = self._input.readline()
            if not line:
                raise ProtocolError()
            if line == ".\n":
                break
            if line[0] != " ":
                raise ProtocolError()
            lines.append(line[1:])
        return "".join(lines)


class Master(Protocol):

    def __init__(self, myinput, output):
        Protocol.__init__(self, myinput, output)
        self._commands = {
            "section": self._switch_section,
            "recycle": self._recycle,
            "idle": self._idle,
            "status": self._status,
            "reserve": self._reserve,
            "unreserve": self._unreserve,
            "pass": self._pass,
            "fail": self._fail,
            "untestable": self._untestable,

            # debug commands, unstable and undocumented interface
            "_state": self._state,
            "_depends": self._depends,
            "_recursive-depends": self._recursive_depends,
            "_depcycle": self._depcycle,
            "_list": self._list,
        }
        self._section = None
        self._lock = None
        self._writeline("hello")

    def _init_section(self, section):
        if self._lock:
            self._lock.close()

        # clear all settings from a previous section and set defaults
        self._section = None
        self._lock = None
        self._recycle_mode = False
        self._idle_mode = None
        self._idle_stamp = os.path.join(section, "idle.stamp")
        self._package_databases = None
        self._binary_db = None

        config = Config(section=section, defaults_section="global")
        try:
            config.read(CONFIG_FILE)
        except MissingSection:
            return False

        if not os.path.exists(section):
            os.makedirs(section)

        self._lock = open(os.path.join(section, "master.lock"), "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return False

        self._section = section

        logging.debug(timestamp() + " switching logfile")
        logfile = config["log-file"] or os.path.join(section, "master.log")
        setup_logging(logging.DEBUG, logfile)
        logging.debug(timestamp() + " connected")

        # start with a dummy _binary_db (without Packages file), sufficient
        # for submitting finished logs
        self._binary_db = piupartslib.packagesdb.PackagesDB(prefix=section)

        return True

    def _init_db(self):
        if self._package_databases is not None:
            return

        self._package_databases = {}
        self._load_package_database(self._section)
        self._binary_db = self._package_databases[self._section]

    def _load_package_database(self, section):
        if section in self._package_databases:
            return

        config = Config(section=section, defaults_section="global")
        config.read(CONFIG_FILE)
        distro_config = piupartslib.conf.DistroConfig(DISTRO_CONFIG_FILE, config["mirror"])
        db = piupartslib.packagesdb.PackagesDB(prefix=section)
        if self._recycle_mode and self._section == section:
            db.enable_recycling()
        self._package_databases[section] = db
        if config["depends-sections"]:
            deps = config["depends-sections"].split()
            for dep in deps:
                self._load_package_database(dep)
            db.set_dependency_databases([self._package_databases[dep] for dep in deps])
        db.load_packages_urls(
            distro_config.get_packages_urls(
                config.get_distro(),
                    config.get_area(),
                    config.get_arch()))
        if config.get_distro() != config.get_final_distro():
            # take version numbers (or None) from final distro
            db.load_alternate_versions_from_packages_urls(
                distro_config.get_packages_urls(
                    config.get_final_distro(),
                    config.get_area(),
                    config.get_arch()))

    def _clear_idle(self):
        if not self._idle_mode is False:
            self._idle_mode = False
            if os.path.exists(self._idle_stamp):
                os.unlink(self._idle_stamp)

    def _set_idle(self):
        if not self._idle_mode is True:
            self._idle_mode = True
            open(self._idle_stamp, "w").close()
            os.utime(self._idle_stamp, (-1, self._binary_db._stamp))

    def _get_idle_status(self):
        """ Returns number of seconds a cached idle status is still valid, or 0 if not known to be idle. """
        if not os.path.exists(self._idle_stamp):
            return 0
        stamp_mtime = os.path.getmtime(self._idle_stamp)
        ttl = stamp_mtime + 3600 - time.time()
        if ttl <= 0:
            return 0  # stamp expired
        if stamp_mtime < self._binary_db.get_mtime():
            return 0  # stamp outdated
        return ttl + random.randrange(120)

    def do_transaction(self):
        line = self._readline()
        if line:
            parts = line.split()
            if len(parts) > 0:
                command = parts[0]
                args = parts[1:]
                if self._section is None and command != "section":
                    raise CommandSyntaxError("Expected 'section' command, got %s" % command)
                if command in self._commands:
                    self._commands[command](command, args)
                    return True
                else:
                    raise CommandSyntaxError("Unknown command %s" % command)
        return False

    def _check_args(self, count, command, args):
        if len(args) != count:
            raise CommandSyntaxError("Need exactly %d args: %s %s" %
                                     (count, command, " ".join(args)))

    def dump_pkgs(self):
        for st in self._binary_db.get_states():
            for name in self._binary_db.get_pkg_names_in_state(st):
                logging.debug("%s : %s\n" % (st, name))

    def _switch_section(self, command, args):
        self._check_args(1, command, args)
        if self._init_section(args[0]):
            self._short_response("ok")
        elif self._lock is None:
            # unknown section
            self._short_response("error")
        else:
            self._short_response("busy")

    def _recycle(self, command, args):
        self._check_args(0, command, args)
        if self._binary_db.enable_recycling():
            self._idle_stamp = os.path.join(self._section, "recycle.stamp")
            self._recycle_mode = True
            self._short_response("ok")
        else:
            self._short_response("error")

    def _idle(self, command, args):
        self._check_args(0, command, args)
        self._short_response("ok", "%d" % self._get_idle_status())

    def _status(self, command, args):
        self._check_args(0, command, args)
        self._init_db()
        stats = ""
        if self._binary_db._recycle_mode:
            stats += "(recycle) "
        total = 0
        for state in self._binary_db.get_active_states():
            count = len(self._binary_db.get_pkg_names_in_state(state))
            total += count
            stats += "%s=%d " % (state, count)
        stats += "total=%d" % total
        self._short_response("ok", stats)

    def _reserve(self, command, args):
        self._check_args(0, command, args)
        self._init_db()
        package = self._binary_db.reserve_package()
        if package is None:
            self._set_idle()
            self._short_response("error")
        else:
            self._clear_idle()
            self._short_response("ok",
                                 package.name(),
                                 package.test_versions())

    def _unreserve(self, command, args):
        self._check_args(2, command, args)
        self._binary_db.unreserve_package(args[0], args[1])
        self._short_response("ok")

    def _pass(self, command, args):
        self._check_args(2, command, args)
        log = self._read_long_part()
        try:
            self._binary_db.pass_package(args[0], args[1], log)
        except LogfileExists:
            logging.info("Ignoring duplicate submission: %s %s %s"
                         % ("pass", args[0], args[1]))
        self._short_response("ok")

    def _fail(self, command, args):
        self._check_args(2, command, args)
        log = self._read_long_part()
        try:
            self._binary_db.fail_package(args[0], args[1], log)
        except LogfileExists:
            logging.info("Ignoring duplicate submission: %s %s %s"
                         % ("fail", args[0], args[1]))
        self._short_response("ok")

    def _untestable(self, command, args):
        self._check_args(2, command, args)
        log = self._read_long_part()
        try:
            self._binary_db.make_package_untestable(args[0], args[1], log)
        except LogfileExists:
            logging.info("Ignoring duplicate submission: %s %s %s"
                         % ("untestable", args[0], args[1]))
        self._short_response("ok")

    # debug command
    def _state(self, command, args):
        self._check_args(1, command, args)
        self._short_response("ok", self._binary_db.get_package_state(args[0]),
                             self._binary_db.get_test_versions(args[0]))

    # debug command
    def _depends(self, command, args):
        self._check_args(1, command, args)
        if self._binary_db.has_package(args[0]):
            package = self._binary_db.get_package(args[0])
            self._short_response("ok", *package.dependencies())
        else:
            self._short_response("error")

    # debug command
    def _recursive_depends(self, command, args):
        self._check_args(1, command, args)
        if self._binary_db.has_package(args[0]):
            package = self._binary_db.get_package(args[0])
            self._short_response("ok", *self._binary_db._get_recursive_dependencies(package))
        else:
            self._short_response("error")

    # debug command
    def _depcycle(self, command, args):
        self._check_args(1, command, args)
        if self._binary_db.has_package(args[0]):
            self._short_response("ok", *self._binary_db._get_dependency_cycle(args[0]))
        else:
            self._short_response("error")

    # debug command
    def _list(self, command, args):
        self._check_args(1, command, args)
        if args[0] in self._binary_db.get_states():
            self._short_response("ok", *self._binary_db.get_pkg_names_in_state(args[0]))
        else:
            self._short_response("error")


def main():
    setup_logging(logging.INFO, None)
    global_config = Config(section="global")
    global_config.read(CONFIG_FILE)
    if global_config["proxy"]:
        os.environ["http_proxy"] = global_config["proxy"]
    master_directory = global_config["master-directory"]

    if not os.path.exists(master_directory):
        os.makedirs(master_directory)

    os.chdir(master_directory)

    m = Master(sys.stdin, sys.stdout)
    try:
        while m.do_transaction():
            pass
    except URLError as e:
        logging.error("ABORT: URLError: " + str(e.reason))
    except BrokenPipeError:
        logging.error("ABORT: BrokenPipeError")
        logging.debug(timestamp() + " disconnected")
        # https://docs.python.org/3/library/signal.html#note-on-sigpipe
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)

    logging.debug(timestamp() + " disconnected")

if __name__ == "__main__":
    main()

# vi:set et ts=4 sw=4 :
