prefix = /usr/local
sbindir = $(prefix)/sbin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
man8dir = $(mandir)/man8
libdir = $(prefix)/lib
docdir = $(prefix)/share/doc/piuparts
site3 = $(libdir)/python3/dist-packages
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
DOCS_GENERATED		 = piuparts.1 piuparts_slave_run.8 piuparts_slave_join.8 piuparts_slave_stop.8 docs/build

define placeholder_substitution
	sed -r \
	-e 's/__PIUPARTS_VERSION__/$(version)/g' \
	-e 's%@libdir@%$(libdir)%g' \
	-e 's%@sharedir@%$(sharedir)%g' \
	-e 's%@sbindir@%$(sbindir)%g' \
	$< > $@
endef

%: %.in Makefile
	$(placeholder_substitution)

%: %.py Makefile
	$(placeholder_substitution)


all: build

python_scripts	 = $(wildcard *.py piupartslib/*.py master-bin/*.py slave-bin/*.py)
python-syntax-check:
	@set -e -x; $(foreach py,$(python_scripts),python3 -m py_compile $(py);)
	$(RM) $(python_scripts:=c)

build: build-stamp build-master-stamp
build-slave: build-stamp
build-master: build-stamp build-master-stamp

build-stamp: $(SCRIPTS_GENERATED) $(DOCS_GENERATED) Makefile
	$(MAKE) -C instances
	$(MAKE) python-syntax-check
	touch $@

build-master-stamp:
	(cd helpers/debiman-piuparts-distill && go build)
	touch $@

build-doc: $(DOCS_GENERATED)

docs/build: docs/build
	python3 -m sphinx docs/ docs/build/

piuparts.1: docs/piuparts/piuparts.1.txt
	python3 -m sphinx -b man -c docs/piuparts/ docs/piuparts/ ./

piuparts_slave_run.8: docs/piuparts_slave_run/piuparts_slave_run.8.txt
	python3 -m sphinx -b man -c docs/piuparts_slave_run/ docs/piuparts_slave_run/ ./

piuparts_slave_join.8: docs/piuparts_slave_join/piuparts_slave_join.8.txt
	python3 -m sphinx -b man -c docs/piuparts_slave_join/ docs/piuparts_slave_join/ ./

piuparts_slave_stop.8: docs/piuparts_slave_stop/piuparts_slave_stop.8.txt
	python3 -m sphinx -b man -c docs/piuparts_slave_stop/ docs/piuparts_slave_stop/ ./

install-doc: build-stamp
	# txt
	install -d $(DESTDIR)$(docdir)/
	install -m 0644 docs/README.txt docs/README_server.txt $(DESTDIR)$(docdir)/
	# html
	install -d $(DESTDIR)$(docdir)/html/
	install -m 0644 docs/build/*.html $(DESTDIR)$(docdir)/html/
	install -m 0644 docs/build/searchindex.js $(DESTDIR)$(docdir)/html/
	install -m 0644 docs/build/objects.inv $(DESTDIR)$(docdir)/html/
	install -d $(DESTDIR)$(docdir)/html/_static/
	install -m 0644 docs/build/_static/* $(DESTDIR)$(docdir)/html/_static
	install -d $(DESTDIR)$(docdir)/html/piuparts/
	install -m 0644 docs/build/piuparts/index.html $(DESTDIR)$(docdir)/html/piuparts/
	install -m 0644 docs/build/piuparts/piuparts.1.html $(DESTDIR)$(docdir)/html/piuparts/
	install -d $(DESTDIR)$(docdir)/html/piuparts_slave_run/
	install -m 0644 docs/build/piuparts_slave_run/index.html $(DESTDIR)$(docdir)/html/piuparts_slave_run/
	install -m 0644 docs/build/piuparts_slave_run/piuparts_slave_run.8.html $(DESTDIR)$(docdir)/html/piuparts_slave_run/
	install -d $(DESTDIR)$(docdir)/html/piuparts_slave_join/
	install -m 0644 docs/build/piuparts_slave_join/index.html $(DESTDIR)$(docdir)/html/piuparts_slave_join/
	install -m 0644 docs/build/piuparts_slave_join/piuparts_slave_join.8.html $(DESTDIR)$(docdir)/html/piuparts_slave_join/
	install -d $(DESTDIR)$(docdir)/html/piuparts_slave_stop/
	install -m 0644 docs/build/piuparts_slave_stop/index.html $(DESTDIR)$(docdir)/html/piuparts_slave_stop/
	install -m 0644 docs/build/piuparts_slave_stop/piuparts_slave_stop.8.html $(DESTDIR)$(docdir)/html/piuparts_slave_stop/
	install -d $(DESTDIR)$(docdir)/html/
	install -m 0644 docs/build/*.html $(DESTDIR)$(docdir)/html/
	install -m 0644 docs/build/searchindex.js $(DESTDIR)$(docdir)/html/
	install -m 0644 docs/build/objects.inv $(DESTDIR)$(docdir)/html/
	install -d $(DESTDIR)$(docdir)/html/_static/
	install -m 0644 docs/build/_static/* $(DESTDIR)$(docdir)/html/_static
	install -d $(DESTDIR)$(docdir)/html/piuparts/
	install -m 0644 docs/build/piuparts/index.html $(DESTDIR)$(docdir)/html/piuparts/
	install -m 0644 docs/build/piuparts/piuparts.1.html $(DESTDIR)$(docdir)/html/piuparts/
	install -d $(DESTDIR)$(docdir)/html/piuparts_slave_run/
	install -m 0644 docs/build/piuparts_slave_run/index.html $(DESTDIR)$(docdir)/html/piuparts_slave_run/
	install -m 0644 docs/build/piuparts_slave_run/piuparts_slave_run.8.html $(DESTDIR)$(docdir)/html/piuparts_slave_run/
	install -d $(DESTDIR)$(docdir)/html/piuparts_slave_join/
	install -m 0644 docs/build/piuparts_slave_join/index.html $(DESTDIR)$(docdir)/html/piuparts_slave_join/
	install -m 0644 docs/build/piuparts_slave_join/piuparts_slave_join.8.html $(DESTDIR)$(docdir)/html/piuparts_slave_join/
	install -d $(DESTDIR)$(docdir)/html/piuparts_slave_stop/
	install -m 0644 docs/build/piuparts_slave_stop/index.html $(DESTDIR)$(docdir)/html/piuparts_slave_stop/
	install -m 0644 docs/build/piuparts_slave_stop/piuparts_slave_stop.8.html $(DESTDIR)$(docdir)/html/piuparts_slave_stop/
	# manpages
	install -d $(DESTDIR)$(man1dir)
	install -m 0644 piuparts.1 $(DESTDIR)$(man1dir)/
	gzip -9fn $(DESTDIR)$(man1dir)/piuparts.1
	install -d $(DESTDIR)$(man8dir)
	install -m 0644 piuparts_slave_run.8 piuparts_slave_join.8 piuparts_slave_stop.8 $(DESTDIR)$(man8dir)/
	gzip -9fn $(DESTDIR)$(man8dir)/piuparts_slave_run.8
	gzip -9fn $(DESTDIR)$(man8dir)/piuparts_slave_join.8
	gzip -9fn $(DESTDIR)$(man8dir)/piuparts_slave_stop.8

install-conf: build-stamp
	install -d $(DESTDIR)$(etcdir)/piuparts
	install -m 0644 conf/piuparts.conf.sample $(DESTDIR)$(etcdir)/piuparts/piuparts.conf
	install -m 0644 conf/distros.conf $(DESTDIR)$(etcdir)/piuparts/
	install -d $(DESTDIR)$(etcdir)/apache2/conf-available
	install -m 0644 conf/piuparts-master.conf $(DESTDIR)$(etcdir)/apache2/conf-available/

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

install-common: build-stamp
	install -d $(DESTDIR)$(site3)/piupartslib
	install -m 0644 piupartslib/*.py $(DESTDIR)$(site3)/piupartslib/

	install -d $(DESTDIR)$(sharedir)/piuparts/lib
	install -m 0644 lib/*.sh $(DESTDIR)$(sharedir)/piuparts/lib/

install-master: build-master-stamp install-common
	install -d $(DESTDIR)$(libdir)/piuparts/
	install -m 0755 helpers/debiman-piuparts-distill/debiman-piuparts-distill $(DESTDIR)$(libdir)/piuparts/

	install -d $(DESTDIR)$(sharedir)/piuparts
	install -m 0755 piuparts-master piuparts-master-backend piuparts-report piuparts-analyze $(DESTDIR)$(sharedir)/piuparts/

	# do not install the templates (*.in, *.py, *.) nor __pycache__
	install -d $(DESTDIR)$(sharedir)/piuparts/master
	install -m 0755 $(filter-out %.in %.py %__pycache__,$(wildcard master-bin/*)) $(DESTDIR)$(sharedir)/piuparts/master/

	install -d $(DESTDIR)$(sharedir)/piuparts/known_problems
	install -m 0644 known_problems/*.conf $(DESTDIR)$(sharedir)/piuparts/known_problems/

	install -d $(DESTDIR)$(htdocsdir)
	install -m 0644 htdocs/*.* $(DESTDIR)$(htdocsdir)/

	install -d $(DESTDIR)$(htdocsdir)/images
	install -m 0644 htdocs/images/*.* $(DESTDIR)$(htdocsdir)/images/

	install -d $(DESTDIR)$(htdocsdir)/templates/mail
	install -m 0644 bug-templates/*.mail $(DESTDIR)$(htdocsdir)/templates/mail/

	#install -d $(DESTDIR)$(etcdir)/piuparts/known_problems
	#install -m 0644 known_problems/*.conf $(DESTDIR)$(etcdir)/piuparts/known_problems/

install-slave: install-common
	install -d $(DESTDIR)$(sbindir)
	install -m 0755 piuparts $(DESTDIR)$(sbindir)/

	install -d $(DESTDIR)$(sharedir)/piuparts
	install -m 0755 piuparts-slave $(DESTDIR)$(sharedir)/piuparts/

	# do not install the templates (*.in, *.py) nor __pycache__
	install -d $(DESTDIR)$(sharedir)/piuparts/slave
	install -m 0755 $(filter-out %.in %.py %__pycache__,$(wildcard slave-bin/*)) $(DESTDIR)$(sharedir)/piuparts/slave/

	install -d $(DESTDIR)$(etcdir)/piuparts
	@set -e -x ; \
	for d in $$(ls custom-scripts) ; do \
		install -d $(DESTDIR)$(etcdir)/piuparts/$$d ; \
		install -m 0755 custom-scripts/$$d/* $(DESTDIR)$(etcdir)/piuparts/$$d/ ; done

install: install-master install-slave


check:
	python3 -m nose --verbose

clean:
	rm -f build-stamp
	rm -f build-master-stamp
	rm -fr $(DOCS_GENERATED)
	rm -fr .doctrees/
	find . -iname '*.pyc' -type f -delete
	find . -iname __pycache__ -type d -delete
	rm -f $(SCRIPTS_GENERATED)
	$(RM) helpers/debiman-piuparts-distill/debiman-piuparts-distill
	$(MAKE) -C instances clean


# for maintainer convenience only
check-whitespace:
	grep -r --exclude-dir .git --exclude '*.pyc' --exclude '*.png' --exclude '*.ico' -E '\s+$$' . || echo "no trailing whitespace found"
	grep -r --exclude-dir .git --exclude '*.pyc' --exclude '*.png' --exclude '*.ico' -P ' \t' . || echo "no space-tab combo found"

# for maintainer convenience only
tg-deps:
	tg summary --graphviz | dot -T png -o deps.png
	xli deps.png &
