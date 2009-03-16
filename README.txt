Notes about the installation 
============================

todo
----
- use local mirror
- document/do: /var/www needs to be populated, /etc/apache2/ too
- fix the Makefile so that there is clean way not to install example configuration
- there should be a 2nd group of piuparts-people. those who can sudo into piupartsm to process logfiles. maybe make that the qa-group

done
----
- in /org/
	svn co svn://svn.debian.org/svn/piuparts/piatti/org/piuparts.debian.org .
	mkdir slave master tmp cd slave && mkdir sid squeeze lenny2squeeze \
          && cd ../master && mkdir sid squeeze lenny2squeeze && cd .. && chmod g+w slave master
- in /home/piupartss:
	put "export PYTHONPATH=/org/piuparts.debian.org/lib/python2.4/site-packages:/org/piuparts.debian.org/lib/python2.5/site-packages" into .bashrc
- in /home/piupartsm:
	put id_rsa.pub from piupartss into .ssh/authorized_keys
	put "export PYTHONPATH=/org/piuparts.debian.org/lib/python2.4/site-packages:/org/piuparts.debian.org/lib/python2.5/site-packages" into .bashrc

piuparts users
--------------
A piupartss and a piupartsm user is need. Both are members of the group piuparts and /org/piuparts.debian.org is 774 piupartss.piuparts.

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

cd /org/puiparts.debian.org
svn co svn://svn.debian.org/svn/piuparts/trunk src
# checkout elsewhere
# run script

generating reports
------------------
piuparts-report.py is run from ~/piupartsm/crontab

to start a new run and throw away all results:
----------------------------------------------
piupartss@piatti:/org/piuparts.debian.org$ ./update-piuparts-setup
piupartss@piatti:/org/piuparts.debian.org/slave$ nice python ../../share/piuparts/piuparts-slave.py 

filing bugs
-----------
to be written


March 2009
Luk Claes <luk@debian.org>
Holger Levsen <holger@debian.org> 
