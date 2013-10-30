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


import bz2
import gzip
import urllib2
import cStringIO


import conf
import dependencyparser
import packagesdb


def open_packages_url(url):
    """Open a Packages.bz2 file pointed to by a URL"""
    assert url.endswith(".bz2")
    url = url[:-len(".bz2")]
    socket = None
    for ext in ['.bz2', '.gz']:
        try:
            socket = urllib2.urlopen(url + ext)
        except urllib2.HTTPError as httperror:
            pass
        else:
            break
    if socket is None:
        raise httperror
    if ext == '.bz2':
        decompressed = cStringIO.StringIO()
        decompressor = bz2.BZ2Decompressor()
        while True:
            data = socket.read(1024)
            if not data:
                socket.close()
                break
            decompressed.write(decompressor.decompress(data))
        decompressed.seek(0)
    elif ext == '.gz':
        compressed = cStringIO.StringIO()
        while True:
            data = socket.read(1024)
            if not data:
                socket.close()
                break
            compressed.write(data)
        compressed.seek(0)
        decompressed = gzip.GzipFile(fileobj=compressed)
    else:
        raise ext
    return decompressed

# vi:set et ts=4 sw=4 :
