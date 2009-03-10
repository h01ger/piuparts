#!/bin/sh

apt-get update 
echo debug XXX
cat /etc/apt/sources.list
dpkg -l tzdata && apt-get install libstdc++6 && apt-get dist-upgrade
