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
import string

import piupartslib


CONFIG_FILE = "/etc/piuparts/piuparts.conf"


HTML_HEADER = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
 <html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>piuparts.debian.org / piuparts.cs.helsinki.fi</title>
  <link type="text/css" rel="stylesheet" href="/style.css">
  <link rel="shortcut icon" href="/favicon.ico">
 </head>

 <body>
 <div id="header">
   <h1 class="header">
    <a href="http://www.debian.org/">
     <img src="http://piuparts.debian.org/images/openlogo-nd-50.png" border="0" hspace="0" vspace="0" alt=""></a>
    <a href="http://www.debian.org/">
     <img src="http://piuparts.debian.org/images/debian.png" border="0" hspace="0" vspace="0" alt="Debian Project"></a>
    Quality Assurance
   </h1>
  <table class="reddy">
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
 </div>
 <hr>
<div id="main">
<table class="containertable">
 <tr class="containerrow" valign="top">
  <td class="containercell">
   <table class="lefttable">
    <tr class="titlerow">
     <td class="titlecell">
      General information
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="/">Overview</a>
     </td>
    </tr>
      <td class="contentcell">
      <a href="http://wiki.debian.org/piuparts" target="_blank">About</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://wiki.debian.org/piuparts/FAQ" target="_blank">FAQ</a> 
     </td>
     </tr>     
    <tr class="titlerow">
     <td class="titlecell">
      Available reports
     </td>
    </tr>
    $section_navigation
    <tr>
     <td class="contentcell">
      <a href="http://bugs.debian.org/cgi-bin/pkgreport.cgi?tag=piuparts;users=debian-qa@lists.debian.org&archive=both" target="_blank">Bugs filed</a> 
     </td>
    </tr>     
    <tr class="titlerow">
     <td class="titlecell">
      Other Debian QA efforts
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://edos.debian.net" target="_blank">EDOS tools</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://lintian.debian.org" target="_blank">Lintian</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://packages.qa.debian.org" target="_blank">Package Tracking System</a>
     </td>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://udd.debian.org" target="_blank">Ultimate Debian Database</a>
     </td>
    </tr>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      Documentation
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://www.debian.org/doc/debian-policy/" target="_blank">Debian policy</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="/doc/README.html" target="_blank">piuparts README</a>
     </td>
    </tr>
    <tr class="titlerow">
    <tr class="normalrow">
     <td class="contentcell">
      <a href="/doc/piuparts.1.html" target="_blank">piuparts manpage</a>
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      Last update
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      $time
     </td>
    </tr>
   </table>
  </td>
  <td class="containercell">
"""


HTML_FOOTER = """
  </td>
 </tr>
</table> 
</div>
 <hr>
 <div id="footer">
  <div>
   piuparts was written by <a href="mailto:liw@iki.fi">Lars Wirzenius</a> and is now maintained by 
   <a href="mailto:holger@debian.org">Holger Levsen</a>,  
   <a href="mailto:luk@debian.org">Luk Claes</a> and others. GPL2 licenced.
   <br>
  </div>
  <div>
   <a href="http://validator.w3.org/check?uri=referer">
    <img border="0" src="/images/valid-html401.png" alt="Valid HTML 4.01!" height="31" width="88">
   </a>
   <a href="http://jigsaw.w3.org/css-validator/check/referer">
    <img border="0" src="/images/vcss.png" alt="Valid CSS!"  height="31" width="88">
   </a>
  </div>
 </div>
</body>
</html>
"""


LOG_LIST_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      $title in $section
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      $preface
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      The list has $count packages, with $versioncount total versions.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <ul>
       $loglist
      </ul>
     </td>
    </tr>
   </table>
"""


STATE_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      Packages in state "$state" in $section
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <ul>
       $list
      </ul>
     </td>
    </tr>
   </table>
