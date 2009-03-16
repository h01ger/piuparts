Notes about the installation 
============================

todo
----
- use local mirror
- look at the irssi_away script to see how to monitor screen sessions, to notify when piuparts is hanging
- document/do: /var/www needs to be populated, /etc/apache2/ too
- document users needed
- document sudoers need
- in -master.py and -slave.py: create master + slave dirs if they dont exists 
- fix the Makefile so that there is clean way not to install example configuration

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
- installation from svn source
	cd /org/puiparts.debian.org
	svn co svn://svn.debian.org/svn/piuparts/trunk src
        cd src
	sudo make prefix=/org/piuparts.debian.org etcdir=/org/piuparts.debian.org/etc install && sudo rm ../etc/piuparts/ -Rf
- piuparts-report.py is run from ~/piupartsm/crontab

to start a new run and throw away all results:
----------------------------------------------
piupartss@piatti:/org/piuparts.debian.org$ ./update-piuparts-setup
piupartss@piatti:/org/piuparts.debian.org/slave$ nice python ../../share/piuparts/piuparts-slave.py 


March 2009
Luk Claes <luk@debian.org>
Holger Levsen <holger@debian.org> 
