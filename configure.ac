#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.69])
AC_INIT([Telefono], [1.0], [friedrich.lunacek@gmx.de],
        [telefono], [https://gitlab.mn.tu-dresden.de/josc941e/telefono])
AC_CONFIG_SRCDIR([src/ipc.py])
AC_CONFIG_AUX_DIR([build-aux])
AC_CONFIG_MACRO_DIR([build-macro])

AM_INIT_AUTOMAKE([foreign -Wall -Werror subdir-objects])

AM_MAINTAINER_MODE([enable])

AC_PROG_MKDIR_P()

# Checks for programs.
AM_PATH_PYTHON(3)

PKG_PROG_PKG_CONFIG()

AC_ARG_ENABLE([service],
[AS_HELP_STRING([--disable-service],
                [don't automatically enable systemd service])])

AC_ARG_WITH([systemddir],
     [AS_HELP_STRING([--with-systemddir=DIR], [Directory for systemd service files])],,
     [with_systemddir=auto])

AS_IF([test "x$with_systemddir" = "xyes" -o "x$with_systemddir" = "xauto"], [
  systemddir=$($PKG_CONFIG --variable=systemdsystemunitdir systemd)

  AS_IF([test "x$systemddir" = "x"],
    [AS_IF([test "x$with_systemddir" = "xyes"],
      [AC_MSG_ERROR([systemd support requested but pkg-config unable to query systemd package])])
    with_systemddir=no])])

AC_SUBST([systemddir], [$systemddir])

AM_CONDITIONAL([HAVE_SYSTEMD], [test "x$with_systemddir" != "xno"])
AM_CONDITIONAL([INSTALL_SYSTEMD_SERVICE], [test "x$enable_service" != "xno"])

# Checks for libraries.

# Checks for header files.

# Checks for typedefs, structures, and compiler characteristics.

# Checks for library functions.

# Makefiles
AC_CONFIG_FILES([Makefile])

AC_OUTPUT