"""


SECTION_STATS_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell" colspan="3">
      $section statistics
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2" colspan="3">
      $description
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell" colspan="3">
      Packages per state
     </td>
    </tr>
    $tablerows
    <tr class="titlerow">
     <td class="titlecell" colspan="3">
      URL to packages file(s)
     </td>
    </tr>
     <tr class="normalrow">
     <td class="contentcell2" colspan="3">
      <code>$packagesurl</code>
     </td>
    </tr>
   </table>
"""

SOURCE_PACKAGE_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell" colspan="3">
      Source package
     </td>
    </tr>
    $rows
   </table>
"""

INDEX_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      piuparts.debian.org / piuparts.cs.helsinki.fi
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      piuparts is a tool for testing that .deb packages can be installed, upgraded, and removed without problems. The
      name, a variant of something suggested by Tollef Fog Heen, is short for "<em>p</em>ackage <em>i</em>nstallation, 
      <em>up</em>grading <em>a</em>nd <em>r</em>emoval <em>t</em>esting <em>s</em>uite". 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      It does this by  creating a minimal Debian installation in a chroot, and installing,
      upgrading, and removing packages in that environment, and comparing the state of the directory tree before and after. 
      piuparts reports any files that have been added, removed, or modified during this process.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      piuparts is meant as a quality assurance tool for people who create .deb packages to test them before they upload 
      them to the Debian package archive.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      To make sure piuparts is run on all packages, piuparts.debian.org was set up.
      <br>
      piuparts.debian.org is a service running on <a href="http://db.debian.org/machines.cgi?host=piatti" target="_blank">piatti.debian.org</a>,
      generously donated by <a href="http://hp.com/go/debian/" target="_blank">HP</a> and hosted at piuparts.cs.helsinki.fi by 
      the University of Helsinki, at the <a href="http://cs.helsinki.fi/index.en.html" target="_blank">Department of Computer Science</a> in Finland.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      This setup is currently still being polished. Better reports and statistics as well as PTS integration is
      planned. Join #debian-qa if you want to help.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      These pages are updated daily.
     </td>
    </tr>
     <td class="titlecell">
      News
      <!-- This shall properly be included in future -->
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      2009-04-04: Deleted all failed logfiles so far for two reasons: until now, only three out of ten failure types where logged with a pattern to search for in the logfiles, now this is done for all ten types of failures. And second, the way of breaking circular dependencies was not bulletproof, thus there were false positives in the failures. Now it should be fine, though maybe this will lead to lots of untestable packages... we'll see.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      2009-03-19: lenny2squeeze is not needed, so all logs for squeeze (as well as lenny2squeeze) were deleted. (As squeeze now includes two kinds of tests: installation and removal in squeeze, and installation in lenny, upgrade to squeeze, removal in squeeze.)
     </td>
    </tr>
    </table>
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
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
            {
                "sections": "report",
                "output-directory": "html",
                "packages-url": None,
                "sources-url": None,
                "master-directory": ".",
                "description": "",
            }, "")


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
    return str


def emphasize_reason(str):
    if str == "unknown-package" or str == "failed-testing":
      str = "<em>" + str + "</em>"
    return str


def source_subdir(source):
    if source[:3] == "lib":
      return source[:4]
    else:
      return source[:1]


def find_files_with_suffix(dir,suffix):
    name=[name for name in os.listdir(dir) if name.endswith(suffix)]
    subdirs=os.listdir(dir)
    for subdir in subdirs:
      if os.path.isdir(os.path.join(dir,subdir)):
        name+=[name for name in os.listdir(os.path.join(dir,subdir)) if name.endswith(suffix)]
    return name


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


def append_file(filename, contents):
    f = file(filename, "a")
    f.write(contents)
    f.close()

def read_file(filename):
    f = file(filename, "r")
    l = f.readlines()
    f.close()
    return l

def create_section_navigation(section_names):
    tablerows = ""
    for section in section_names:
        tablerows += ("<tr class=\"normalrow\"><td class=\"contentcell\"><a href='/%s'>%s</a></td></tr>\n") % \
                          (html_protect(section), html_protect(section))
    return tablerows;

def merge_templates(templates, section_names, source_pages_output_dir):
    logging.debug("Merging package templates from %s" % section_names)
    for src_tpl in templates:
        source_tpl = os.path.join(source_pages_output_dir,source_subdir(src_tpl),src_tpl)
        f = file(source_tpl, "r")
        rows = file.read(f)
        f.close()
        os.unlink(source_tpl)
        template_path = source_tpl[:-len(".tpl_src")]

        for section in section_names:
            section_tpl = os.path.join(template_path+".tpl_"+section)
            if os.path.isfile(section_tpl):
                 f = file(section_tpl, "r")
                 rows += file.read(f)
                 f.close()
                 os.unlink(section_tpl)
 
        htmlpage = string.Template(HTML_HEADER + SOURCE_PACKAGE_BODY_TEMPLATE + HTML_FOOTER)
        package = os.path.basename(src_tpl)[:-len(".tpl_src")]
        filename = os.path.join(source_pages_output_dir,source_subdir(package),package+".html")
        f = file(filename, "w")
        f.write(htmlpage.safe_substitute( {
           "section_navigation": create_section_navigation(section_names),
           "time": time.strftime("%Y-%m-%d %H:%M %Z"),
           "rows": rows,
         }))
        f.close()

def assemble_source_pages(output_directory,section_names):
    logging.debug("Assembling all source package summaries in %s" % output_directory)    
    templates = find_files_with_suffix(output_directory, ".tpl_src")
    merge_templates(templates, section_names, output_directory)

class Section:

    def __init__(self, section):
        self._config = Config(section=section)
        self._config.read(CONFIG_FILE)
        logging.debug("-------------------------------------------")
        logging.debug("Running section " + self._config.section)
        logging.debug("Loading and parsing Packages file")

        logging.info("Fetching %s" % self._config["packages-url"])
        packages_file = piupartslib.open_packages_url(self._config["packages-url"])
        self._binary_db = piupartslib.packagesdb.PackagesDB()
        self._binary_db.read_packages_file(packages_file)
        packages_file.close()

        if self._config["sources-url"]:
          logging.info("Fetching %s" % self._config["sources-url"])
          sources_file = piupartslib.open_packages_url(self._config["sources-url"])
          self._source_db = piupartslib.packagesdb.PackagesDB()
          self._source_db.read_packages_file(sources_file)
          sources_file.close()

    def write_log_list_page(self, filename, title, preface, logs):
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

        htmlpage = string.Template(HTML_HEADER + LOG_LIST_BODY_TEMPLATE + HTML_FOOTER)
        f = file(filename, "w")
        f.write(htmlpage.safe_substitute( {
                    "section_navigation": create_section_navigation(self._section_names),
                    "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                    "title": html_protect(title),
                    "section": html_protect(self._config.section),
                    "preface": preface,
                    "count": len(packages),
                    "versioncount": version_count,
                    "loglist": "".join(lines)
                }))
        f.close()


    def print_by_dir(self, output_directory, logs_by_dir):
        for dir in logs_by_dir:
            list = []
            for basename in logs_by_dir[dir]:
                assert basename.endswith(".log")
                assert "_" in basename
                package, version = basename[:-len(".log")].split("_")
                list.append((os.path.join(dir, basename), package, version))
            self.write_log_list_page(os.path.join(output_directory, dir + ".html"),
                                title_by_dir[dir], 
                                desc_by_dir[dir], list)


    def link_to_source_summary(self, package_name):
        link = "<a href=\"/source/%s\">%s</a>" % (
                source_subdir(package_name)+"/"+package_name+".html",
                html_protect(package_name))
        return link

    def link_to_state_page(self, section, package_name, state):
        link = "<a href=\"/%s/%s\">%s</a>" % (
                section,
                state+".html"+"#"+package_name,
                state)
        return link

    def generate_html_output(self):
        logging.debug("Finding log files")
        dirs = ["pass", "fail", "bugged", "fixed", "reserved", "untestable"]
        logs_by_dir = {}
        for dir in dirs:
            logs_by_dir[dir] = find_files_with_suffix(dir, ".log")

        logging.debug("Copying log files")
        copy_logs(logs_by_dir, self._output_directory)

        logging.debug("Removing old log files")
        remove_old_logs(logs_by_dir, self._output_directory)

        logging.debug("Writing per-dir HTML pages")
        self.print_by_dir(self._output_directory, logs_by_dir)

        logging.debug("Writing section statistics page")    
        tablerows = ""
        for state in self._binary_db.get_states():
            dir_link = ""
            for dir in dirs:
              if state_by_dir[dir] == state:
                dir_link += "<a href='%s.html'>%s</a> logs<br>" % (dir, html_protect(dir))
            tablerows += ("<tr class=\"normalrow\"><td class=\"contentcell2\"><a href='state-%s.html'>%s</a></td>" +
                          "<td class=\"contentcell2\">%d</td><td class=\"contentcell2\">%s</td></tr>\n") % \
                          (html_protect(state), html_protect(state),
                          len(self._binary_db.get_packages_in_state(state)),
                          dir_link)
        tablerows += "<tr class=\"normalrow\"> <td class=\"labelcell\">Total</td> <td class=\"labelcell\" colspan=\"2\">%d</td></tr>\n" % \
                          self._binary_db.get_total_packages()
        htmlpage = string.Template(HTML_HEADER + SECTION_STATS_BODY_TEMPLATE + HTML_FOOTER)
        write_file(os.path.join(self._output_directory, "index.html"), htmlpage.safe_substitute( {
            "section_navigation": create_section_navigation(self._section_names),
            "time": time.strftime("%Y-%m-%d %H:%M %Z"),
            "section": html_protect(self._config.section),
            "description": html_protect(self._config["description"]),
            "tablerows": tablerows,
            "packagesurl": html_protect(self._config["packages-url"]), 
           }))

        for state in self._binary_db.get_states():
            logging.debug("Writing page for %s" % state)
            list = "<ul>\n"
            for package in self._binary_db.get_packages_in_state(state):
                list += "<li id=\"%s\">%s (%s)" % (
                                         package["Package"],
                                         self.link_to_source_summary(self._binary_db.get_source_package(package["Package"])),
                                         html_protect(package["Maintainer"]))
                if package.dependencies():
                    list += "\n<ul>\n"
                    for dep in package.dependencies():
                        list += "<li>dependency %s is %s</li>\n" % \
                                  (html_protect(dep), 
                                  emphasize_reason(html_protect(self._binary_db.state_by_name(dep))))
                    list += "</ul>\n"
                list += "</li>\n"
            list += "</ul>\n"
            htmlpage = string.Template(HTML_HEADER + STATE_BODY_TEMPLATE + HTML_FOOTER)
            write_file(os.path.join(self._output_directory, "state-%s.html" % state), htmlpage.safe_substitute( {
                                        "section_navigation": create_section_navigation(self._section_names),
                                        "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                                        "state": html_protect(state),
                                        "section": html_protect(self._config.section),
                                        "list": list
                                       }))

    def write_counts_summary(self):
        logging.debug("Writing counts.txt")    
        header = "date"
        current_day = "%s" % time.strftime("%Y%m%d")
        counts = current_day
        for state in self._binary_db.get_states():
            count = len(self._binary_db.get_packages_in_state(state))
            header += ", %s" % state
            counts += ", %s" % count
            logging.debug("%s: %s" % (state, count))
        header += "\n"       
        counts += "\n"       

        countsfile = os.path.join(self._output_directory, "counts.txt") 
        if not os.path.isfile(countsfile):
          write_file(countsfile, header)
        else:
          last_line = read_file(countsfile)[-1]
        if not current_day in last_line:
          append_file(countsfile, counts)

    def find_log(self, package):
        n = self._binary_db._logdb._log_name(package["Package"], package["Version"])
        for dirname in self._db._all:
            nn = os.path.join(dirname, n)
            if os.path.exists(nn):
                return nn
        return None

    def prepare_package_summaries(self):
        logging.debug("Writing package templates in %s" % self._config.section)    

        sources = ""
        for source in self._source_db.get_all_packages():

            summary_page_path = os.path.join(self._output_directory, "../source", source_subdir(source))
            if not os.path.exists(summary_page_path):
               os.makedirs(summary_page_path)

            binaries = self._source_db.get_control_header(source, "Binary")
            version = self._source_db.get_control_header(source, "Version")
            maintainer = self._source_db.get_control_header(source, "Maintainer")

            sourcerows = "<tr class=\"normalrow\"><td class=\"contentcell2\"><a href=\"http://packages.qa.debian.org/%s\" target=\"_blank\">%s</a></td><td class=\"contentcell2\" colspan=\"2\">%s</td></tr>" % (source, html_protect(source), html_protect(maintainer))

            filename = os.path.join(summary_page_path, (source + ".tpl_src"))
            if not os.path.isfile(filename):
                f = file(filename, "w")
                f.write(sourcerows)
                f.close()

            success = True
            failed = False
            binaryrows = "<tr class=\"titlerow\"><td class=\"titlecell\" colspan=\"3\">Binary package(s) in "+self._config.section+"</td></tr>"
            for binary in binaries.split(", "):
              state = self._binary_db.state_by_name(binary)
              binaryrows += "<tr class=\"normalrow\"><td class=\"contentcell2\">%s</td><td class=\"contentcell2\">%s</td><td class=\"contentcell2\">%s</td></tr>" % (binary, self.link_to_state_page(self._config.section,source,state), version)
              if state != "successfully-tested":
                success = False
              if state == "failed-testing":
                failed = True
            filename = os.path.join(summary_page_path, (source + ".tpl_"+self._config.section))
            f = file(filename, "w")
            f.write(binaryrows)
            f.close()

            source_state="unknown"
            if success: source_state="success"
            if failed:  source_state="failed"
            sources += "%s: %s\n" % (source, source_state)

        write_file(os.path.join(self._output_directory, "sources.txt"), sources)

    def generate_file_output(self):
        self.write_counts_summary()
        if self._config["sources-url"]:
            self.prepare_package_summaries()

    def generate_output(self, master_directory, output_directory, section_names):
        self._section_names = section_names
        self._master_directory = os.path.abspath(os.path.join(master_directory, self._config.section))
        if os.path.exists(self._master_directory):

            self._output_directory = os.path.abspath(os.path.join(output_directory, self._config.section))
            if not os.path.exists(self._output_directory):
                os.mkdir(self._output_directory)

            oldcwd = os.getcwd()
            os.chdir(self._master_directory)

            self.generate_html_output()
            self.generate_file_output()

            os.chdir(oldcwd)
        else:
            logging.debug("Warning: %s does not exist. Did you ever let the slave work on %s?" % self._master_directory, self._config.section)

def main():
    setup_logging(logging.DEBUG, None)

    # For supporting multiple architectures and suites, we take a command-line
    # argument referring to a section in configuration file.  
    # If no argument is given, the "global" section is assumed.
    section_names = []
    if len(sys.argv) > 1:
        section = sys.argv[1]
    else:
        global_config = Config(section="global")
        global_config.read(CONFIG_FILE)
        section_names = global_config["sections"].split()

    sections = []
    for section_name in section_names:
        section = Section(section_name)
        section.generate_output(master_directory=global_config["master-directory"],output_directory=global_config["output-directory"],section_names=section_names)
        sections.append(section)

    assemble_source_pages(os.path.join(global_config["output-directory"],"source"),section_names)

    logging.debug("Writing index page")
    htmlpage = string.Template(HTML_HEADER + INDEX_BODY_TEMPLATE + HTML_FOOTER)
    write_file(os.path.join(global_config["output-directory"],"index.html"), htmlpage.safe_substitute( {
                                 "section_navigation": create_section_navigation(section_names),
                                 "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                              }))

if __name__ == "__main__":
    main()
