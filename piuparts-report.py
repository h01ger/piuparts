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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA


"""Create HTML reports of piuparts log files

Lars Wirzenius <liw@iki.fi>
"""


import os
import sys
import time
import logging
import ConfigParser
import urllib
import shutil


import piupartslib


CONFIG_FILE = "piuparts-report.conf"


LOG_LIST_PAGE_TEMPLATE = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
    <title>%(title)s</title>
    <link rel="stylesheet" href="piuparts.css" type="text/css"/>
</head>
<body>
<div class="main">
<h1>%(title)s</h1>
<p>%(preface)s</p>
<p>The list has %(count)d packages, with %(versioncount)s total versions.
This page was generated: %(time)s.</p>
<ul>
%(loglist)s
</ul>
</div>
</body>
</html>
"""


STATS_PAGE_TEMPLATE = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
    <title>Statistics of packages</title>
    <link rel="stylesheet" href="piuparts.css" type="text/css"/>
</head>
<body>
<div class="main">
<h1>Statistics of packages</h1>
<p>This page contains some statistics about packages piuparts is looking
at.</p>
%(table)s
</div>
</body>
</html>
"""


STATE_PAGE_TEMPLATE = """
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
    <title>%(state)s</title>
    <link rel="stylesheet" href="piuparts.css" type="text/css"/>
</head>
<body>
<div class="main">
<h1>Packages in state "%(state)s"</h1>
<p>This page contains a list of package in state "%(state)s".</p>
%(list)s
</div>
</body>
</html>
"""


title_by_dir = {
    "pass": "PASSED piuparts logs",
    "fail": "Failed UNREPORTED piuparts logs",
    "bugged": "Failed REPORTED piuparts logs",
    "fixed": "Failed and FIXED packages",
    "reserved": "RESERVED packages",
    "untestable": "UNTESTABLE packages",
}


desc_by_dir = {
    "pass": "Log files for packages that have PASSED testing.",
    "fail": "Log files for packages that have FAILED testing. " +
            "Bugs have not yet been reported.",
    "bugged": "Log files for packages that have FAILED testing. " +
              "Bugs have been reported, but not yet fixed.",
    "fixed": "Log files for packages that have FAILED testing, but for " +
             "which a fix has been made.",
    "reserved": "Packages that are RESERVED for testing on a node in a " +
                "distributed piuparts network.",
    "untestable": "Log files for packages that have are UNTESTABLE with " +
                  "piuparts at the current time.",
}

state_by_dir = {
    "pass": "successfully-tested",
    "fail": "failed-testing",
    "bugged": "failed-testing",
    "fixed": "fix-not-yet-tested",
    "reserved": "waiting-to-be-tested",
    "untestable": "dependency-cannot-be-tested",
}


class Config(piupartslib.conf.Config):

    def __init__(self, section="report"):
        piupartslib.conf.Config.__init__(self, section,
            {
                "output-dir": "html",
                "index-page": "index.html",
                "packages-url": None,
            },
            ["output-dir", "packages-url"])


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


def html_protect(str):
    str = "&amp;".join(str.split("&"))
    str = "&lt;".join(str.split("<"))
    str = "&gt;".join(str.split(">"))
    str = "&#34;".join(str.split('"'))
    str = "&#39;".join(str.split("'"))
    if str == "unknown-package":
      str = "<b>unknown-package</b>"
    return str


def write_log_list_page(filename, title, preface, logs):
    packages = {}
    for pathname, package, version in logs:
        packages[package] = packages.get(package, []) + [(pathname, version)]

    names = packages.keys()
    names.sort()
    lines = []
    version_count = 0
    for package in names:
        versions = []
        for pathname, version in packages[package]:
            version_count += 1
            versions.append("<a href='%s'>%s</a>" % 
                            (html_protect(pathname), 
                             html_protect(version)))
        line = "<li>%s %s</li>\n" % (html_protect(package), 
                                     ", ".join(versions))
        lines.append(line)

    f = file(filename, "w")
    f.write(LOG_LIST_PAGE_TEMPLATE % 
            {
                "title": html_protect(title),
                "preface": preface,
                "loglist": "".join(lines),
                "count": len(logs),
                "versioncount": version_count,
                "time": time.strftime("%Y-%m-%d %H:%M:%S %z"),
            })
    f.close()


def print_by_dir(config, logs_by_dir):
    for dir in logs_by_dir:
        list = []
        for basename in logs_by_dir[dir]:
            assert basename.endswith(".log")
            assert "_" in basename
            package, version = basename[:-len(".log")].split("_")
            list.append((os.path.join(dir, basename), package, version))
        write_log_list_page(os.path.join(config["output-dir"], dir + ".html"),
                            title_by_dir[dir], 
                            desc_by_dir[dir], list)


