piuparts README_server
----------------------

Authors: Lars Wirzenius, Holger Levsen and Andreas Beckmann
Email: <debian-qa@lists.debian.org>

=== piuparts runs itself and other stuff as root

WARNING: Please note that running piuparts on unknown packages is somewhat
risky, to say the least. There are security implications that you want to
consider. It's best to do it on machines that you don't mind wiping clean
at a moment's notice, and preferably so that they don't have direct network
access.

You have been warned.

== piuparts in master/slave mode

As part of the quality assurance efforts of Debian, piuparts is
run on the Debian package archive. This requires a lot of
processing power, and so the work can be distributed over several
hosts.

There is one central machine, the master, and any number of slave
machines. Each piuparts-slave instance connects to the master,
via ssh, and runs the piuparts-master program to report results
of packages it has tested already, and to get more work.

To set this up for yourself, the following steps should suffice:

=== Setting up the master

. Pick a machine for running the piuparts master. It cannot be a chroot, but
 basically any real (or properly virtualized) Debian system is good enough.
. Install the package 'piuparts-master' on it.
. Create an account for the master, if you install the piuparts-master package
 it will automatically create a 'piupartsm' user for you.
. Configure '/etc/piuparts/piuparts.conf' appropriately.
. Create the master and backup directories as defined in that 'piuparts.conf'
 and make sure master owns them.
. To generate the web reports, configure your webserver as needed. If you
 want to use the supplied 'conf-available/piuparts-master.conf' for apache2,
 you will need to do two things: a.) enable it and b.) link the htdocs
 directory defined in 'piuparts.conf' to '/var/lib/piuparts/htdocs'
 (thats the DocumentRoot as defined in 'conf-available/piuparts-master.conf').

=== Setting up the slave(s)

. Pick one or more machines for running one or several piuparts slaves. You
 can use the machine which is running the master also for running a slave.
 It's also perfectly ok to run several slaves on a multi-core machine which
 has lots of IO available.
. Install the package 'piuparts-slave' on it.
. Configure '/etc/piuparts/piuparts.conf' appropriately - if master
 and slave share the machine, they also share the config file.
 If you want to run more than one slave on a machine, set the slave-count
 parameter as desired. By default one slave will be run.
. Create the slave and tmp directories as defined in that 'piuparts.conf' and
 make sure the slave can read and write there.
. Create an account for the slave. This must be different from the master
 account. The piuparts-slave package will create a 'piupartss' user on
 installation. Whether you run one or many slaves, they run with the same
 user.
. Create an ssh keypair for the slave. No passphrase. If you installed the
 piuparts-slave package this was done automatically and the public key can
 be found in '/var/lib/piuparts/piupartss/.ssh/id_rsa.pub'
. Copy the slave's public key to the master's '.ssh/authorized_keys', for
 an installation from packages this will be
 '/var/lib/piuparts/piupartsm/.ssh/authorized_keys'.
 The key should be restricted to only allow running 'piuparts-master'
 by prefixing it with
 'command="/usr/share/piuparts/piuparts-master",no-port-forwarding,no-X11-forwarding,no-agent-forwarding '
. Configure sudo to allow the slave account to run several commands as root
 as root without password. See the example provided in
 '/usr/share/doc/piuparts-slave/examples/' to learn which.
. Run '/usr/bin/piuparts_slave_run' and 'piuparts_slave_join' to actually
 let the slave(s) run and to join their sessions.
. Run '/usr/bin/piuparts_slave_stop' to stop all piuparts-slaves on a host.
. The logs go into the master account, into subdirectories.

=== Tuning the setup

The piuparts-server package installs a piuparts server along the lines of
https://piuparts.debian.org/.

Custome '/etc/piuparts/piuparts.conf' according to your needs, most probably
you will want to re-define the 'sections' to be tested (e.g. 'sid') and also
maybe use a different Debian mirror. Note that the server can place a
significant load on the repository. Consider setting up a local mirror,
or a caching proxy for http and apt-get, to reduce the load. Running multiple
slaves on a fast host can easily saturate a 100 MBit link.

Logs are stored under '/var/lib/piuparts' by default. They are stored there
because they are basically the result of piuparts running.

There are maintenance cron jobs defined in
/usr/share/doc/piuparts-(master|slave)/examples/. In particular,
piuparts-report will create static html pages, defaulting to
http://localhost/piuparts to be served by any webserver.

