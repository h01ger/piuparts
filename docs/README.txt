.. raw:: html

 <style> .blue {color:navy} </style>

.. role:: blue


.. _top1:

README
======

Author: Lars Wirzenius
Email: <liw@iki.fi>

After reading this README you probably also want to have a look
at the piuparts manpage, to learn about the available options.
But read this document first!

:blue:`Introduction`
^^^^^^^^^^^^^^^^^^^^

piuparts is a tool for testing that .deb packages can be
installed, upgraded, and removed without problems. The
name, a variant of something suggested by Tollef Fog
Heen, is short for "package installation, upgrading, and
removal testing suite".

piuparts is licensed under the GNU General Public License,
version 2, or (at your option) any later version.

https://piuparts.debian.org has been testing the Debian archive
since the Lenny release in 2009, though responsible maintainers
run piuparts locally before uploading packages to the archive.


:blue:`How to use piuparts in 5 minutes`


:blue:`Basic Usage`
^^^^^^^^^^^^^^^^^^^

Testing your packages with piuparts is as easy as typing at the
console prompt:::

 piuparts sm_0.6-1_i386.deb


Note that in order to work, piuparts has to be executed as user
root, so you need to be logged as root or use 'sudo'.

This will create a sid chroot with debootstrap, where it'll test
your package.

If you want to test your package in another release, for example,
testing, you can do so with:::

 # piuparts ./sm_0.6-1_i386.deb -d testing


By default, this will read the first mirror from your
'/etc/apt/sources.list' file. If you want to specify a different
mirror you can do it with the option '-m':::

 # piuparts ./sm_0.6-1_i386.deb -m http://ftp.de.debian.org/debian


It's possible to use -d more than once. For example, to do a first
installation in stable, then upgrade to testing, then upgrade to
unstable and then upgrade to the local package use this:::

 # piuparts -d stable -d testing -d unstable ./sm_0.6-1_i386.deb


:ref:`top <top1>`

:blue:`Some tips`
^^^^^^^^^^^^^^^^^

piuparts also has a manpage, where all available options are explained.

If you use piuparts on a regular basis, waiting for it to create
a chroot every time takes too much time, even if you are using a
local mirror or a caching tool such as approx.

Piuparts has the option of using a tarball as the contents of the
initial chroot, instead of building a new one with debootstrap. A
easy way to use this option is use a tarball created with
pbuilder. If you are not a pbuilder user, you can create this
tarball with the command (again, as root):::

 # pbuilder --create


then you only have to remember to update this tarball with:::

 # pbuilder --update


To run piuparts using this tarball:::

 # piuparts -p ./sm_0.6-1_i386.deb


If you want to use your own pre-made tarball:::

 # piuparts --basetgz=/path/to/my/tarball.tgz ./sm_0.6-1_i386.deb


Piuparts also has the option of using a tarball as the contents
of the initial chroot, instead of building a new one with
pbuilder. You can save a tarball for later use with the '-s'
('*-*-save') piuparts option. Some people like this, others prefer
to only have to maintain one tarball. Read the piuparts manpage
about the '-p', '-b' and '-s' options

While pbuilder itself supports using cdebootstrap, this is not
fully supported by piuparts: You will need to use debootstrap
or use the '*-*-warn-on-debsums-errors' option for piuparts and then
you will still see spurious warnings in the log.


:ref:`top <top1>`

:blue:`Piuparts tests`
^^^^^^^^^^^^^^^^^^^^^^

By default, piuparts does two tests:

. Installation and purging test.

. Installation, upgrade and purging tests.

The first test installs the package in a minimal chroot, removes
it and purges it. The second test installs the current version in
the archive of the given packages, then upgrades to the new
version (deb files given to piuparts in the input), removes and
purges.

If you only want to perfom the first test, you can use the
option: '*-*-no-upgrade-test'


:ref:`top <top1>`

:blue:`Testing packages in the config-files-remaining state`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The *-*-install-remove-install option modifies the three piuparts
tests in order to test package installation while config files
from a previous installation are remaining, but the package itself
was removed inbetween.
This exercises different code paths in the maintainer scripts.

. Installation and purging test: install, remove, install again
 and purge.

. Installation, upgrade and purging test: install the old version,
 remove, install the new version and purge.

. Distupgrade test: install the version from the first
 distribution, remove, distupgrade to the last distribution,
 install the new version.


:ref:`top <top1>`

:blue:`Analyzing piuparts results`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When piuparts finishes all the tests satisfactorily, you will get
these lines as final output:::

 0m39.5s INFO: PASS: All tests.
 0m39.5s INFO: piuparts run ends.


