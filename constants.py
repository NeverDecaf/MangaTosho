import sys,os
##try:
##    sys._MEIPASS
##    os.chdir(os.path.dirname(sys.executable))
##except:
##    os.chdir(os.path.dirname(os.path.realpath(__file__)))
from PyQt5.QtGui import QIcon       
# from qtable
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base_path, relative_path)

def storage_path(relative_path):
    """ Get absolute path to dir where .exe or .py is located. """
    try:
        sys._MEIPASS
        base_path = os.path.dirname(sys.executable)
    except Exception:
        base_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base_path, relative_path)

MAX_UPDATE_THREADS = 8
MAX_SIMULTANEOUS_UPDATES_PER_SITE = 1
MMCE=resource_path("!MMCE_Win32\MMCE_Win32.exe")
SERIES_UPDATE_FREQ = 1000*60*20 #20m, time between update queueing
STALLED_TIME = 86400 * 100 # days before marked stalled
SEVERE_ERROR_TIME = 86400 * 14 #error considered severe if no updates in this time.

COMPLETE_ICON_PATH = resource_path('complete.png')
STALLED_ICON_PATH = resource_path('stalled.png')
ONGOING_ICON_PATH = resource_path('ongoing.png')
UNREAD_ICON_PATH = resource_path('unread.png')
ERROR_ICON_PATH = resource_path('error.png')
SEVERE_ERROR_ICON_PATH = resource_path('severe_error.png')
RIP_ICON_PATH = resource_path('rip.png')

# from mangasql
TABLE_COLUMNS = ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime',
                 'Error', 'SuccessTime', 'Error Message', 'Rating', 'LastUpdateAttempt']
LOGGING=False # If true, will log individual series errors to Series_Errors.log
MIN_UPDATE_FREQ = 60*60*4 #4 hrs, this is per series.
MAX_UPDATE_FREQ = 60*60*24 #24 hrs, this is per series.
if os.path.exists(storage_path('DEBUG_TEST')):
    LOGGING=True

# from parsers
REQUEST_TIMEOUT = 60
ALLOWED_IMAGE_ERRORS_PER_CHAPTER = 0 # Image errors means missing images, probably will always keep this at 0.
CHAPTER_DELAY=(3,5) # seconds between chapters, to keep from getting banned.
PARSER_VERSION = 2.14 # update if parsers.py changes in a way that is incompatible with older parsers.xml
