import sqlite3
import parsers
import time
import os.path
import os
import shutil
import zipfile
import logging
from PIL import Image
from io import BytesIO
from requests import session
from requests import exceptions
DELAY=5 # seconds between chapters, to keep from getting banned.
LOGGING=False # If true, will log individual series errors to Series_Errors.log
ALLOWED_IMAGE_ERRORS_PER_CHAPTER = 0 # I don't like this one bit. Should be 0. If you don't care about missing images increase this.
ONE_MONTH = 2592000 # seconds.
AUTO_COMPLETE = ONE_MONTH * 3 # seconds before a series claimed to be complete by the site is marked as completed (in the db).

if os.path.exists('DEBUG_TEST'):
    LOGGING=True

#######################################################
######takeown + zip, utlility functions################
#######################################################
#YMMV, this probably doesnt even help.
def takeown(func, path, excinfo):
    os.chmod(path, stat.S_IWUSR | stat.S.IWGRP | stat.S_IWOTH) # give write permissions to everyone
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
    COLUMNS = ['Url', 'Title', 'Read', 'Chapters', 'Unread', 'Site', 'Complete', 'UpdateTime', 'Error', 'SuccessTime', 'Error Message']
    
    def __init__(self, parserFetch):
        self.conn = sqlite3.connect('manga.db')
        self.parserFetch = parserFetch
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS series
                     (url text PRIMARY KEY, title text, last_read text, latest text, unread number, site text, complete number, update_time number, error number, last_success)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                     (id integer PRIMARY KEY DEFAULT 0, readercmd text)''')
        c.execute('''CREATE TABLE IF NOT EXISTS site_info
                     (name text PRIMARY KEY, username text DEFAULT '', password text DEFAULT '')''')
        c.execute('''INSERT OR IGNORE INTO user_settings (id, readercmd) VALUES (0,'')''')
        try:
            c.execute('''ALTER TABLE series ADD COLUMN error_msg text''')
        except sqlite3.OperationalError:
            pass # col exists
        c.executemany('''INSERT OR IGNORE INTO site_info (name) VALUES (?)''',[(site.__name__,) for site in parserFetch.get_req_credentials_sites()])
        self.conn.commit()
        c.close()

        self.getCredentials() # to update the parserfetch correctly.
        
        if LOGGING:
            logging.basicConfig(level=logging.ERROR, filename='Series_Errors.log')
        else:
            logging.basicConfig(level=logging.DEBUG, stream=BytesIO())
            logging.disable(logging.ERROR)

    def updateParserCredentials(self,creds):
        self.parserFetch.updateCreds(creds)

    def getCredentials(self):
        c = self.conn.cursor()
        c.execute("SELECT name,username,password FROM site_info")
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
        c.execute("REPLACE INTO user_settings (id,readercmd) VALUES (0,?)",(cmd,))
        self.conn.commit()
        c.close()
        
    def getReader(self):
        c = self.conn.cursor()
        c.execute("SELECT readercmd FROM user_settings WHERE id=0")
        cmd = c.fetchall()
        c.close()
        return cmd[0][0]
        
    def addSeries(self,url):
        series = self.parserFetch.fetch(url)
##        parser=self.parserFetch.match(url)
        if series==None:
            return None
        
##        series = parser(url)
        title = series.get_title()
        c = self.conn.cursor()
        data=(url,title,'N','?',0,series.get_shorthand(),0,time.time(),0,time.time(),'')
        try:
            c.execute("INSERT INTO series VALUES (?,?,?,?,?,?,?,?,?,?,?)",data)
        except sqlite3.IntegrityError:
            self.conn.commit()
            c.close()
            return False # returns false if the data already exists in your db.
        self.conn.commit()
        c.close()
        return list(data)
        
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
        return ''.join(c for c in name if c in '-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

    def removeSeries(self,url,removeData=False):
        c = self.conn.cursor()
        c.execute("DELETE FROM series WHERE url=?",(url,))
        self.conn.commit()
        c.close()
        if removeData:
            validname = SQLManager.cleanName(removeData)
            if os.path.exists(validname):
                shutil.rmtree(validname, onerror=takeown)

    def rollbackSeries(self,url,last_read,title):
        c = self.conn.cursor()
        c.execute("UPDATE series set last_read=? WHERE url=?",(last_read-1,url))
        self.conn.commit()
        c.close()
        validname = SQLManager.cleanName(title)
        chaptername = SQLManager.formatName(last_read)
        chapter = os.path.join(validname,chaptername)
        if os.path.exists(chapter):
                shutil.rmtree(chapter, onerror=takeown)
                
    def completeSeries(self,url,completed):
        c = self.conn.cursor()
        c.execute("UPDATE series set complete=? WHERE url=?",(completed,url))
        self.conn.commit()
        c.close()


    # this method is extremely outdated and terribly coded BUT it still works somehow so we just leave it alone. Everything around it has changed drastically so it could probably be cut down
    # to much, much fewer lines of code. (And more readable)
    def updateSeries(self,data):
        working_chapter = None
        working_page = None
        try:
            errtype = 1
            errmsg = ''
            data=list(data)
            series = self.parserFetch.fetch(data[self.COLUMNS.index('Url')])
            if not series:
                return 4,['Parser Error: Site no longer supported.']
            nums,chapters = series.get_chapters()
            if not len(chapters):
                return errtype,['Parser Error: No chapters found.'] # type 1 is a generic parser error
##            if chapters[-1][0]!=data[3] or data[2]!=chapters[-1][0]: #[3]=latest != newlatest or last_read != newlatest, this makes more work but gives us 100% accuracy so we must
            if chapters[-1][0]!=data[self.COLUMNS.index('Chapters')] or data[self.COLUMNS.index('Read')]!=chapters[-1][0]:
                data[self.COLUMNS.index('Chapters')] = chapters[-1][0] #update our latest chapter
##                print nums
                try:
                    idx = nums.index(data[self.COLUMNS.index('Read')]) #[2]=last read ch
                except:#
                    idx=-1
                    if is_number(data[self.COLUMNS.index('Read')]): # we try to fit the last read into the nums somwhere, even though the file doesn't exist.
##                        idx=0
##                        print 'fitting',data[2]
                        idx=SQLManager.fitnumber(float(data[self.COLUMNS.index('Read')]),nums)-1
##                        print'@ index',idx
##                        for i in range(len(nums)):
##                            if float(nums[i])<float(data[2]):
##                                idx+=1
                toupdate = chapters[idx+1:]
                unread_count = 0
                updated_count = 0
                validname = SQLManager.cleanName(data[self.COLUMNS.index('Title')])#[1]=name of series
                errors=0
                try:
                    print('updating',len(toupdate),'chapters from',data[self.COLUMNS.index('Title')])
                except:
                    try:
                        print(data[self.COLUMNS.index('Title')].encode('utf8'))
                    except:
                        print('could not encode name')
                iindex=0
                for ch in toupdate:
                    try:
                        img_dl_errs = 0
                        ch=list(ch)
                        ch[0]=SQLManager.formatName(ch[0])
                        if not os.path.exists(os.path.join(validname,ch[0])):
##                            print 'about to get images, if fails, you prob looped infinite'
                            images = series.get_images(ch) # throws licensedError and maybe ?parsererror?
##                            print 'images gotten'
                            iindex=0
                            tempdir= os.path.join(validname,'#temp')
                            if os.path.exists(tempdir):
                                shutil.rmtree(tempdir, onerror=takeown)
                            os.makedirs(tempdir)
                            for image in images:
##                                print 'attempting to fetch image from',image
                                try: # give the site another chance (maybe)
                                    response = series.SESSION.get(image)
                                    #this little bit retries an image as .jpg if its .png and vice versa, its pretty much used exclusively for batoto
                                    if response.status_code == 404:
                                        del response
                                        url,ext = os.path.splitext(image)
                                        if ext == '.jpg':
                                            ext='.png'
                                            response = series.SESSION.get(url+ext)
                                        elif ext == '.png':
                                            ext='.jpg'
                                            response = series.SESSION.get(url+ext)
                                    response.raise_for_status()#raise error code if occured
                                    
                                    filename = os.path.join(tempdir,str(iindex)+os.path.splitext(image)[1])
                                    img = Image.open(BytesIO(response.content))
                                    img.save(os.path.splitext(filename)[0]+r'.'+img.format)
                                    iindex+=1
                                    
                                except:
                                    if img_dl_errs<ALLOWED_IMAGE_ERRORS_PER_CHAPTER:
                                        img_dl_errs+=1
                                        pass
                                    else:
                                        raise
                            shutil.move(tempdir,os.path.join(validname,ch[0]))
                            if os.path.exists(tempdir):
                                shutil.rmtree(tempdir, onerror=takeown)
                            updated_count+=1
                            #sleep should be OK in this inner loop, otherwise nothing is downloaded.
                            time.sleep(DELAY)
                        unread_count+=1
                        
                    except parsers.LicensedError as e:
                        errors+=1
                        errtype=3
                        errmsg=e.display
                        logging.exception('Type 3-M (Licensed) ('+data[1]+' c.'+str(ch[0])+' p.'+str(iindex)+'): '+str(e))
                        break
##                    except urllib2.HTTPError, e:
                    except exceptions.HTTPError as e:
                        errors+=1
                        if e.response.status_code==403: # mangareader and their tricks
                            errtype=3
                            errmsg='Error 403, likely licensed'
                            logging.exception('Type 3 (Licensed) ('+data[1]+' c.'+str(ch[0])+' p.'+str(iindex)+'): '+str(e))
                            break
                        else:
                            errmsg='HTTP Error %s on Ch.%g Page %g'%(e.response.status_code,float(ch[0]),iindex)
                            logging.exception('Type 1 ('+data[1]+' c.'+str(ch[0])+' p.'+str(iindex)+'): '+str(e))
                            break
                    except Exception as e:
                        errors+=1
                        errmsg='Error on Ch.%g Page %g'%(float(ch[0]),iindex)
                        logging.exception('Type 1 ('+data[1]+' c.'+str(ch[0])+' p.'+str(iindex)+'): '+str(e))
                        if hasattr(e, 'display'):
                            errmsg=e.display
                        else:
                            errmsg+= type(e).__name__
                        break
                    
##                print 'finished with',errors,'errors'
                if errors==0:# and unread_count>0: # commenting this allows for an initial update, we also need it commented for successtime to be accurate.
                    data[self.COLUMNS.index('Unread')] = unread_count
                    data[self.COLUMNS.index('Error')] = 0 #set error to 0
                    try:
                        if time.time() - AUTO_COMPLETE > data[self.COLUMNS.index('UpdateTime')]:
                            data[self.COLUMNS.index('Complete')] = int(series.is_complete())
                    except:
                        errmsg = 'Failure parsing series completion'
                        logging.exception('Type 2 ('+data[self.COLUMNS.index('Title')]+'): Failure parsing series completion '+str(e))
                        return 2,[errmsg] # err type 2 is a severe parser error
                    if updated_count>0: # if no chapters have been updated, we don't want to change the update time
                        return 0,data
                    else:
                        return -1,data # -1 is just a successful update with no new chapters added.
                else:
                    #return error type
                    return errtype,[errmsg] # type 1 is a generic parser error
    ##        return False
            return 0,[]
        except Exception as e:
            errmsg = 'Error downloading: '
            
            if hasattr(e, 'display'):
                errmsg+= e.display
            else:
                errmsg+= type(e).__name__
            logging.exception('Type 2 ('+data[self.COLUMNS.index('Title')]+'): '+str(e))
            return 2,[errmsg] # err type 2 is a severe parser error
                
            
    def getSeries(self):
        #gets a list of lists containing all data
        c = self.conn.cursor()
        c.execute('''SELECT * FROM series''')
        series = c.fetchall()
        self.conn.commit()
        c.close()
        return list(list(x) for x in series)
    
    def changeSeries(self,data):
        # REPLACE the data into the db.
        c = self.conn.cursor()
        c.execute("REPLACE INTO series VALUES (?,?,?,?,?,?,?,?,?,?,?)",data)
        self.conn.commit()
        c.close()
        
