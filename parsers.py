import re
from lxml import html as lxmlhtml
import xml.etree.ElementTree as ET
import hashlib
import urllib.parse
import html.entities
from io import StringIO
import time
##from requests import session
import requests
import posixpath
import sys
import inspect
import os,shutil
import base64
import pyaes
import hashlib
import mangasql
from PIL import Image
from io import BytesIO
from fake_useragent import UserAgent
import urllib.request, urllib.parse, urllib.error
##import lxml.etree.XPathEvalError as XPathError
from lxml.etree import XPathEvalError as XPathError
from functools import reduce
import random
import jsbeautifier
# add the cacert.pem file to the path correctly even if compiled with pyinstaller:
# Get the base directory
if getattr( sys , 'frozen' , None ):    # keyword 'frozen' is for setting basedir while in onefile mode in pyinstaller
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname( __file__ )
    basedir = os.path.normpath( basedir )

if hasattr(sys,'_MEIPASS'):
    # Locate the SSL certificate for requests
    # we should only do this if this is running as an executable.
    os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(basedir , 'certifi', 'cacert.pem')

# need to set working directory for this to work with pyinstaller:
try:
    sys._MEIPASS
    os.chdir(os.path.dirname(sys.argv[0]))
except:
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

# we also need to add the resources directory to path to use the bundled nodejs
os.environ["PATH"] += os.pathsep + basedir
# only import cfscrape AFTER setting PATH
import cfscrape

REQUEST_TIMEOUT = 60
ALLOWED_IMAGE_ERRORS_PER_CHAPTER = 0 # I don't like this one bit. Should be 0. If you don't care about missing images increase this.
CHAPTER_DELAY=(4,5) # seconds between chapters, to keep from getting banned.

def hash_no_newline(stringdata):
    #got easier in python 3 thanks to universal newline mode being the default.
    return hashlib.md5(stringdata).hexdigest()
    return hashlib.md5(stringdata.replace('\n','').replace('\r','')).hexdigest()
##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(html.entities.name2codepoint[text[1:-1].lower()])
            except KeyError:
                pass
        return text # leave as is
    return re.sub(r"&#?\w+;", fixup, text)

# sites than have been abandoned:
# KissManga (crazy js browser verification, MangaFox (banned in the US), MangaPandaNet (taken by russian hackers), MangaTraders (not suitable for this program)
WORKING_SITES = []
PARSER_VERSION = 2.05 # update if this file changes in a way that is incompatible with older parsers.xml

class ParserFetch:
    ''' you should only get parsers through the fetch() method, otherwise they will not use the correct session object '''
    
    def get_valid_parsers(self):
        return self.parsers

    def get_valid_sites(self):
        v = []
        ret = ''
        for parser in (self.get_valid_parsers() - self.get_req_credentials_sites()):
            v.append(parser.SITE_URL+' ('+parser.ABBR+')')
        ret = '<br/>'.join(v)
        if self.get_req_credentials_sites():
            ret+= '<br/><font color="gray">'
            v=[]
            for parser in self.get_req_credentials_sites():
                v.append(parser.SITE_URL+' ('+parser.ABBR+')')
            ret += '<br/>'.join(v) + "</font>"
        return ret

    def get_req_credentials_sites(self):
        return self.parsers_req_creds
    
    def __init__(self, credentials = {}):
        global WORKING_SITES
        self.matchers=[]
        self.parsers_req_creds=set()
        self.version_uptodate = 0
        try:
            self.version_uptodate = self._update_parsers()
        except:
##            raise
            'ignore all exceptions to avoid a program-ending failure. should log them somewhere though.'
        self._generate_parsers()
        self.parsers = set(WORKING_SITES)#[globals()[cname] for cname in WORKING_SITES]
        for parser in self.parsers:
            if parser.USE_CFSCRAPE:
                self.matchers.append((parser.SITE_PARSER_RE,parser,cfscrape.create_scraper()))
            else:
                self.matchers.append((parser.SITE_PARSER_RE,parser,requests.session()))
            if parser.REQUIRES_CREDENTIALS:
                self.parsers_req_creds.add(parser)
        self.updateCreds(credentials)

    def version_mismatch(self):
        return self.version_uptodate==-1 # we are only interested in whether the version of mangatosho does not match the version of parsers.
    
    def match(self,url):
        ' do NOT use to get usable parser objects. use fetch instead. '
        #returns the parser class
        for rex in self.matchers:
            if rex[0].match(url):
                return rex[1]
        return None
    def fetch(self,url):
        # None =  site not supported (doesn't regex match)
        # -1 : error 4xx meaning invalid url or something similar (site is down)
        # -2: error 5xx meaning server error aka temporary issue (mostlikely)
        #returns an actual parser object
        for rex in self.matchers:
            if rex[0].match(url):
                try:
                    parser = rex[1](url,rex[2]) # initiate with shared session
                    if parser.VALID:
                        return parser
                    else:
                        return None
                except requests.exceptions.InvalidSchema:
                    return None
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code//100==5:
                        try:
                            if b'cloudflare' in e.response.content:
                                return -3
                        except:
                            pass
                        return -2
##                    if e.reponse.status_code//100==4:
                    return -1
                except requests.exceptions.Timeout:
                    return -1
        return None
    def updateCreds(self,credentials):
        for parser in self.parsers_req_creds:
            for k in credentials:
                if parser.__name__==k:
                    if len(credentials[k][0]) and len(credentials[k][1]):
                        parser.USERNAME = credentials[k][0]
                        parser.PASSWORD = credentials[k][1]
                        break

    def _update_parsers(self):
        # auto-update the parsers xml file if possible.
        if not os.path.exists('NO_PARSER_UPDATE'):
            r=requests.get('https://raw.githubusercontent.com/NeverDecaf/MangaTosho/master/parsers.md5', timeout = REQUEST_TIMEOUT)
            targethash = r.text
            if not os.path.exists('parsers.xml'):
                return update_parsers(PARSER_VERSION,targethash)
            else:
                with open('parsers.xml', 'rb') as f:
                    stringdata = f.read()
                    currenthash = hash_no_newline(stringdata)
