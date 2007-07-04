prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
libdir = $(prefix)/lib
site23 = $(libdir)/python2.3/site-packages
site24 = $(libdir)/python2.4/site-packages
etcdir = $(prefix)/etc
version=${shell dpkg-parsechangelog | sed -n 's/^Version: *//p'}


# mirror = -m 'http://liw.iki.fi/debian main'
ignore = -I fdmount -N

all: piuparts.1 

piuparts.1: piuparts.docbook
	docbook2x-man --encoding=utf-8 piuparts.docbook

install: all
	install -d $(sbindir) 
	echo $(version)
	sed 's/__PIUPARTS_VERSION__/$(version)/g' piuparts.py > piuparts
	install piuparts $(sbindir)/piuparts

	install -d $(man1dir) 
	install -m 0644 piuparts.1 $(man1dir)
	gzip -9f $(man1dir)/piuparts.1

	install -d $(sharedir)/piuparts
	for file in piuparts-slave piuparts-master; do \
	    sed "/^CONFIG_FILE = /s:\".*\":\"/etc/piuparts/$$file.conf\":" \
	        $$file.py > $(sharedir)/piuparts/$$file.py; done
	install piuparts-analyze.py $(sharedir)/piuparts/piuparts-analyze
	chmod +x $(sharedir)/piuparts/*.py

	install -d $(site23)/piupartslib
	install -d $(site24)/piupartslib
	install -m 0644 piupartslib/*.py $(site23)/piupartslib
	install -m 0644 piupartslib/*.py $(site24)/piupartslib

	install -d $(etcdir)/piuparts
	for x in master slave; do \
	    install -m 0644 piuparts-$$x.conf.sample \
	                    $(etcdir)/piuparts/piuparts-$$x.conf; done

# The 'check' target probably only works for me. Sorry. Eventually this
# should get a proper test suite, but that's for a later day.
check: unittests
	python piuparts.py $(mirror) $(ignore) -l tmp.log -d sarge test-debs/liwc*.deb
	python piuparts.py $(mirror) $(ignore) -l tmp2.log -d sarge -d etch test-debs/liwc*.deb
	python piuparts.py $(mirror) $(ignore) -l tmp3.log -d sarge -d etch -a liwc

unittests:
	python piuparts.py unittest
	python unittests.py

clean:
	rm -rf piuparts.1 piuparts
