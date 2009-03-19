Notes about the piuparts installation on piatti.debian.org 
==========================================================

todo
----
- script for starting piuparts-slave in screen and cronjob to send mail with its output
- cronjob to check number of mounts on /org/piuparts.d.o/tmp/
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
* sudo apt-get install apt python debootstrap lsof lsb-release python-debian 
* Copy 'svn:/svn.debian.org/svn/piuparts/piatti/home/piupartss/bin/update-piuparts-setup' on the host and run it. It assumes you want to set it up in '/org/piuparts.debian.org' and does all further svn checkouts as well as source code installation. It needs the piupartss and piupartsm user set up as described below, though.
	
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

        DocumentRoot /srv/piuparts.debian.org/htdocs

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
piuparts-report.py is run from ~/piupartsm/crontab

to start a new run and throw away all results:
----------------------------------------------
----
piupartss@piatti:/org/piuparts.debian.org$ ./update-piuparts-setup
piupartss@piatti:/org/piuparts.debian.org/slave$ nice python ../../share/piuparts/piuparts-slave.py 
----

filing bugs
-----------
to be written


March 2009
Luk Claes <luk@debian.org>
Holger Levsen <holger@debian.org> 
