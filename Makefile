prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
libdir = $(prefix)/lib
docdir = $(prefix)/share/doc/piuparts/
site26 = $(libdir)/python2.6/dist-packages
site27 = $(libdir)/python2.7/dist-packages
htdocsdir	 = $(sharedir)/piuparts/htdocs
etcdir = $(prefix)/etc

distribution=${shell dpkg-parsechangelog | sed -n 's/^Distribution: *//p'}
ifeq ($(distribution),UNRELEASED)
version		:= ${shell echo "`dpkg-parsechangelog | sed -n 's/^Version: *//p'`~`date +%Y%m%d%H%M`~`git describe --dirty`"}
else
version		:= ${shell dpkg-parsechangelog | sed -n 's/^Version: *//p'}
endif


# generate several scripts, conffiles, ... from templates (*.in, *.py)
# by substituting placeholders
SCRIPTS_TEMPLATES	 = $(wildcard master-bin/*.in slave-bin/*.in conf/*.in)
SCRIPTS_PYTHON_BINARY	 = $(wildcard *.py)
SCRIPTS_GENERATED	 = $(SCRIPTS_TEMPLATES:.in=) $(SCRIPTS_PYTHON_BINARY:.py=)
DOCS_GENERATED		 = piuparts.1 piuparts.1.html README.html

define placeholder_substitution
	sed -r \
	-e 's/__PIUPARTS_VERSION__/$(version)/g' \
	-e 's%@sharedir@%$(sharedir)%g' \
	$< > $@
endef

%: %.in Makefile
	$(placeholder_substitution)

%: %.py Makefile
	$(placeholder_substitution)


all: install install-doc

python-syntax-check:
	@set -e -x; $(foreach py,$(wildcard *.py piupartslib/*.py),python -m py_compile $(py);)

build: build-stamp

build-stamp: $(SCRIPTS_GENERATED) $(DOCS_GENERATED) Makefile
	$(MAKE) python-syntax-check
	touch $@

build-doc: $(DOCS_GENERATED)

README.html: README.txt
	a2x --copy -a toc -a toclevels=3 -f xhtml -r /etc/asciidoc/ README.txt

piuparts.1: piuparts.1.txt
	a2x -f manpage piuparts.1.txt

piuparts.1.html: piuparts.1.txt
	a2x --copy -f xhtml piuparts.1.txt

install-doc: build-stamp
	install -d $(DESTDIR)$(docdir)/
	install -m 0644 README.txt README.html docbook-xsl.css $(DESTDIR)$(docdir)/
	install -d $(DESTDIR)$(man1dir)
	install -m 0644 piuparts.1 $(DESTDIR)$(man1dir)/
	gzip -9f $(DESTDIR)$(man1dir)/piuparts.1
	install -m 0644 piuparts.1.html $(DESTDIR)$(docdir)/

install-conf: build-stamp
	install -d $(DESTDIR)$(etcdir)/piuparts
	install -m 0644 conf/piuparts.conf.sample $(DESTDIR)$(etcdir)/piuparts/piuparts.conf
	install -m 0644 conf/distros.conf $(DESTDIR)$(etcdir)/piuparts/

	install -d $(DESTDIR)$(etcdir)/cron.d
	install -m 0644 conf/crontab-master $(DESTDIR)$(etcdir)/cron.d/piuparts-master
	install -m 0644 conf/crontab-slave $(DESTDIR)$(etcdir)/cron.d/piuparts-slave
	sed -i -r '/^[^#]+/s/^/#/' $(DESTDIR)$(etcdir)/cron.d/piuparts-*

	install -d $(DESTDIR)$(etcdir)/sudoers.d
	install -m 440 conf/piuparts.sudoers $(DESTDIR)$(etcdir)/sudoers.d/piuparts
	sed -i -r '/^[^#]+/s/^/#/' $(DESTDIR)$(etcdir)/sudoers.d/piuparts

	install -d $(DESTDIR)$(etcdir)/apache2/conf.d
	install -m 0644 conf/piuparts.apache $(DESTDIR)$(etcdir)/apache2/conf.d/

install-conf-4-running-from-git: build-stamp
	install -d $(DESTDIR)$(etcdir)/piuparts
	install -m 0644 conf/crontab-master $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 conf/crontab-slave $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 conf/distros.conf $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 instances/forward.* $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 instances/piuparts.conf.* $(DESTDIR)$(etcdir)/piuparts/
	install -d $(DESTDIR)$(sharedir)/piuparts/slave
	install -m 0755 update-piuparts-setup $(DESTDIR)$(sharedir)/piuparts/slave/

install: build-stamp
	install -d $(DESTDIR)$(sbindir)
	install -m 0755 piuparts $(DESTDIR)$(sbindir)/

	install -d $(DESTDIR)$(sharedir)/piuparts
	install -m 0755 piuparts-slave piuparts-master-backend piuparts-report piuparts-analyze $(DESTDIR)$(sharedir)/piuparts/

	install -d $(DESTDIR)$(site26)/piupartslib
	install -d $(DESTDIR)$(site27)/piupartslib
	install -m 0644 piupartslib/*.py $(DESTDIR)$(site26)/piupartslib/
	install -m 0644 piupartslib/*.py $(DESTDIR)$(site27)/piupartslib/

	install -d $(DESTDIR)$(sharedir)/piuparts/lib
	install -m 0644 lib/*.sh $(DESTDIR)$(sharedir)/piuparts/lib/

	# do not install the templates (*.in)
	install -d $(DESTDIR)$(sharedir)/piuparts/master
	install -m 0755 $(filter-out %.in,$(wildcard master-bin/*)) $(DESTDIR)$(sharedir)/piuparts/master/

	install -d $(DESTDIR)$(sharedir)/piuparts/known_problems
	install -m 0644 known_problems/*.conf $(DESTDIR)$(sharedir)/piuparts/known_problems/

	# do not install the templates (*.in)
	install -d $(DESTDIR)$(sharedir)/piuparts/slave
	install -m 0755 $(filter-out %.in,$(wildcard slave-bin/*)) $(DESTDIR)$(sharedir)/piuparts/slave/

	install -d $(DESTDIR)$(htdocsdir)
	install -m 0644 htdocs/*.* $(DESTDIR)$(htdocsdir)/

	install -d $(DESTDIR)$(htdocsdir)/images
	install -m 0644 htdocs/images/*.* $(DESTDIR)$(htdocsdir)/images/

	install -d $(DESTDIR)$(htdocsdir)/templates/mail
	install -m 0644 bug-templates/*.mail $(DESTDIR)$(htdocsdir)/templates/mail/

	install -d $(DESTDIR)$(etcdir)/piuparts
	@set -e -x ; \
	for d in $$(ls custom-scripts) ; do \
		install -d $(DESTDIR)$(etcdir)/piuparts/$$d ; \
		install -m 0755 custom-scripts/$$d/* $(DESTDIR)$(etcdir)/piuparts/$$d/ ; done

	#install -d $(DESTDIR)$(etcdir)/piuparts/known_problems
	#install -m 0644 known_problems/*.conf $(DESTDIR)$(etcdir)/piuparts/known_problems/


check:
	python piuparts.py unittest
	python unittests.py

clean:
	rm -f build-stamp
	rm -f piuparts.1 piuparts.1.xml piuparts.1.html README.xml README.html docbook-xsl.css piuparts.html
	rm -f *.pyc piupartslib/*.pyc
	rm -f $(SCRIPTS_GENERATED)
