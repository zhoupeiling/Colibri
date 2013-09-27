#!/bin/env python
# -*- coding: utf-8
#

#    Copyright (C) 2008-2011 Thomas Capricelli <orzel@freehackers.org>
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

# system stuff
import sys, logging, logging.handlers, email
from email.parser import Parser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTPException
from signal import SIGTERM, SIGINT, signal
from optparse import OptionParser
from time import sleep
from datetime import date
from random import randint
from forward import create_outbound_message
from os import getpid, path, environ, system, unlink, listdir, stat, mkdir, umask

#django  stuff
basedir = path.dirname(path.dirname(path.abspath( __file__)))
sys.path.append(basedir)
# set environment variable DJANGO_SETTINGS_MODULE to make django happy
environ[ 'DJANGO_SETTINGS_MODULE' ] = 'settings'

from main.models import *
from settings import INCOMING_DIR, REJECT_DIR, BOUNCED_DIR, ARCHIVE_DIR, PIDFILE
from django.core.mail import SMTPConnection
from main.views import find_email


'''
colibrid is the daemon in charge of checking incoming mails in the right
directory, and handle them, which means:
    * check for bounces
    * create archives/html files
    * forward mails to subscribed people
'''

ARCHIVE_DIR=path.abspath(ARCHIVE_DIR)
BOUNCED_DIR=path.abspath(BOUNCED_DIR)

# interval at which the mainloop wakes up to check everything (in seconds)
WAKEUP_INTERVAL = 5

#
# debug loggers
#
LOG_COLIBRID='colibrid'

# regular format
LOG_FORMAT_WITH_TIME = '%(asctime)s %(levelname)7s %(name)-15s %(message)s'

DEEPDEBUG=1
DEBUG=logging.DEBUG
INFO =logging.INFO
ERROR=logging.ERROR
logging.addLevelName( DEEPDEBUG, 'DeepDBG' )

# method that will be bound to getLoggerClass()
def deepdebug(self, msg, *args, **kwargs):
    """
    Log 'msg % args' with severity 'DEEPDEBUG'.

    To pass exception information, use the keyword argument exc_info with
    a true value, e.g.

    logger.debug("Houston, we have a %s", "thorny problem", exc_info=1)
    """
    apply(self._log, (DEEPDEBUG, msg, args), kwargs)
    return
    if self.manager.disable >= DEEPDEBUG:
        return
    if DEEPDEBUG >= self.getEffectiveLevel():
        apply(self._log, (DEEPDEBUG, msg, args), kwargs)

def init_logging(level=INFO, LogStdout=True, LogFileName=None):
    '''
    Initialize some generic stuff about log
    '''
    # install deepdebug method:
    logging.getLoggerClass().deepdebug = deepdebug
    # root log sends all debug log to all handlers
    logging.getLogger('').setLevel( DEEPDEBUG )

    if LogStdout:
        stdoutHandler = logging.StreamHandler( sys.stdout )
        stdoutHandler.setLevel( level)
        stdoutHandler.setFormatter( logging.Formatter( LOG_FORMAT_WITH_TIME ) )
        logging.getLogger( LOG_COLIBRID).addHandler( stdoutHandler )

    if LogFileName != None:
        fileHandler = logging.handlers.RotatingFileHandler( LogFileName, 'a', 30 * 1024 * 1024, 20 ) # 20 x 30 Mbytes max
        fileHandler.setFormatter( logging.Formatter( LOG_FORMAT_WITH_TIME ) )
        fileHandler.setLevel( level)
        logging.getLogger( LOG_COLIBRID).addHandler( fileHandler )

logInitDone=False
if not logInitDone:
    from colibrisettings import LogStdout, LogFileName
    logInitDone = True
    init_logging(DEBUG, LogStdout, LogFileName)

deepdbg = logging.getLogger(LOG_COLIBRID).deepdebug
dbg     = logging.getLogger(LOG_COLIBRID).debug
err     = logging.getLogger(LOG_COLIBRID).error
info    = logging.getLogger(LOG_COLIBRID).info


#
# utilities
#

validchar= "abcdefghijklmnopqrstuvwxyz0123456789"
validcharlen = len(validchar)
def random_letter():
    return validchar[randint(0,validcharlen-1)]
def random_suffix(len):
    ret=""
    for i in range(len):
        ret+=random_letter()
    return ret