=== Setup from GIT

https://piuparts.debian.org has been set up directly from GIT, this is
described in '/usr/share/doc/piuparts-master/README_pejacevic.txt'.


== Distributed piuparts testing protocol

The slave machine and the piuparts-master program communicate
using a simplistic line based protocol. SSH takes care of
authentication, so there is nothing in the protocol for that. The
protocol is transaction based: the slave gives a command, the
master program responds.  Commands and responses can be simple (a
single line) or long (a status line plus additional data lines).
Simple commands and responses are of the following format:

    'keyword arg1 arg2 arg3 ... argN'

The keyword is a command or status code ("ok"), and it and the
arguments are separated by spaces. An argument may not contain a
space.

A long command or response is deduced from the context: certain
commands always include additional data, and certain commands
always get a long response, if successful (error responses are
always simple). The first line of a long command or response is
the same as for a simple one, the additional lines are prefixed
with a space, and followed by a line containing only a period.

A sample session (">>" indicates what the slave sends, "<<" what
the master responds with):

----
<< hello
>> section sid
<< ok
>> pass liwc 1.2.3-4
>>  The piuparts
>>  log file comes
>>  here
>> .
<< ok
>> reserve
<< ok vorbisgain 2.3-4
----

Here the slave first reports a successful test of package liwc,
version 1.2.3-4, and sends the piuparts log file for it. Then it
reserves a new package to test and the master gives it
vorbisgain, version 2.3-4.

The communication always starts with the master saying "hello".
The slave shall not speak until the master has spoken.

Commands and responses in this protocol:

----
Command: section <string>
Success: ok
Failure: error
Failure: busy
----
Slave asks master to select the given section.
This must be the very first command sent by the slave, but may
be repeated later on to switch between sections.
It will return "error" if the section is unknown and "busy" if
it is currently processed by another master instance. If the
section command fails, no other commands than "section" will be
allowed until one succeeds.

----
Command: recycle
Success: ok
Failure: error
----
Slave asks master to enable logfile recycling mode. In this mode
logfiles that have been marked for rechecking will be deleted
and reissued in subsequent "reserve" commands. The "recycle"
command must be issued before the first "reserve" (or "status")
command. It will return "error" if no more logfiles are marked
for rechecking or the command is issued too late.

----
Command: idle
Success: ok <int>
----
Slave asks master whether it remembers having no packages
available at a previous "reserve" command. Returns 0 (not known
to be idle or timeout expired) or the number of seconds until
the master wants to recompute the package state. This command
should be given after "recycle" and logfile submission, but
before "reserve" or "status" commands. If the slave closes the
connection without issuing a "reserve" or "status" command, the
expensive Packages file parsing and status computation will be
skipped.

----
Command: reserve
Success: ok <packagename> <packageversion>
Failure: error
----
Slave asks master to reserve a package (a particular version of
it) for the slave to test.  The slave may reserve any number of
packages to test. If the transaction fails, there are no more
packages to test, and the slave should disconnect, wait some time
and try again.

----
Command: unreserve <packagename> <packageversion>
Success: ok
----

Slave informs master it cannot test the desired version of a
package and the package should be rescheduled by the master.

----
Command: pass <packagename> <packageversion>
          log file contents
         .
Success: ok
----

Slave reports that it has tested a particular version of a
package and that the package passed all tests. Master records
this and stores the log file somewhere suitable.

----
Command: fail <packagename> <packageversion>
          log file contents
         .
Success: ok
----

Same as "pass", but package failed one or more tests.

----
Command: untestable <packagename> <packageversion>
          log file contents
         .
Success: ok
----

Slave informs master it cannot test the desired version of a
package (perhaps it went away from the mirror?).

----
Command: status
Success: ok <package-state>=<count> <package-state>=<count>...
----
Slave asks master to report the number of packages in all
different states. The "status" command should only be issued
after all logs have been transmitted ("pass", "fail", and
"untestable" commands).

In all cases, if the master cannot respond with "ok" (e.g.,
because of a disk error storing a log file), it aborts and the
connection fails. The slave may only assume the command has
succeeded if the master responds with "ok".

The master may likewise abort, without an error message, if the
slave sends garbage, or sends too much data.


