#
# detect packages with some inadequate tag from adequate
#
PATTERN='(FAIL|WARN): Running adequate resulted in .* missing-alternative'
WHERE='pass fail bugged affected'
ISSUE=1
HEADER="Packages tagged 'missing-alternative' by adequate"
HELPTEXT="
<p>Running <a href="https://packages.debian.org/adequate" target="_blank">adequate</a> resulted in the package being tagged 'missing-alternative' which indicates a bug similar to this situation: a package is a provider of the virtual package 'x-terminal-emulator', but it  doesn't register itself as an alternative for '/usr/bin/x-terminal-emulator'. See debian-policy 11.8.3 and 11.8.4.
</p>
"