##                    root = ET.fromstring(stringdata)#.getroot()
##                    currentversion = root.find('info').find('version').content
                if targethash!=currenthash:
                    return update_parsers(PARSER_VERSION,targethash)
                    
    def _generate_parsers(self):
        global WORKING_SITES
        tree = ET.parse('parsers.xml')
        root = tree.getroot()
        is_class_member = lambda member: inspect.isclass(member) and member.__module__ == __name__
        clsmembers = dict(inspect.getmembers(sys.modules[__name__], is_class_member))
        for site in root.iter('site'):
            classname = site.attrib['name']
            # remove None values and convert string booleans to booleans.
            # also create regex object for any key ending with _re
            data={k.upper(): {'True':True,'False':False,'None':None}.get(v,re.compile(v,re.IGNORECASE) if k=='site_parser_re' else re.compile(v,re.IGNORECASE) if k.endswith('_re') else tuple(map(float,v.split(','))) if k.endswith('_delay') else v) for k, v in list(self.__children_as_dict(site).items()) if v!=None}
            if classname!='TemplateSite':
                if classname in clsmembers:
                    WORKING_SITES.append(type(classname,(clsmembers[classname],),data))
                else:
                    WORKING_SITES.append(type(classname,(SeriesParser,),data))
    @staticmethod
    def _get_conversions():
        conversions = []
        tree = ET.parse('parsers.xml')
        root = tree.getroot()
        for conv in root.find('domain_changes').iter('conversion'):
            conversions.append(conv.text.split(','))
        return conversions
                    
    def __children_as_dict(self,t):
        d={}
        for v in list(t):
            d[v.tag]=v.text
        return d

class ParserError(Exception):
    pass

class LicensedError(Exception):
    pass

class DelayedError(Exception):
    pass

class SeriesParser(object):
    # these class vars should NEVER be edited by methods of this class or any subclass, doing so may break parsers.
    #required args
    SITE_URL=''#url of the home site.
    ABBR='' # abbreviated version of site's name, 2 letters
    SITE_PARSER_RE='' # determines whether the given url matches the site's url
    TITLE_XPATH = ''#xpath to fetch the series title. will be "cleaned" and formatted for uniformity.
    CHAPTER_NUMS_XPATH = '' #hopefully the site has formatted it well, most likely not.
    CHAPTER_URLS_XPATH = ''
    IMAGE_URL_XPATH ='' #parses the image url from a page of the series
    NEXT_URL_XPATH ='' #parses the link to the next page from a page of the series.
    IS_COMPLETE_XPATH = '/is/not/complete/must/override/this' # if this matches, it indicates the series has been marked complete by the site (and should no longer be parsed to save resources)
    CHAPTER_NUMS_RE = re.compile(r'(\d+\.?\d*)(?:v\d+)? *\Z')#match all chapter numbers, replacing this with NAMES won't hurt MUCH but it will cause the GUI to show a name instead of latest ch #

    #optional args:
    SKIP_MATURE = '' #url fragment added to skip mature content block (ex: skip=1)
    LICENSED_CHECK_RE = None # checks if series has been licensed
    REQUIRES_CREDENTIALS = False # if login credentials are required to use this site.
    REVERSE =True #indicates if the chapters are listed in reverse order, will be true for most sites
    AUTHOR_RE = re.compile(r' \(.*?\)\Z') # matches the author if included in the title, this regex is used to remove the author for cleaner series names
    # note that adding 2 series with the same name but different authors WILL cause a problem. there may or may not be a fix in place but i have yet to encounter this
    AIO_IMAGES_RE = None # some sites include all the image urls in one page, if so this RE matches all the image urls
    IGNORE_BASE_PATH = False # VERY dangerous, if set true you could download an entire series instead of just 1 chapter.
    # these 2 are used for sites with iterative page numbers, we can get a list of all pages of a chapter without jumping from one to the next.
    # this is currently only used for animeA so look there for more details.
    PAGE_TEMPLATE_RE = None # matches a prefix and suffix for the url [0] [1]
    ALL_PAGES_RE = None # matches a list of all page numbers that will be sandwiched between page_template
    IMAGE_URL_RE = None # Fallback for IMAGE_URL_XPATH if hidden in js
    NEXT_URL_RE = None # Fallback for NEXT_URL_XPATH if hidden in js
    USE_CFSCRAPE = True # Will use the cfscrape session instead of requests.session

    # will be used if site REQUIRES_CREDENTIALS, use class vars so we can set before creating an instance.
    USERNAME = None 
    PASSWORD = None

    IMAGE_DOWNLOAD_DELAY = (0,0) # delay to use when downloading images, for sites with a rate limit
    AUTO_COMPLETE_TIME = 2592000 * 3 # 3 months before a series claimed to be complete by the site is marked as completed (in the db).
    LICENSED_AS_403 = False # some sites use error 403 to indicate a licensed series.

    def __init__(self,url,sessionobj=None):
        #loads the html from the series page, also checks to ensure the site is valid
        #note if this returns False you cannot use this object.
        self.VALID=True # is set to false if the given url doesnt match the sites url
        self.UA = None
        self.TITLE = None
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        self.MAIN_URL = url
        if self.SITE_PARSER_RE.match(url)==None:
            self.VALID=False
            return
        # create a random user agent
        if not sessionobj:
            if self.USE_CFSCRAPE:
                self.SESSION = cfscrape.create_scraper()
            else:
                self.SESSION = requests.session()
        else:
            self.SESSION = sessionobj
        if sessionobj and hasattr(sessionobj,'init'):
            'session already exists and has been set up'
        else:
            if not hasattr(self,'HEADERS'):
                self.HEADERS = {}
            if not self.UA:
                self.UA = UserAgent(use_cache_server=False, fallback='Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36')
            self._cycle_UA()
            adapter = requests.adapters.HTTPAdapter(max_retries=1)
            self.SESSION.mount('https://', adapter)
            self.SESSION.mount('http://', adapter)
            
            self.SESSION.keep_alive = False
            
        self.login()
        r=self.SESSION.get(url, timeout = REQUEST_TIMEOUT)
        r.raise_for_status()
        # use this very first request to set the referer header (in case of redirect)
        if not hasattr(self.SESSION,'init'):
            try:
                ref = urllib.parse.urlunsplit(urllib.parse.urlsplit(r.history[-1].url)[:2]+('',)*3)
            except IndexError:
                ref = urllib.parse.urlunsplit(urllib.parse.urlsplit(r.url)[:2]+('',)*3)
            try:
                if not 'Referer' in self.HEADERS:
                    self.HEADERS['Referer'] = ref
            except AttributeError:
                self.HEADERS = {'Referer':ref}
            self.SESSION.headers.update(self.HEADERS)
        self.HTML = r.text
        self.etree = lxmlhtml.fromstring(self.HTML)
        if not self.get_title():
            self.VALID=False
        if self.VALID:
            self.SESSION.init = True # only init when valid so we are sure we didn't accidentally set referer to a 404 page or something
    def _cycle_UA(self):
        self.HEADERS['User-Agent'] = random.choice((self.UA.chrome,self.UA.firefox))
    def login(self):
        #log in to the site if authentication is required
        # this should check to see if you are logged in before attempting a login because session objects are shared.
        return
    def get_shorthand(self):
        #returns an abbreviated version of hte site's name
        return self.ABBR
    def get_title(self):
        #returns the title of the series
        if self.TITLE:
            return self.TITLE
        title = unescape(self.etree.xpath(self.TITLE_XPATH))
        split = title.split()
        for i in range(len(split)):
            if split[i].isupper() or i==0:
                split[i]=split[i].capitalize()
        ret = r' '.join(split)
        self.TITLE = self.AUTHOR_RE.sub(r'',ret)
        return self.TITLE
    def is_complete(self):
        return not not self.etree.xpath(self.IS_COMPLETE_XPATH)
    def extrapolate_nums(self, nums):
        #helper function that adds in chapter numbers for chapters without them (assumed to be extras or misc things otherwise you have a real problem here.)
        #check if there are no chapters
        if not len(nums):
            return []
