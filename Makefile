prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
libdir = $(prefix)/lib
docdir = $(prefix)/share/doc/piuparts/
svrdocdir = $(prefix)/share/doc/piuparts-master
site26 = $(libdir)/python2.6/dist-packages
site27 = $(libdir)/python2.7/dist-packages
htdocsdir	 = $(sharedir)/piuparts/htdocs
etcdir = $(prefix)/etc
distribution=${shell dpkg-parsechangelog | sed -n 's/^Distribution: *//p'}
ifeq ($(distribution),UNRELEASED)
version=${shell echo "`dpkg-parsechangelog | sed -n 's/^Version: *//p'`~`date +%Y%m%d%H%M`~`git describe --tags --dirty`"}
else
version=${shell dpkg-parsechangelog | sed -n 's/^Version: *//p'}
endif

ignore = -I fdmount -N

all: install-conf install-doc install

install-doc:
	# build and install manual
	a2x --copy -a toc -a toclevels=3 -f xhtml -r /etc/asciidoc/ README.txt
	install -d $(docdir)/
	for file in README.txt README.html docbook-xsl.css ; do \
	    install -m 0644 $$file $(docdir)/ ; done
	# build and install manpage
	a2x -f manpage piuparts.1.txt
	install -d $(man1dir)
	install -m 0644 piuparts.1 $(man1dir)
	gzip -9f $(man1dir)/piuparts.1
	a2x --copy -f xhtml piuparts.1.txt
	install -m 0644 piuparts.1.html $(docdir)
	install -d $(svrdocdir)/
	install -m 0755 README_server.txt $(svrdocdir)/

install-conf:
	install -d $(etcdir)/piuparts
	install -m 0644 conf/piuparts.conf.sample $(etcdir)/piuparts/piuparts.conf

	install -d $(etcdir)/cron.d
	install -m 0644 home/piupartsm/crontab $(etcdir)/cron.d/piuparts-master
	install -m 0644 home/piupartss/crontab $(etcdir)/cron.d/piuparts-slave
	sed -i -r '/^[^#]+/s/^/#/' $(etcdir)/cron.d/piuparts-*

	install -d $(etcdir)/piuparts/known_problems
	for fl in home/piupartsm/bin/known_problems/* ; do\
            install -m 0644 $$fl $(etcdir)/piuparts/known_problems; \
        done

	install -d $(etcdir)/sudoers.d
	install -m 440 conf/piuparts.sudoers $(etcdir)/sudoers.d/piuparts
	sed -i -r '/^[^#]+/s/^/#/' $(etcdir)/sudoers.d/piuparts

	install -d $(etcdir)/apache2/conf.d
	install -m 0644 conf/piuparts.apache $(etcdir)/apache2/conf.d

	install -d $(etcdir)/piuparts/scripts
	install org/piuparts.debian.org/etc/scripts/* $(etcdir)/piuparts/scripts

install:
	install -d $(sbindir)
	sed -e 's/__PIUPARTS_VERSION__/$(version)/g' piuparts.py > piuparts
	install piuparts $(sbindir)/piuparts
	rm piuparts

	install -d $(sharedir)/piuparts
	for file in piuparts-slave piuparts-master piuparts-report piuparts-analyze; do \
	    sed -e 's/__PIUPARTS_VERSION__/$(version)/g' $$file.py > $$file ; \
	    install -m 0755 $$file $(sharedir)/piuparts/$$file ; \
	    rm $$file ; done

	install -d $(site26)/piupartslib
	install -d $(site27)/piupartslib
	install -m 0644 piupartslib/*.py $(site26)/piupartslib
	install -m 0644 piupartslib/*.py $(site27)/piupartslib

	install -d $(sharedir)/piuparts/master

	for fl in home/piupartsm/bin/* ; do\
            if [ -f $$fl ] ; then install $$fl $(sharedir)/piuparts/master ; fi ; done

	install -d $(sharedir)/piuparts/slave

	cp -r home/piupartss/bin/* $(sharedir)/piuparts/slave

	install -d $(DESTDIR)$(htdocsdir)
	for file in org/piuparts.debian.org/htdocs/* ; do\
            if [ -f $$file ] ; then \
                install -m 0644 $$file $(DESTDIR)$(htdocsdir) ;\
            fi \
        done

	install -d $(DESTDIR)$(htdocsdir)/images
	install -m 0644 org/piuparts.debian.org/htdocs/images/* $(DESTDIR)$(htdocsdir)/images/
	ln -sf /usr/share/icons/Tango/24x24/status/sunny.png $(DESTDIR)$(htdocsdir)/images/sunny.png
	ln -sf /usr/share/icons/Tango/24x24/status/weather-severe-alert.png $(DESTDIR)$(htdocsdir)/images/weather-severe-alert.png

	install -d $(DESTDIR)$(htdocsdir)/templates/mail
	for file in org/piuparts.debian.org/htdocs/templates/mail/* ; do\
		if [ -f $$file ] ; then \
			install -m 0644 $$file $(DESTDIR)$(htdocsdir)/templates/mail ;\
		fi \
	done


check:
	python piuparts.py unittest
	python unittests.py

clean:
	rm -f piuparts.1 piuparts.1.xml piuparts.1.html piuparts README.xml README.html docbook-xsl.css piuparts.html
	rm -f *.pyc piupartslib/*.pyc
