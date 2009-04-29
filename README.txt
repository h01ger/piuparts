Notes about the piuparts installation on piatti.debian.org 
==========================================================

== ToDo

- review sudoers and come up with (a bit) more restrictive one
- there should be a 2nd group of piuparts-people. those who can sudo into piupartsm to process logfiles. maybe make that the qa-group

== Installation

=== User setup

A piupartss and a piupartsm user is need. Both are members of the group piuparts and /org/piuparts.debian.org is 774 piupartss.piuparts.
Both user have some files in $HOME which are kept in svn, including hidden files.

Create an SSH keypair for piupartss and put it into ~/.ssh/authorized_keys of the piupartsm user, so the piupartss can login with ssh to localhost as piupartsm.

=== '/etc/sudoers' for piatti

----
# The piuparts slave needs to handle chroots
piupartss       ALL=(ALL) NOPASSWD: ALL

#piuparts admins
%piuparts       ALL=(piupartss) ALL
%piuparts       ALL=(piupartsm) ALL
---

=== piuparts installation from svn source

* sudo apt-get install apt python debootstrap lsof lsb-release python-debian make dpkg-dev python-support asciidoc xmlto python-rpy r-recommended r-base-dev gs
* you need a webserver too, if you run the master
* Copy 'svn://svn.debian.org/svn/piuparts/piatti/home/piupartss/bin/update-piuparts-setup' on the host and run it. It assumes you want to set it up in '/org/piuparts.debian.org' and does all further svn checkouts as well as source code installation. It needs the piupartss and piupartsm user set up as described below, though.
* sudo ln -s /org/piuparts.debian.org/etc/ /etc/piuparts
	
=== Apache configuration

(Any other webserver will do.)
----
<VirtualHost *:80>
        ServerName piuparts.debian.org
        ServerAlias piuparts.cs.helsinki.fi

        ServerAdmin debian-admin@debian.org

        ErrorLog /var/log/apache2/piuparts.debian.org-error.log
        CustomLog /var/log/apache2/piuparts.debian.org-access.log combined

        DocumentRoot /org/piuparts.debian.org/htdocs

        HostnameLookups Off
        UseCanonicalName Off
        ServerSignature On
        <IfModule mod_userdir.c>
                UserDir disabled
        </IfModule>
</VirtualHost>
----

== Updating the piuparts installtion

----
piupartss@piatti:/org/piuparts.debian.org$ ./update-piuparts-setup
----

== Running piuparts

=== Starting the slave

Run the following script under *your* user account you will start piuparts-slave on piatti, piuparts-master will be started automatically by the slave.

----
holger@piatti:~$ sudo /home/piupartss/bin/slave_run 
----

There are several cronjobs installed via '~piupartsm/crontab' and '~piupartss/crontab') which monitor the slave and the host it's running on.

=== Joining an existing slave session

Run the following script under *your* user account:

----
holger@piatti:~$ sudo /home/piupartss/bin/slave_join 
----

=== Filing bugs

Use the following usertags:

----
User: debian-qa@lists.debian.org
Usertags: piuparts piuparts.d.o
----

=== Generating reports for the website

'piuparts-report' is run daily five minutes after midnight from '~piupartsm/crontab'

=== Cronjobs to aid problem spotting

Some cronjobs to aid problem spotting reside in '~piupartsm/bin/' and are run daily by '~piupartsm/crontab'.

- 'detect_network_issues' should detect failed piuparts runs due to network issues on the host.
- 'detect_stale_mounts' should detect stale mountpoints (usually of /proc) from failed piuparts runs.

More checks should be added as we become aware of them.


== Authors

March+April 2009

Holger Levsen <holger@debian.org>
Luk Claes <luk@debian.org>

