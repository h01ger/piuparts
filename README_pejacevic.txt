Notes about the piuparts installation on pejacevic.debian.org and it's slave(s)
===============================================================================

This document describes the setup for https://piuparts.debian.org - it's used
for reference for the Debian System Administrators (DSA) as well as a guide
for other setting up a similar system, with the piuparts source code
installed from git. For regular installations we recommend to use the
piuparts-master and piuparts-slaves packages as described in
/usr/share/doc/piuparts-master/README_server.txt

== Installation

piuparts.debian.org is a setup running on three systems:

* pejacevic.debian.org, running the piuparts-master instance and an apache
  webserver to display the results.
* piu-slave-bm-a.debian.org, running four piuparts-slave nodes to run the
  actual tests.
* piu-slave-ubc-01.debian.org, running four piuparts-slave nodes as well.

=== piuparts installation from source

* basically, apt-get build-dep piuparts - in reality both systems get their
  package configuration from git.debian.org/git/mirror/debian.org.git
* pejacevic runs a webserver as well (see below for apache configuration)
* Copy 'https://salsa.debian.org/debian/piuparts/blob/develop/update-piuparts-master-setup'
  and 'https://salsa.debian.org/debian/piuparts/blob/develop/update-piuparts-slave-setup'
  to the hosts which should be master and slave. (It's possible and has been
  done for a long time to run them on the same host.(
  Run the scripts as the piupartsm and piupartss users and clone that git
  repository into '/srv/piuparts.debian.org/src' in the first place. Then
  checkout the develop branch.
* Ideally provide '/srv/piuparts.debian.org/tmp' on (a sufficiently large)
  tmpfs.
* `sudo ln -s /srv/piuparts.debian.org/etc/piuparts /etc/piuparts`
* See below for further user setup instructions.

=== User setup

On pejacevic the piuparts-master user piupartsm needs to be created, on
piu-slave-bm-a and piu-slave-ubc-01 a piupartss user is needed for the slave.
Both are members of the group piuparts and '/srv/piuparts.debian.org' needs to
be chmod 2775 and chown piuparts(sm):piuparts.

==== '~/bashrc' for piupartsm and piupartss

Do this for the piupartsm user on pejacevic and piupartss on the slave(s):

----
piupartsm@pejacevic$ cat >> ~/.bashrc <<-EOF

# added manually for piuparts
umask 0002
export PATH="~/bin:\$PATH"
EOF
----

==== set up ssh pubkey authentification

Then create an SSH keypair for piupartss and put it into
'/etc/ssh/userkeys/piupartsm' on pejacevic, so the piupartss user can login
with ssh and run only piuparts-master. Restrict it like this:

----
$ cat /etc/ssh/userkeys/piupartsm
command="/srv/piuparts.debian.org/share/piuparts/piuparts-master",from="2001:41c8:1000:21::21:7,5.153.231.7",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-rsa ...
----

=== Setup sudo for the slave(s)

This is actually done by DSA:

==== '/etc/sudoers' for piu-slave-bm-a and piu-slave-ubc-01

----
# The piuparts slave needs to handle chroots.
piupartss       ALL = NOPASSWD: /usr/sbin/piuparts *, \
                                /bin/umount /srv/piuparts.debian.org/tmp/tmp*, \
                                /usr/bin/test -f /srv/piuparts.debian.org/tmp/tmp*, \
                                /usr/bin/rm -rf --one-file-system /srv/piuparts.debian.org/tmp/tmp*
----

=== Apache configuration

Any other webserver will do but apache is used on pejacevic (and maintained by DSA):

----
<VirtualHost *:80>
	ServerName piuparts.debian.org

	ServerAdmin debian-admin@debian.org

	ErrorLog /var/log/apache2/piuparts.debian.org-error.log
	CustomLog /var/log/apache2/piuparts.debian.org-access.log combined

	DocumentRoot /srv/piuparts.debian.org/htdocs
	AddType text/plain .log
	AddDefaultCharset utf-8

	HostnameLookups Off
	UseCanonicalName Off
	ServerSignature On
	<IfModule mod_userdir.c>
		UserDir disabled
	</IfModule>
</VirtualHost>
# vim:set syn=apache:
----

== Running piuparts

=== Updating the piuparts installation

Updating the master, pejacevic.debian.org:

----
holger@pejacevic~$ sudo su - piupartsm update-piuparts-master-setup develop origin
----

Updating the slave(s), for example on piu-slave-bm-a.debian.org:

----
holger@piu-slave-bm-a~$ sudo su - piupartss update-piuparts-slave-setup develop origin
----

=== Running piuparts

When running piuparts in master/slave mode, the master is never run by itself,
instead it is always started by the slave(s).

==== Starting and stopping the slaves

Run the following script under *your* user account to start four instances of
piuparts-slave on pejacevic, piuparts-master will be started automatically by
the slaves.

----
holger@piu-slave-bm-a:~$ sudo -u piupartss -i slave_run
----

There are several cronjobs installed via '~piupartsm/crontab' and
'~piupartss/crontab') to monitor both master and slave as well as the hosts
they are running on.

It's possible to kill a slave any time by pressing Ctrl-C.
Pressing Ctrl-C once will wait for the current test to finish,
pressing twice will abort the currently running test (which will be redone).
Clean termination may take some time and can be aborted by a third Ctrl-C,
but that may leave temporary directories and processes around.

See the 'piuparts_slave_run (8)' manpage for more information on 'slave_run'.

==== Joining an existing slave session

Run the following script under *your* user account:

----
holger@pejacevic:~$ sudo -u piupartss -i slave_join
----

See the 'piuparts_slave_join (8)' manpage for more information on 'slave_join'.

=== Generating reports for the website

'piuparts-report' is run daily at midnight and at noon from
'~piupartsm/crontab' on pejacevic.

=== Cronjobs to aid problem spotting

Some cronjobs to aid problem spotting reside in '~piupartsm/bin/' and are run
daily by '~piupartsm/crontab'.

- 'detect_network_issues' should detect failed piuparts runs due to network
  issues on the host.
- 'detect_stale_mounts' should detect stale mountpoints (usually of /proc)
  from failed piuparts runs.

More checks should be added as we become aware of them.


== Authors

Last updated: February 2017

Holger Levsen <holger@layer-acht.org>

// vim: set filetype=asciidoc:
