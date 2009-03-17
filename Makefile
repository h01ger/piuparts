prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
libdir = $(prefix)/lib
site24 = $(libdir)/python2.4/site-packages
site25 = $(libdir)/python2.5/site-packages
etcdir = $(prefix)/etc
distribution=${shell dpkg-parsechangelog | sed -n 's/^Distribution: *//p'}
ifeq ($(distribution),UNRELEASED)
version=${shell echo "`dpkg-parsechangelog | sed -n 's/^Version: *//p'`~`date +%Y%m%d`"}
else
version=${shell dpkg-parsechangelog | sed -n 's/^Version: *//p'}
endif

ignore = -I fdmount -N

all: piuparts.1 

piuparts.1: piuparts.docbook
	docbook2x-man --encoding=utf-8 piuparts.docbook

install-conf:
	install -d $(etcdir)/piuparts
	for x in master slave report; do \
	    install -m 0644 piuparts-$$x.conf.sample \
	                    $(etcdir)/piuparts/piuparts-$$x.conf; done

install-py: 
	install -d $(sbindir) 
	echo $(version)
	sed -e 's/__PIUPARTS_VERSION__/$(version)/g' piuparts.py > piuparts
	install piuparts $(sbindir)/piuparts

	install -d $(man1dir) 
	install -m 0644 piuparts.1 $(man1dir)
	gzip -9f $(man1dir)/piuparts.1

	install -d $(sharedir)/piuparts
	for file in piuparts-slave piuparts-master piuparts-report; do \
	    sed "/^CONFIG_FILE = /s:\".*\":\"/etc/piuparts/$$file.conf\":" \
	        $$file.py > $(sharedir)/piuparts/$$file.py; done
	install piuparts-analyze.py $(sharedir)/piuparts/piuparts-analyze
	chmod +x $(sharedir)/piuparts/*.py

	install -d $(site24)/piupartslib
	install -d $(site25)/piupartslib
	install -m 0644 piupartslib/*.py $(site24)/piupartslib
	install -m 0644 piupartslib/*.py $(site25)/piupartslib

install: install-py install-conf

check:
	python piuparts.py unittest
	python unittests.py

clean:
	rm -rf piuparts.1 piuparts
