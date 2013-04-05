# -*- coding: utf-8 -*-

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


"""Parser for Debian package relationship strings

This module contains the class DependencyParser, which parses Debian
package relationship strings (e.g., the Depends header). The class
raises the DependencySyntaxError exception on syntactic errors.
The result uses SimpleDependency objects.

Lars Wirzenius <liw@iki.fi>
"""


import re


class DependencySyntaxError(Exception):

    """Syntax error in package dependency declaration"""

    def __init__(self, msg, cursor):
        self._msg = "Error: %s: %s (text at error: '%s', full text being parsed: '%s')" % \
                    (cursor.get_position(), msg, cursor.get_text(10),
                     cursor.get_full_text())

    def __str__(self):
        return self._msg

    def __repr__(self):
        return self._msg


class _Cursor:

    """Store an input string and a movable location in it"""

    def __init__(self, input):
        self._input = input
        self._len = len(self._input)
        self._pos = 0

    def skip_whitespace(self):
        while self._pos < self._len and self._input[self._pos].isspace():
            self.next()

    def at_end(self):
        """Are we at the end of the input?"""
        self.skip_whitespace()
        return self._pos >= self._len

    def next(self):
        """Move to the next character"""
        if self._pos < self._len:
            self._pos += 1

    def get_char(self):
        """Return current character, None if at end"""
        if self._pos >= self._len:
            return None
        else:
            return self._input[self._pos]

    def get_full_text(self):
        return self._input

    def get_text(self, length):
        """Return up to length characters from the current position"""
        if self._pos >= self._len:
            return ""
        else:
            return self._input[self._pos:self._pos + length]

    def match(self, regexp):
        """Match a regular expression against the current position

        The cursor is advanced by the length of the match, if any.

        """
        m = regexp.match(self._input[self._pos:])
        if m:
            self._pos += len(m.group())
        return m

    def match_literal(self, literal):
        """Match a literal string against the current position.

        Return True and move position if there is a match, else return
        False.

        """
        if self.get_text(len(literal)) == literal:
            self._pos += len(literal)
            return True
        else:
            return False

    def get_position(self):
        """Return current position, as string"""
        return "pos %d" % self._pos


class SimpleDependency:

    """Express simple dependency towards another package"""

    def __init__(self, name, operator, version, arch):
        self.name = name
        self.operator = operator
        self.version = version
        self.arch = arch

    def __repr__(self):
        return "<DEP: %s, %s, %s, %s>" % (self.name, self.operator,
                                          self.version, self.arch)


class DependencyParser:

    """Parse Debian package relationship strings

    Debian packages have a rich language for expressing their
    relationships. See the Debian Policy Manual, chapter 7 ("Declaring
    relationships between packages"). This Python module implements a
    parser for strings expressing such relationships.

    Syntax of dependency fields (Pre-Depends, Depends, Recommends,
    Suggests, Conflicts, Provides, Replaces, Enhances, Build-Depends,
    Build-Depends-Indep, Build-Conflicts, Build-Conflicts-Indep), in a
    BNF-like form:

        depends-field ::= EMPTY | dependency ("," dependency)*
        dependency ::= possible-dependency ("|" possible-dependency)*
        possible-dependency ::= package-name version-dependency?
                                arch-restriction?
        version-dependency ::= "(" relative-operator version-number ")"
        relative-operator ::= "<<" | "<=" | "=" | ">=" | ">>" | "<" | ">"
        version-number ::= epoch? upstream-version debian-revision?
        arch-restriction ::= "[" arch-name arch-name* "]" |
                              "[" "!" arch-name ("!" arch-name)* "]"
        package-name ::= alphanumeric name-char name-char* ":any"?
        epoch ::= integer ":"
        upstream-version ::= alphanumeric version-char*
            -- policy says "should start with digit", but not all packages do
        debian-revision ::= "-" debian-version-char debian-version-char*
        arch-name ::= alphanumeric alphanumeric*
        EMPTY ::= ""
        integer ::= digit digit*
        alphanumeric ::=
            "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j" |
            "k" | "l" | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t" |
            "u" | "v" | "w" | "x" | "y" | "z" | digit
        digit ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
        name-char ::= alphanumeric | "+" | "-" | "." | "_"
        version-char ::= alphanumeric | "." | "+" | "-" | ":" | "~"
        debian-version-char ::= alphanumeric | "." | "+"

    White space can occur between any tokens except inside package-name,
    version-number, or arch-name. Some of the headers restrict the syntax
    somewhat, e.g., Provides does not allow version-dependency, but this is
    not included in the syntax for simplicity.

    Note: Added "_" to name-char, because some packages (type-handling
    in particular) use Provides: headers with bogus package names.

    Note: Added upper case letters to name pattern, since it some of the
    Mozilla localization packages use or used them.

    """

    def __init__(self, input_string):
        self._cursor = _Cursor(input_string)
        self._list = self._parse_dependencies()

    def get_dependencies(self):
        """Return parsed dependencies

        The result is a list of lists of SimpleDependency objects.
        Let's try that again.

        The result is a list of dependencies, corresponding to
        the comma-separated items in the dependency list. Each dependency
        is also a list, or SimpleDependency objects, representing
        alternative ways to fulfill the dependency; in other words,
        items separated by the vertical bar (|).

        For example, "foo, bar | foobar" would result in the following
        list: [[foo], [bar, foobar]].

        """
        return self._list

    def _parse_dependencies(self):
        vlist = []
        dep = self._parse_dependency()
        while dep:
            vlist.append(dep)
            self._cursor.skip_whitespace()
            if self._cursor.at_end():
                break
            if not self._cursor.match_literal(","):
                raise DependencySyntaxError("Expected comma", self._cursor)
            dep = self._parse_dependency()
        return vlist

    def _parse_dependency(self):
        vlist = []
        dep = self._parse_possible_dependency()
        while dep:
            vlist.append(dep)
            self._cursor.skip_whitespace()
            if not self._cursor.match_literal("|"):
                break
            dep = self._parse_possible_dependency()
        return vlist

    def _parse_possible_dependency(self):
        name = self._parse_package_name()
        if not name:
            return None
        (op, version) = self._parse_version_dependency()
        arch = self._parse_arch_restriction()
        return SimpleDependency(name, op, version, arch)

    _name_pat = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+._-]+")
    _any_suffix_pat = re.compile(r":any")

    def _parse_package_name(self):
        self._cursor.skip_whitespace()
        if self._cursor.at_end():
            return None
        m = self._cursor.match(self._name_pat)
        if not m:
            raise DependencySyntaxError("Expected a package name",
                                        self._cursor)
        if self._cursor.match(self._any_suffix_pat):
            pass
        return m.group()

    _op_pat = re.compile(r"(<<|<=|=|>=|>>|<(?![<=])|>(?![>=]))")
    _version_pat = re.compile(r"(?P<epoch>\d+:)?" +
                              r"(?P<upstream>[a-zA-Z0-9+][a-zA-Z0-9.+:~-]*)" +
                              r"(?P<debian>-[a-zA-Z0-9.+]+)?")

    def _parse_version_dependency(self):
        self._cursor.skip_whitespace()
        if self._cursor.get_char() == "(":
            self._cursor.next()

            self._cursor.skip_whitespace()
            opm = self._cursor.match(self._op_pat)
            if not opm:
                raise DependencySyntaxError("Expected a version relation " +
                                            "operator", self._cursor)
            operator = opm.group()
            if operator == "<":
                operator = "<="
            elif operator == ">":
                operator = ">="

            self._cursor.skip_whitespace()
            verm = self._cursor.match(self._version_pat)
            if not verm:
                raise DependencySyntaxError("Expected a version number",
                                            self._cursor)

            self._cursor.skip_whitespace()
            if self._cursor.get_char() != ")":
                raise DependencySyntaxError("Expected ')'", self._cursor)
            self._cursor.next()

            return opm.group(), verm.group()
        else:
            return None, None

    _arch_pat = re.compile(r"!?[a-zA-Z0-9-]+")

    def _parse_arch_restriction(self):
        self._cursor.skip_whitespace()
        if self._cursor.get_char() == "[":
            self._cursor.next()

            vlist = []
            while True:
                self._cursor.skip_whitespace()
                if self._cursor.get_char() == "]":
                    self._cursor.next()
                    break
                m = self._cursor.match(self._arch_pat)
                if not m:
                    raise DependencySyntaxError("Expected architecture name",
                                                self._cursor)
                vlist.append(m.group())

            return vlist
        else:
            return None

# vi:set et ts=4 sw=4 :
