#!/bin/sh

cd ~piupartsm/piuparts-master/

set -e

while true
do
    echo $(date "+%Y-%m-%d %H:%M") \
        pass: $(ls pass | wc -l) \
        fail: $(ls fail | wc -l) \
	spass: $(ls ~piupartss/pass | wc -l) \
	sfail: $(ls ~piupartss/fail | wc -l)
    sleep 600
done
