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
import urllib
import ConfigParser
import os
import tempfile

import piupartslib


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

    def __init__(self, section="master"):
        piupartslib.conf.Config.__init__(self, section,
            {
                "log-file": None,
                "packages-url": None,
                "master-directory": ".",
                "known_circular_depends": "",
            }, "")


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
            line = self._readline()
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

    def __init__(self, input, output, packages_file, known_circular_depends="", section=None):
        Protocol.__init__(self, input, output)
        self._commands = {
            "reserve": self._reserve,
            "unreserve": self._unreserve,
            "pass": self._pass,
            "fail": self._fail,
            "untestable": self._untestable,
        }
        self._binary_db = piupartslib.packagesdb.PackagesDB(prefix=section)
        self._binary_db.create_subdirs()
        self._binary_db.read_packages_file(packages_file)
        my_known_circular_depends = []
        for kcd in known_circular_depends.split():
          my_known_circular_depends.append(kcd)
          logging.debug("circular depends: " + kcd)
        try:
          self._binary_db.set_known_circular_depends(my_known_circular_depends)
        except:
          pass
        self._writeline("hello")

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

    def _reserve(self, command, args):
        self._check_args(0, command, args)
        package = self._binary_db.reserve_package()
        if package is None:
            self._short_response("error")
        else:
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
        self._binary_db.pass_package(args[0], args[1], log)
        self._short_response("ok")

    def _fail(self, command, args):
        self._check_args(2, command, args)
        log = self._read_long_part()
        self._binary_db.fail_package(args[0], args[1], log)
        self._short_response("ok")

    def _untestable(self, command, args):
        self._check_args(2, command, args)
        log = self._read_long_part()
        self._binary_db.make_package_untestable(args[0], args[1], log)
        self._short_response("ok")

def main():
    # piuparts-master is always called by the slave with a section as argument
    if len(sys.argv) == 2:
        global_config = Config(section="global")
        global_config.read(CONFIG_FILE)
        master_directory = global_config["master-directory"]

        section = sys.argv[1]
        config = Config(section=section)
        config.read(CONFIG_FILE)
    
        setup_logging(logging.DEBUG, config["log-file"])

        if not os.path.exists(os.path.join(master_directory, section)):
          os.makedirs(os.path.join(master_directory, section))
    
        logging.info("Fetching %s" % config["packages-url"])
        packages_file = piupartslib.open_packages_url(config["packages-url"])
        known_circular_depends = config["known_circular_depends"]

        m = Master(sys.stdin, sys.stdout, packages_file, known_circular_depends, section=section)
        while m.do_transaction():
            pass
        packages_file.close()
    else:
        print 'piuparts-master needs to be called with a valid sectionname as argument, exiting...'
        sys.exit(1)

if __name__ == "__main__":
    main()
