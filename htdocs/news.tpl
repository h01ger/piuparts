   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      News
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2019-12-27</b>
	piuparts.debian.org switch to python3 done. Many thanks to all who contributed: Herbert Parentes Fortes Neto, Thomas Goirand, Mattia Rizzolo, Holger Levsen, Bastian Venthur, Nis Martensen and James Clarke.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2019-07-31</b>
	Add two new suites, <a href="https://piuparts.debian.org/bullseye">bullseye</a> and <a href="https://piuparts.debian.org/bullseye-rcmd">bullseye-rcmd</a>, after the release of buster on July 6th.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2019-05-04</b> Release of piuparts 1.0.0 - may the force be with you! If everything goes as planned, this is also the last Python 2 release. Many thanks and kudos to Lars Wirzenius for starting to write piuparts 14 years ago.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2019-04-10</b> Another suite added: <a href="https://piuparts.debian.org/sid-merged-usr">sid-merged-usr</a>, to test package installation, removal and purge in sid in a --merged-usr environment.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2018-11-28</b>: The output of various maintenance scripts is now available at <a href="https://piuparts.debian.org/logs/" target="_blank">https://piuparts.debian.org/logs/</a> instead of sending it via mails to the piuparts.d.o maintainers only.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2018-10-19</b>: Three and a half years after stopping linking to packages.qa.debian.org (which was called <em>PTS</em>) we finally drop all references to the PTS and use <em>tracker.d.o</em> instead.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2018-08-28</b>: Enable the logrotate test again to confirm <a href="https://bugs.debian.org/582630" target="_blank">#582630</a> has been fixed.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2018-04-22</b> Move git repo to <a href="https://salsa.debian.org/debian/piuparts.git">salsa.debian.org</a>. Many thanks to the alioth.debian.org admins for providing such nice services so long!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-08-14</b> Improve testing coverage of Wheezy LTS: <a href="https://piuparts.debian.org/wheezy2lts">wheezy2lts</a>, <a href="https://piuparts.debian.org/squeeze2wheezy-lts">squeeze2wheezy-lts</a> and <a href="https://piuparts.debian.org/squeeze2bpo2wheezy">squeeze2bpo2wheezy</a> now test upgrades up to wheezy-lts.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-04-28</b> Another suite added: <a href="https://piuparts.debian.org/stable2sid">stable2sid</a>, to test package installation in stable (currently jessie), then upgrade directly to sid (always unstable), then removal and purge... This is useful to detect bugs before they reach testing.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-04-10</b> Another suite added: <a href="https://piuparts.debian.org/oldstable222sid">oldstable222sid</a>, to test package installation in oldstable (currently wheezy), then upgrade to stable (currently jessie), then upgrade to testing (currently stretch), then upgrade to sid (always unstable), then removal and purge..
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-04-07</b> Another suite added: <a href="https://piuparts.debian.org/stable22sid">stable22sid</a>, to test package installation in stable (currently jessie), then upgrade to testing (currently stretch), then upgrade to sid (always unstable), then removal and purge..
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-03-08</b> Changed cron to update the webpages two times a day instead of four. In the past updating took longer than six hours, so effectivly only two updates per day were done anyway.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-03-07</b> Another suite added: <a href="https://piuparts.debian.org/oldstable22testing">oldstable22testing</a>, to test package installation in wheezy, then upgrade to jessie, then upgrade to testing, then removal and purge..
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-02-27</b> Thanks again to DSA, <a href="https://munin.debian.org/debian.org/pejacevic.debian.org/cpu.html">pejacevic.debian.org</a> is now a quad-core system instead of the single core system it was until now.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2017-02-25</b> To cope with the ever increasing Debian archive, a second slave node was added to the <code>piuparts.debian.org</code> setup, so that now there is
	<a href="https://db.debian.org/machines.cgi?host=pejacevic">pejacevic<a>, the master host, plus
	<a href="https://db.debian.org/machines.cgi?host=piu-slave-bm-a">piu-slave-bm-a</a>, the old node, and
	<a href="https://db.debian.org/machines.cgi?host=piu-slave-ubc-01">piu-slave-ubc-01</a>, the new node. All these nodes still only run the <code>amd64</code> architecture,
        help to extend the code (and the web UI) to support testing several architectures would be greatly appriciated. Many thanks to <a href="https://dsa.debian.org/">DSA</a> for maintaining the machines <code>piuparts.debian.org</code> is being run on!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2016-12-20</b> Another suite added: <a href="https://piuparts.debian.org/sid-strict">sid-strict</a>, to test packages a bit stricter than usual: first instead of a simple install, an install, followed by a remove and then install is done and then file leftover after purge are also considered an error.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2016-12-04</b> <a href="https://nthykier.wordpress.com/2016/12/04/piuparts-integration-in-britney/">piuparts results have been integrated with britney</a>, the tool the release team uses for testing migrations.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2016-06-09</b> Two new suites were added: <a href="https://piuparts.debian.org/jessie2bpo">jessie2bpo</a>, to test packages upgrades from jessie to jessie-backports and <a href="https://piuparts.debian.org/jessie2bpo2stretch">jessie2bpo2stretch</a>, where these packages are also tested for upgrading to stretch.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2015-09-29</b> Another new suite was added: <a href="https://piuparts.debian.org/wheezy-pu">wheezy-pu</a>, to <em>only</em> test packages in wheezy-proposed-updates.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2015-04-25</b> With the release of Jessie two new suites are being tested: <a href="https://piuparts.debian.org/jessie2stretch">jessie2stretch</a> and <a href="https://piuparts.debian.org/stretch">stretch</a>, which will become the next Debian release.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2015-02-04</b> Link to the new <a href="https://tracker.debian.org">Debian Package Tracker</a> (tracker.debian.org) instead to the old <a href="https://packages.qa.debian.org">Package Tracker System</a> (PTS).
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2015-01-24</b> Another suite was added: <a href="https://piuparts.debian.org/jessie-rcmd">jessie-rcmd</a>, to test installations in jessie with --install-recommends.
     </td>
    </tr>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-12-19</b> Two more new suites were added: <a href="https://piuparts.debian.org/jessie-pu">jessie-pu</a>, to <em>only</em> test packages in jessie-proposed-updates and <a href="https://piuparts.debian.org/wheezy2jessie-rcmd">wheezy2jessie-rcmd</a>, to test package upgrades from wheezy to jessie with --install-recommends.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-12-05</b> In preparation of the jessie release, another new suite was added: <a href="https://piuparts.debian.org/jessie2proposed">jessie2proposed</a>, testing installation in jessie, then upgrade to jessie-proposed-upgrades, ending in purge as usual. Web pages are now updated four times a day.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-05-30</b> Results from debsums on wheezy2jessie and wheezy2bpo2jessie are not being ignored anymore as <a href="https://bugs.debian.org/744398" target="_blank">#744398</a> has been fixed.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-05-22</b> Add squeeze-lts to the distros being testing (by testing <a href="https://piuparts.debian.org/squeeze2squeeze-lts">squeeze2squeeze-lts</a> upgrades).
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-05-19</b> Add a graph to the startpage showing the number of RC and non-RC bugs filed due to running piuparts.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-05-11</b> Temporarily ignore debsums results for wheezy2jessie and wheezy2bpo2jessie due to <a href="https://bugs.debian.org/744398" target="_blank">#744398</a>.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2014-02-26</b> A new <a href="https://piuparts.debian.org/summary.json">JSON summary file</a> is being published, showing package testing state, status URL, and the number of packages being blocked by failures, for each distribution.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-07-16</b> To better track bugs in piuparts.debian.org and piuparts itself, a new pseudo-package was created in the BTS: <a href="https://bugs.debian.org/cgi-bin/pkgreport.cgi?src=piuparts.debian.org" target="_blank">piuparts.debian.org</a>, which will be used for tracking all issues with the piuparts.debian.org service.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-06-05</b> In preparation of the first wheezy point release, another new suite was added: <a href="https://piuparts.debian.org/squeeze2wheezy-proposed">squeeze2wheezy-proposed</a>, testing installation in squeeze, then upgrade to wheezy-proposed-upgrades, ending in purge as usual.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-05-30</b> Another new suite added: <a href="https://piuparts.debian.org/wheezy2proposed">wheezy2proposed</a>, testing installation in wheezy, then upgrade to wheezy-proposed-upgrades, ending in purge as usual.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-05-29</b> Another new suite added: <a href="https://piuparts.debian.org/squeeze2bpo-sloppy">squeeze2bpo-sloppy</a>, testing the upgrade from squeeze to squeeze-backports-sloppy, ending in purge as usual.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-05-22</b> The webpages served by <a href="https://piuparts.debian.org">https://piuparts.debian.org</a> are updated twice a day now. Further changes which were applied last week: debsums failures have been reenabled, adequate is now run by piuparts (see <a href="https://bugs.debian.org/703902" target="_blank">#703902</a>) and two new suites were added: <a href="https://piuparts.debian.org/experimental">experimental</a> and <a href="https://piuparts.debian.org/sid-nodoc">sid-nodoc</a>, which tests sid without files in /usr/share/doc/&lt;package&gt;.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-05-14</b> Thanks to the new "hardware", piu-slave-bm-a is running four slaves now. Plus, these slaves are also considerably faster than piatti. And there are two new suites being tested: wheezy2jessie and wheezy2bpo2jessie - whoohoo!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-05-13</b> piuparts.debian.org has been moved to a new hardware and hosting location, now running virtualized on <a href="http://bits.debian.org/2013/04/bytemark-donation.html" target="_blank">this nice cluster</a> at Bytemark. Thanks to the Debian System Administrators for their assistence in setting up the host and maintaining the Debian infrastructure! Also many thanks and kittos to the <a href="http://cs.helsinki.fi/index.en.html" target="_blank">Department of Computer Science</a> at the University of Helsinki, Finland, for hosting piatti.debian.org since 2005!<br>For maintaining this setup we used the *bikeshed* git branch.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-03-15</b> Among many other new features the 0.50 release offers much greater flexibility for configuring and selecting (partial) suites and different mirrors.
	Therefore it is possible to test nearly arbitrary upgrade pathes. On piuparts.debian.org this is now used for testing <a href="https://piuparts.debian.org/squeeze2bpo2wheezy">squeeze2bpo2wheezy</a> and <a href="https://piuparts.debian.org/sid2experimental">sid2experimental</a>. Thanks to Andreas Beckmann for this great new feature!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2013-03-02</b> While the <a href="https://anonscm.debian.org/cgit/piuparts/piuparts.git">piuparts.git repo on Alioth</a> (update 2018-04-23: moved to <a href="https://salsa.debian.org/debian/piuparts.git">salsa</a>) will continue to be the main repo, there is also a <a href="https://github.com/h01ger/piuparts">piuparts clone on github</a>, for those who prefer to send pull requests that way.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-06-21</b> piuparts 0.45 has been released, featuring piuparts-master and piuparts-slave packages to ease installation of such a setup. If you run piuparts in master/slave mode, please let us know.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-06-04</b> Wheezy freeze is approaching and lots of uploads happening. Old piatti hardware has problems keeping up with the pace of uploads, number of packages and distros being tested! :-) Piatti is about six years old...
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-03-31</b> Disable lenny2squeeze tests, as lenny has been archived.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-03-05</b>: temporarily disabled this again until we've sorted out problems with it.
      <br>
      <b>2012-02-20</b>: piuparts-analyze now sends commands the BTS: if a bug has not been explicitly marked fixed in the new version, it can rather very savely be assumed it's still present.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-01-30</b>: Add new suite to be tested, <a href="https://piuparts.debian.org/testing2sid">testing2sid</a>, to catch upgrade problems before they reach testing.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-01-22</b>: Since some weeks, piuparts-analyze is captable of moving logfiles from fail to bugged, if there is a bug report usertagged 'piuparts' against that package+version combination. Thus, since today there is a webpage, explaining <a href="bug_howto.html">how to file bugs based on tests run on piuparts.debian.org</a>. So now the question how to help can easily be answered: read that page and start filing bugs!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2012-01-20</b>: As squeeze2wheezy has been fully tested by today, re-enable rescheduling of old logs for sid, wheezy and squeezewheezy: 200 successful logs older than 90 days are rescheduled each day, plus 25 failed logs older than 30 days.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-12-20</b>: Currently, while the machine is busy testing all of squeeze2wheeezy, all old log rescheduling has been disabled. Normally, these reschedulings happen for sid, wheezy and squeezewheezy: 200 successful logs old than 180 days are rescheduled each day, plus 25 failed logs older than 30 days.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-12-10</b>: Finally, upgrades from squeeze to wheezy are also being tested. Yay!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-11-21</b>: All mails created by the piuparts master-slave setup on piatti.d.o are now sent to the <a href="https://lists.alioth.debian.org/mailman/listinfo/piuparts-reports" target="_blank">piuparts-reports mailinglist</a> on alioth. Subcribe and learn more about the details of this setup!
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-10-31</b>: Re-create base.tgz's every week now, as they will only be replaced if the recreation was successful.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-10-23</b>: Since today piuparts.debian.org is maintained in git, using the piatti branch.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-07-10</b>: Since today dpkg is run with --force-unsafe-io by for all suites except lenny2squeeze, as dpkg from lenny doesn't support this option.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-07-10</b>: systemd-sysv is the eighth package getting special treatment by piuparts as it needs removal of sysvinit before installation and installation of that package before removal...
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-04-02</b>: New daily cronjob to reschedule the oldest 200 logfiles of each sid and wheezy, if they are older then 180 days. IOW: make sure no logfile for sid and wheezy is older than half a year.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-02-22</b>: piatti.debian.org has been upgraded to squeeze.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-02-07</b>: Add <a href="https://piuparts.debian.org/wheezy">wheezy</a>! Whoohoo!<br>For now, the Wheezy distribution has just been added with the same testing options as Squeeze. In future, squeeze and lenny2squeeze will not be tested anymore, and squeeze2wheezy will also be added...
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2011-01-25</b>: Reschedule 27655 successfully tested packages in Squeeze, since they were tested before the deep freeze. Yesterday all 70 failed and bugged packages were rescheduled too, which surprisingly led to 6 successful tests, followed by a few more dependent packages also being tested.
     </td>
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
      <b>2010-11-28</b>: debconf-english is the seventh package getting special treatment by piuparts: before removal, debconf-i18n is installed (see <a href="https://bugs.debian.org/539146" target="_blank">#539146</a> has the details and the news entry for 2010-11-25 lists the other six packages.)
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
      <b>2010-11-24</b>: Disable the logrotate test until <a href="https://bugs.debian.org/582630" target="_blank">#582630</a> is fixed and reschedule all 51 packages in sid failed due to it.
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
      <b>2010-11-06</b>: The lists of known circular depends is now taken from <a href="http://debian.semistable.com/debgraph.out.html" target="_blank">http://debian.semistable.com/debgraph.out.html</a> and maintained separately (and manually) for each tested distribution in piuparts.conf - this is not optimal (which would be piuparts detecting them automatically) but much better than the hardcoded list which we had in the piuparts library since December 2009.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-09-04</b>: Schedule all 27438 passed packages in squeeze for re-testing now that squeeze is frozen.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-07-24</b>: <a href="https://bugs.debian.org/531349" target="_blank">#531349</a> has been fixed, piuparts results are now displayed in the <a href="http://packages.qa.debian.org/">PTS</a>.
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
      <b>2010-02-28</b>: Due to <a href="https://bugs.debian.org/571925" target="_blank">#571925</a> testing of sid had to be disabled temporarily. On an unrelated note, testing of lenny2squeeze still has some issues atm...
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2010-02-25</b>: Since yesterday, squeeze and lenny2squeeze are being tested with "--warn-on-leftovers-after-purge" making piuparts only warn about leftover files after purge. This has two effects: an decrease in the number of failed logs to process, to better focus on more important problems and second, more packages will be tested, as less packages are (seen as) buggy. Today all failed packages in squeeze and lenny2squeeze have been rescheduled for testing.
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
      <b>2009-12-24</b>: Enable work-in-progress code to enable testing of packages with circular depends. This will allow testing of 5-6000 more packages in sid and squeeze, see <a href="https://bugs.debian.org/526046" target="_blank">#526046</a> and the 0.39 changelog for details. The list of packages with circular depends is currently hard-coded and will probably become a configuration option but not auto detected. But that's code yet to be written :-)
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
      <b>2009-09-16</b>: Reschedule testing for 233 failing packages in sid which were affected by <a href="https://bugs.debian.org/545949" target="_blank">#545949</a>. No packages in squeeze were affected.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-06-20</b>: Failed logs are not grouped into (at the moment) seven types of known errors and one type of issues is detected in successful logs.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-06-06</b>: Reschedule testing for 163 successful and 27 failing packages in sid which were affected by <a href="https://bugs.debian.org/530501" target="_blank">#530501</a>. Once openssh 1:5.1p1-6 has reached squeeze, this will be done again with 194 packages there.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-05-27</b>: Throw away all failed logs as there was a bug in piuparts leading to use a more uptodate mirror for getting the list of available packages and another for doing the tests. This lead to at least one fixed package which was incorrectly tested as failing, as an old version of the package was tested. To rule out some false positives about 1000 packages will be retested, but on this machine this will only take about a day :-)
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-05-11</b>: Filed <a href="https://bugs.debian.org/528266" target="_blank">#528266</a> and made piuparts ignore files in /tmp after purge. This got rid of 20 failures in sid and 14 in squeeze.
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
      <b>2009-04-18</b>: Deleted all 14 failed logfiles which complained about <code>/var/games</code> being present after purge, as this ain't an issue, see <a href="https://bugs.debian.org/524461" target="_blank">#524461</a>.
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
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2009-02-28</b>: Start maintaining piatti.debian.org via the piuparts svn repository on alioth.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2007-02-24</b>: Holger <a href="https://lists.alioth.debian.org/pipermail/piuparts-devel/2007-February/000020.html" target="_blank">puts piuparts source in svn</a>.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2006-10-02</b>: <a href="https://bugs.debian.org/390754" target="_blank">#390754 O: piuparts -- package installation, upgrading and removal testing tool"</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2006-09-29</b>: Lars <a href="https://lists.debian.org/debian-devel/2006/09/msg01068.html" target="_blank">seeks help maintaining piuparts</a>.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2005-07-05</b>: <a href="https://bugs.debian.org/317033" target="_blank">#317033 ITP: piuparts -- .deb package installation, upgrading, and removal testing tool</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <b>2005-06-19</b>: Lars writes <a href="http://liw.iki.fi/liw/log/2005-Debian.html#20050619b" target="_blank">the first blog post about piuparts</a> (version 0.4).
     </td>
    </tr>
    </table>

