# -*- coding: utf-8 -*-

# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# Copyright © 2013-2015 Andreas Beckmann (anbe@debian.org)
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


import bz2
import lzma
import zlib

from six.moves import urllib


class DecompressedStream():

    def __init__(self, fileobj, decompressor=None):
        self._input = fileobj
        self._decompressor = decompressor
        self._buffer = ""
        self._line_buffer = []
        self._i = 0
        self._end = 0

    def _refill(self):
        if self._input is None:
            return False
        while True:
            # repeat until decompressor yields some output or input is exhausted
            chunk = self._input.read(4096)
            if not chunk:
                self.close()
                return False
            if self._decompressor:
                chunk = self._decompressor.decompress(chunk)
            if isinstance(chunk, bytes):
                chunk = chunk.decode()
            self._buffer = self._buffer + chunk
            if chunk:
                return True

    def readline(self):
        while not self._i < self._end:
            self._i = self._end = 0
            self._line_buffer = None
            empty = not self._refill()
            if not self._buffer:
                break
            self._line_buffer = self._buffer.splitlines(True)
            self._end = len(self._line_buffer)
            self._buffer = ""
            if not self._line_buffer[-1].endswith("\n") and not empty:
                self._buffer = self._line_buffer[-1]
                self._end = self._end - 1
        if self._i < self._end:
            self._i = self._i + 1
            return self._line_buffer[self._i - 1]
        return ""

    def close(self):
        if self._input:
            self._input.close()
        self._input = self._decompressor = None


def open_packages_url(url):
    """Open a Packages.bz2 file pointed to by a URL"""
    socket = None
    error = None
    for ext in ['.xz', '.bz2', '.gz', '']:
        try:
            socket = urllib.request.urlopen(url + ext)
        except urllib.error.HTTPError as e:
            error = e
        else:
            break
    else:
        raise error
    url = socket.geturl()
    if ext == '.bz2':
        decompressor = bz2.BZ2Decompressor()
        decompressed = DecompressedStream(socket, decompressor)
    elif ext == '.gz':
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        decompressed = DecompressedStream(socket, decompressor)
    elif ext == '.xz':
        decompressor = lzma.LZMADecompressor()
        decompressed = DecompressedStream(socket, decompressor)
    elif ext == '':
        decompressed = socket
    else:
        raise Exception('Unknown compression: {}'.format(ext))
    return (url, decompressed)

# vi:set et ts=4 sw=4 :