== piuparts.conf configuration file

piuparts-master, piuparts-slave and piuparts-report share the
configuration file '/etc/piuparts/piuparts.conf'. The syntax is
defined by the Python ConfigParser class, and is, briefly, like
this:

----
    [master]
    foo = bar
----

=== global configuration

These settings have to be placed in the [global] section and are
used for all further sections.

* "sections" defaults to sid and defines which sections should be
 processed in master-slave mode. Each section defined here has to
 have a section with the section specific settings explained below.
 The first section defined should always be sid, because the data
 from first section a package is in is used for the source package
 html report.

* "basetgz-sections" is an additional list of sections that are only
 used to maintain the basetgz tarballs and will therefore be ignored
 by all scripts except piuparts-slave.
 This list is empty by default.

* "master-host" is the host where the master exists. The slave will
 give this host to ssh. This option is mandatory.

* "master-user" is the username of the master. The slave will log in
 using this username. This option is mandatory.

* "master-directory" is the directory where the master keeps its
 files. Can be relative to the master's home directory.

* "slave-directory" is the directory where the slave keeps its
 files. Can be relative to the slave's home directory.

* "slave-count" is the number of concurrent slaves to start.
 Default: "1".

* "output-directory" is the directory where piuparts-report places
 the logfiles, generated html files, charts, ... that can be
 served by a webserver.

* "backup-directory" is the directory where the prepare_backup
 script will place copies of the history data needed to generate the
 plots. This directory should be included in system backups while
 the logfiles and html pages in 'master-directory' and
 'output-directory' (several GB of data) are regeneratable with some
 effort and can be excluded from backups. By default this is
 undefined meaning that no backups of the history data will be made.

* "web-host" is the domain name for the reporting web server.
 Default: "piuparts.debian.org".

* "doc-root" is the location where the webserver will serve the
 piuparts report from. Default: "/".

* "slave-load-max" specifies the system load limit when
 piuparts-slave will enter sleep mode. Operation will be resumed
 after load drops below 'slave-load-max - 1.0'. Floating point
 value. Defaults to 0 (= disabled).

* "proxy" sets the http_proxy that will be used for fetching
 Packages files etc. (by master/slave/report) and .debs etc. (by
 piuparts). This will override a http_proxy setting in the
 environment. By default (no value being set) the http_proxy
 variable from the environment will be used (and no proxy will be
 used if this is not set). It is highly recommended to use a proxy
 running on localhost (e.g. installing squid and using a setting of
 "http://localhost:3128") due to the high bandwidth consumption of
 piuparts and repeated downloading of the same files.

=== section specific configuration

The section specific settings will be reloaded each time a section
is being run. All these keys can be specified in the [global]
section, too, and will serve as defaults for all other sections
(overriding the builtin defaults).

* "master-command" is the command to run on master-host to start
 the master. Better then setting it here is actually setting it in
 '~piupartsm/.ssh/authorized_keys' to limit ssh access to that
 single command.  The key should be restricted to only allow running
 'piuparts-master' by prefixing it with
 'command="/usr/share/piuparts/piuparts-master",no-pty,no-port-forwarding'.

* "idle-sleep" is the length of time the slave should wait before
 querying the master again if the master didn't have any new
 packages to test. In seconds, so a value of 300 would mean five
 minutes, and that seems to be a good value for a repo that gets
 updated frequently. The default is 300 seconds.

* "max-tgz-age" is used to specify the maximum age (in seconds)
 after which basesystem tarballs will be recreated. If recreation
 fails, the old tarball will be used again. The default is 2592000
 seconds, which is 30 days. A value of 0 disables recreation.

* "min-tgz-retry-delay" is used to specify the minimum time (in
 seconds) between attempts to recreate a tarball which was created
 more than "max-tgz-age" seconds ago. The default is 21600 seconds,
 which is 6h.

* "log-file" is the name of a file to where the master should write
 its log messages. In the default configuration file it is
 "$SECTION/master.log". To disable logging, set it to "/dev/null".
 The global "log-file" setting (defaulting to master-error.log) is
 used for logging stderr output from piuparts-master. This logfile
 will be placed in the 'master-directory' and has the PID appended.

