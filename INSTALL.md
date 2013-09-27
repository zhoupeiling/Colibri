General notes about installing colibri
======================================

> Organized from http://labs.freehackers.org/projects/colibri/wiki/Installing_colibri

Prerequisites
-------------

* A mail server that accepts mail sent to the mailing lists handled by colibri
* mhonarc somewhere in the PATH where the colibri daemon can find it.
* A place on the filesystem where Colibri can read and write files, to handle 
  spools and archives. The MTA needs to be able to write to a subdirectory of 
  this spool.
* A way to send email : typically the IP+port of an email server that will
  accept mails from the server colibrid runs on.
* If you want to use the web frontend (you are highly encouraged to!)
* A web server that can execute python code

Configuration
-------------

There are several places where colibri can read its configuration:

The file `colibrisettings.py`, at the top of the source directory, 
contains configuration about the spool directory place and layout, and 
configuration about log files.

Variables in the `init.d` script decide if/where the PID should be written
(recommended) and where the colibri software is installed.

Initialize the database
-----------------------

This is no more different than any django website, and you can check the
(great) [django documentation](https://docs.djangoproject.com/en/1.5/).

If you've done the previous step carefully , you should have configured the
database (mysql, sqlite3, postgresql) and db settings (host, name, password..).
Initializing the database should be no more complicated than running

    ./manage.py  syncdb

from the main directory of colibri.

Detailed example using Postfix
------------------------------

In /etc/postfix/main.cf, I have

    default_privs = colibri

so that when postfix writes files in the colibri spool directory, it changes
the ownership of files to the user colibri.

In the alias file (/etc/mail/aliases in postfix) I include rules so that mails
that should be handled by colibri are put by postfix inside colibri spool
directory.

For example:

    # ------------------- colibri-test@freehackers.org
    colibri-test: /var/spool/colibri/
    colibri-test-request: /var/spool/colibri/
    colibri-test-editor: /var/spool/colibri/
    #colibri-test-subscribe: /var/spool/colibri/
    colibri-test-unsubscribe: /var/spool/colibri/
    colibri-test-owner: /var/spool/colibri/

Init.d script
-------------

in the source you can find scripts/gentoo.initsript which should be installed
as `/etc/init.d/colibrid`. The script is probably easy to adapt to other 
distribution. Please contact author if you do so, I will include it in the
source code, and I will be able to update it when/if modifications are made.

Solving problems
----------------

When colibrid starts, some checks are performed, like availability of mhonarc
or permissions on the spool directory. If any check fails, colibrid will refuse
to start and print information about the failing test. The configuration of log
files is in the file `colibrisettings.py`: check those log files to know what
the problem is/are.
