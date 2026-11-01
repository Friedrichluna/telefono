#!/bin/sh
# rebuild and reinstall telefono from the commit checked out in this
# source tree, then restart it
#
#   tools/update.sh                 the current commit
#   tools/update.sh --pull          git pull --ff-only first
#   tools/update.sh -- <options>    configure with these options instead
#                                   of the ones of the last build
#
# configure forgets its options, so they are taken from
# build/config.status (./config.status --config); without a build the
# default is --sysconfdir=/etc. make install deletes nothing, so the
# installed package, data and helper directories are emptied first
# (recordings, telefono.conf and the certificate are elsewhere and kept)

set -e

cd "$(dirname "$0")/.."

pull=no
while [ $# -gt 0 ]
do
	case "$1" in
	--pull) pull=yes; shift ;;
	--) shift; break ;;
	-h|--help) sed -n '2,15s/^# \{0,1\}//p' "$0"; exit 0 ;;
	*) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
	esac
done

if [ "$pull" = yes ]
then
	git pull --ff-only origin master
fi

if [ $# -gt 0 ]
then
	:
elif [ -x build/config.status ]
then
	eval "set -- $(build/config.status --config)"
else
	set -- --sysconfdir=/etc
fi

echo "building $(git describe --long --tags --dirty --always) with: $*"

[ -d .git ] && [ ! -e .git/hooks/post-checkout ] && cp hooks/* .git/hooks/ || true

mkdir -p build
cd build
# otherwise the version of the last build is baked into CONSTANTS.py
rm -f vcs_version CONSTANTS.py
../configure "$@" >/dev/null
make clean >/dev/null
make

dirs=$(printf 'print:\n\t@echo $(pkgpythondir) $(pkgdatadir) $(pkglibexecdir)\n' \
       | make -s --no-print-directory -f Makefile -f - print)
for dir in $dirs
do
	case "$dir" in
	*/telefono) echo "removing $dir"; sudo rm -rf "$dir" ;;
	*) echo "not removing $dir (does not end in /telefono)" >&2 ;;
	esac
done

sudo make install
sudo systemctl restart telefono

echo "installed $(cat vcs_version), telefono restarted:"
systemctl is-active telefono telefono-mdns telefono-hotspot || true