* "piuparts-command" is the command the slave uses to start
 piuparts. It should include 'sudo' if necessary so that piuparts
 runs with sufficient priviledges to do its testing (and that
 means root priviledges). This command should be given in the
 [global] section and include all flags that are common for all
 sections.

* "piuparts-flags" are appended to "piuparts-command" and should
 contain the section-specific flags.

* "tmpdir" is the scratch area where piuparts will create the
 chroots. Note: the filesystem where this is located must not be
 mounted with the nodev or nosuid options. This is a mandatory
 setting with no default. The scripts that are monitoring this
 directory for leftover mountpoints and chroots only evaluate the
 [global] setting.

* "description" is a synopsis of the test used in the report. A
 default description will be generated if this is not set or will
 be prepended (appended) if the description starts (ends) with
 '+'.

* "mirror" tells the slave which mirror it is to use. The slave
 gives this to piuparts when it runs it. The URLs for Packages and
 Sources files will be generated from this setting, too. Default
 (for fetching Packages/Sources): "http://deb.debian.org/debian".

* "distro" is the distribution the slave should tell piuparts to
 use for basic install/purge testing. It is also possible to use a
 "partial" distribution as defined in distros.conf. No default.
 If 'upgrade-test-distros' is set, this selects the distribution
 that will be used for getting the packages to be tested. Defaults
 to the last entry in 'upgrade-test-distros', but other useful
 settings are the first entry (to test upgrades of "disappearing"
 packages) or the restricted set in a partial distribution (e.g.
 stable to backports to testing).
 The special keyword "None" is used to denote that no packages
 are to be tested, but only the basetgz tarball will be created
 and refreshed regularily (for the distribution given in
 'upgrade-test-distros'). This reference basetgz can be shared
 between several sections without being affected by their flags.

* "area" is the archive area used to get the list of packages to
 be tested. The Packages file for this area will be loaded. The
 default is "main" and the possible values depend on the vendor,
 for Debian these are main, contrib, non-free.

* "components" sets the archive areas that will be available when
 testing the packages selected via the "area" setting. These will
 be enabled in the generated sources.list.  Defaults to "", which
 means all components will be available. A useful setting is
 "main" together with area = main to avoid using packages outside
 main. Testing packages from a 'partial' area like contrib or
 non-free usually requires additional or all components to be
 available.

* "arch" is the architecture to use.
 Default: dpkg --print-architecture.

* "chroot-tgz" is the name of the file the slave should use for
 the tarball containing the base chroot. The default name is
 generated automatically from the "distro" or "upgrade-test-distros"
 setting. If the tarball doesn't exist, the slave creates it.

* "basetgz-directory" is the directory where "chroot-tgz" (or the
 automatically selected default name) is located. The default is
 '.'.

* "chroot-meta-auto" (global, section) is a file in the section
 directory where the slave will store cached chroot meta data for
 the reference target chroot in distupgrade tests. This speeds up
 distupgrade tests since it avoids doing an empty upgrade test to
 generate this data on-the-fly as part of each test. Cached data
 will be valid for 6 hours unless a mismatch in the package
 versions available in the chroot is detected earlier.
 This is not set (and therefore not enabled) by default.

* "upgrade-test-distros" is the space delimited list of
 distributions the slave should use for testing upgrades
 between distributions (i.e., Debian versions). Using "partial"
 distributions as defined in distros.conf is possible. Currently,
 "jessie stretch sid" is a good choice.
 Setting this switches from doing install/purge tests to
 dist-upgrade tests. Not set by default.

* "max-reserved" is the maximum number of packages the slave will
 reserve at once. It should be large enough that the host that
 runs master is not unduly stressed by frequent ssh logins and
 running master (both of which take quite a bit of CPU cycles),
 yet at the same time it should not be so large that one slave
 grabs so many packages all other slaves just sit idle. The number
 obviously depends on the speed of the slave. A good value seems
 to be enough to let the slave test packages for about an hour
 before reporting results and reserving more. For a contemporary
 AMD64 machine with a reasonably fast disk subsystem the value 50
 seems to work fine. To disable a section set this to 0.

* "keep-sources-list" controls whether the slave runs piuparts
 with the '--keep-sources-list' option.  This option does not
 apply to upgrade tests.  The value should be "yes" or "no", with
 the default being "no".  Use this option for dists that you need
 a custom sources.list for, such as "stable-proposed-updates".

