# Copyright © 2011 Andreas Beckmann <debian@abeckmann.de>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

#
# Helper function for getting values from piuparts.conf.
# Used by several master and slave scripts.
#


PIUPARTS_CONF=${PIUPARTS_CONF:-/etc/piuparts/piuparts.conf}
[ -f "$PIUPARTS_CONF" ] || exit 0

# usage: get_config_value VARIABLE section key [default]
get_config_value()
{
	local section key value
	test -n "$1" && test "$1" = "$(echo "$1" | tr -c -d '[:alnum:]_')" || exit 1
	section="$2"
	key="$3"
	value="$(sed -rn '\#^\['"$section"'\]#,/^\[/ {/^'"$key"'\s*=/ {s/^'"$key"'\s*=\s*//; s/\s*$//; p}}' "$PIUPARTS_CONF")"
	test -n "$value" || value="$4"
	if [ -z "$value" ]; then
		echo "'$key' not set in section [$section] of $PIUPARTS_CONF, exiting." >&2
		exit 1
	fi
	eval "$1"='"$value"'
}
