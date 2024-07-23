## Process this file with automake to produce Makefile.in

pkgpython_PYTHON =
pkgpython_PYTHON += src/__init__.py
pkgpython_PYTHON += src/__main__.py
pkgpython_PYTHON += src/button.py
pkgpython_PYTHON += src/dial.py
pkgpython_PYTHON += src/event_queue.py
pkgpython_PYTHON += src/ipc.py
pkgpython_PYTHON += src/network.py
pkgpython_PYTHON += src/player.py
pkgpython_PYTHON += src/recorder.py
pkgpython_PYTHON += src/speaker.py

webappdir = $(pkgpythondir)/webapp
webapp_PYTHON =
webapp_PYTHON += src/webapp/__init__.py
webapp_PYTHON += src/webapp/__main__.py
webapp_PYTHON += src/webapp/webapp.py

nodist_pkgpython_PYTHON =
nodist_pkgpython_PYTHON += CONSTANTS.py

noinst_PYTHON =
noinst_PYTHON += src/CONSTANTS.py.in


edit = sed -e 's|@pkgdatadir[@]|$(pkgdatadir)|g' \
           -e 's|@pkglocalstatedir[@]|$(pkglocalstatedir)|g' \
           -e 's|@templatedir[@]|$(templatedir)|g'

all: CONSTANTS.py

CONSTANTS.py: $(srcdir)/src/CONSTANTS.py.in Makefile
	$(MKDIR_P) src
	rm -f $@ $@.tmp
	$(edit) $< >$@.tmp

	chmod +x $@.tmp
	chmod a-w $@.tmp
	mv $@.tmp $@

CLEANFILES = CONSTANTS.py


dist_pkgdata_DATA =
dist_pkgdata_DATA += data/startup.wav
dist_pkgdata_DATA += data/shutdown.wav
dist_pkgdata_DATA += data/ring.wav

templatedir = $(pkgdatadir)/templates
dist_template_DATA =
dist_template_DATA += src/webapp/templates/base.html
dist_template_DATA += src/webapp/templates/edit.html
dist_template_DATA += src/webapp/templates/index.html
dist_template_DATA += src/webapp/templates/list.html
dist_template_DATA += src/webapp/templates/say.html
dist_template_DATA += src/webapp/templates/upload.html

pkglocalstatedir = $(localstatedir)/$(PACKAGE)
dist_pkglocalstate_DATA =
dist_pkglocalstate_DATA += data/records.list.example

dist_doc_DATA =
dist_doc_DATA += README.md
dist_doc_DATA += todo.txt
dist_doc_DATA += docs/circuit_diagram.png

EXTRA_DIST =


if HAVE_SYSTEMD
systemd_DATA = telefono.service

if INSTALL_SYSTEMD_SERVICE
install-data-hook:
	systemctl daemon-reload
	systemctl enable telefono

uninstall-hook:
	systemctl daemon-reload
	systemctl disable telefono
endif
endif

EXTRA_DIST += telefono.service

ACLOCAL_AMFLAGS = --install -I build-macro

AM_DISTCHECK_CONFIGURE_FLAGS = --with-systemddir=$$dc_install_base$(systemddir) --disable-service


run: install
	systemctl restart telefono

status: run
	sleep 3
	systemctl status telefono --full

.PHONY: run status