Anyway, it is a good idea to read the whole log in order to
discover possible problems that did not stop the piuparts
execution.

If you do not get those lines, piuparts has failed during a test.
The latest lines should give you a pointer to the problem with
your package.


:ref:`top <top1>`

:blue:`Custom scripts with piuparts`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can specify several custom scripts to be run inside piuparts.
You have to store them in a directory and give it as argument to
piuparts: '*-*-scriptsdir=/dir/with/the/scripts'
This option can be given multiple times. The scripts from all
directories will be merged together (and later ones may overwrite
earlier scripts with the same filename).

By default this is *not* set to anything. Have a look at
'/etc/piuparts/scripts*' to learn which scripts and script
directories are shipped by the package.

The script prefix determines in which step it is executed. You
can run several scripts in every step, they are run in
alphabetical order.

The scripts need to be executable and are run *inside* the piuparts
chroot and can only be shell scripts. If you want to run Python or
Perl scripts, you have to install Python or Perl. The chroot where
piuparts is run is minimized and does not include Perl.

The variable PIUPARTS_OBJECTS is set to the packages currently
being tested (seperated by spaces, if applicable) or the .changes
file(s) being used.  So when running in master-slave mode, it
will be set to the (one) package being tested at a time.

Depending on the current test, the variable PIUPARTS_TEST is set
to

. 'install' (installation and purging test),

. 'upgrade' (installation, upgrade and purging tests) or

. 'distupgrade'.


During the 'upgrade' and 'distupgrade' tests, the variable
PIUPARTS_PHASE is set to one of the following values:

. 'install' while initially installing the packages from the
 repository,

. 'upgrade' when upgrading to the .debs,

. 'distupgrade' while reinstalling the packages after
 'apt-get dist-upgrade' to ensure they were not removed accidently


During the 'install' test, the PIUPARTS_PHASE variable is set to
'install'.

The current distribution is available in the variable
PIUPARTS_DISTRIBUTION.

The following prefixes for scripts are recognized:

'post_chroot_unpack' - after the chroot has been unpacked/debootrapped.
Before the chroot gets updated/dist-upgraded initially.

'post_setup\_' - after the *setup* of the chroot is finished.
Before metadata of the chroot is recorded for later comparison.

'pre_test\_' - at the beginning of each test. After metadata of
the chroot was recorded for later comparison.

'is_testable\_' - before *installing* your package. If this script
returns a non-zero return value, the installation of the package
will be skipped. With a return value of 1 the test will be reported
as successful, but with a return value if 2 it will be reported as
failed.
Use this to flag packages that cannot be be tested with piuparts
by design (e.g. usrmerge), require not publicly available external
ressources (e.g. some downloader packages) or are broken beyond
repair (e.g. buggy packages in archived releases). Use the return
value of 2 for seriously broken packages that can break piuparts.

'pre_install\_' - before *installing* your package. Depending on
the test, this may be run multiple times. The PIUPARTS_TEST and
PIUPARTS_PHASE variables can be used to distinguish the cases.

'post_install\_' - after *installing* your package and its
dependencies.  Depending on the test, this may be run multiple
times. The PIUPARTS_TEST and PIUPARTS_PHASE variables can be used
to distinguish the cases.

'pre_remove\_' - before *removing* your package.
Depending on the test, this may be run multiple times.

'post_remove\_' - after *removing* your package.
Depending on the test, this may be run multiple times.

'post_purge\_' - after *purging* your package.
Depending on the test, this may be run multiple times.

'post_test\_' - at the end of each test. Right before performing
final checks and comparing the chroot with the reference chroot
metadata.

'pre_distupgrade\_' - before *upgrading* the chroot to the *next
distribution*. The next distribution is available in the variable
PIUPARTS_DISTRIBUTION_NEXT.

'post_distupgrade\_' - after *upgrading* the chroot to the *next
distribution*. The previous distribution is available in the
variable PIUPARTS_DISTRIBUTION_PREV.


:ref:`top <top1>`

:blue:`Example custom scripts`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

 '$ cat post_install_numbers'
 #!/bin/bash

 number=`dpkg -l | wc -l`
 echo "There are $number packages installed."
 exit 0


 '$ cat post_setup_package'
 #!/bin/sh

 echo "$PIUPARTS_OBJECTS will now get tested."
 exit 0


:ref:`top <top1>`

:blue:`Distributed testing`
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is described in README_server.txt.
