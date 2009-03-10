#!/bin/sh

echo "DebugXXX: running $0"

apt-get update 
cat /etc/apt/sources.list
dpkg -l tzdata && { 
	apt-get -y --force-yes install libstdc++6
	apt-get upgrade
	apt-get dist-upgrade
}
	
