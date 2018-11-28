# Copyright © 2018 Holger Levsen (holger@debian.org)
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
# with this program. If not, see <https://www.gnu.org/licenses/>

#
# Helper function for publishing logfiles
#

publish_logs() {
	local LOG_OUTPUT=$1
	local LOG_PREFIX=$2
	local HTDOCS="$3"
	local LOG=$4
	local YEAR=$(date -u +%Y)
	local MONTH=$(date -u +%m)
	local DAY=$(date -u +%d)
	local DIR="$HTDOCS/logs/$YEAR/$MONTH/$DAY"
	mkdir -p "$DIR"
	if [ -n "$LOG_PREFIX" ] && [ ! -s "$DIR/$LOG.txt" ] ; then
		cat $LOG_PREFIX >> "$DIR/$LOG.txt"
		rm -f $LOG_PREFIX >/dev/null
	fi
	cat $LOG_OUTPUT >> "$DIR/$LOG.txt"
	rm -f $LOG_OUTPUT >/dev/null
}