##        if reduce(lambda x,y:x or self.CHAPTER_NUMS_RE.search(y),[0]+nums): # check to make sure at least one chapter has a legitimate number.
        
        # now we just fill in the missing chapters (assumed to be extras, etc.) (use the numbering system .01 .02 .03 to avoid conflict)
        # since this is a messy one liner heres what it does if you come back to look at this later:
        # if CHAPTER_NUMS_RE matches the number, simply use the number it matches, otherwise take the previous number and add .01 then use that instead.
        # HOWEVER, if the parsed number already exists in the list, add .01 to the prev instead.
        # finally, map them all with %g to truncate the .0 from whole numbers.
        
        # the list passed to reduce is just nums with the first element parsed with CHAPTER_NUMS_RE or 0 if parsing fails.
        floatnumbers = reduce(lambda x,y:
                              x+[float(self.CHAPTER_NUMS_RE.findall(y)[-1])] if self.CHAPTER_NUMS_RE.search(y) and (float(self.CHAPTER_NUMS_RE.findall(y)[-1]) not in x)
                                  else x+[(x[-1]*100.0+1.0)/100.0],
                              [[float(self.CHAPTER_NUMS_RE.findall(nums[0])[-1])]]+nums[1:] if self.CHAPTER_NUMS_RE.search(nums[0])
                                else [[0]]+nums[1:])
        if len(floatnumbers)==1 or sorted(floatnumbers)[-1] >= 1.0 or self.CHAPTER_NUMS_RE.search(nums[0]): # if there are no legit numbers then we don't want to return this UNLESS there is only one chapter, then we assume it is a oneshot with no number and allow it.
            # added this third clause to handle series with all chapters labeled chapter 0 (gon on mangahere)
            return ['{0:g}'.format(x) for x in floatnumbers]
        return []
    def get_chapters(self):
        #returns a list of all chapters, where each entry is a tuple (number,url)
        nums = self.etree.xpath(self.CHAPTER_NUMS_XPATH)
        urls = self.etree.xpath(self.CHAPTER_URLS_XPATH)
        if self.REVERSE:
            nums.reverse()
            urls.reverse()
        nums = self.extrapolate_nums(nums)
        urls = [urllib.parse.urljoin(self.MAIN_URL,x) for x in urls]

        if len(nums)!=len(urls):
            e = ParserError('Chapter Numbers and URLS do not match in '+self.get_title()+' (%i nums vs %i urls, site:%s)'%(len(nums),len(urls),type(self).__name__))
            e.display = 'Error parsing chapter list'
            raise e
            return False
        return nums,list(zip(nums,urls))
    
    def get_images(self,chapter,delay=(0,0),fix_urls = True):
        #returns links to every image in the chapter where chapter is the url to the first page
        #uses a new approach where we follow links until the end of the chapter
        self.login()
        try:
            if delay==(0,0):
                delay = self.IMAGE_DELAY
        except AttributeError:
            pass
        number,url = chapter

        ## If all image urls are easily parsable from the first page, we can finish up quickly.
        if self.AIO_IMAGES_RE:
            html = self.SESSION.get(url, timeout = REQUEST_TIMEOUT).text
            all_images=re.compile(self.AIO_IMAGES_RE)
            return [c if (c.startswith('http://') or not fix_urls) else urllib.parse.urljoin(self.SITE_URL,c) for c in [c.replace('\\','') for c in all_images.findall(html)]]
        ##
        images=[]
        first_chapter = True # first chapter sometimes has a slightly different url so we will refresh it after the first page.
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        chapter_path = posixpath.dirname(pieces[2])

        while self.IGNORE_BASE_PATH or posixpath.dirname(urllib.parse.urlsplit(url)[2]) == chapter_path:
##            print('reading',url)
            r= self.SESSION.get(url, timeout = REQUEST_TIMEOUT)
            r.raise_for_status()
            html = r.text
            etree = lxmlhtml.fromstring(html)
            
            time.sleep(random.uniform(*delay))
            
            if self.LICENSED_CHECK_RE!=None and self.LICENSED_CHECK_RE.search(html)!=None:
                e = LicensedError('Series '+self.get_title()+' is licensed.')
                e.display = 'Series is licensed'
                raise e

            if self.IMAGE_URL_RE:
                pictureurl = self.IMAGE_URL_RE.findall(html)[0].replace('\\','') # this is likely js, so remove backslashes
            else:
                pictureurl = etree.xpath(self.IMAGE_URL_XPATH)