def move_file(oldpath, _newpath, msg="moving"):
    # check if destination already exists
    newpath = _newpath
    while path.exists(newpath):
        newpath = _newpath+'.'+random_suffix(7)
    from shutil import move
    deepdbg('%s %s -> %s', msg, oldpath, newpath)
    move(oldpath, newpath)
    return

def checkAndCreateDirectory(dir,basedir):
    """
    Ensure the whole path exists, creating missing directories
    This is not really bound to the instance/class, and could/should
    be moved outside of the class.
    """
    # cleaning
    dir = path.normpath(dir)
    basedir = path.normpath(basedir)
#        deepdbg('checkAndCreateDirectory(%s)'% dir)
    # check for both bad argument or problem with recursion
    assert(dir.startswith(basedir))
    try:
        stat(dir)
    except OSError:
        # does not exist, create it
        deepdbg('"%s" does not exist, create it', dir)
        checkAndCreateDirectory(path.dirname(dir),basedir) # recursive check of parent dir
        info("Creating %s", dir)
        mkdir(dir)
    return


def is_subscriber(fromfield, list):
    """
    Check if the fromfield is a subscriber of the list, taking 
    OtherEmailKey into account.

    Return True of False.
    """
    # find out email
    name, address = email.utils.parseaddr(fromfield) # split "myname<myemail>" -> [myname, myemail]
    if address=='':
        info("is_subscriber : Can't extract email in the 'From' field ('%s')" % fromfield)
        return False

    # find profile
    deepdbg("is_subscriber with address = %s", address)
    profile = find_email(address)
    if profile is None: return False

    # find
    deepdbg("is_subscriber : profile found, count is %d", Subscription.objects.filter(profile=profile, list=list).count())
    return Subscription.objects.filter(profile=profile, list=list).count()>0


class Colibrid:
    """
    implementation of the daemon
    """

    def __init__(self):
        # install signal handler
        signal(SIGTERM, self.catch_sig)
        signal(SIGINT, self.catch_sig)
        self.stop_asap = False
        # TODO : probably we should use HeaderParser here
        self.parser = Parser()
        if not self.initial_checks():
            raise RunTimeError()

    def catch_sig(self, sig, stack):
        info('Caught signal %d', sig)
        self.stop_asap = True

    def initial_checks(self):
        """
        Perform some initial checks, such as
        * can we access the incoming dir ?
        * can we unlink files in the incoming dir ?
        * can we write to the reject dir ?
        * can we write to the archve dir ?
        * can we find mhonarc ?
        * can we execute mhonarc ?

        * r/w access to pid file
        * r/w access to rw/ dir
        * r/w access do dataase

        This method is responsible for outputting useful err() messages
        """
        # check that mhonarc is available
        if system("which mhonarc > /dev/null")!=0:
            err("mhonarc can not be found")
            return False
        dbg("mhonarc found")
        if system("mhonarc --help > /dev/null")!=0:
            err("mhonarc can not be run")
            return False
        # check that important directories are available
        if not path.exists(INCOMING_DIR):
            err('INCOMING_DIR does not exist : "%s"' % INCOMING_DIR)
            return False
        if not path.exists(REJECT_DIR):
            err('REJECT_DIR does not exist : "%s"' % REJECT_DIR)
            return False
        if not path.exists(BOUNCED_DIR):
            err('BOUNCED_DIR does not exist : "%s"' % BOUNCED_DIR)
            return False
        if not path.exists(ARCHIVE_DIR):
            err('ARCHIVE_DIR does not exist : "%s"' % ARCHIVE_DIR)
            return False
        # TODO..
        return True

    def run(self):
        deepdbg("colibrid run() called")
        while not self.stop_asap:
            self.checkIncomingMails()
            sleep( WAKEUP_INTERVAL )

    def checkIncomingMails(self):
        files = listdir(INCOMING_DIR)
        # ignore some common patterns
        for n in [ '.keep', 'old', 'save' ]:
            while n in files: files.remove(n)
        if len(files)<1: return
        deepdbg('checkIncomingMails : %d file(s)'%len(files))
        for filename in files:
            # handle it
            self.checkOneFile(filename)
            # check the file is removed, whatever the way
            # (forwarded/archived, rejected, error, bounce...)
            assert not path.exists(INCOMING_DIR+filename)

    def checkOneFile(self, filename):
        # basic checks
        deepdbg('checkOneFile : %s' % filename)
        try:
            m = self.parser.parse(file(INCOMING_DIR+filename, 'r'))
        except:
            info("Error while parsing %s: %s, mail rejected" %( filename, unicode(sys.exc_info()[0])))
            self.reject(filename)
            return
        if not self.checkMailValidity(m):
            info("The content of %s is not valid, mail rejected" % filename)
            self.reject(filename)
            return
        # Find out recipient / clean
        if m['X-Original-To'] is not None:
            recipient = m['X-Original-To']
        else:
            recipient = m['Delivered-To']
        assert(recipient is not None)
        name, addr = email.utils.parseaddr(recipient) # split "myname<myemail>" -> [myname, myemail]
        if addr=='':
            info("Can't extract email from recipient ('%s'), rejected" % recipient)
            self.reject(filename)
            return
        name, host = addr.split('@')
        if name=='' or host=='':
            info("Can't extract name and host from recipient('%s'), got '%s','%s', rejected" % (recipient, name, host))
            self.reject(filename)
            return
        deepdbg('To: %s,%s' % (name, host))

        # Check for *-editor *-subscribe *-unsubscribe
        if name.endswith('-editor') or name.endswith('-subscribe') or name.endswith('-unsubscribe') or name.endswith('-help'):
            # TODO : improve speed with regexp here ?
            info("-editor/-subscribe/-unsubsribe/-help not handled yet, mail rejected")
            self.reject(filename)
            return

        # check for *-request
        if name.endswith('-request'): # TODO : improve speed with regexp here ?
            self.handleRequest(name[:-8], host, m, filename)
            return

        # check for *-owner
        if name.endswith('-owner'): # TODO : improve speed with regexp here?
            self.handleOwner(name[:-6], host, m, filename)
            return

        # ok, now, the mail should be toward an actual mailing list

        # Try to find the mailing list
        lists = List.objects.filter(name=name).filter(host=host)
        deepdbg('Found %d lists for this criteria' % lists.count())
        if lists.count()!=1:
            info("Unknown mailing list : %s@%s, rejected" % (name,host))
            self.reject(filename)
            return

        # ok, now we have the corresponding mailing list
        mylist = lists[0] # dont call the variable 'list', it's the name of a python class
        info('Incoming mail for %s' % mylist)

        # check list state
        if mylist.state!=1: # "production"
            # TODO : send an email back for all those errors, but not until
            # loop detection / bounces and such are implemented
            info("This mailing list is not in production state, rejecting")
            self.reject(filename)
            return

        # check this mail is allowed to get through
        if is_subscriber(m['From'], mylist):
            # TODO : handle MODERATE case
            accepted = mylist.posting_from_subscriber == LIST_MODERATE_ACCEPT
            error = u"Subscribers are not allowed to post to the list (read-only list)"
        else:
            # TODO : handle MODERATE case
            accepted = mylist.posting_from_external == LIST_MODERATE_ACCEPT
            error = u"People not subscribed to the list are not allowed to post."
        if not accepted:
            # TODO: probably better to keep a copy in rw/refused/<list>
            unlink(INCOMING_DIR+filename)
            self.refuse(m, mylist, error)
            return
        self.forward_and_archive(m, mylist, filename)

    def forward_and_archive(self, m, mylist, filename):
        deepdbg('forward_and_archive for list %s' % unicode(mylist))
        #
        # find active subscribers, exit if none
        #
        subscribers = [sub.profile.user.email for sub in Subscription.objects.filter(list=mylist).filter(profile__user__is_active=True)]
        nbsubscribers = len(subscribers)
        if nbsubscribers==0:
            info("No active subscriber for %s, done." % unicode(mylist))
            return
        dbg("Found %d active subscribers" % nbsubscribers)
        deepdbg("active subscribers : '%s'" % ", ".join(subscribers))

        # send
        mail = create_outbound_message(m, mylist)
        self.forward_mail_to_subscribers(mail, subscribers, mylist)

        # archive
        archive_dir = self.archive_mail(filename, mylist)
        # TODO: currently we start mhonarc once for every mail, which is clearly
        # not optimized, we'll optimze that later
        self.do_mhonarc(archive_dir, unicode(mylist))

    def forward_mail_to_subscribers(self, mail, subscribers, mylist):
        # actually forward it
        try:
            connection = SMTPConnection() # we use the django one, configured with stuff from settings
            connection.open()
            if not connection.connection:
                raise SMTPException, "Fail to create SMTPConnection.connection"
            connection.connection.sendmail(
                mylist.list_address_extended('owner'),  # from, will be set in Return-Path
                subscribers,                            # to
                mail.as_string())                       # content
        except SMTPException, detail:
            err('SMTP Error while sending the email: %s'%detail)
            return # TODO : prevent loops if smtp fails : the mail stays in incoming and will be tried again in loop
        info("Mail forwarded to %d subscribers" % len(subscribers))

    def refuse(self, m, mylist, reason):
        deepdbg('Refuse mail for %s' % unicode(mylist))

        msgfrom = mylist.list_address_extended('owner')
        msgto = m['From']
        reason = u"\n\nYour message to the list %s has been refused\n\n" % unicode(mylist) + reason

        # create mail
        mail = MIMEMultipart()
        mail['Subject'] = u"Your message to the list %s has been refused " % unicode(mylist)
        mail['From'] = msgfrom
        mail['To'] = msgto
        mail.attach(MIMEText(reason, 'plain', 'utf8')) # error msg
        mail.attach(m) # previous mail

        # ugly hack we need to add headers at the TOP
#        items = m.items()
#        for key,val in items: m.__delitem__(key) # delete them all
#        for key,val in items: m.add_header(key,val) # re-add them all
#        mail.attach(m) # add original mail

        # send it
        try:
            connection = SMTPConnection() # we use the django one, configured with stuff from settings
            connection.open()
            if not connection.connection:
                raise SMTPException, "Fail to create SMTPConnection.connection"
            connection.connection.sendmail(
                mylist.list_address_extended('owner'),  # from, will be set in Return-Path
                [ msgto ],                              # to
                mail.as_string())                       # content
        except SMTPException, detail:
            err('refuse: SMTP Error while sending the email: %s'%detail)
            return # TODO : prevent loops if smtp fails : the mail stays in incoming and will be tried again in loop
        dbg("Refused mail sent to %s" % msgto)

    def archive_mail(self, filename, mylist):
        """
        store a (raw) copy of the email in the right archive
        directory.
        returns the corresponding (main) archive directory

        the main archive directory is ARCHIVE_DIR/<listname>/<year>/<month>/
        there are two directories inside this one
            /text/ for the original raw mails
            /html/ for the html stuff generated by mhonarc
        """

        today = date.today()
        date.today().year
        archive_dir = ARCHIVE_DIR+"/%s/%s/%s/" % (unicode(mylist), today.year, today.month)
        text_dir = archive_dir+ "text/"
        html_dir = archive_dir+ "html/"
#        deepdbg("archive_mail, archive_dir is %s"%archive_dir)
        # check the directory exists
        checkAndCreateDirectory(text_dir,ARCHIVE_DIR)
        # move the file
        move_file(INCOMING_DIR+filename, text_dir+path.basename(filename), 'archive')
        return archive_dir

    def do_mhonarc(self, archive_dir, list_name):
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
        dbg('do_mhonarc() : executing "%s"' % command)
        errno = system(command)
        if errno!=0:
            err("do_mhonarc(%s,%s,%s) : error %d while executing mhonarc" % (html_dir, list_name, errno))
            return

    def handleRequest(self, name, host, m, filename):
        """
        name is the name without the -request suffix
        m is an instance of email.message.Message
        """
        info("-request not handled yet, mail rejected")
        self.reject(filename)
        return

    def handleOwner(self, name, host, m, filename):
        """
        name is the name without the -owner suffix
        m is an instance of email.message.Message
        """

        # Try to find the mailing list
        lists = List.objects.filter(name=name).filter(host=host)
        if lists.count()!=1:
            info("handleOwner: unknown mailing list : %s@%s, rejected" % (name,host))
            self.reject(filename)
            return
        mylist = lists[0]

        # find out the report part
        if not m.get_content_type()=='multipart/report':
            info("handleOwner : returned message is not a multipart/report, don't know what to to with it, rejected")
            self.reject(filename)
            return
        for part in m.walk():
            if part.get_content_type()=='message/delivery-status':
                break
        else:
            info("handleOwner : Can't find the message/delivery-status part in returned message, rejected")
            self.reject(filename)
            return

        # Following http://www.faqs.org/rfcs/rfc3464.html (error msg format)
        # and  http://www.ietf.org/rfc/rfc3463.txt (status code)

        # find out the problematic address
        for line in part.as_string().split('\n'):
            if line.startswith('Final-Recipient:'):
                break
        else:
            info("handleOwner : Can't find the Final-Recipient: in deliveery-status, rejected")
            self.reject(filename)
            return
        bounced_email = line.split(':')[1].split(';')[1].strip()
        info("handleOwner : bounced email is %s" % bounced_email)

        # find out the status string
        for line in part.as_string().split('\n'):
            if line.startswith('Status:'):
                status = line.split(':')[1].strip()
                break
        else:
            status = "Colibri could not find the status sting the the bounced mail"

        # find the colibri profile associated with this email
        profile = find_email(bounced_email, checkOthers=False)
        if profile == None:
            info("handleOwner : Can't find this email in the database, returned mail rejected")
            self.reject(filename)
            return

        # create bounce object, update profile
        bounce = Bounce(profile=profile, status=status, filename= "/%s/%s" % (unicode(mylist),filename)) # TODO :  parse and set bounce.datetime
        bounce.save()
        profile.bounces_count = profile.bounces_count+1
        profile.save()

        # move the file to rw/bounced/*
        # specification : the file goes to the directory BOUNCED_DIR/<listname>/
        bounced_dir = BOUNCED_DIR + "/%s/" % unicode(mylist)
        checkAndCreateDirectory(bounced_dir,BOUNCED_DIR)
        move_file("%s/%s" % (INCOMING_DIR, filename), bounced_dir+path.basename(filename), "bounced file")
        # we are done

    def checkMailValidity(self, mail):
        """
        Apply some heuristics to decide if the mail is valid (return True),
         or not (return False)
        """
        if mail['From']==None: return False
        if mail['Date']==None: return False
        if mail['Message-ID']==None: return False
        if mail['X-Original-To']==None and mail['Delivered-To']==None: return False
        return True

    def reject(self, filename):
        """
        Reject the mail to some folder
        """
        move_file(INCOMING_DIR+filename, REJECT_DIR+path.basename(filename), 'reject')

