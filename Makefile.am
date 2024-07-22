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

webappdir = $(pkgpythondir)/webapp
webapp_PYTHON =
webapp_PYTHON += telefono/webapp/__init__.py
webapp_PYTHON += telefono/webapp/__main__.py
webapp_PYTHON += telefono/webapp/webapp.py

nodist_pkgpython_PYTHON =
nodist_pkgpython_PYTHON += telefono/CONSTANTS.py

noinst_PYTHON =
noinst_PYTHON += telefono/CONSTANTS.py.in


edit = sed -e 's|@pkgdatadir[@]|$(pkgdatadir)|g' \
           -e 's|@pkglocalstatedir[@]|$(pkglocalstatedir)|g' \
           -e 's|@templatedir[@]|$(templatedir)|g'

all: telefono/CONSTANTS.py

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

templatedir = $(pkgdatadir)/templates
dist_template_DATA =
dist_template_DATA += telefono/webapp/templates/base.html
dist_template_DATA += telefono/webapp/templates/edit.html
dist_template_DATA += telefono/webapp/templates/index.html
dist_template_DATA += telefono/webapp/templates/list.html
dist_template_DATA += telefono/webapp/templates/say.html
dist_template_DATA += telefono/webapp/templates/upload.html

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

install-data-hook:
	-sudo systemctl enable telefono
endif

EXTRA_DIST += telefono.service

ACLOCAL_AMFLAGS = --install -I build-macro

AM_DISTCHECK_CONFIGURE_FLAGS = --with-systemddir=$$dc_install_base/$(systemddir)
