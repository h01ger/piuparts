ARCH				 = amd64
MIRROR				 = http://deb.debian.org/debian/

ARCH_piu-slave-1und1-01		 = i386
MIRROR_piu-slave-1und1-01	 = http://mirror.1und1.de/debian/

GENCONF		 = piuparts.conf.pejacevic
GENCONF		+= piuparts.conf.piu-slave-1und1-01
GENCONF		+= piuparts.conf.piu-slave-ubc-01
GENCONF		+= piuparts.conf.piu-slave-conova-01

all: $(GENCONF)

clean:
	$(RM) $(GENCONF)

piuparts.conf.%: piuparts.conf-template.pejacevic Makefile piuparts.conf-header.%
	cat piuparts.conf-header.$* > $@.tmp
	echo "" >> $@.tmp
	sed 's,@MIRROR@,$(or $(MIRROR_$*),$(MIRROR)),; s,@ARCH@,$(or $(ARCH_$*),$(ARCH)),;' < $< >> $@.tmp
	mv $@.tmp $@
