import re
from lxml import html as lxmlhtml
import xml.etree.ElementTree as ET
import hashlib
import urllib.parse
import html.entities
from io import StringIO
import time
from requests import session
import requests
import posixpath
import sys
import os,shutil
from fake_useragent import UserAgent
import urllib.request, urllib.parse, urllib.error
##import lxml.etree.XPathEvalError as XPathError
from lxml.etree import XPathEvalError as XPathError
from functools import reduce
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
    os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(basedir , 'requests', 'cacert.pem')

# need to set working directory for this to work with pyinstaller:
try:
    sys._MEIPASS
    os.chdir(os.path.dirname(sys.argv[0]))
except:
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

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
PARSER_VERSION = 1.4 # update if this file changes in a way that is incompatible with older parsers.xml

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
            self.matchers.append((parser.SITE_PARSER_RE,parser,session()))
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
            r=requests.get('https://raw.githubusercontent.com/NeverDecaf/MangaTosho/master/parsers.md5')
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
        for site in root.iter('site'):
            classname = site.attrib['name']
            # remove None values and convert string booleans to booleans.
            # also create regex object for any key ending with _re
            data={k.upper(): {'True':True,'False':False}.get(v,re.compile(v,re.IGNORECASE) if k=='site_parser_re' else re.compile(v,re.IGNORECASE) if k.endswith('_re') else v) for k, v in list(children_as_dict(site).items()) if v!=None}
            if classname!='TemplateSite':
                if classname=='Batoto':
                    WORKING_SITES.append(type(classname,(BatotoBase,),data))
                else:
                    WORKING_SITES.append(type(classname,(SeriesParser,),data))
                
class ParserError(Exception):
    pass

class LicensedError(Exception):
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
    # these 2 are used for sites with iterative page numbers, we can get a list of all pages of a chapter without jumping from one to the next.
    # this is currently only used for animeA so look there for more details.
    PAGE_TEMPLATE_RE = None # matches a prefix and suffix for the url [0] [1]
    ALL_PAGES_RE = None # matches a list of all page numbers that will be sandwiched between page_template

    # will be used if site REQUIRES_CREDENTIALS, use class vars so we can set before creating an instance.
    USERNAME = None 
    PASSWORD = None

    def __init__(self,url,sessionobj=None):
        #loads the html from the series page, also checks to ensure the site is valid
        #note if this returns False you cannot use this object.
        self.VALID=True # is set to false if the given url doesnt match the sites url
        self.UA = None
        self.TITLE = None
        # create a random user agent
        if not self.UA:
            self.UA = UserAgent(fallback='Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36')
        self._cycle_UA()
        try:
            if not 'Referer' in self.HEADERS:
                self.HEADERS['Referer'] = self.SITE_URL
        except NameError:
            self.HEADERS = {}
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        self.MAIN_URL = url
        if self.SITE_PARSER_RE.match(url)==None:
            self.VALID=False
            return
        if not sessionobj:
            self.SESSION = session()
        else:
            self.SESSION = sessionobj
        adapter = requests.adapters.HTTPAdapter(max_retries=1)
        self.SESSION.mount('https://', adapter)
        self.SESSION.mount('http://', adapter)
        
        self.SESSION.keep_alive = False
        self.SESSION.headers.update(self.HEADERS)
        self.login()
        self.HTML = self.SESSION.get(url).text
        self.etree = lxmlhtml.fromstring(self.HTML)
        if not self.get_title():
            self.VALID=False
    def _cycle_UA(self):
        self.HEADERS['User-Agent'] = self.UA.random
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
    
    def get_images(self,chapter,delay=0):
        self.login()
        #returns links to every image in the chapter where chapter is the url to the first page
        #uses a new approach where we follow links until the end of the chapter
        number,url = chapter

        #special EZ cases:
        if self.AIO_IMAGES_RE:
            html = self.SESSION.get(url).text
            all_images=re.compile(self.AIO_IMAGES_RE)
            return [c if c.startswith('http://') else urllib.parse.urljoin(self.SITE_URL,c) for c in [c.replace('\\','') for c in all_images.findall(html)]]
        
        pieces = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])

        images=[]
        pagebase = None

        chapter_path = posixpath.dirname(pieces[2])
        first_chapter = 1 # first chapter sometimes has a slightly different url so we will refresh it after the first page.
        
        while posixpath.dirname(urllib.parse.urlsplit(url)[2]) == chapter_path:
##            print 'reading',url
            html = self.SESSION.get(url).text

            #we should be able to remove html once we replace everyting with xpath
            etree = lxmlhtml.fromstring(html)
            
            time.sleep(delay)
            
            if pagebase==None and self.PAGE_TEMPLATE_RE!=None:
                pagebase = self.PAGE_TEMPLATE_RE.findall(html)[0]
                page_list = iter(self.ALL_PAGES_RE.findall(html))
                next(page_list) #pop off the first item as it will be accessed already.
                
            if self.LICENSED_CHECK_RE!=None and self.LICENSED_CHECK_RE.match(html)!=None:
                e = LicensedError('Series '+self.get_title()+' is licensed.')
                e.display = 'Series is licensed'
                raise e
            
