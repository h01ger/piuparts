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


import bz2
import urllib
import cStringIO


import conf
import dependencyparser
import packagesdb


def open_packages_url(url):
    """Open a Packages.bz2 file pointed to by a URL"""
    assert url.endswith(".bz2")
    socket = urllib.urlopen(url)
    decompressor = bz2.BZ2Decompressor()
    file = cStringIO.StringIO()
    while True:
        data = socket.read(1024)
        if not data:
            break
        file.write(decompressor.decompress(data))
    socket.close()
    file.seek(0)
    return file
