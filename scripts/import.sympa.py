#!/bin/env python
# -*- coding: utf-8
# vim: set fileencoding=utf-8

#    Copyright (C) 2008-2010 Thomas Capricelli <orzel@freehackers.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This script can be used to import a mailing list from sympa
Currently it only import archives, not the settings
"""

import sys, os

#django  stuff
basedir = os.path.dirname(os.path.dirname(os.path.abspath( __file__)))
sys.path.append(basedir)
# set environment variable DJANGO_SETTINGS_MODULE to make django happy
os.environ[ 'DJANGO_SETTINGS_MODULE' ] = 'settings'

from main.models import *
from settings import INCOMING_DIR, REJECT_DIR, BOUNCED_DIR, ARCHIVE_DIR, PIDFILE
from django.contrib.auth.models import User
from main.views import find_email, create_profile

ARCHIVE_DIR=os.path.abspath(ARCHIVE_DIR)
BOUNCED_DIR=os.path.abspath(BOUNCED_DIR)


def do_mhonarc(archive_dir, list_name):
    """
    Call mhonarc to update the archive : html files are created from new raw files.
    """
    text_dir = archive_dir+ "text/"
    html_dir = archive_dir+ "html/"
    checkAndCreateDirectory(html_dir,ARCHIVE_DIR)
    title = "Archive for the list %s" % list_name
    ttitle = "Threaded archive for the list %s" % list_name
    resourcefile = basedir + "/scripts/myresource.mrc"
    command = 'mhonarc -mhpattern "^[^\.]" -add -quiet -title "%s" -ttitle "%s" -rcfile %s -outdir %s %s' % (title, ttitle, resourcefile, html_dir, text_dir)
    #print 'do_mhonarc() : executing "%s"' % command
    errno = os.system(command)
    if errno!=0:
        err("do_mhonarc(%s,%s,%s) : error %d while executing mhonarc" % (html_dir, list_name, errno))
        return

def strip_leading_slash(path):
    if path[-1]=='/':
        return path[:-1]
    return path

def checkAndCreateDirectory(dir,basedir):
    """
    Ensure the whole path exists, creating missing directories
    This is not really bound to the instance/class, and could/should
    be moved outside of the class.
    """
    dir = strip_leading_slash(dir) # cleaning
    from os import stat, mkdir 
    # check for both bad argument or problem with recursion
    if not dir.startswith(strip_leading_slash(basedir)):
        raise ValueError
    try:
        stat(dir)
    except OSError:
        # does not exist, create it
        checkAndCreateDirectory(os.path.dirname(dir),basedir) # recursive check of parent dir
#        print "Creating %s" % dir
        mkdir(dir)
    return
 
def do_system_checks():
    # check that mhonarc is available
    if os.system("which mhonarc > /dev/null")!=0:
        print("mhonarc can not be found")
        exit(1)
    if os.system("mhonarc --help > /dev/null")!=0:
        print("mhonarc can not be run")
        exit(1)

def do_option_checks():
    if len(sys.argv)>1:
        sympa_path = sys.argv[1]
        if not os.path.exists(sympa_path):
            raise ValueError("The path you specified for sympa (%s) does not exist (?)" % sympa_path)
        if not os.path.exists(sympa_path+"/bounce") or not os.path.exists(sympa_path+"/expl") or not os.path.exists(sympa_path+"/arc"):
            raise ValueError("The path you specified for sympa (%s) does not seem to contain a normal sympa install (?)" % sympa_path)
        lists_available = os.listdir(sympa_path+'/arc')
        
    if len(sys.argv)!=4:
        print "You need to supply exactly two arguments to this script:"
        print " * the path for the main directory of sympa"
        print " * the path for the web configuration file sympa.conf"
        print " * the name of the mailing list to import"
        print " "
        print "Example : %s /opt/sympa /etc/sympa.conf test\@mysite.org" % sys.argv[0]
        print " "
        if len(sys.argv)>1:
            print "Available lists:\n\t", "\n\t".join(lists_available)
        exit(1)

    conffile = sys.argv[2]
    if not os.path.exists(conffile):
        print "The web config file specified (%s) can not be found" % conffilee
        raise ValueError("Can't find the config file")

    list_name = sys.argv[3]
    if not list_name in lists_available:
        print "The list you specified (%s) can not be found" % list_name
        print "Available lists:\n\t", "\n\t".join(lists_available)
        raise ValueError("Can't find the list")

    return sympa_path, conffile, list_name

def copy_files(fromdir, todir):
    from shutil import copy2
    checkAndCreateDirectory(todir,ARCHIVE_DIR)
    files = os.listdir(fromdir)
    for f in files:
        copy2(fromdir+'/'+f, todir)

def import_one_directory(dir, list_name):
    dirs=os.path.basename(dir).split('-')
    if len(dirs)!=2:
        raise ValueError("import_one_directory couldn't parse directory name")
    year = dirs[0]
    month = "%d" % int(dirs[1]) # remove first 0 if present
    fromdir = dir + '/arctxt'
    if not os.path.exists(fromdir):
        raise ValueError("import_one_directory %s does not exist ?" % fromdir)
    archive_dir = ARCHIVE_DIR+"/%s/%s/%s/" % (list_name, year, month)
    archive_dir_text = archive_dir+'text'
    print "importing %s -> %s" % (fromdir, archive_dir_text)

    # copy files
    copy_files(fromdir, archive_dir_text)

    # mhonarc it
    do_mhonarc(archive_dir, list_name)

def import_archive(sympa_path, list):
    mlpath = strip_leading_slash(sympa_path+'/arc/'+unicode(list))
    if not os.path.exists(mlpath):
        raise ValueError("Path (%s) does not exist" % mlpath)

    print "-> Import archives from '%s'" % mlpath
    print "-> The colibri archive dir is '%s'" % ARCHIVE_DIR

    colibri_archive_dir = ARCHIVE_DIR+"/"+unicode(list)
    if os.path.exists(colibri_archive_dir):
        raise ValueError("The colibri archive dir '%s' already exists, aborting" % colibri_archive_dir)

    # list archive directories
    dirs = os.listdir(mlpath)
    for d in dirs:
        import_one_directory(mlpath+'/'+d, unicode(list))

def find_option_value(options, option, default=None):
    candidates =  [o for o in options if o.startswith(option)]
    if len(candidates)>1:
        raise ValueError("Too much candidates for option %s : %s" % (option, str(candidates)) )
    if len(candidates)<1:
        if default is None: raise ValueError("Can't find option %s" % option)
        return default
    splitted = candidates[0].split()
    if splitted[0]!=option:
        raise ValueError('Error matching option "%s", found "%s"' % (option, splitted[0]))
    return " ".join(splitted[1:])

def import_settings(sympa_path, list_name, list_host):
    "Parse information in the expl/ directory and return the newly created list"
    options = [l.strip() for l in open(sympa_path+'/expl/'+list_name+'/config', 'r').readlines() if l !='\n' ]
    subject = find_option_value(options, "subject")
    custom_subject = find_option_value(options, "custom_subject")
    visibility = find_option_value(options, "visibility")
    review = find_option_value(options, "review", "owner")

    # subscribe
    subscribe = find_option_value(options, "subscribe")
    if subscribe=="open":
        who_can_subscribe = LIST_SUBSCRIPTION_OPEN
    elif subscribe=="open_notify":
        who_can_subscribe = LIST_SUBSCRIPTION_OPEN
    elif subscribe=="owner":
        who_can_subscribe = LIST_SUBSCRIPTION_ADMIN
    elif subscribe=="closed":
        who_can_subscribe = LIST_SUBSCRIPTION_CLOSED
    else:
        raise ValueError('Unknown value for option "subscribe" "%s"' % subscribe)

    # Status
    status = find_option_value(options, "status")
    if status=='closed':
        state = LIST_STATE_DISABLED
    elif status=='open':
        state = LIST_STATE_PRODUCTION
    else: # typically 'pending'
        state = LIST_STATE_REQUESTED

    if List.objects.filter(name=list_name).filter(host=list_host).count()>0:
        raise ValueError('A list with those name/host already exist in the colibri database')

    list = List.objects.create(
        owner = Profile.objects.get(id=1),
        name = list_name,
        host = list_host,
        subject = subject,
        public = visibility=="noconceal",
        subject_tag = custom_subject,
        state = state,
        who_can_subscribe = who_can_subscribe,
        subscribers_list_visible = review=="private",
    )
    print "-> Created new list %s" % unicode(list)
    return list

def import_db(conffile, list):
    options = [l.strip() for l in open(conffile, 'r').readlines() if l !='\n' and not l.startswith('#') ]
    #print "\t\n".join(options)

    db_type = find_option_value(options, "db_type")
    if db_type!="mysql":
        raise ValueError('Only mysql is currently supported by the sympa import script')
    db_name = find_option_value(options, "db_name")
    db_host = find_option_value(options, "db_host")
    db_user = find_option_value(options, "db_user")
    db_passwd = find_option_value(options, "db_passwd")
    if db_name is None or db_host is None or db_user is None or db_passwd is None:
        raise ValueError('Unable to recover database parameters from the sympa conf file')

    import MySQLdb
    db = MySQLdb.connect(host=db_host, user=db_user, passwd=db_passwd, db=db_name)
    cursor = db.cursor()
    cursor.execute("select * from subscriber_table where list_subscriber='%s'" % list.name)
    subscribers = cursor.fetchall()
    newprofiles = 0
    for sub in subscribers:
        # user already in the db ?
        profile = find_email(sub[1])
        if profile is None:
            # create a new one, use a random username. Emails can be more than 30 chars.. :-(
            user = User.objects.create_user(User.objects.make_random_password(25), sub[1], User.objects.make_random_password())
            profile = create_profile(user)
            newprofiles += 1
        Subscription.objects.create(profile=profile, list=list, started=sub[2], updated=sub[3])
    print "-> Imported %d subscribers, created %d new users/profiles" % (len(subscribers), newprofiles)

def main():
    # checks
    do_system_checks()
    sympa_path, conffile, list_name = do_option_checks()
    splitted = list_name.split('@')
    if len(splitted)!=2:
        raise ValueError("Bad list name (%s) with bad number (%d) of signs '@'" % (list_name, len(splitted)-1) )

    # do it
    list = import_settings(sympa_path, splitted[0], splitted[1])
    import_db(conffile, list)
    import_archive(sympa_path, list)
    print "Import of %s Done" % list_name

# if python says run, then we should run
if __name__ == '__main__':
    main() 

# vim: ai ts=4 sts=4 et sw=4
