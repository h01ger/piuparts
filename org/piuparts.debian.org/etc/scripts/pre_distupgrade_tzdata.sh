#!/bin/sh

dpkg -l tzdata && apt-get install libstdc++6 && apt-get dist-upgrade
