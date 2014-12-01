#!/bin/sh

# we rely on wget being available, make sure to use "--include=wget" in your deboostrap cmdline
echo "Setting up https://example.com/internal_key.asc for apt-get usage."
wget -O - 'https://example.com/internal_key.asc' | apt-key add -

echo "Running apt-get update to have a verified and working Debian repository available."
apt-get update