def find_log_files(dir):
    return [name for name in os.listdir(dir) if name.endswith(".log")]


def update_file(source, target):
    if os.path.exists(target):
        aa = os.stat(source)
        bb = os.stat(target)
        if aa.st_size == bb.st_size and aa.st_mtime < bb.st_mtime:
            return
    shutil.copyfile(source, target)


def copy_logs(logs_by_dir, output_dir):
    for dir in logs_by_dir:
        fulldir = os.path.join(output_dir, dir)
        if not os.path.exists(fulldir):
            os.makedirs(fulldir)
        for basename in logs_by_dir[dir]:
            source = os.path.join(dir, basename)
            target = os.path.join(fulldir, basename)
            update_file(source, target)


def remove_old_logs(logs_by_dir, output_dir):
    for dir in logs_by_dir:
        fulldir = os.path.join(output_dir, dir)
        if os.path.exists(fulldir):
            for basename in os.listdir(fulldir):
                if basename not in logs_by_dir[dir]:
                    os.remove(os.path.join(fulldir, basename))


def write_file(filename, contents):
    f = file(filename, "w")
    f.write(contents)
    f.close()


def main():
    # For supporting multiple architectures and suites, we take a command-line
    # argument referring to a section in the reports configuration file.  For
    # backwards compatibility, if no argument is given, the "report" section is
    # assumed.
    if len(sys.argv) == 2:
        section = sys.argv[1]
        config = Config(section=section)
    else:
        section = None
        config = Config()
    config.read(CONFIG_FILE)

    setup_logging(logging.DEBUG, None)
        
    logging.debug("Finding log files")
    dirs = ["pass", "fail", "bugged", "fixed", "reserved", "untestable"]
    logs_by_dir = {}
    for dir in dirs:
        logs_by_dir[dir] = find_log_files(dir)

    logging.debug("Copying log files")
    if not os.path.exists(config["output-dir"]):
        os.makedirs(config["output-dir"])
    copy_logs(logs_by_dir, config["output-dir"])

    logging.debug("Removing old log files")
    remove_old_logs(logs_by_dir, config["output-dir"])

    logging.debug("Writing per-dir HTML pages")
    print_by_dir(config, logs_by_dir)
    
    if os.path.exists(config["index-page"]):
        logging.debug("Writing index page")
        update_file(config["index-page"], 
                    os.path.join(config["output-dir"], "index.html"))

    logging.debug("Loading and parsing Packages file")
    if 1:
        logging.info("Fetching %s" % config["packages-url"])
        packages_file = piupartslib.open_packages_url(config["packages-url"])
    else:
        packages_file = file("Packages")
    st = piupartslib.packagesdb.PackagesDB()
    st.read_packages_file(packages_file)
    packages_file.close()

    logging.debug("Writing package statistics page")    
    table = "<table>\n"
    for state in st.get_states():
        dirlink = "<td>"
        for dir in dirs:
          if state_by_dir[dir] == state:
            dirlink += "<a href='%s.html'>%s</a> logs<br>" % (dir, html_protect(dir))
        dirlink += "</td>"
        table += ("<tr><td><a href='state-%s.html'>%s</a></td>" +
                  "<td>%d</td>%s</tr>\n") % \
                    (html_protect(state), html_protect(state),
                     len(st.get_packages_in_state(state)),
                     dirlink)
    table += "<tr> <th>Total</th> <th>%d</th></tr>\n" % \
                st.get_total_packages()
    table += "</table>\n"
    write_file(os.path.join(config["output-dir"], "stats.html"),
               STATS_PAGE_TEMPLATE % { "table": table })

    for state in st.get_states():
        logging.debug("Writing page for %s" % state)
        list = "<ul>\n"
        for package in st.get_packages_in_state(state):
            list += "<li>%s (%s)" % (html_protect(package["Package"]),
                                     html_protect(package["Maintainer"]))
            if package.dependencies():
                list += "\n<ul>\n"
                for dep in package.dependencies():
                    list += "<li>dependency %s is %s</li>\n" % \
                            (html_protect(dep), 
                             html_protect(st.state_by_name(dep)))
                list += "</ul>\n"
            list += "</li>\n"
        list += "</ul>\n"
        write_file(os.path.join(config["output-dir"], 
                                "state-%s.html" % state),
                   STATE_PAGE_TEMPLATE % {
                       "state": html_protect(state),
                       "list": list
                   })


if __name__ == "__main__":
    main()
