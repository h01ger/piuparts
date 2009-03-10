#!/bin/sh

apt-get update
echo debugXXX
cat /etc/apt/sources.list
apt-get -yf install apt
apt-get -yf dist-upgrade