##            print('pix is',pictureurl)
            if not len(pictureurl):
                # this means the image wasnt found. (parser is outdated)
                e = ParserError('Image Parsing failed on %s, chapter:%s'%(self.get_title(),number))
                e.display="Failed parsing images for Ch.%s"%number
                raise e
            # do some small url repairs
            if fix_urls:
                repair = urllib.parse.urlsplit(self.SITE_URL)
                img_url = urllib.parse.urlsplit(pictureurl)
                pictureurl = urllib.parse.urlunsplit([repair[i] if i<2 and not img_url[i] else img_url[i] for i in range(len(img_url))])
            if pictureurl in images: #prevents loops
                break
            images.append(pictureurl)

            try:
                if self.NEXT_URL_RE:
                    nexturl = self.NEXT_URL_RE.findall(html)[0].replace('\\','') # this is likely js, so remove backslashes
                else:
                    nexturl = etree.xpath(self.NEXT_URL_XPATH)
            except (XPathError,IndexError): # if IGNORE_BASE_PATH is true this is the only way to escape this infinite loop.
                if self.IGNORE_BASE_PATH:
                    break
                else:
                    raise
            
            newurl = urllib.parse.urljoin(url,nexturl)#join the url to correctly follow relative urls
            if newurl == url: # prevents fetching the same page twice (there is a second failsafe for this via pictureurl)
                break
            url = newurl
            if first_chapter:
                first_chapter = False
                chapter_path = posixpath.dirname(urllib.parse.urlsplit(url)[2])
##            print('next url is',url)
        return images
    def save_images(self,sname,chapters):
        updated_count=0
        unread_count=0
        for ch in chapters:
            try:
            # this is our num,url tuple
                img_dl_errs = 0
                ch=list(ch)
                ch[0]=mangasql.SQLManager.formatName(ch[0])
                if not os.path.exists(os.path.join(sname,ch[0])):
                    iindex=0
                    tempdir= os.path.join(sname,'#temp')
                    if os.path.exists(tempdir):
                        shutil.rmtree(tempdir, onerror=mangasql.takeown)
                    images = self.get_images(ch) # throws licensedError and maybe ?parsererror?
                    os.makedirs(tempdir)
                    for image in images:
        ##                                print('attempting to fetch image from',image)
                        try: # give the site another chance (maybe)
                            try:
                                response = self.SESSION.get(image, timeout = REQUEST_TIMEOUT, headers={'referer': self.IMAGE_REFERER})
                            except AttributeError:
                                response = self.SESSION.get(image, timeout = REQUEST_TIMEOUT)
##                                new = cfscrape.create_scraper()
##                                response=new.get(image, timeout = REQUEST_TIMEOUT)
                            #this little bit retries an image as .jpg if its .png and vice versa, its pretty much used exclusively for batoto
                            # batoto doesn't even exist so forget this part
    ##                        if response.status_code == 404:
    ##                            
    ##                            firstresponse = response
    ##                            spliturl = urlsplit(image)
    ##                            path,ext = os.path.splitext(spliturl.path)
    ##                            if ext == '.jpg':
    ##                                newpath = path+'.png'
    ##                            elif ext == '.png':
    ##                                newpath = path+'.jpg'
    ##                            response = series.SESSION.get(urlunsplit((spliturl.scheme,spliturl.netloc,newpath,spliturl.query,spliturl.fragment)), timeout = parsers.REQUEST_TIMEOUT)
    ##                            if not response.ok:
    ##                                firstresponse.raise_for_status()

                            response.raise_for_status()#raise error code if occured
                            time.sleep(random.uniform(*self.IMAGE_DOWNLOAD_DELAY))
                            
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
                    shutil.move(tempdir,os.path.join(sname,ch[0]))
                    if os.path.exists(tempdir):
                        shutil.rmtree(tempdir, onerror=mangasql.takeown)
                    updated_count+=1
                    #sleep should be OK in this inner loop, otherwise nothing is downloaded.
                    time.sleep(random.uniform(*CHAPTER_DELAY))
                unread_count+=1
            except Exception as e:
                e.chapter =str(ch[0])
                e.imagenum =str(iindex)
                raise e
        return unread_count,updated_count
    
################################################################################
class MangaDex(SeriesParser):
    # copied from mangarock, similar in that both have json api.
    def __init__(self,url,sessionobj=None):
        #loads the html from the series page, also checks to ensure the site is valid
        #note if this returns False you cannot use this object.
        self.VALID=True # is set to false if the given url doesnt match the sites url
        self.UA = None
        self.TITLE = None
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        self.MAIN_URL = url
        if self.SITE_PARSER_RE.match(url)==None:
            self.VALID=False
            return
        # create a random user agent
        if not sessionobj:
            if self.USE_CFSCRAPE:
                self.SESSION = cfscrape.create_scraper()
            else:
                self.SESSION = requests.session()
        else:
            self.SESSION = sessionobj
        if sessionobj and hasattr(sessionobj,'init'):
            'session already exists and has been set up'
        else:
            if not hasattr(self,'HEADERS'):
                self.HEADERS = {}
            if not self.UA:
                self.UA = UserAgent(use_cache_server=False, fallback='Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36')
            self._cycle_UA()
            adapter = requests.adapters.HTTPAdapter(max_retries=1)
            self.SESSION.mount('https://', adapter)
            self.SESSION.mount('http://', adapter)
            
            self.SESSION.keep_alive = False
        self.login()
        series_id = pieces[2].split('/')[2]
        query = self.SITE_URL.strip('/')+'/api/manga/{}'.format(series_id)
        r=self.SESSION.get(query, timeout = REQUEST_TIMEOUT)
        r.raise_for_status()
        # use this very first request to set the referer header (in case of redirect)
        if not hasattr(self.SESSION,'init'):
            try:
                ref = urllib.parse.urlunsplit(urllib.parse.urlsplit(r.history[-1].url)[:2]+('',)*3)
            except IndexError:
                ref = urllib.parse.urlunsplit(urllib.parse.urlsplit(r.url)[:2]+('',)*3)
            try:
                if not 'Referer' in self.HEADERS:
                    self.HEADERS['Referer'] = ref
            except AttributeError:
                self.HEADERS = {'Referer':ref}
            self.SESSION.headers.update(self.HEADERS)
##        self.HTML = r.text
        self.JSON = r.json()
