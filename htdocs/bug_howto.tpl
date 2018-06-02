   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      How to file bugs based on tests run on piuparts.debian.org
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	This page shall grow into a well written explaination how to file useful bugs fast. It assumes you are familar with <a href="https://www.debian.org/Bugs/Reporting" target="_blank">reporting bugs in Debian</a>.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	First, of all, read the piuparts logfile and identify why piuparts testing failed.
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Then, check the BTS for that package, to see if this issue was already filed as a bug. Often it's also useful to check the source packages bug page. Sometimes a bug already exists, describing the problem piuparts has found. More often, new bugs have to be filed.
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      Usertagging existing bugs to make them known to piuparts.debian.org
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	If there already is a bug describing the same problem you're seeing in the piuparts logfile, you can usertag it, so that the next piuparts-analyze run will be able to link the bug report with the logfile on piuparts.debian.org. (piuparts-analyze runs twice a day.)
	<pre>
 User: debian-qa@lists.debian.org
 Usertags 987654 + piuparts
	</pre>
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      Filing new bugs
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	More often, there is no existing bug and you need to file one. To make this easy as well to have consistent quality bug reports, we collect templates for filing these bugs. Please <a href="templates/mail/">use these templates</a>! The following is an example bug report for illustration:
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	<pre>
 To: submit@bugs.debian.org
 Subject: $package: fails to upgrade from 'testing' - trying to overwrite ...

 Package: $package
 Version: $version
 Severity: serious
 User: debian-qa@lists.debian.org
 Usertags: piuparts

 Hi,

 during a test with piuparts I noticed your package fails to upgrade from
 'testing'. It installed fine in 'testing', then the upgrade to 'sid'
 fails because it tries to overwrite other packages files without
 declaring a replaces relation.

 See policy 7.6 at
 https://www.debian.org/doc/debian-policy/#overwriting-files-and-replacing-packages-replaces

 From the attached log (scroll to the bottom...):

 $useful_except_from_logfile

 cheers,
        $your_name

 attachment: $failed_logfile
	</pre>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Please take care when filing bugs to file meaningful bugs and to not annoy maintainers. Don't nitpick or insist on severities, the important thing is to get the bug fixed, not the right severity. Optionally you can also send copies to the piuparts-devel mailinglist by adding <i>X-debbugs-cc: piuparts-devel@alioth-lists.debian.net</i> pseudo-headers.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Also, you should be aware that what you are doing can probably be seen as mass bug filing (even if you just file a few now, they are part of a series of bugs of one kind) and as such needs to be discussed on debian-devel@lists.d.o first! For many types of bugs this has already been done. This is or should be indicated in the summary web pages as well as the mail templates.
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      Marking bugs as affecting other packages
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Sometimes there is a bug in another package which affects a package being tested. The following explains how to tell this to the BTS in a way piuparts-analyze will pick up:
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	<pre>
 # assume 987654 is our bug report in buggy-package,
 # but the problem only shows up when testing (upgrades of)
 # failing-package with piuparts:
 bts affects 987654 failing-package

 # and if failing-package is from a different source with a different
 # version number:
 bts found 987654 failing-package/$FAILED_VERSION
	</pre>
     </td>
    </tr>
    </table>

