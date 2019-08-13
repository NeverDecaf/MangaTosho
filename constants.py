import sys,os
from PyQt5.QtGui import QIcon
# from qtable
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

MAX_UPDATE_THREADS = 8
MAX_SIMULTANEOUS_UPDATES_PER_SITE = 1
MMCE=resource_path("!MMCE_Win32\MMCE_Win32.exe")
SERIES_UPDATE_FREQ = 1000*60*20 #20m, time between update queueing
STALLED_TIME = 86400 * 100 # days before marked stalled
SEVERE_ERROR_TIME = 86400 * 14 #error considered severe if no updates in this time.

COMPLETE_ICON_PATH = 'complete.png'
STALLED_ICON_PATH = 'stalled.png'
ONGOING_ICON_PATH = 'ongoing.png'
UNREAD_ICON_PATH = 'unread.png'
ERROR_ICON_PATH = 'error.png'
SEVERE_ERROR_ICON_PATH = 'severe_error.png'
RIP_ICON_PATH = 'rip.png'

# from mangasql
TABLE_COLUMNS = ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime',
                 'Error', 'SuccessTime', 'Error Message', 'Rating', 'LastUpdateAttempt']
LOGGING=False # If true, will log individual series errors to Series_Errors.log
MIN_UPDATE_FREQ = 60*60*4 #4 hrs, this is per series.
if os.path.exists('DEBUG_TEST'):
    LOGGING=True

# from parsers
REQUEST_TIMEOUT = 60
ALLOWED_IMAGE_ERRORS_PER_CHAPTER = 0 # Image errors means missing images, probably will always keep this at 0.
CHAPTER_DELAY=(3,5) # seconds between chapters, to keep from getting banned.
PARSER_VERSION = 2.08 # update if parsers.py changes in a way that is incompatible with older parsers.xml
