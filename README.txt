Notes about the piuparts installation on piatti.debian.org 
==========================================================

todo
----
- script for starting piuparts-slave in screen and cronjob to send mail with its output
- use local mirror
- there should be a 2nd group of piuparts-people. those who can sudo into piupartsm to process logfiles. maybe make that the qa-group


User setup
----------
A piupartss and a piupartsm user is need. Both are members of the group piuparts and /org/piuparts.debian.org is 774 piupartss.piuparts.
Both user have some files in $HOME which are kept in svn, including hidden files.

Create an SSH keypair for piupartss and put it into ~/.ssh/authorized_keys of the piupartsm user, so the piupartss can login with ssh to localhost as piupartsm.

'/etc/sudoers' for piatti
-------------------------
# The piuparts slave needs to handle chroots
piupartss       ALL=(ALL) NOPASSWD: ALL

#piuparts admins
%piuparts       ALL=(piupartss) ALL
%piuparts       ALL=(piupartsm) ALL
---

piuparts installation from svn source
-------------------------------------
* sudo apt-get install apt python debootstrap lsof lsb-release python-debian make dpkg-dev docbook2x python-support docbook-xml asciidoc 
* you need a webserver too, if you run the master
* Copy 'svn://svn.debian.org/svn/piuparts/piatti/home/piupartss/bin/update-piuparts-setup' on the host and run it. It assumes you want to set it up in '/org/piuparts.debian.org' and does all further svn checkouts as well as source code installation. It needs the piupartss and piupartsm user set up as described below, though.
* sudo ln -s /org/piuparts.debian.org/etc/ /etc/piuparts
	
Apache configuration
--------------------
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

Generating reports for the website
----------------------------------
'piuparts-report' is run from '~piupartsm/crontab'


Cronjobs to aid problem spotting
--------------------------------
Reside in '~piupartsm/bin/' and are run by '~piupartsm/crontab'.

- 'detect_network_issues' should detect failed piuparts runs due to network issues on the host.
- 'detect_stale_mounts' should detect stale mountpoints (usually of /proc) from failed piuparts runs.

More checks should be added as we become aware of them.


to start a new run and throw away all results:
----------------------------------------------
----
piupartss@piatti:/org/piuparts.debian.org$ ./update-piuparts-setup
piupartss@piatti:/org/piuparts.debian.org/slave$ nice python ../share/piuparts/piuparts-slave 
----

filing bugs
-----------
to be written


March 2009
Luk Claes <luk@debian.org>
Holger Levsen <holger@debian.org> 
