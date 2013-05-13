Notes about the piuparts installation on pejacevic.debian.org and it's slave
============================================================================

This document describes the setup for http://piuparts.debian.org - it's used 
for reference for the Debian System Administrators (DSA) as well as a guide
for other setting up a similar system, with the piuparts source code
installed from git. For regular installations we recommend to use the
piuparts-master and piuparts-slaves packages as described in 
/usr/share/doc/piuparts-master/README_server.txt

== Installation

piuparts.debian.org is a setup running on two systems: pejacevic.debian.org, running the piuparts-master instance and an apache webserver to display the results and piu-slave-bm-a.debian.org, running a piuparts-slave node. Hopefully soon there should be several slave-nodes running on that system.

=== User setup

A piupartss (on piu-slave-bm-a) and a piupartsm (on pejacevic) user is needed. Both are members of the group piuparts and '/srv/piuparts.debian.org' is 774 piupartss:piuparts.

Create an SSH keypair for piupartss and put it into '/etc/ssh/userkeys/piupartsm' on pejacevic, so the piupartss can login with ssh and run piuparts-master.
Restrict it like this:

----
$ cat /etc/ssh/userkeys/piupartsm
command="/srv/piuparts.debian.org/share/piuparts/piuparts-master",from="2001:41c8:1000:21::21:7,5.153.231.7",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-rsa ...
----

=== '/etc/sudoers' for pejacevic

----
#piuparts admins
%piuparts       ALL=(piupartsm) ALL
----

=== '/etc/sudoers' for piu-slave-bm-a

----
# The piuparts slave needs to handle chroots.
piupartss       ALL = NOPASSWD: ALL

#piuparts admins
%piuparts       ALL=(piupartss) ALL
----


=== piuparts installation from source

* sudo apt-get build-dep piuparts
* you need a webserver too, if you run the master
* Copy 'http://anonscm.debian.org/gitweb/?p=piuparts/piuparts.git;hb=develop;a=blob_plain;f=update-piuparts-setup' on the host and run it under the 'piupartss' user. It assumes you want to set it up in '/srv/piuparts.debian.org' and does all further updates from git as well as the initial installation. It needs the piupartss and piupartsm user set up as described below, though.
* mkdir /srv/piuparts.debian.org
* sudo ln -s /srv/piuparts.debian.org/etc/piuparts /etc/piuparts

=== Apache configuration

(Any other webserver will do.)
----
<VirtualHost *:80>
        ServerName piuparts.debian.org

        ServerAdmin debian-admin@debian.org

        ErrorLog /var/log/apache2/piuparts.debian.org-error.log
        CustomLog /var/log/apache2/piuparts.debian.org-access.log combined

        DocumentRoot /srv/piuparts.debian.org/htdocs

        DefaultType text/plain

        HostnameLookups Off
        UseCanonicalName Off
        ServerSignature On
        <IfModule mod_userdir.c>
                UserDir disabled
        </IfModule>
</VirtualHost>
----

== Updating the piuparts installation

Updating the master, pejacevic.debian.org:

----
holger@pejacevic$ sudo su - piupartsm update-piuparts-master-setup bikeshed origin
----

Updating the slave, piu-slave-bm-a.debian.org:

----
holger@piu-slave-bm-a$ sudo su - piupartss update-piuparts-slave-setup bikeshed origin
----

== Running piuparts

=== Starting and stopping the slave

Run the following script under *your* user account you will start piuparts-slave on pejacevic, piuparts-master will be started automatically by the slave.

----
holger@pejacevic:~$ sudo -u piupartss -i slave_run
----

There are several cronjobs installed via '~piupartsm/crontab' and
'~piupartss/crontab') which monitor the slave and the host it's running on.

It's possible to kill the slave any time by pressing Ctrl-C.
Pressing Ctrl-C once will wait for the current test to finish,
pressing twice will abort the currently running test (which will be redone).
Clean termination may take some time and can be aborted by a third Ctrl-C,
but that may leave temporary directories and processes around.

=== Joining an existing slave session

Run the following script under *your* user account:

----
holger@pejacevic:~$ sudo -u piupartss -i slave_join
----

=== Filing bugs

Use the following usertags:

----
User: debian-qa@lists.debian.org
Usertags: piuparts piuparts.d.o
----

=== Generating reports for the website

'piuparts-report' is run daily five minutes after midnight from '~piupartsm/crontab' on pejacevic.

=== Cronjobs to aid problem spotting

Some cronjobs to aid problem spotting reside in '~piupartsm/bin/' and are run daily by '~piupartsm/crontab'.

- 'detect_network_issues' should detect failed piuparts runs due to network issues on the host.
- 'detect_stale_mounts' should detect stale mountpoints (usually of /proc) from failed piuparts runs.

More checks should be added as we become aware of them.


== Authors

Last updated: May 2013

Holger Levsen <holger@debian.org>

// vim: set filetype=asciidoc:
