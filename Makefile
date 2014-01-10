prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
man8dir = $(mandir)/man8
libdir = $(prefix)/lib
docdir = $(prefix)/share/doc/piuparts/
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
SCRIPTS_TEMPLATES	 = $(wildcard *.in master-bin/*.in slave-bin/*.in conf/*.in)
SCRIPTS_PYTHON_BINARY	 = $(wildcard *.py master-bin/*.py slave-bin/*.py)
SCRIPTS_GENERATED	 = $(SCRIPTS_TEMPLATES:.in=) $(SCRIPTS_PYTHON_BINARY:.py=)
DOCS_GENERATED		 = piuparts.1 piuparts.1.html piuparts_slave_run.8 piuparts_slave_join.8 README_1st.html README_server.html

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


all: build

python_scripts	 = $(wildcard *.py piupartslib/*.py master-bin/*.py slave-bin/*.py)
python-syntax-check:
	@set -e -x; $(foreach py,$(python_scripts),python -m py_compile $(py);)
	$(RM) $(python_scripts:=c)

build: build-stamp

build-stamp: $(SCRIPTS_GENERATED) $(DOCS_GENERATED) Makefile
	$(MAKE) python-syntax-check
	touch $@

build-doc: $(DOCS_GENERATED)

README_1st.html: README_1st.txt
	a2x --copy -a toc -a toclevels=3 -f xhtml -r /etc/asciidoc/ README_1st.txt

README_server.html: README_server.txt
	a2x --copy -a toc -a toclevels=3 -f xhtml -r /etc/asciidoc/ README_server.txt

piuparts.1: piuparts.1.txt
	a2x -f manpage piuparts.1.txt

piuparts_slave_run.8: piuparts_slave_run.8.txt
	a2x -f manpage piuparts_slave_run.8.txt

piuparts_slave_join.8: piuparts_slave_join.8.txt
	a2x -f manpage piuparts_slave_join.8.txt

piuparts.1.html: piuparts.1.txt
	a2x --copy -f xhtml piuparts.1.txt

install-doc: build-stamp
	install -d $(DESTDIR)$(docdir)/
	install -m 0644 README_1st.txt README_1st.html README_server.txt README_server.html docbook-xsl.css $(DESTDIR)$(docdir)/
	install -d $(DESTDIR)$(man1dir)
	install -m 0644 piuparts.1 $(DESTDIR)$(man1dir)/
	install -d $(DESTDIR)$(man8dir)
	install -m 0644 piuparts_slave_run.8 piuparts_slave_join.8 $(DESTDIR)$(man8dir)/
	gzip -9f $(DESTDIR)$(man1dir)/piuparts.1
	gzip -9f $(DESTDIR)$(man8dir)/piuparts_slave_run.8
	gzip -9f $(DESTDIR)$(man8dir)/piuparts_slave_join.8
	install -m 0644 piuparts.1.html $(DESTDIR)$(docdir)/

install-conf: build-stamp
	install -d $(DESTDIR)$(etcdir)/piuparts
	install -m 0644 conf/piuparts.conf.sample $(DESTDIR)$(etcdir)/piuparts/piuparts.conf
	install -m 0644 conf/distros.conf $(DESTDIR)$(etcdir)/piuparts/

	install -d $(DESTDIR)$(etcdir)/cron.d
	install -m 0644 conf/crontab-master $(DESTDIR)$(etcdir)/cron.d/piuparts-master
	install -m 0644 conf/crontab-slave $(DESTDIR)$(etcdir)/cron.d/piuparts-slave
	# disable shipped crontabs
	sed -i -r '/^[^#]+/s/^/#/' $(DESTDIR)$(etcdir)/cron.d/piuparts-*

	install -d $(DESTDIR)$(etcdir)/sudoers.d
	install -m 440 conf/piuparts.sudoers $(DESTDIR)$(etcdir)/sudoers.d/piuparts
	# disable shipped sudoers
	sed -i -r '/^[^#]+/s/^/#/' $(DESTDIR)$(etcdir)/sudoers.d/piuparts

	install -d $(DESTDIR)$(etcdir)/apache2/conf.d
	install -m 0644 conf/piuparts.apache $(DESTDIR)$(etcdir)/apache2/conf.d/

install-conf-4-running-from-git: build-stamp
	install -d $(DESTDIR)$(etcdir)/piuparts
	install -m 0644 conf/crontab-master $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 conf/crontab-slave $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 conf/distros.conf $(DESTDIR)$(etcdir)/piuparts/
	install -m 0644 instances/piuparts.conf.* $(DESTDIR)$(etcdir)/piuparts/
	install -d $(DESTDIR)$(sharedir)/piuparts/slave
	install -m 0755 update-piuparts-slave-setup $(DESTDIR)$(sharedir)/piuparts/slave/
	install -d $(DESTDIR)$(sharedir)/piuparts/master
	install -m 0755 update-piuparts-master-setup $(DESTDIR)$(sharedir)/piuparts/master/

install: build-stamp
	install -d $(DESTDIR)$(sbindir)
	install -m 0755 piuparts $(DESTDIR)$(sbindir)/

	install -d $(DESTDIR)$(sharedir)/piuparts
	install -m 0755 piuparts-slave piuparts-master piuparts-master-backend piuparts-report piuparts-analyze $(DESTDIR)$(sharedir)/piuparts/

	install -d $(DESTDIR)$(site27)/piupartslib
	install -m 0644 piupartslib/*.py $(DESTDIR)$(site27)/piupartslib/

	install -d $(DESTDIR)$(sharedir)/piuparts/lib
	install -m 0644 lib/*.sh $(DESTDIR)$(sharedir)/piuparts/lib/

	# do not install the templates (*.in, *.py)
	install -d $(DESTDIR)$(sharedir)/piuparts/master
	install -m 0755 $(filter-out %.in %.py,$(wildcard master-bin/*)) $(DESTDIR)$(sharedir)/piuparts/master/

	install -d $(DESTDIR)$(sharedir)/piuparts/known_problems
	install -m 0644 known_problems/*.conf $(DESTDIR)$(sharedir)/piuparts/known_problems/

	# do not install the templates (*.in, *.py)
	install -d $(DESTDIR)$(sharedir)/piuparts/slave
	install -m 0755 $(filter-out %.in %.py,$(wildcard slave-bin/*)) $(DESTDIR)$(sharedir)/piuparts/slave/

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
	nosetests -c nosetests.cfg

clean:
	rm -f build-stamp
	rm -f $(DOCS_GENERATED)
	rm -f piuparts.1.xml README.xml README_server.xml docbook-xsl.css piuparts.html
	rm -f *.pyc piupartslib/*.pyc master-bin/*.pyc slave-bin/*.pyc
	rm -f $(SCRIPTS_GENERATED)


# for maintainer convenience only
tg-deps:
	tg summary --graphviz | dot -T png -o deps.png
	xli deps.png &