* "precedence" controls the order the sections are being processed
 by the slave. Sections with a larger precedence value will be run
 only if all sections with a smaller precedence value are idle,
 i.e. master does not have any packages that this slave could
 test. Sections with the same precedence value will be processed
 round-robin until they are all idle (or a more important section
 has packages to be tested). The default is 1.

* "depends-sections" lists additional sections that will be
 searched for dependencies that are not available in the current
 section if that describes a partial distro.

* "known-problem-directory" is the path to the directory containing
 definitions of known problems.
 Default: "${prefix}/share/piuparts/known_problems"

* "debug" tells the slave whether to log debug level messages. The
 value should be "yes" or "no", with the default being "no".
 piuparts itself currently always produces debug output and there
 is no way to disable that.

* "PYTHONPATH" (global) sets the search path to the piupartslib
 python modules if they are not installed in their default location
 in /usr.

* "reschedule-untestable-days" (global) sets the rescheduling
 delay for untestable packages (e.g. due to unsatisfied
 dependencies). This is handled by the 'report_untestable_packages'
 script and the default is "7" days.

* "reschedule-old-days" (global, section) and the following five
 settings define the rescheduling scheme that it performed by the
 'reschedule_oldest_logs' script. Passed/failed logs that are
 older than reschedule-(old|fail)-days will be marked for
 rechecking (limited to reschedule-(old|fail)-count). Only packages
 that are actually testable will be reissued by piuparts-master (and
 the "old" log will be deleted at that time).  Logs that are marked
 for recycling but have not been rechecked due to missing/failing
 dependecies will be deleted anyway if they are older than
 expire-(old|fail)-days.

* "reschedule-old-count" (global, section) is the maximum number of
 passed logs that will be marked for recycling. Set to 0 to disable
 rescheduling passed logs.

* "expire-old-days" (global, section) can be set to a value larger
 than 'reschedule-old-days' to delete logs older than the setting
 that are marked for recycling but haven't been rechecked due to
 failing or missing dependecies. Disabled by default ("0").

* "reschedule-fail-days" (global, section) sets the minimum age of
 failing logs (fail/*.log or affected/*.log) before they will be
 rechecked.

* "reschedule-fail-count" (global, section) is the maximum number
 of failed logs that will be marked for recycling. Set to 0 to
 disable rescheduling failed logs.

* "expire-fail-days" (global, section) can be set to a value larger
 than 'reschedule-fail-days' to delete logs older than the setting
 that are marked for recycling but haven't been rechecked due to
 failing or missing dependecies. Disabled by default ("0").

* "auto-reschedule" (section) can be set to "no" to disable
 rescheduling of passed and failed packages. To disable only
 rescheduling one of passed or failed logs, set the corresponding
 -count variable to zero.

* "json-sections" is a space-separated list of the
 section/distribution names which receive test results for this
 section. The results, by package, are stored with this name/these
 names in the section and global test summary.json files. If
 "json-sections" is undefined, or defined as "default", piuparts
 will assign the section to one of "unstable", "testing", "stable",
 "oldstable", "experimental", or "unknown". If "json-sections"
 is "none", the summary will not be created. The "json-sections"
 name "overall" is reserved.

Some of the configuration items are not required, but it is best
to set them all to be sure what the configuration actually is.

=== piuparts.debian.org specific configuration

In addition to some of the above settings the following
configuration settings are used by the scripts in '~piuparts?/bin/'
used to run piuparts.debian.org. They are all optional, default
values are set in the scripts.

* "urlbase" (global) is the base url of the webserver serving this
 piuparts instance. Used to provide links to logfiles in email
 reports. It defaults to "https://piuparts.debian.org".

== Running piuparts-report as it is done for piuparts.debian.org

If you want to run piuparts-report (which is only+very useful if
you run piuparts in master-slave mode), you need to 'apt-get
install python-rpy r-recommended r-base-dev'. For more
information see
link:https://anonscm.debian.org/cgit/piuparts/piuparts.git/tree/README_pejacevic.txt[https://anonscm.debian.org/cgit/piuparts/piuparts.git/tree/README_pejacevic.txt].

To generate the report on the master host run:

----
piupartsm@pejacevic:~$ /usr/share/piuparts/master/generate_daily_report
----

// vim: set filetype=asciidoc:
