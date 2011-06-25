prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
libdir = $(prefix)/lib
docdir = $(prefix)/share/doc/piuparts/
site25 = $(libdir)/python2.5/site-packages
site26 = $(libdir)/python2.6/site-packages
etcdir = $(prefix)/etc
distribution=${shell dpkg-parsechangelog | sed -n 's/^Distribution: *//p'}
ifeq ($(distribution),UNRELEASED)
version=${shell echo "`dpkg-parsechangelog | sed -n 's/^Version: *//p'`~`date +%Y%m%d%H%M`"}
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
	    install -m 0755 $$file $(docdir)/ ; done
	# build and install manpage
	a2x -f manpage piuparts.1.txt
	install -d $(man1dir) 
	install -m 0644 piuparts.1 $(man1dir)
	gzip -9f $(man1dir)/piuparts.1
	a2x --copy -f xhtml piuparts.1.txt
	install -m 0755 piuparts.1.html $(docdir)

install-conf:
	install -d $(etcdir)/piuparts
	install -m 0644 piuparts.conf.sample $(etcdir)/piuparts/piuparts.conf

install:
	install -d $(sbindir) 
	echo $(version)
	sed -e 's/__PIUPARTS_VERSION__/$(version)/g' piuparts.py > piuparts
	install piuparts $(sbindir)/piuparts
	
	install -d $(sharedir)/piuparts
	for file in piuparts-slave piuparts-master piuparts-report piuparts-analyze; do \
	    install -m 0755 $$file.py $(sharedir)/piuparts/$$file ; done
	
	install -d $(site25)/piupartslib
	install -d $(site26)/piupartslib
	install -m 0644 piupartslib/*.py $(site25)/piupartslib
	install -m 0644 piupartslib/*.py $(site26)/piupartslib

check:
	python piuparts.py unittest
	python unittests.py

clean:
	rm -rf piuparts.1 piuparts.1.xml piuparts.1.html piuparts README.xml README.html docbook-xsl.css piuparts.html 