def daemonize(usepidfile):
    from os import fork, chdir, setsid
    #  Daemonize
    # do the UNIX double-fork magic, see Stevens' "Advanced 
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    try: 
        pid = fork() 
        if pid > 0:
            # exit first parent
            sys.exit(0) 
    except OSError, e: 
        err ("fork #1 failed: %d (%s)" % (e.errno, e.strerror) )
        sys.exit(1)

    # decouple from parent environment
    chdir("/") 
    setsid() 
    umask(0) 

    # do second fork
    try: 
        pid = fork() 
        if pid > 0:
            # exit from second parent, print eventual PID before
            if usepidfile:
                file(PIDFILE,'w+').write("%s\n" % pid)
            else:
                info("Daemon PID %d" % pid)
            sys.exit(0) 
    except OSError, e: 
        err ("fork #2 failed: %d (%s)" % (e.errno, e.strerror))
        sys.exit(1) 
    info('colibrid successfully started in background')

def main():
    # parse options
    MyOptionParser = OptionParser()
    MyOptionParser.add_option("--fork", action="store_true", dest="fork", default=False)
    MyOptionParser.add_option("--pidfile", action="store_true", dest="usepidfile", default=True)
    MyOptionParser.add_option("--debug", action="store_true", dest="debug", default=False)
    options, arguments = MyOptionParser.parse_args()
 
    if options.usepidfile:
        try:
            pf  = file(PIDFILE,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        if pid:
            err("Start aborded since pid file '%s' exists.\n" % PIDFILE)
            sys.exit(1)

    # start
    info('------------------------------------------')
    info('Colibrid started, watching INCOMING_DIR=%s', INCOMING_DIR)

    if options.debug:
        # do only one check, could be used with a cron
        colibrid = Colibrid()
        colibrid.checkIncomingMails()
        sys.exit(0)

    # become daemon AFTER all checks, as late as possible
    if options.fork:
        # fork you
        daemonize(options.usepidfile)
        # we keep the umask(0) in daemonize as this seems to be standard
        umask(~0755)
    else:
        # keep only one process: write pidfile
        if options.usepidfile:
            file(PIDFILE,'w+').write("%s\n" % getpid())
        info('Not forking, pid=%d', getpid())

    # start the daemon main loop
    colibrid = Colibrid()
#    colibrid.run()
    try:
        colibrid.run()
    except: #python doc says it is a very bad practice to catch all exception
        err("Unexpected error", exc_info=1)
        info('Caught something while running mainloop() : giving up')
    info('colibrid exiting cleanly')

    # remove pidfile
    if options.usepidfile:
        unlink(PIDFILE)
    sys.exit(0)

# if python says run, then we should run
if __name__ == '__main__':
    main() 
