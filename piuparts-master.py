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


"""Distributed piuparts processing, master program

Lars Wirzenius <liw@iki.fi>
"""


import sys
import logging
import ConfigParser
import os
import fcntl
import time

import piupartslib
from piupartslib.packagesdb import LogfileExists


CONFIG_FILE = "/etc/piuparts/piuparts.conf"


def setup_logging(log_level, log_file_name):
    logger = logging.getLogger()
    logger.setLevel(log_level)

    if log_file_name:
        handler = logging.FileHandler(log_file_name)
    else:
        handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)


class Config(piupartslib.conf.Config):

    def __init__(self, section="master", defaults_section=None):
        piupartslib.conf.Config.__init__(self, section,
            {
                "log-file": None,
                "master-directory": ".",
                "mirror": None,
                "distro": None,
                "area": None,
                "arch": None,
                "upgrade-test-distros": None,
            },
            defaults_section=defaults_section)


class CommandSyntaxError(Exception):

    def __init__(self, msg):
        self.args = msg


class ProtocolError(Exception):

    def __init__(self):
        self.args = "EOF, missing space in long part, or other protocol error"


class Protocol:

    def __init__(self, input, output):
        self._input = input
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

    _failed_states = (
        "failed-testing",
    )
    _passed_states = (
        "successfully-tested",
    )

    def __init__(self, input, output, section):
        Protocol.__init__(self, input, output)
        self._commands = {
            "recycle": self._recycle,
            "status": self._status,
            "reserve": self._reserve,
            "unreserve": self._unreserve,
            "pass": self._pass,
            "fail": self._fail,
            "untestable": self._untestable,
        }
        self._section = section
        self._recycle_mode = False
        self._idle_mode = None
        self._idle_stamp = os.path.join(section, "idle.stamp")
        self._package_databases = None
        # start with a dummy _binary_db (without Packages file), sufficient
        # for submitting finished logs
        self._binary_db = piupartslib.packagesdb.PackagesDB(prefix=section)
        self._writeline("hello")

    def _init_db(self):
        if self._package_databases is not None:
            return

        self._package_databases = {}
        self._load_package_database(self._section)
        self._binary_db = self._package_databases[self._section]
        if self._recycle_mode:
            self._binary_db.enable_recycling()

    def _load_package_database(self, section):
        config = Config(section=section, defaults_section="global")
        config.read(CONFIG_FILE)
        db = piupartslib.packagesdb.PackagesDB(prefix=section)
        self._package_databases[section] = db
        logging.info("Fetching %s" % config.get_packages_url())
        packages_file = piupartslib.open_packages_url(config.get_packages_url())
        db.read_packages_file(packages_file)
        packages_file.close()

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


    def do_transaction(self):
        line = self._readline()
        if line:
            parts = line.split()
            if len(parts) > 0:
                command = parts[0]
                args = parts[1:]
                self._commands[command](command, args)
            return True
        else:
            return False

    def _check_args(self, count, command, args):
        if len(args) != count:
            raise CommandSyntaxError("Need exactly %d args: %s %s" %
                                     (count, command, " ".join(args)))
    def dump_pkgs(self):
         for st in self._binary_db.get_states():
            for name in self._binary_db.get_pkg_names_in_state(st):
                logging.debug("%s : %s\n" % (st,name))

    def _recycle(self, command, args):
        self._check_args(0, command, args)
        if self._binary_db.enable_recycling():
            self._idle_stamp = os.path.join(self._section, "recycle.stamp")
            self._recycle_mode = True
            self._short_response("ok")
        else:
            self._short_response("error")

    def _status(self, command, args):
        self._check_args(0, command, args)
        self._init_db()
        stats = ""
        if self._binary_db._recycle_mode:
            stats += "(recycle) "
        total = 0
        for state in self._binary_db.get_states():
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
                                 package["Package"],
                                 package["Version"])

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


def main():
    # piuparts-master is always called by the slave with a section as argument
    if len(sys.argv) == 2:
        global_config = Config(section="global")
        global_config.read(CONFIG_FILE)
        master_directory = global_config["master-directory"]

        section = sys.argv[1]
        config = Config(section=section, defaults_section="global")
        config.read(CONFIG_FILE)

        setup_logging(logging.DEBUG, config["log-file"])

        if not os.path.exists(os.path.join(master_directory, section)):
            os.makedirs(os.path.join(master_directory, section))

        os.chdir(master_directory)

        lock = open(os.path.join(section, "master.lock"), "we")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print 'busy'
            sys.exit(0)

        m = Master(sys.stdin, sys.stdout, section)
        while m.do_transaction():
            pass
    else:
        print 'piuparts-master needs to be called with a valid sectionname as argument, exiting...'
        sys.exit(1)

if __name__ == "__main__":
    main()

# vi:set et ts=4 sw=4 :
