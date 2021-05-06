import sqlite3
import parsers
import time
import os
import shutil
import zipfile
import logging
import random
from io import BytesIO
from requests import session
from requests import exceptions
from requests.packages.urllib3.exceptions import NewConnectionError
from urllib.parse import urlsplit,urlunsplit
import stat
from constants import *
import re

#######################################################
######takeown + zip, utlility functions################
#######################################################
#YMMV, this probably doesnt even help.
def takeown(func, path, excinfo):
    os.chmod(path, stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) # give write permissions to everyone
    func(path)
##    if not os.access(path,os.W_OK):
##        os.chmod(path, 0777)#whatever just go full 777 stat.S_IWUSR) # nah, dont.

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    
class SQLManager():
    COLUMNS = ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime', 'Error', 'SuccessTime', 'Error Message','Rating','LastUpdateAttempt']
    
    def __init__(self, parserFetch):
        self.conn = sqlite3.connect(storage_path('manga.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function('cleanName',1,SQLManager.cleanName)
        self.conn.create_function('regexsub',3,re.sub)
        self.parserFetch = parserFetch
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS series
                     (url text PRIMARY KEY, title text, last_read text, latest text, unread number, site text, complete number, update_time number, error number, last_success)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                     (id integer PRIMARY KEY DEFAULT 0, readercmd text)''')
        c.execute('''CREATE TABLE IF NOT EXISTS site_info
                     (name text PRIMARY KEY, username text DEFAULT '', password text DEFAULT '')''')
        # history doesn't need all these columns but it won't really hurt as the max size of this table is around 5 rows
        c.execute('''CREATE TABLE IF NOT EXISTS history
                     (url text PRIMARY KEY, title text, last_read text, path text)''')
        c.execute('''DROP TRIGGER IF EXISTS prune_history''')
        c.execute('''CREATE TRIGGER IF NOT EXISTS prune_history AFTER INSERT ON history
                    BEGIN
                        delete from history where
                        (select count(*) from history)>10 AND 
                        rowid in (SELECT rowid FROM history order by rowid limit 1);
                    END''')
        c.execute('''INSERT OR IGNORE INTO user_settings (id, readercmd) VALUES (0,'')''')
        try:
            c.execute('''ALTER TABLE series ADD COLUMN error_msg text''')
        except sqlite3.OperationalError:
            pass # col exists
        try:
            c.execute('''ALTER TABLE series ADD COLUMN rating integer DEFAULT -1''')
        except sqlite3.OperationalError:
            pass # col exists
        try:
            c.execute('''ALTER TABLE series ADD COLUMN last_update_attempt number DEFAULT 0''')
        except sqlite3.OperationalError:
            pass # col exists
        try:
            c.execute('''ALTER TABLE series ADD COLUMN data1 text DEFAULT NULL''')
        except sqlite3.OperationalError:
            pass # col exists
        for col in ('global_threadsmax int DEFAULT {}'.format(MAX_UPDATE_THREADS),
                    'site_threadsmax int DEFAULT {}'.format(MAX_SIMULTANEOUS_UPDATES_PER_SITE),
                    'start_hidden int DEFAULT 0',
                    'start_with_windows int DEFAULT 0',
                    'series_update_freq int DEFAULT {}'.format(MIN_UPDATE_FREQ//60),
                    'convert_webp_to_jpeg int DEFAULT 2',
                    ):
            try:
                c.execute('''ALTER TABLE user_settings ADD COLUMN {}'''.format(col))
            except sqlite3.OperationalError:
                pass # col exists
        c.executemany('''INSERT OR IGNORE INTO site_info (name) VALUES (?)''',[(site.__name__,) for site in parserFetch.get_req_credentials_sites()])
        self.conn.commit()
        c.close()

        self.getCredentials() # to update the parserfetch correctly.
        self.legacyConversions()
        self.regexLegacyConversions()
        if LOGGING:
            logging.basicConfig(level=logging.ERROR, filename=storage_path('Series_Errors.log'))
        else:
            logging.basicConfig(level=logging.DEBUG, stream=BytesIO())
            logging.disable(logging.ERROR)

    def close(self):
        self.conn.close()

    def legacyConversions(self):
        c = self.conn.cursor()
        # change old site urls to new ones.
        for conv in parsers.ParserFetch._get_conversions():
            c.execute('''UPDATE series SET url=replace(url,?,?) WHERE site=? AND url LIKE ?''',(conv[1],conv[2],conv[0],conv[3]))
        self.conn.commit()
        c.close()
        
    def regexLegacyConversions(self):
        c = self.conn.cursor()
        # change old site urls to new ones.
        for conv in parsers.ParserFetch._get_regex_conversions():
            c.execute('''UPDATE series SET url=regexsub(?,?,url) WHERE site=?''',conv)
        self.conn.commit()
        c.close()
        
    def updateParserCredentials(self,creds):
        self.parserFetch.updateCreds(creds)

    def getCredentials(self):
        site_names = str(tuple([t.__name__ for t in self.parserFetch.get_valid_parsers()])).replace("'",'"')
        c = self.conn.cursor()
        c.execute("SELECT name,username,password FROM site_info WHERE name IN {}".format(site_names))
        triples = c.fetchall()
        c.close()
        credentials = dict([[a,[b,c]] for a,b,c in triples])
        self.updateParserCredentials(credentials)
        return credentials

    def setCredentials(self, credentials):
        c = self.conn.cursor()
        flat = [(k,v[0],v[1]) for k,v in list(credentials.items())]
        cmd = "REPLACE INTO site_info (name,username,password) VALUES ("+','.join(['?']*len(flat))+")"
        c.executemany("REPLACE INTO site_info VALUES (?,?,?)",flat)
        self.conn.commit()
        c.close()
        self.updateParserCredentials(credentials) # put this last in case something goes wrong.
    
    def setReader(self, cmd):
        cmd = str(cmd)
        c = self.conn.cursor()
        c.execute("UPDATE user_settings set readercmd=? WHERE id=0",(cmd,))
        self.conn.commit()
        c.close()
        
    def getReader(self):
        c = self.conn.cursor()
        c.execute("SELECT readercmd FROM user_settings WHERE id=0")
        cmd = c.fetchall()
        c.close()
        return cmd[0][0]

    def writeSettings(self, settings_dict):
        c = self.conn.cursor()
        query = 'UPDATE user_settings SET {}=? WHERE id=0'.format('=?, '.join(settings_dict.keys()))
        c.execute(query, [v if v==None else str(v) for v in list(settings_dict.values())])
        self.conn.commit()
        c.close()

    def readSettings(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM user_settings WHERE id=0")
        data = c.fetchone()
        c.close()
        return data


    SERIES_URL_CONFLICT = 65
    SERIES_TITLE_CONFLICT = 66
    SERIES_NO_CONFLICT  = 64
    
    def addSeries(self,series,alt_title=None,read = 'N', chapters='?', unread = 0, rating = -1):
        ' series is the result of parserFetch.fetch(url) '
        title = alt_title or series.get_title()
        url = series.get_url()
        c = self.conn.cursor()
        try:
            r = c.execute('SELECT EXISTS(SELECT 1 FROM series WHERE url=?)',(url,))
            if r.fetchone()[0]:
                return self.SERIES_URL_CONFLICT, None
            
            #very inefficient.
            r = c.execute('SELECT * FROM series WHERE cleanName(title)=? LIMIT 1',(SQLManager.cleanName(title),))
            results=r.fetchone()
            if results:
                return self.SERIES_TITLE_CONFLICT, results
            
            data=(url,title,read,chapters,unread,series.get_shorthand(),0,time.time(),0,time.time(),rating)
            c.execute("INSERT INTO series (url,title,last_read,latest,unread,site,complete,update_time,error,last_success,rating) VALUES ({})".format(','.join(['?']*len(data))),data)
            self.conn.commit()
            r = c.execute("SELECT * FROM series WHERE url=?",(url,))
            return self.SERIES_NO_CONFLICT, r.fetchone()
        finally:
            c.close()
        
    @staticmethod
    def formatName(name):
        try:
            name='%#06.2f'%float(name)
        except:
            pass # just leave it
        return name

    @staticmethod
    def fitnumber(number,nums):
        try:
            number=float(number)
        except:
            return 0 # return 0 if number isn't a number
        #finds the index of nums that is greater than number
        idx=0
        for num in sorted(nums):
            if number>=float(num):
                idx+=1
        return idx

    @staticmethod
    def cleanName(name):
        return (''.join(c for c in name if c in '-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')).strip()

    def removeSeries(self,url,removeData=False):
        c = self.conn.cursor()
        c.execute("DELETE FROM series WHERE url=?",(url,))
        self.conn.commit()
        c.close()
        if removeData:
            validname = storage_path(SQLManager.cleanName(removeData))
            if os.path.exists(validname):
                try:
                    shutil.rmtree(validname, onerror=takeown)
                except:
                    'could not remove files - likely missing'

    def rollbackSeries(self,url,last_read,title):
        c = self.conn.cursor()
        c.execute("UPDATE series set last_read=? WHERE url=?",(last_read-1,url))
        self.conn.commit()
        c.close()
        validname = SQLManager.cleanName(title)
        chaptername = SQLManager.formatName(last_read)
        chapter = storage_path(os.path.join(validname,chaptername))
        if os.path.exists(chapter):
                shutil.rmtree(chapter, onerror=takeown)
                
    def completeSeries(self,url,completed):
        c = self.conn.cursor()
        c.execute("UPDATE series set complete=? WHERE url=?",(completed,url))
        self.conn.commit()
        c.close()
        
    def updateSeriesUrl(self,url,newurl):
        c = self.conn.cursor()
        c.execute("UPDATE series set url=? WHERE url=?",(newurl,url))
        self.conn.commit()
        c.close()

    # this method is extremely outdated and terribly coded BUT it still works somehow so we just leave it alone. Everything around it has changed drastically so it could probably be cut down
    # to much, much fewer lines of code. (And more readable)
    def updateSeries(self, data, convert_webp = False):
        working_chapter = None
        working_page = None
        errtype = 1
        errmsg = ''
        data=list(data)
        logsafe_title = data[TABLE_COLUMNS.index('Title')]
        try:
            # this isnt ideal but it works and thats all we care about for logging
            logsafe_title = str(str(data[TABLE_COLUMNS.index('Title')]).encode('utf8'))
        except:# UnicodeEncodeError:
            logsafe_title = '[Could not encode name]'
        try:
            series = self.parserFetch.fetch(data[TABLE_COLUMNS.index('Url')])
            if not isinstance(series,parsers.SeriesParser):
##            if not series:
                if series==-3:
                    logging.exception('Type 2 (cloudflare bypass failed for '+logsafe_title)
                    return 2,['Cloudflare bypass failed.']
                if series==-2:
                    #server error
                    logging.exception('Type 1 (failed accessing series page for '+logsafe_title+' due to server error 5xx)')
                    return 1,['Webpage could not be reached. (Server Error)']
                if series==-1:
                    #client error
                    logging.exception('Type 2 (failed accessing series page for '+logsafe_title+' due to client error 4xx)')
                    return 2,['Webpage could not be reached.']
                if series!=-4 and self.parserFetch.match(data[TABLE_COLUMNS.index('Url')]) is not None:#got a match, but still invalid (this means the title wasnt parsed correctly)
                    logging.exception('Type 1 (couldnt parse series title for '+logsafe_title+')')
                    return 1,['Parser needs updating.']
                #else is None aka invalid site
                logging.exception('Type 4 (series not supported: '+logsafe_title+')')
                return 4,['Parser Error: Site/series no longer supported.']
            if convert_webp:
                series.set_webp_conversion()
            nums,chapters = series.get_chapters()
            sorted_chapters = sorted(zip(nums,chapters), key=lambda pair: float(pair[0]))
            nums,chapters = [[i for i,_ in sorted_chapters],
                             [i for _,i in sorted_chapters]]
            if not len(chapters):
                logging.exception('Type 1 (Parser Error: No chapters found: '+logsafe_title+')')
                return errtype,['Parser Error: No chapters found.'] # type 1 is a generic parser error
##            if chapters[-1][0]!=data[3] or data[2]!=chapters[-1][0]: #[3]=latest != newlatest or last_read != newlatest, this makes more work but gives us 100% accuracy so we must
            if chapters[-1][0]!=data[TABLE_COLUMNS.index('Chapters')] or data[TABLE_COLUMNS.index('Read')]!=chapters[-1][0]:
                data[TABLE_COLUMNS.index('Chapters')] = chapters[-1][0] #update our latest chapter
##                print nums
                try:
                    idx = nums.index(data[TABLE_COLUMNS.index('Read')]) #[2]=last read ch
                except:#
                    idx=-1
                    if is_number(data[TABLE_COLUMNS.index('Read')]): # we try to fit the last read into the nums somwhere, even though the file doesn't exist.
                        idx=SQLManager.fitnumber(float(data[TABLE_COLUMNS.index('Read')]),nums)-1
                toupdate = chapters[idx+1:]
                unread_count = 0
                validname = SQLManager.cleanName(data[TABLE_COLUMNS.index('Title')])#[1]=name of series
                errors=0
                print(time.strftime('%m/%d %H:%M'),'updating',len(toupdate),'chapters from',logsafe_title)
                try:
                    unread_count,updated_count = series.save_images(validname, toupdate)
                except parsers.DelayedError as e:
                    # this a very special error used only by mangadex (for now).
                    # this indicates the chapter is on hold by scanlators, meaning no programmming/parser error
                    # to handle this we should modify the value of latest chapter.
                    updated_count = e.updated_count
                    unread_count = e.unread_count
                    if e.last_updated !=None:
                        data[TABLE_COLUMNS.index('Chapters')] = e.last_updated
                    elif idx:
                        data[TABLE_COLUMNS.index('Chapters')] = chapters[idx][0]
                        
                except parsers.LicensedError as e:
                    errors+=1
                    errtype=3
                    errmsg=e.display
                    logging.exception('Type 3-M (Licensed) ('+logsafe_title+' c.'+e.chapter+' p.'+e.imagenum+'): '+str(e))
                except exceptions.HTTPError as e:
                    errors+=1
                    if e.response.status_code in series.LICENSED_ERROR_CODES:
                        errtype=3
                        errmsg='HTTP error {}, likely licensed'.format(e.response.status_code)
                        logging.exception('Type 3 (http Licensed) ('+logsafe_title+' c.'+e.chapter+' p.'+e.imagenum+'): '+str(e))
                    elif hasattr(e, 'display'):
                        errmsg=e.display
                        logging.exception('Type 1 ('+logsafe_title+' c.'+e.chapter+' p.'+e.imagenum+'): '+str(e))
                    else:
                        errmsg='HTTP Error {} on Ch.{} Page {}'.format(e.response.status_code,e.chapter,e.imagenum)
                        logging.exception('Type 1 ('+logsafe_title+' c.'+e.chapter+' p.'+e.imagenum+'): '+str(e))
                except Exception as e:
                    errors+=1
                    errmsg='Error on Ch.{} Page {} '.format(e.chapter,e.imagenum)
                    logging.exception('Type 1 ('+logsafe_title+' c.'+e.chapter+' p.'+e.imagenum+'): '+str(e))
                    if hasattr(e, 'display'):
                        errmsg=e.display
                    else:
                        errmsg+= type(e).__name__
                        
##                print 'finished with',errors,'errors'
                if errors==0:# and unread_count>0: # commenting this allows for an initial update, we also need it commented for successtime to be accurate.
                    data[TABLE_COLUMNS.index('Unread')] = unread_count
                    data[TABLE_COLUMNS.index('Error')] = 0 #set error to 0
                    try:
                        if time.time() - series.AUTO_COMPLETE_TIME > data[TABLE_COLUMNS.index('UpdateTime')]:
                            data[TABLE_COLUMNS.index('Complete')] = int(series.is_complete())
                    except:
                        errmsg = 'Failure parsing series completion'
                        logging.exception('Type 2 ('+logsafe_title+'): Failure parsing series completion '+str(e))
                        return 2,[errmsg] # err type 2 is a severe parser error
                    if updated_count>0: # if no chapters have been updated, we don't want to change the update time
                        return 0,data
                    else:
                        return -1,data # -1 is just a successful update with no new chapters added.
                else:
                    #return error type
                    return errtype,[errmsg] # type 1 is a generic parser error
    ##        return False
            else:
                #no update needed but we should check autocopmlete
                #important that we only update here if the series is complete, otherwise it will reset last update time incorrectly.
                if not data[TABLE_COLUMNS.index('Error')] and int(series.is_complete()) and time.time() - series.AUTO_COMPLETE_TIME > data[TABLE_COLUMNS.index('UpdateTime')]:
                    data[TABLE_COLUMNS.index('Complete')] = int(series.is_complete())
                    return 0,data
                
            return 0,[]
            
        except NewConnectionError as e:
            if 'Errno 11004' in str(e):
                ''' this means we don't have internet access (most likely)
                    11004 is getaddrinfo failed '''
                logging.exception('Type 1-nointernet ('+logsafe_title+' c.'+str(ch[0])+' p.'+str(iindex)+'): '+str(e))
                return 1,['No Internet Connection']
        except Exception as e:
            if isinstance(e,ValueError) and str(e)=='Captcha':
                e.display = 'Cloudflare Captcha Requested'
            errmsg = 'Error downloading: '
            if hasattr(e, 'display'):
                errmsg+= e.display
            else:
                errmsg+= type(e).__name__
            logging.exception('Type 2 ('+logsafe_title+'): '+str(e))
            return 2,[errmsg] # err type 2 is a severe parser error
                
            
    def getSeries(self):
        #gets a list of lists containing all data
        c = self.conn.cursor()
        c.execute('''SELECT * FROM series''')
        series = c.fetchall()
        self.conn.commit()
        c.close()
        return list(list(x) for x in series)

    def getToUpdate(self, update_all=0):
        # get data for series which are eligible for update
        c = self.conn.cursor()
        c.execute('''SELECT * FROM series WHERE NOT complete AND last_update_attempt<strftime('%s', 'now')-?''',(update_all or MIN_UPDATE_FREQ,))
        series = c.fetchall()
        self.conn.commit()
        c.close()
        return list(list(x) for x in series)
    
    def changeSeries(self,data,_tbl='series'):
        # REPLACE the data into the db.
        c = self.conn.cursor()
        c.execute("REPLACE INTO `{}` VALUES ({})".format(_tbl,','.join(['?']*len(TABLE_COLUMNS))),data)
        self.conn.commit()
        c.close()

    def addHistory(self, data, last_read, path):
        # REPLACE the data into the db.
        reldata = data[:2] # url, title
        try:
            reldata.append(float(last_read))
        except ValueError:
            #last_read is #temp or another invalid directory name
            return -1
        reldata.append(path)
##        localcopy = data.copy()
##        localcopy[TABLE_COLUMNS.index('Read')] = float(last_read)
        c = self.conn.cursor()
        c.execute("REPLACE INTO `history` VALUES (?,?,?,?)",reldata)
        self.conn.commit()
        c.close()

##        return self.changeSeries(localcopy,_tbl='history')
        
    def getHistory(self, count=5):
        c = self.conn.cursor()
        c.execute('''SELECT title,last_read,path FROM history ORDER BY rowid DESC LIMIT ?''',(count,))
        res = c.fetchall()
        c.close()
        return res
    
