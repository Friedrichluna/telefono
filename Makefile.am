## Process this file with automake to produce Makefile.in

pkgpython_PYTHON =
pkgpython_PYTHON += telefono/__init__.py
pkgpython_PYTHON += telefono/__main__.py
pkgpython_PYTHON += telefono/button.py
pkgpython_PYTHON += telefono/dial.py
pkgpython_PYTHON += telefono/event_queue.py
pkgpython_PYTHON += telefono/ipc.py
pkgpython_PYTHON += telefono/player.py
pkgpython_PYTHON += telefono/recorder.py
pkgpython_PYTHON += telefono/records.py
pkgpython_PYTHON += telefono/speaker.py
pkgpython_PYTHON += telefono/tts.py
pkgpython_PYTHON += telefono/webapp.py

nodist_pkgpython_PYTHON =
nodist_pkgpython_PYTHON += telefono/CONSTANTS.py

EXTRA_DIST =
EXTRA_DIST += telefono/CONSTANTS.py.in

edit = sed -e 's|@pkgdatadir[@]|$(pkgdatadir)|g'

telefono/CONSTANTS.py: Makefile
	$(MKDIR_P) telefono
	rm -f $@ $@.tmp
	srcdir=''; \
		test -f ./$@.in || srcdir=$(srcdir)/; \
		$(edit) $${srcdir}$@.in >$@.tmp

	chmod +x $@.tmp
	chmod a-w $@.tmp
	mv $@.tmp $@

telefono/CONSTANTS.py: $(srcdir)/telefono/CONSTANTS.py.in

CLEANFILES = telefono/CONSTANTS.py


dist_pkgdata_DATA =
dist_pkgdata_DATA += data/startup.wav
dist_pkgdata_DATA += data/shutdown.wav
dist_pkgdata_DATA += data/ring.wav
dist_pkgdata_DATA += data/dial.wav


EXTRA_DIST += README.md
EXTRA_DIST += todo.txt
EXTRA_DIST += telefono/templates/base.html
EXTRA_DIST += telefono/templates/edit.html
EXTRA_DIST += telefono/templates/index.html
EXTRA_DIST += telefono/templates/list.html
EXTRA_DIST += telefono/templates/say.html
EXTRA_DIST += telefono/templates/upload.html
EXTRA_DIST += data/records.list


if HAVE_SYSTEMD
systemd_DATA = telefono.service

install-data-hook:
	-systemctl enable telefono
endif

EXTRA_DIST += telefono.service

ACLOCAL_AMFLAGS = --install -I build-macro

AM_DISTCHECK_CONFIGURE_FLAGS = --with-systemddir=$$dc_install_base/$(systemddir)