##        self.etree = lxmlhtml.fromstring(self.HTML)
        if self.JSON['status']!='OK':
            self.VALID=False
        elif not self.get_title():
            self.VALID=False
        if self.VALID:
            self.SESSION.init = True # only init when valid so we are sure we didn't accidentally set referer to a 404 page or something
    def get_title(self):
        #returns the title of the series
        if self.TITLE:
            return self.TITLE
        title = unescape(self.JSON['manga']['title'])
        split = title.split()
        for i in range(len(split)):
            if split[i].isupper() or i==0:
                split[i]=split[i].capitalize()
        ret = r' '.join(split)
        self.TITLE = self.AUTHOR_RE.sub(r'',ret)
        return self.TITLE
    def is_complete(self):
        return self.JSON['manga']['status']==2
    def get_chapters(self):
        #returns a list of all chapters, where each entry is a tuple (number,url)
        # for mangarock this is (order,oid)
        # this is a bit complex, we have volume and chapter. need to extrapolate a bit, but how to do it cleanly?
        # just build our own dict from scratch, too confusing otherwise.
        volumes = {}
        for k,v in self.JSON['chapter'].items():
            if v['lang_code'] in ['en','gb']:
                # eng chapter, add it.
                try:
                    thisvol = int(v['volume'])
                except:
                    thisvol = 0
                try:
                    thisch = float(v['chapter'])
                except:
                    thisch = 0.0
                volumes.setdefault(thisvol,{})[thisch]=k

        nums = []
        urls = []
        vol_base = 0
        cvol = None
        for vol in sorted(volumes.keys(), key=lambda x:x or 99999): # sorts with 0 last
            for ch in sorted(volumes[vol].keys()):
                if cvol==None:
                    cvol = vol
                if vol != cvol:
                    if ch<=float(nums[-1]):
                        vol_base = float(nums[-1])
                    if ch == 0:
                        vol_base=int(vol_base+1)
                    cvol = vol
                nums.append(str(ch + vol_base))
                urls.append(volumes[vol][ch])
        nums = self.extrapolate_nums(nums)
        if len(nums)!=len(urls):
            e = ParserError('Chapter Numbers and URLS do not match in '+self.get_title()+' (%i nums vs %i urls, site:%s)'%(len(nums),len(urls),type(self).__name__))
            e.display = 'Error parsing chapter list'
            raise e
            return False
        return nums,list(zip(nums,urls))
    
    def get_images(self,chapter,delay=(0,0),fix_urls = True):
        self.login()
        try:
            if delay==(0,0):
                delay = self.IMAGE_DELAY
        except AttributeError:
            pass
        number,cid = chapter
        query = self.SITE_URL.strip('/')+'/api/chapter/{}'.format(cid)
        r= self.SESSION.get(query, timeout = REQUEST_TIMEOUT)
        delayed = 0
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code==409:
                ex = DelayedError()
                ex.display='Chapter {} delayed.'.format(number)
                raise ex
            raise e
            
        chjs = r.json()
        
        if chjs['status']=='OK':
            chash = chjs['hash']
            cserver = chjs['server']
            if cserver.strip('/')=='data':
                return [self.SITE_URL.strip('/')+'/data/{}/{}'.format(chash,img) for img in chjs['page_array']]
            return ['/'.join([s.strip('/') for s in (cserver,chash,img)]) for img in chjs['page_array']]
        else:
            e = ParserError('Json query failed on %s, chapter:%s'%(self.get_title(),number))
            e.display="Failed querying images for Ch.%s"%number
            raise e
    def save_images(self,sname,chapters):
        updated_count=0
        unread_count=0
        delayed_err = None
        for ch_index,ch in enumerate(chapters):
            try:
            # this is our num,url tuple
                img_dl_errs = 0
                ch=list(ch)
                ch[0]=mangasql.SQLManager.formatName(ch[0])
                if not os.path.exists(os.path.join(sname,ch[0])):
                    iindex=0
                    tempdir= os.path.join(sname,'#temp')
                    if os.path.exists(tempdir):
                        shutil.rmtree(tempdir, onerror=mangasql.takeown)
                        
                    try:
                        images = self.get_images(ch) # throws licensedError and maybe ?parsererror?
                    except DelayedError as e:
                        # set some vars and return
                        delayed_err = e
                        if ch_index:
                            e.last_updated = chapters[ch_index-1][0]
                        else:
                            e.last_updated = None
                        e.updated_count = updated_count
                        e.unread_count = unread_count
                        raise e  

                    os.makedirs(tempdir)
                    for image in images:
                        try: # give the site another chance (maybe)
                            try:
                                response = self.SESSION.get(image, timeout = REQUEST_TIMEOUT, headers={'referer': self.IMAGE_REFERER})
                            except AttributeError:
                                response = self.SESSION.get(image, timeout = REQUEST_TIMEOUT)

                            response.raise_for_status()#raise error code if occured
                            time.sleep(random.uniform(*self.IMAGE_DOWNLOAD_DELAY))
                            
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
                    shutil.move(tempdir,os.path.join(sname,ch[0]))
                    if os.path.exists(tempdir):
                        shutil.rmtree(tempdir, onerror=mangasql.takeown)
                    updated_count+=1
                    #sleep should be OK in this inner loop, otherwise nothing is downloaded.
                    time.sleep(random.uniform(*CHAPTER_DELAY))
                unread_count+=1
            except Exception as e:
                e.chapter =str(ch[0])
                e.imagenum =str(iindex)
                raise e
        return unread_count,updated_count
################################################################################
class MangaRock(SeriesParser):
    def __init__(self,url,sessionobj=None):
        #loads the html from the series page, also checks to ensure the site is valid
        #note if this returns False you cannot use this object.
        self.VALID=True # is set to false if the given url doesnt match the sites url
        self.UA = None
        self.TITLE = None
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        self.MAIN_URL = url
        if self.SITE_PARSER_RE.match(url)==None:
            self.VALID=False
            return
        # create a random user agent
        if not sessionobj:
            if self.USE_CFSCRAPE:
                self.SESSION = cfscrape.create_scraper()
            else:
                self.SESSION = requests.session()
        else:
            self.SESSION = sessionobj
        if sessionobj and hasattr(sessionobj,'init'):
            'session already exists and has been set up'
        else:
            if not hasattr(self,'HEADERS'):
                self.HEADERS = {}
            if not self.UA:
                self.UA = UserAgent(use_cache_server=False, fallback='Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36')
            self._cycle_UA()
            adapter = requests.adapters.HTTPAdapter(max_retries=1)
            self.SESSION.mount('https://', adapter)
            self.SESSION.mount('http://', adapter)
            
            self.SESSION.keep_alive = False
        self.login()
        series_url = pieces[2].split('/')[2]
        query = self.MANGAROCK_API_DOMAIN.strip('/')+'/query/web{}/info?oid={}&last=0'.format(self.MANGAROCK_QUERY_VERSION,series_url)
        r=self.SESSION.get(query, timeout = REQUEST_TIMEOUT)
        r.raise_for_status()
        # use this very first request to set the referer header (in case of redirect)
        if not hasattr(self.SESSION,'init'):
            try:
                ref = urllib.parse.urlunsplit(urllib.parse.urlsplit(r.history[-1].url)[:2]+('',)*3)
            except IndexError:
                ref = urllib.parse.urlunsplit(urllib.parse.urlsplit(r.url)[:2]+('',)*3)
            try:
                if not 'Referer' in self.HEADERS:
                    self.HEADERS['Referer'] = ref
            except AttributeError:
                self.HEADERS = {'Referer':ref}
            self.SESSION.headers.update(self.HEADERS)
