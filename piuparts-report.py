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


HTML_HEADER = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
 <html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>piatti.debian.org / piatti.cs.helsinki.fi</title>
  <link type="text/css" rel="stylesheet" href="/style.css">
  <link rel="shortcut icon" href="/favicon.ico">
 </head>
 <body>
  <div align="center">
   <a href="http://www.debian.org/">
    <img src="http://piuparts.debian.org/images/openlogo-nd-50.png" border="0" hspace="0" vspace="0" alt=""></a>
   <a href="http://www.debian.org/">
    <img src="http://piuparts.debian.org/images/debian.png" border="0" hspace="0" vspace="0" alt="Debian Project"></a>
  </div>
  <br />
  <table class="reddy" width="100%">
   <tr>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-upperleft.png" align="left" border="0" hspace="0" vspace="0"
      alt="" width="15" height="16"></td>
    <td rowspan="2" class="reddy">Policy is your friend. Trust the Policy. Love the Policy. Obey the Policy.</td>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-upperright.png" align="right" border="0" hspace="0" vspace="0"
     alt="" width="16" height="16"></td>
   </tr>
   <tr>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-lowerleft.png" align="left" border="0" hspace="0" vspace="0"
      alt="" width="16" height="16"></td>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-lowerright.png" align="right" border="0" hspace="0" vspace="0"
      alt="" width="15" height="16"></td>
   </tr>
  </table>
"""


HTML_FOOTER = """
<a href="http://validator.w3.org/check?uri=referer">
    <img border="0" src="/images/valid-html401.png" alt="Valid HTML 4.01!" height="31" width="88">
</a>
<a href="http://jigsaw.w3.org/css-validator/check/referer">
    <img border="0" src="/images/vcss.gif" alt="Valid CSS!"  height="31" width="88">
</a>
    
</body>
</html>
"""


LOG_LIST_BODY_TEMPLATE = """
<div class="main">
<h1>%(title)s</h1>
<p>%(preface)s</p>
<p>The list has %(count)d packages, with %(versioncount)s total versions.
This page was generated: %(time)s.</p>
<ul>
%(loglist)s
</ul>
</div>
"""


STATS_BODY_TEMPLATE = """
<div class="main">
<h1>Statistics of packages</h1>
<p>This page contains some statistics about packages piuparts is looking
at.</p>
%(table)s
</div>
"""


STATE_BODY_TEMPLATE = """
<div class="main">
<h1>Packages in state "%(state)s"</h1>
<p>This page contains a list of package in state "%(state)s".</p>
%(list)s
</div>
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
    f.write(HTML_HEADER + LOG_LIST_BODY_TEMPLATE % 
            {
                "title": html_protect(title),
                "preface": preface,
                "loglist": "".join(lines),
                "count": len(logs),
                "versioncount": version_count,
                "time": time.strftime("%Y-%m-%d %H:%M:%S %z"),
            } + HTML_FOOTER)
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
               HTML_HEADER + STATS_BODY_TEMPLATE % { "table": table } + HTML_FOOTER)

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
                   HTML_HEADER + STATE_BODY_TEMPLATE % {
                       "state": html_protect(state),
                       "list": list
                   } + HTML_FOOTER)


if __name__ == "__main__":
    main()
