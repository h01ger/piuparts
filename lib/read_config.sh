# Copyright © 2011, 2013 Andreas Beckmann <anbe@debian.org>
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

	# First select the [$section] block (\#^\[$section\]#) (use # as
	# marker because $section may contain slashes) up to the start of the
	# next section (/^\[/). The select the $key=value, this may be wrapped
	# with indented lines and comment lines embedded. The $key=value is
	# over once we hit the next key (or any line not starting with # or
	# whitespace. Throw away comments (/^#/d), the following key, remove
	# our $key= part, trim the value, remove empty lines, and print it.
	value="$(sed -rn '\#^\['"$section"'\]#,/^\[/ {/^'"$key"'\s*=/,/^[^ \t#]/ {/^#/d; /^'"$key"'\s*=|^\s/!d; s/^'"$key"'\s*=\s*//; s/^\s*//; s/\s*$//; /^$/d; p}}' "$PIUPARTS_CONF")"

	if [ -z "$value" ]; then
		if [ -n "${4+set}" ]; then
			value="$4"
		else
			echo "'$key' not set in section [$section] of $PIUPARTS_CONF, exiting." >&2
			exit 1
		fi
	fi
	eval "$1"='"$value"'
}