##        self.HTML = r.text
        self.JSON = r.json()
##        self.etree = lxmlhtml.fromstring(self.HTML)
        if self.JSON['code']:
            self.VALID=False
        elif not self.get_title():
            self.VALID=False
        if self.VALID:
            self.SESSION.init = True # only init when valid so we are sure we didn't accidentally set referer to a 404 page or something
    def get_title(self):
        #returns the title of the series
        if self.TITLE:
            return self.TITLE
        title = unescape(self.JSON['data']['name'])
        split = title.split()
        for i in range(len(split)):
            if split[i].isupper() or i==0:
                split[i]=split[i].capitalize()
        ret = r' '.join(split)
        self.TITLE = self.AUTHOR_RE.sub(r'',ret)
        return self.TITLE
    def is_complete(self):
        return self.JSON['data']['completed']
    def get_chapters(self):
        #returns a list of all chapters, where each entry is a tuple (number,url)
        # for mangarock this is (order,oid)
        raw = self.JSON['data']['chapters']
        return [c['order']+1 for c in raw],[(c['order']+1,c['oid']) for c in raw]
    
    def get_images(self,chapter,delay=(0,0),fix_urls = True):
        # chapter here is the mangarock oid
        self.login()
        try:
            if delay==(0,0):
                delay = self.IMAGE_DELAY
        except AttributeError:
            pass
        number,oid = chapter
        query = self.MANGAROCK_API_DOMAIN.strip('/')+'/query/web{}/pages?oid={}'.format(self.MANGAROCK_QUERY_VERSION,oid)
        r= self.SESSION.get(query, timeout = REQUEST_TIMEOUT)
        r.raise_for_status()
        chjs = r.json()
        if not chjs['code']:
            return chjs['data']
        else:
            e = ParserError('Json query failed on %s, chapter:%s'%(self.get_title(),number))
            e.display="Failed querying images for Ch.%s"%number
            raise e
        
    def save_images(self,sname,chapters):
        def decodeMRI(content):
            #content is response.content from requests.get
            #decode logic from: https://github.com/MinusGix/MangarockDownloader
            buflen= len(content)
            n = buflen +7
            
            data = [0]*15
            data[0] = 82# // R
            data[1] = 73# // I
            data[2] = 70# // F
            data[3] = 70# // F
            data[7] = n >> 24 & 255
            data[6] = n >> 16 & 255
            data[5] = n >> 8 & 255
            data[4] = 255 & n
            data[8] = 87# // W
            data[9] = 69# // E
            data[10] = 66# // B
            data[11] = 80# // P
            data[12] = 86# // V
            data[13] = 80# // P
            data[14] = 56# // 8

            decoded = BytesIO()
            decoded.seek(0)
            decoded.write(bytes(data))
            decoded.write(bytes([101 ^ b for b in content]))

            return decoded
        updated_count=0
        unread_count=0
        for ch in chapters:
            try:
            # this is our num,url tuple
                img_dl_errs = 0
                ch=list(ch)
                ch[0]=mangasql.SQLManager.formatName(ch[0])
                if not os.path.exists(os.path.join(sname,ch[0])):
                    tempdir= os.path.join(sname,'#temp')
                    if os.path.exists(tempdir):
                        shutil.rmtree(tempdir, onerror=mangasql.takeown)
                    images = self.get_images(ch) # throws licensedError and maybe ?parsererror?
                    iindex=0
                    os.makedirs(tempdir)
                    for image in images:
                        try: # give the site another chance (maybe)
                            try:
                                response = self.SESSION.get(image, timeout = REQUEST_TIMEOUT, headers={'referer': self.IMAGE_REFERER})
                            except AttributeError:
                                response = self.SESSION.get(image, timeout = REQUEST_TIMEOUT)

                            response.raise_for_status()#raise error code if occured
                            time.sleep(random.uniform(*self.IMAGE_DOWNLOAD_DELAY))
                            
                            filename = os.path.join(tempdir,str(iindex)+os.path.splitext(image)[1])
                            buf = decodeMRI(response.content)
                            img = Image.open(buf)
                            img.save(os.path.splitext(filename)[0]+r'.jpeg') # force conversion to jpeg as mmce doesnt support webp
                            iindex+=1
                        except:
                            if img_dl_errs<ALLOWED_IMAGE_ERRORS_PER_CHAPTER:
                                img_dl_errs+=1
                                pass
                            else:
                                raise
                    shutil.move(tempdir,os.path.join(sname,ch[0]))
                    if os.path.exists(tempdir):
                        shutil.rmtree(tempdir, onerror=mangasql.takeown)
                    updated_count+=1
                    #sleep should be OK in this inner loop, otherwise nothing is downloaded.
                    time.sleep(random.uniform(*CHAPTER_DELAY))
                unread_count+=1
            except Exception as e:
                e.chapter =str(ch[0])
                e.imagenum =str(iindex)
                raise e
        return unread_count,updated_count
