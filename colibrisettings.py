
#
# Those settings are specific to COLIBRI, not django
#
# They are stored in a different file than settings.py, so that they can be
# included without python loading the whole django
#

from os.path import dirname, abspath
rootdir = dirname( abspath( __file__))

rwdir='/var/tmp/colibri/'

ARCHIVE_DIR = rwdir+"/rw/archives/"
REJECT_DIR = rwdir+"/rw/rejected/"
BOUNCED_DIR = rwdir+"/rw/bounced/"

INCOMING_DIR = '/var/spool/colibri/new/'


# should colibrid output its log on stdout ? probably only useful for debugging
LogStdout = False

# if set to something different than "None", will log to the filename, check access permission twice
LogFileName="/var/log/colibri.log"

PIDFILE = "/var/run/colibri/colibrid.pid"

ALLOW_USER_TO_REQUEST_NEW_LIST = True
USE_TOPICS = True
