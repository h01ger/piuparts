   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      How to file bugs based on tests run on piuparts.debian.org
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	This page shall grow into a well written explaination how to file useful bugs fast. It assumes you are familar with <a href="http://www.debian.org/Bugs/Reporting" target="_blank">reporting bugs in Debian</a>.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	First, of all, read the piuparts logfile and identify why piuparts testing failed.
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Then, check the BTS for that package, to see if this issue was already filed as a bug. Often it's also useful to check the source packages bug page.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Then, if there is none, file a bug. If there already is a bug describing the same problem you're seeing in the piuparts logfile, usertag it like this:
	<pre>
 User: debian-qa@lists.debian.org
 Usertags: piuparts
	</pre>
	This will make sure, piuparts.debian.org picks up your bug report (actually, it's piuparts-analyse.py) and marks it as <i>bugged</i> in the database.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Also, if you file a new bug report, don't forget to usertag it! The following is an example bug report. There are many more <a href="templates/mail/">templates</a> available for you to make use from!
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
 http://www.debian.org/doc/debian-policy/ch-relationships.html#s-replaces

 From the attached log (scroll to the bottom...):

 $useful_except_from_logfile

 cheers,
        $your_name

 attachment: $failed_logfile
	</pre>
	Please take care when filing bugs to file meaningful bugs and to not annoy maintainers. Don't nitpick or insist on severities, the important thing is to get the bug fixed, not the right severity. Optionally you can also send copies to the piuparts-devel mailinglist by adding <i>X-debbugs-cc: piuparts-devel@lists.alioth.debian.org</i> pseudo-headers.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Also, you should be aware that what you are doing can probably be seen as mass bug filing (even if you just file a few now, they are part of a series of bugs of one kind) and as such needs to be discussed on debian-devel@lists.d.o first! For many types of bugs this has already been done. This is or should be indicated in the summary web pages as well as the mail templates.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
	Finally, besides simply usertagging a bug, piuparts-analyse understands more, and you can also do the following:
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