################################################################################
class Batoto(SeriesParser):
    def get_images(self,chapter,delay=(0,0)):
        # currently batoto does not require a login when accessing the reader, it is only needed for fetching the chapter list.
        number,url = chapter

        chapter_id = urllib.parse.urlsplit(url)[4]
        url = urllib.parse.urljoin(self.BT_READER_URL,'?id=%s&p=1'%chapter_id)

        html = self.SESSION.get(url, timeout = REQUEST_TIMEOUT).text
        etree = lxmlhtml.fromstring(html)
        # use a set to remove duplicates.
        seen = set()
        seen_add = seen.add
        page_nums = [re.split('[ _]+',a)[-1] for a in etree.xpath(self.BATOTO_PAGES_XPATH) if not (a in seen or seen_add(a))]
        images=[]
        for page_num in page_nums:
            time.sleep(random.uniform(*delay))
            url = urllib.parse.urljoin(self.BT_READER_URL,'?id=%s&p=%i'%(chapter_id,int(page_num)))
            html = self.SESSION.get(url, timeout = REQUEST_TIMEOUT).text
            etree = lxmlhtml.fromstring(html)
            pictureurl = etree.xpath(self.IMAGE_URL_XPATH)
            images.append(pictureurl)
        return images
    
    # we won't override login() here because we dont need it to download images, just to get the chapter list
    # bato.to is a slow site so we want to minimize the number of requests we make 
    def _login(self):
        tries = 0
        max_tries = 2
        e = None
        self.FORM_DATA['ips_username'] = self.USERNAME
        self.FORM_DATA['ips_password']= self.PASSWORD
        # this url is the key to avoiding 403 errors when attempting logins (if already logged in)
        referer_url = '?'.join((self.BT_LOGIN_URL,urllib.parse.urlencode({i:self.QUERY_STRING[i] for i in self.QUERY_STRING if i!='do'})))
        while tries<max_tries:
            # no need to verify login because this method will only be called if NOT already logged in.
            response = self.SESSION.get(referer_url, timeout = REQUEST_TIMEOUT)
            etree = lxmlhtml.fromstring(response.text)
            self.FORM_DATA['auth_key'] = etree.xpath(self.BT_AUTH_KEY_XPATH)
            time.sleep(.25) # small break between requests
            response = self.SESSION.post(self.BT_LOGIN_URL, params=self.QUERY_STRING, data=self.FORM_DATA, headers={'referer': referer_url})
            etree = lxmlhtml.fromstring(response.text)
            if etree.xpath(self.BT_LOGGED_IN_XPATH) and not etree.xpath(self.BT_LOGIN_FAILED_XPATH):
                self.LOGGED_IN = True
                return True
            else:
                e = ParserError('Batoto Login Failed')
                e.display = 'Batoto login failed'
            tries += 1
            time.sleep(2)
        raise e
    
    def __init__(self,url,sessionobj=None):
        self.LOGGED_IN = False
        self.FORM_DATA = {
        'rememberMe': '1',
        'anonymous': '1',}
        self.QUERY_STRING = {
        'app':'core',
        'module':'global',
        'section':'login',
        'do':'process'
        }
        if not sessionobj or not hasattr(sessionobj,'init'):
            self.HEADERS={'Referer':'http://bato.to/reader',
                          'X-Requested-With':'XMLHttpRequest'}
        retval = super().__init__(url,sessionobj)
        if self.VALID:
            if not self.etree.xpath(self.BT_LOGGED_IN_XPATH):
                self._login()
                retval = super().__init__(url,self.SESSION)
            else:
                self.LOGGED_IN = True
        return retval
################################################################################
class SadPanda(SeriesParser):
    EX_DELAY = (2,3)

    AUTO_COMPLETE_TIME = -1

    def get_images(self,chapter,delay=(0,0)):
        imgs = super().get_images(chapter,delay)
        if imgs and imgs[-1].endswith('509.gif'):
            e = ParserError('Bandwidth Exceeded')
            e.display = 'Bandwidth Exceeded'
            raise e
        return imgs
    
    def login(self):
        if [x for x in self.SESSION.cookies if x.name == 'ipb_member_id' and x.domain == '.exhentai.org' and x.expires>time.time()]:
            return True
        self.FORM_DATA = {
            'CookieDate':1,
            'b':'d',
            'bt':'1-1',
            'ipb_login_submit':'Login!'
        }
        self.FORM_DATA['UserName'] = self.USERNAME
        self.FORM_DATA['PassWord'] = self.PASSWORD
        response = self.SESSION.post(self.EX_LOGIN_URL,data = self.FORM_DATA)
        time.sleep(random.uniform(*self.EX_DELAY))
        etree = lxmlhtml.fromstring(response.text)
        if not etree.xpath('//div[@id="redirectwrap"]/h4[text()="Thanks"]'):
            e = ParserError('Ex Login Failed')
            e.display = 'Ex login failed'
            raise e
        panda = self.SESSION.get(self.SITE_URL, timeout = REQUEST_TIMEOUT)
        time.sleep(random.uniform(*self.EX_DELAY))
        if hashlib.md5(panda.content).hexdigest() == self.SAD_PANDA:
            e = ParserError('Ex Login Failed (sadpanda)')
            e.display = 'Ex login failed (sad panda)'
            raise e
        time.sleep(random.uniform(*self.EX_DELAY))
        return True
################################################################################
class KissManga(SeriesParser):
    
    def get_images(self,chapter,delay=(0,0),fix_urls=False):
        # this is the only place (for now) where we use fix_urls = false
        res = super().get_images(chapter,delay,fix_urls)
        try:
            imgs = [self._decrypt_url(url.encode()) for url in res]
        except:
            e = ParserError('Error decoding KissManga image urls on '+self.get_title()+' (%s ch.%s)'%(chapter[1],chapter[0]))
            e.display = 'Error decoding KissManga URLS'
            raise e
        return imgs

    def _decrypt_url(self,encrypted_url):
        # all credit for the logic goes to https://github.com/someonesapien/MangaDownloader
        # this method can raise exceptions easily so make sure to catch them.
        b64d = base64.b64decode(encrypted_url)
        iv=bytes.fromhex('a5e8e2e9c2721be0a84ad660c472c1f3')
        keys=[
            b"mshsdf832nsdbash20asdmnasdbasd612basd",
            b"72nnasdasd9asdn123nasdbasd612basd",
            b"72nnasdasd9asdn123",
            b"034nsdfns72nasdasd",
            b"mshsdf832nsdbash20asdm",
            b"nsfd732nsdnds823nsdf"
            ]
        keys=list(map(lambda x:bytes.fromhex(hashlib.sha256(x).hexdigest()),keys))
        chunk_size=16 # required for CBC, luckily the input is already padded to the correct length
        chunks = [b64d[i:i+chunk_size] for i in range(0, len(b64d), chunk_size)]
        for key_attempt in keys:
            aes = pyaes.AESModeOfOperationCBC(key_attempt, iv = iv)
            try:
                return self.KISSMANGA_PADDING_RE.sub('',''.join([aes.decrypt(chunk).decode('utf8') for chunk in chunks]))
            except:
                pass # only one of the keys will work, just trial and error.
        return None