##            pictureurl = self.IMAGE_URL.findall(html)[0]
            
            pictureurl = etree.xpath(self.IMAGE_URL_XPATH)
##            print 'pix is',pictureurl
            if not len(pictureurl):
                # this means the image wasnt found. either your parser is outdated or you've reached the end of the chapter.
                if len(images): # just to make sure the parser isnt at fault, only allow if at least one image has been found.
                    break
                else:
                    e = ParserError('Image Parsing failed on %s, chapter:%s'%(self.get_title(),number))
                    e.display="Failed parsing images for Ch.%s"%number
                    raise e
            if pictureurl in images: #prevents loops
                break
            images.append(pictureurl)

            if self.PAGE_TEMPLATE_RE!=None:
                try:
                    nexturl = page_list.next().join(pagebase)
                except StopIteration:
                    break
            else:
                try:
                    nexturl = etree.xpath(self.NEXT_URL_XPATH)
                except XPathError:
                    nexturl = ''
            if not len(nexturl): #prevents loops
                break
            url = urllib.parse.urljoin(url,nexturl)#join the url to correctly follow relative urls
            if first_chapter:
                first_chapter = 0
                chapter_path = posixpath.dirname(urllib.parse.urlsplit(url)[2])
##            print 'next url is',url
        return images


################################################################################
class BatotoBase(SeriesParser):
    # =======EVERYTHING BELOW HERE IS BATOTO SPECIFIC DUE TO LOGIN REQUIREMENT=========

    # These 3 are used for sites where all *image* (not page) urls can be obtained from the first page. actually this is only for batoto.
##    IMAGE_BASE = re.compile(ur'<img src=[\'"](http://img.bato.to/comics/\d\d[^\'"]*?)(\d+)(\.[^\'"]{3,4})') # 3 parts, prefix, iterative number, and suffix (extension) [0] [1] [2]
##    IMAGE_LAST = re.compile(ur'page (\d*)</option>\s*</select>') # the number of the final page/image in the chapter.
##    IMAGE_FIRST = 1 # the first image is numbered 1, this will probably be true for every site but we'll leave the option to change it here.
##    IMAGE_FIXED_LENGTH = True # if true the image number will be padded with 0s to be the same as the first page (ex: 00001 00010 00015)

##    JS_TEMPLATE = 'http://bato.to/areader?p=1&id='
    READER_URL = 'http://bato.to/areader'

    LOGGED_IN = False

    def get_images(self,chapter,delay=0):
        # currently batoto does not require a login when accessing the reader, it is only needed for fetching the chapter list.
##        self.login()
        number,url = chapter

        chapter_id = urllib.parse.urlsplit(url)[4]
        url = urllib.parse.urljoin(self.READER_URL,'?id=%s&p=1'%chapter_id)

        html = self.SESSION.get(url).text
        etree = lxmlhtml.fromstring(html)
        # use a set to remove duplicates.
        seen = set()
        seen_add = seen.add
        page_nums = [re.split('[ _]+',a)[-1] for a in etree.xpath(self.BATOTO_PAGES_XPATH) if not (a in seen or seen_add(a))]
        images=[]
        for page_num in page_nums:
            time.sleep(delay)
            url = urllib.parse.urljoin(self.READER_URL,'?id=%s&p=%i'%(chapter_id,int(page_num)))
            html = self.SESSION.get(url).text
            etree = lxmlhtml.fromstring(html)
            pictureurl = etree.xpath(self.IMAGE_URL_XPATH)
            images.append(pictureurl)
        return images

    QUERY_STRING = {
        'app':'core',
        'module':'global',
        'section':'login',
        'do':'process'
        }
    
    FORM_DATA = {
        'rememberMe': '1',
        'anonymous': '1',
        # do NOT add this referer field or you will get a 403. add it to headers instead.
##        'referer': u'https://bato.to/forums',
##        'referer': u'https://bato.to/forums/index.php?app=core&module=global&section=login',
        }

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
            response = self.SESSION.get(referer_url)
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
        self.HEADERS={'Referer':'http://bato.to/reader',
                      'X-Requested-With':'XMLHttpRequest'}
        retval = super().__init__(url,sessionobj)
        if self.VALID and not self.etree.xpath(self.BT_LOGGED_IN_XPATH):
            self._login()
            retval = super().__init__(url,self.SESSION)
        return retval

############################################
######## Dynamically create classes ########
############################################
def children_as_dict(t):
    d={}
    for v in list(t):
        d[v.tag]=v.text
    return d

def update_parsers(currentversion,targethash):
    currentversion=float(currentversion)
    r=requests.get('https://raw.githubusercontent.com/NeverDecaf/MangaTosho/master/parsers.xml')
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

