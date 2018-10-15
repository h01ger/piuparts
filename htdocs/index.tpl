   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      About piuparts.debian.org
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <em>piuparts</em> is a tool for testing that .deb packages can be installed, upgraded, and removed without problems.
      <em>piuparts</em> is short for "<em>p</em>ackage <em>i</em>nstallation,
      <em>up</em>grading <em>a</em>nd <em>r</em>emoval <em>t</em>esting <em>s</em>uite" and is
      a variant of something suggested by Tollef Fog Heen.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      It does this by  creating a minimal Debian installation in a chroot, and installing,
      upgrading, and removing packages in that environment, and comparing the state of the directory tree before and after.
      piuparts reports any files that have been added, removed, or modified during this process.
      piuparts is meant as a quality assurance tool for people who create .deb packages to test them before they upload them to the Debian package archive.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
       A quick introduction is available in the <a href="/doc/README.html" target="_blank">piuparts README</a>, and all the options are listed on the <a href="/doc/piuparts.1.html" target="_blank">piuparts manpage</a>.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      To make sure piuparts is run on all packages in Debian, piuparts.debian.org has been set up to run piuparts in <a href="/doc/README_server.html" target="_blank">master/slave mode</a>. This setup currently consists of three hosts: <a href="https://db.debian.org/machines.cgi?host=pejacevic" target="_blank">pejacevic.debian.org</a> and <a href="https://db.debian.org/machines.cgi?host=piu-slave-bm-a" target="_blank">piu-slave-bm-a.debian.org</a> and <a href="https://db.debian.org/machines.cgi?host=piu-slave-ubc-01" target="_blank">piu-slave-ubc-01.debian.org</a>:
     <ul>
      <li> pejacevic acts as the piuparts-master, which is responsible for scheduling test jobs to the slaves. The other main task is to generate the reports which are served via https://piuparts.debian.org.</li>
      <li> piu-slave-bm-a runs four piuparts-slave instances, which then run piuparts itself.</li>
      <li> piu-slave-ubc-01 also runs four piuparts-slave instances.</li>
     </ul>
      The first two of these hosts run as virtualized hardware on <a href="http://bits.debian.org/2013/04/bytemark-donation.html" target="_blank">a nice cluster</a> hosted at <a href="http://www.bytemark.co.uk" target="_blank">Bytemark</a> and the last one runs virtualised at the University of British Columbia.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      To learn more about this setup, follow the <em>"Documentation"</em> links in the navigation menu on the left. Read those READMEs. The piuparts configuration for all the different suite(-combination)s that are currently being tested is also linked there.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      Besides all the information provided here, there is some more information available on wiki.debian.org:
      <ul>
       <li>an overview about <a href="https://wiki.debian.org/piuparts" target="_blank">piuparts</a> and about <a href="https://wiki.debian.org/piuparts/piuparts.debian.org" target="_blank">piuparts.debian.org</a>,</li>
       <li>about <a href="https://wiki.debian.org/piuparts/Development" target="_blank">piuparts development</a>,</li>
       <li>some <a href="https://wiki.debian.org/piuparts/FAQ" target="_blank">frequently asked questions</a></li>
       <li>and some <a href="https://wiki.debian.org/piuparts/HowTos" target="_blank">HowTos</a> suited for package maintainer workflows.</li>
      </ul>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      You can talk to us on #debian-qa on irc.debian.org (OFTC) or send an email on the <a href="https://lists.alioth.debian.org/mailman/listinfo/piuparts-devel" target="_blank">piuparts development mailinglist</a>. The best ways to <a href="https://salsa.debian.org/debian/piuparts/blob/develop/CONTRIBUTING">contribute</a> are to provide patches via GIT pull requests and/or to file bugs based on piuparts runs.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      These pages are updated twice a day.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <img src="images/bts_stats.png" width="100%" alt="Bugs submitted which were found using piuparts" \>
     </td>
    </tr>
    </table>