################################################################################
class MangaHere(SeriesParser):
    def get_images(self,chapter,delay=(0,0),fix_urls = True):
        global beginstr
        beginstr = ''
        #returns links to every image in the chapter where chapter is the url to the first page
        #uses a new approach where we follow links until the end of the chapter
        self.login()
        try:
            if delay==(0,0):
                delay = self.IMAGE_DELAY
        except AttributeError:
            pass
        number,url = chapter

        ## If all image urls are easily parsable from the first page, we can finish up quickly.
        if self.AIO_IMAGES_RE:
            html = self.SESSION.get(url, timeout = REQUEST_TIMEOUT).text
            all_images=re.compile(self.AIO_IMAGES_RE)
            return [c if (c.startswith('http://') or not fix_urls) else urllib.parse.urljoin(self.SITE_URL,c) for c in [c.replace('\\','') for c in all_images.findall(html)]]
        ##
        images=[]
        first_chapter = True # first chapter sometimes has a slightly different url so we will refresh it after the first page.
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        chapter_path = posixpath.dirname(pieces[2])

        while self.IGNORE_BASE_PATH or posixpath.dirname(urllib.parse.urlsplit(url)[2]) == chapter_path:
##            print('reading',url)
            r= self.SESSION.get(url, timeout = REQUEST_TIMEOUT)
            html = r.text
            etree = lxmlhtml.fromstring(html)
            
            time.sleep(random.uniform(*delay))
            
            if self.LICENSED_CHECK_RE!=None and self.LICENSED_CHECK_RE.search(html)!=None:
                e = LicensedError('Series '+self.get_title()+' is licensed.')
                e.display = 'Series is licensed'
                raise e

            ##############################################################
            ###this section is the only part changed from SeriesParser####
            ##############################################################
            cid = re.findall('(?<=var chapterid) ?= ?(\d*)',html)[0]
            imagepage = re.findall('(?<=var imagepage) ?= ?(\d*)',html)[0]

            unpack = jsbeautifier.beautify(re.findall('(eval\(function.*)',html)[0])
            unpack=unpack.replace('\\','')
            b = unpack.split("'+'")
            key = ''.join(b[1:-1])+b[-1][0]

            jsurl= urllib.parse.urljoin(posixpath.dirname(url),'chapterfun.ashx?cid={}&page={}&key={}'.format(cid,imagepage,key))
            r= self.SESSION.get(jsurl, timeout = REQUEST_TIMEOUT)
            
            unpack = jsbeautifier.beautify(r.text)
            a=re.findall('var pix ?= ?"([^"]*)',unpack)[0]
            b=re.findall('var pvalue ?= ?\["([^"]*)',unpack)[0]
            pictureurl = a+b
##            pictureurl = etree.xpath(self.IMAGE_URL_XPATH)
            ##############################################################
            ##############################################################
            ##############################################################
##            print('pix is',pictureurl)
            if not len(pictureurl):
                # this means the image wasnt found. (parser is outdated)
                e = ParserError('Image Parsing failed on %s, chapter:%s'%(self.get_title(),number))
                e.display="Failed parsing images for Ch.%s"%number
                raise e
            # do some small url repairs
            if fix_urls:
                repair = urllib.parse.urlsplit(self.SITE_URL)
                img_url = urllib.parse.urlsplit(pictureurl)
                pictureurl = urllib.parse.urlunsplit([repair[i] if i<2 and not img_url[i] else img_url[i] for i in range(len(img_url))])
            if pictureurl in images: #prevents loops
                break
            images.append(pictureurl)

            try:
                nexturl = etree.xpath(self.NEXT_URL_XPATH)
            except XPathError: # if IGNORE_BASE_PATH is true this is the only way to escape this infinite loop.
                break
            
            newurl = urllib.parse.urljoin(url,nexturl)#join the url to correctly follow relative urls
            if newurl == url: # prevents fetching the same page twice (there is a second failsafe for this via pictureurl)
                break
            url = newurl
            if first_chapter:
                first_chapter = False
                chapter_path = posixpath.dirname(urllib.parse.urlsplit(url)[2])
##            print('next url is',url)
        return images
    def __init__(self,url,sessionobj=None):
        # add this isAdult cookie to bypass the mature check
        if not sessionobj:
            if self.USE_CFSCRAPE:
                sessionobj = cfscrape.create_scraper()
            else:
                sessionobj = requests.session()
        sessionobj.cookies.set('isAdult', '1', domain=urllib.parse.urlparse(self.SITE_URL).netloc, path='/')
##        sessionobj.headers['Upgrade-Insecure-Requests']=1
##        sessionobj.headers['Pragma']='no-cache'
##        sessionobj.headers['Host']='www.mangahere.cc'
##        sessionobj.headers['Accept-Language']='en-US,en;q=0.9'
##        sessionobj.headers['Cache-Control']='no-cache'
##        sessionobj.headers['Accept']='text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3'
##        sessionobj.headers['DNT']=1
##        sessionobj.headers['User-Agent']='Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'
        return super().__init__(url,sessionobj)
    
################################################################################
def update_parsers(currentversion,targethash):
    currentversion=float(currentversion)
    r=requests.get('https://raw.githubusercontent.com/NeverDecaf/MangaTosho/master/parsers.xml', timeout = REQUEST_TIMEOUT)
    with open('parsers.tmp', 'wb') as f:
        f.write(r.content)
    #must reload to file to ensure it was written correctly
    with open('parsers.tmp', 'rb') as f:
        stringdata=f.read()
        temphash = hash_no_newline(stringdata)
    if temphash==targethash:
        #compare version numbers with simultaneously will test for valid xml
        root = ET.fromstring(stringdata)#.getroot()
        newversion = float(root.find('info').find('version').text)
        if currentversion==newversion:
            shutil.copy('parsers.tmp','parsers.xml')
        else:
            return -1
    return 0
