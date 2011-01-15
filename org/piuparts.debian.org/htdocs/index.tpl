   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      About piuparts.d.o
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <em>piuparts</em> is a tool for testing that .deb packages can be installed, upgraded, and removed without problems. The
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
      piuparts is meant as a quality assurance tool for people who create .deb packages to test them before they upload them to the Debian package archive. See the <a href="/doc/README.html" target="_blank">piuparts README</a> for a quick intro and then read the <a href="/doc/piuparts.1.html" target="_blank">piuparts manpage</a> to learn about all the fancy options!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      To make sure piuparts is run on all packages, piuparts.debian.org was set up as a service running on 
      <a href="http://db.debian.org/machines.cgi?host=piatti" target="_blank">piatti.debian.org</a>. 
      This machine was generously donated by <a href="http://hp.com/go/debian/" target="_blank">HP</a> 
      to run piuparts on the Debian archive and is hosted as 
      <a href="http://piuparts.cs.helsinki.fi">piuparts.cs.helsinki.fi</a> by the University of Helsinki, at the 
      <a href="http://cs.helsinki.fi/index.en.html" target="_blank">Department of Computer Science</a>
      in Finland.
      As this is still being polished, see the piuparts wiki page to get an overview about <a href="http://wiki.debian.org/piuparts" target="_blank">piuparts development and the piuparts setup on piatti</a>. Better reports, statistics, tools to report bugs as well as testing on other architectures is planned. Join #debian-qa if you want to help.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      These pages are updated daily.
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      News
     </td>
    </tr>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-01-15</b>: Reschedule 10123 successful and failed logs in lenny2squeeze for re-testing. Those are logs which have been tested before Squeeze was deep frozen or while there was still a bug in piuparts-slave, see last news entry for details.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-01-03</b>: Reschedule 12306 successful and 8 bugged logs in lenny2squeeze for re-testing. Those are logs older than 148 days, which refers to when Squeeze was initially frozen (2010-08-06). Deep freeze was announced on 2010-12-13 and there are 3800 logs older then that too, but for future deletions it's better to use 2010-01-03 (=commit r857), which fixes a bug in piuparts-slave resulting in using the sid packages file for lenny2squeeze tests.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-28</b>: debconf-english is the seventh package getting special treatment by piuparts: before removal, debconf-i18n is installed (see <a href="http://bugs.debian.org/539146" target="_blank">#539146</a> has the details and the news entry for 2010-11-25 lists the other six packages.)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-26</b>: Schedule all 159 failed packages in lenny2squeeze for re-testing.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-25</b>: Treat six packages specially: sudo (sensibly refuses removal if no root password is set), apt-listbugs (is called by apt and exists if there are RC buggy packages being upgraded), fai-nfsroot, ltsp-client-core (these two packages modify the installed system heavily and thus will only install if conditions are met), file-rc and upstart (these two replace essential packages and therefore apt needs to be told to do this). 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-24</b>: Disable the logrotate test until <a href="http://bugs.debian.org/582630" target="_blank">#582630</a> is fixed and reschedule all 51 packages in sid failed due to it.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-14</b>: Schedule all 402 failed packages in sid for re-testing.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-12</b>: Schedule all 108 failed packages in squeeze for re-testing. (Followup on 2010-09-04.)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-11-06</b>: The lists of known circular depends is now taken from <a href="http://debian.semistable.com/debgraph.out.html" target="_blank">http://debian.semistable.com/debgraph.out.html</a> and maintained seperatedly (and maually) for each tested distribution in piuparts.conf - this is not optimal (which would be piuparts detecting them automatically) but much better than the hardcoded list which we had in the piuparts library since December 2009.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-09-04</b>: Schedule all 27438 passed packages in squeeze for re-testing now that squeeze is frozen.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-05-18</b>: From today on, broken logrotate scripts after purge are only reported in sid.
     </td>
    </tr>
     <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-05-16</b>: Finally enabled testing of sid again. (Actually, sid was enabled on 2010-03-05, but piuparts.d.o was broken until today.)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-02-28</b>: Due to <a href="http://bugs.debian.org/571925" target="_blank">#571925</a> testing of sid had to be disabled temporarily. On an unrelated note, testing of lenny2squeeze still has some issues atm...
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-02-25</b>: Since yesterday, squeeze and lenny2squeeze are being tested with "-warn-on-leftovers-after-purge" making piuparts only warn about leftover files after purge. This has two effects: an decrease in the number of failed logs to process, to better focus on more important problems and second, more packages will be tested, as less packages are (seen as) buggy. Today all failed packages in squeeze and lenny2squeeze have been rescheduled for testing.
     </td>
    </tr>
     <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-02-23</b>: Since today, piuparts is able to detect broken logrotate scripts after purge, which will need retesting of all successfully tested packages eventually. The failed packages in squeeze also needs retesting, due to split into squeeze and lenny2squeeze last week.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-02-16</b>: The squeeze test has been split into squeeze and lenny2squeeze, where squeeze means package installation in squeeze, removal and purge test, while lenny2squeeze means package installation in lenny, then upgrade to squeeze, then removal and purge test. This allows more issues to be found in squeeze since (potential) brokeness in lenny is not blurring the results in squeeze. 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-01-05</b>: Reschedule testing for 319 failed packages in sid and 544 in squeeze, since --warn-on-others is now used.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-12-24</b>: Enable work-in-progress code to enable testing of packages with circular depends. This will allow testing of 5-6000 more packages in sid and squeeze, see #526046 and the 0.39 changelog for details. The list of packages with circular depends is currently hard-coded and will probably become a configuration option but not auto detected. But that's code yet to be written :-)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-12-21</b>: So testing of 13398 in squeeze has taken 12 days, which is no big surprise as the squeeze tests are more complex. Today 499 failed packages from sid and 235 from squeeze have been rescheduled for testing, to catch broken symlinks in those too.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-12-12</b>: After testing 14416 packages in sid in three days, reschedule 15944 packages in squeeze... see previous entry for an explanation why.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-12-09</b>: Reschedule testing for 14287 successfully tested packages in sid, those in squeeze will be rescheduled once all testable package in sid have been tested again. This is because piuparts now creates and maintains chroots securily (using gpg signed Release files for both debootstrap and apt-get) and because it warns if broken symlinks are found in a package. 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-12-05</b>: Reschedule testing for ~400 failed packages in sid and ~600 in squeeze, to be followed by a rescheduling of all successful packages. This is because piuparts now warns if broken symlinks are found in a package. 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-10-08</b>: Reschedule testing for ~2000 failed packages in sid, which failed because of a problem when minimizing the chroot at the beginning of the piuparts tests. As of today, piuparts running on piuparts.debian.org does not minimize the chroots anymore.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-09-18</b>: Reschedule testing for 17170 (successfully tested) packages in sid, to make sure they still install fine with dependency based booting enabled now in sid. Throwing away 42806 (successful) logfiles from those packages :-)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-09-16</b>: Reschedule testing for 233 failing packages in sid which were affected by #545949. No packages in squeeze were affected.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-06-20</b>: Failed logs are not grouped into (at the moment) seven types of known errors and one type of issues is detected in successful logs.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-06-06</b>: Reschedule testing for 163 successful and 27 failing packages in sid which were affected by #530501. Once openssh 1:5.1p1-6 has reached squeeze, this will be done again with 194 packages there.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-05-27</b>: Throw away all failed logs as there was a bug in piuparts leading to use a more uptodate mirror for getting the list of available packages and another for doing the tests. This lead to at least one fixed package which was incorrectly tested as failing, as an old version of the package was tested. To rule out some false positives about 1000 packages will be retested, but on this machine this will only take about a day :-)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-05-11</b>: Filed #528266 and made piuparts ignore files in /tmp after purge. This got rid of 20 failures in sid and 14 in squeeze.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-05-06</b>: Only believe statistics you faked yourself! Up until today piuparts used to include virtual packages (those only exist true the Provides: header) into the calculations of statistics of package states and the total number of packages. Suddenly, sid has 2444 packages less! 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-05-01</b>: All packages in squeeze and sid which can be tested have been tested. So it takes about one month to do a full piuparts run against one suite of the archive on this machine, that's almost 1000 packages tested per day.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-04-20</b>: Deleted 86 more failed logfiles (out of 692 failures in total atm) which were due to broken packages, which most likely are temporarily uninstallable issues - a good indicator for this is that all of those failures happened in sid and none in squeeze. For the future there is a cronjob now, to notify the admins daily of such problems. In more distant future those issues should be detected and avoided.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-04-18</b>: Deleted all 14 failed logfiles which complained about <code>/var/games</code> being present after purge, as this ain't an issue, see #524461.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-04-04</b>: Deleted all failed logfiles so far for two reasons: until now, only three out of ten failure types where logged with a pattern to search for in the logfiles, now this is done for all ten types of failures. And second, the way of breaking circular dependencies was not bulletproof, thus there were false positives in the failures. Now it should be fine, though maybe this will lead to lots of untestable packages... we'll see.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-03-19</b>: lenny2squeeze is not needed, so all logs for squeeze (as well as lenny2squeeze) were deleted. (As squeeze now includes two kinds of tests: installation and removal in squeeze, and installation in lenny, upgrade to squeeze, removal in squeeze.)
     </td>
    </tr>
    </table>

