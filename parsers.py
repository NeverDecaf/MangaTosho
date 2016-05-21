import re
from lxml import html as lxmlhtml
import urlparse
import htmlentitydefs
from StringIO import StringIO
import time
from requests import session
import posixpath
import sys
import os
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
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1].lower()])
            except KeyError:
                pass
        return text # leave as is
    return re.sub(ur"&#?\w+;", fixup, text)

class ParserFetch:
    
    def get_valid_parsers(self):
        return self.parsers

    def get_valid_sites(self):
        v = []
        ret = ''
        for parser in self.get_valid_parsers():
            v.append(parser.SITE+' ('+parser.ABBR+')')
        ret = '<br/>'.join(v)
        if self.get_req_credentials_sites():
            ret+= '<br/><font color="gray">'
            v=[]
            for parser in self.get_req_credentials_sites():
                v.append(parser.SITE+' ('+parser.ABBR+')')
            ret += '<br/>'.join(v) + "</font>"
        return ret

    def get_req_credentials_sites(self):
        return self.req_creds
    
    def __init__(self, credentials = {}):
        self.updateCreds(credentials)
        
    def match(self,url):
        #returns the parser class
        for rex in self.res:
            if rex[0].match(url):
                return rex[1]
        return None
    def fetch(self,url):
        #returns an actual parser object
        for rex in self.res:
            if rex[0].match(url):
                return rex[1](url)
        return None
    def updateCreds(self,credentials):
        self.res=[]
        self.req_creds=[]
        self.parsers = [MangaReader,MangaHere,AnimeA,MangaPanda,DynastyScans,Batoto,MangaPandaNet,MangaPark,MangaTraders]#KissManga, decided to do some stupid js test and their site sucks anyway, MangaFox, banned in the US
        for parser in list(self.parsers):
            if parser.REQUIRES_CREDENTIALS:
                for k in credentials:
                    if parser.__name__==k:
                        if len(credentials[k][0]) and len(credentials[k][1]):
                            parser.USERNAME = credentials[k][0]
                            parser.PASSWORD = credentials[k][1]
                            break
                else:
                    self.parsers.remove(parser)
                    self.req_creds.append(parser)
        for parser in self.parsers:
            self.res.append((parser.SITE_PARSER,parser))
    
class ParserError(Exception):
    pass

class LicensedError(Exception):
    pass

class SeriesParser(object):
    SITE=''#url of the home site.
    SITE_PARSER='' # determines whether the given url matches the site's url
    TITLE_XPATH = ''#xpath to fetch the series title. will be "cleaned" and formatted for uniformity.
    
    ABBR='' # abbreviated version of site's name

    CHAPTER_NUMS_XPATH = '' #hopefully the site has formatted it well, most likely not.
    CHAPTER_NUMS = re.compile(ur'(\d+\.?\d*)(?:v\d+)? *\Z')#match all chapter numbers, replacing this with NAMES won't hurt MUCH but it will cause the GUI to show a name instead of latest ch #
    CHAPTER_URLS_XPATH = ''

    IMAGE_URL_XPATH ='' #parses the image url from a page of the series
    NEXT_URL_XPATH ='' #parses the link to the next page from a page of the series.

    #optional args:

    SKIP_MATURE = '' #url fragment added to skip mature content block (ex: skip=1)

    LICENSED_CHECK = None # checks if series has been licensed

    REQUIRES_CREDENTIALS = False # if login credentials are required to use this site.


    #note these headers are only (currently) used when downloading images.
    HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36'} # old one was not working always, this one should be more up to date.
    REVERSE =True#indicates if the chapters are listed in reverse order, will be true for most sites

    IS_COMPLETE_XPATH = '/is/not/complete/must/override/this' # if this matches, it indicates the series has been marked complete by the site (and should no longer be parsed to save resources)

##    FIRST_CHAPTER = '' #added to url path for the first chapter to make it "equal". for example, mangasite.com/mangas/mango/4/2 is page 2 while mangasite.com/mangas/mango/4 might be page 1. FIRST_CHAPTER = '1' will make it mangasite.com/mangas/mango/4/1

    SESSION=None #

    # these 2 are used for sites with iterative page numbers, we can get a list of all pages of a chapter without jumping from one to the next.
    # this is currently only used for animeA so look there for more details.
    PAGE_TEMPLATE = None # matches a prefix and suffix for the url [0] [1]
    ALL_PAGES = None # matches a list of all page numbers that will be sandwiched between page_template

    AUTHOR = re.compile(ur' \(.*?\)\Z') # matches the author if included in the title, this regex is used to remove the author for cleaner series names
    # note that adding 2 series with the same name but different authors WILL cause a problem. there may or may not be a fix in place but i have yet
    # to encounter this...

    #private vars

    USERNAME = None # will be used if site REQUIRES_CREDENTIALS.
    PASSWORD = None

    VALID=True # is set to false if the given url doesnt match the sites url

    def login(self):
        #log in to the site if authentication is required
        return
    def get_shorthand(self):
        #returns an abbreviated version of hte site's name
        return self.ABBR
    def get_title(self):
        #returns the title of the series
        title = unescape(self.etree.xpath(self.TITLE_XPATH)[0])
        split = title.split()
        for i in range(len(split)):
            if split[i].isupper() or i==0:
                split[i]=split[i].capitalize()
        ret = ur' '.join(split)
        return self.AUTHOR.sub(ur'',ret)
    def is_complete(self):
        return not not self.etree.xpath(self.IS_COMPLETE_XPATH)
    def extrapolate_nums(self, nums):
        #helper function that adds in chapter numbers for chapters without them (assumed to be extras or misc things otherwise you have a real problem here.)
        #check if there are no chapters
        if not len(nums):
            return []
##        if reduce(lambda x,y:x or self.CHAPTER_NUMS.search(y),[0]+nums): # check to make sure at least one chapter has a legitimate number.
        
        # now we just fill in the missing chapters (assumed to be extras, etc.) (use the numbering system .01 .02 .03 to avoid conflict)
        # since this is a messy one liner heres what it does if you come back to look at this later:
        # if CHAPTER_NUMS matches the number, simply use the number it matches, otherwise take the previous number and add .01 then use that instead.
        # finally, map them all with %g to truncate the .0 from whole numbers.
        floatnumbers = reduce(lambda x,y: x+[float(self.CHAPTER_NUMS.findall(y)[-1])] if self.CHAPTER_NUMS.search(y) else x+[(x[-1]*100.0+1.0)/100.0], [[float(self.CHAPTER_NUMS.findall(nums[0])[-1])]]+nums[1:] if self.CHAPTER_NUMS.search(nums[0]) else [[0]]+nums[1:])
        if len(floatnumbers)==1 or floatnumbers[-1] >= 1.0: # if there are no legit numbers then we don't want to return this UNLESS there is only one chapter, then we assume it is a oneshot with no number and allow it.
            return map(lambda x:'{0:g}'.format(x), floatnumbers)
        return []
    def get_chapters(self):
        #returns a list of all chapters, where each entry is a tuple (number,url)
        nums = self.etree.xpath(self.CHAPTER_NUMS_XPATH)
        urls = self.etree.xpath(self.CHAPTER_URLS_XPATH)
        if self.REVERSE:
            nums.reverse()
            urls.reverse()
        nums = self.extrapolate_nums(nums)
        urls = [urlparse.urljoin(self.MAIN_URL,x) for x in urls]

        if len(nums)!=len(urls):
            raise ParserError('Chapter Numbers and URLS do not match in '+self.get_title()+' (%i nums vs %i urls, site:%s)'%(len(nums),len(urls),type(self).__name__))
            return False
        return nums,zip(nums,urls)
    
    def get_images(self,chapter,delay=0):
        self.login()
        #returns links to every image in the chapter where chapter is the url to the first page
        #uses a new approach where we follow links until the end of the chapter
        number,url = chapter
            
        pieces = urlparse.urlsplit(url)
        url = urlparse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])

        images=[]
        pagebase = None

        chapter_path = posixpath.dirname(pieces[2])
        first_chapter = 1 # first chapter sometimes has a slightly different url so we will refresh it after the first page.
        
        while posixpath.dirname(urlparse.urlsplit(url)[2]) == chapter_path:
##            print 'reading',url
            html = self.SESSION.get(url).text

            #we should be able to remove html once we replace everyting with xpath
            etree = lxmlhtml.fromstring(html)
            
            time.sleep(delay)
            
            if pagebase==None and self.PAGE_TEMPLATE!=None:
                pagebase = self.PAGE_TEMPLATE.findall(html)[0]
                page_list = iter(self.ALL_PAGES.findall(html))
                page_list.next() #pop off the first item as it will be accessed already.
                
            if self.LICENSED_CHECK!=None and self.LICENSED_CHECK.match(html)!=None:
                raise LicensedError('Series '+self.get_title()+' is licensed.')
            
##            pictureurl = self.IMAGE_URL.findall(html)[0]
            
            pictureurl = etree.xpath(self.IMAGE_URL_XPATH)
            if not len(pictureurl):
                # this means the image wasnt found. either your parser is outdated or you've reached the end of the chapter.
                if len(images): # just to make sure the parser isnt at fault, only allow if at least one image has been found.
                    break
                else:
                    raise ParserError('Image Parsing failed on %s, chapter:%s'%(self.get_title(),number))
            pictureurl = pictureurl[0]
##            print pictureurl
            if pictureurl in images: #prevents loops
                break
            images.append(pictureurl)

            if self.PAGE_TEMPLATE!=None:
                try:
                    nexturl = page_list.next().join(pagebase)
                except StopIteration:
                    break
            else:
                try:
                    nexturl = etree.xpath(self.NEXT_URL_XPATH)[0]
                except:
                    nexturl = ''
            if not len(nexturl): #prevents loops
                break
            url = urlparse.urljoin(url,nexturl)#join the url to correctly follow relative urls
            if first_chapter:
                first_chapter = 0
                chapter_path = posixpath.dirname(urlparse.urlsplit(url)[2])
##            print 'next url is',url
        return images
    
    def __init__(self,url):
        #loads the html from the series page, also checks to ensure the site is valid
        #note if this returns False you cannot use this object.
        pieces = urlparse.urlsplit(url)
        url = urlparse.urlunsplit(pieces[:3]+(self.SKIP_MATURE or pieces[3],)+pieces[4:])
        self.MAIN_URL = url
        if self.SITE_PARSER.match(url)==None:
            self.VALID=False
            return
        if not self.SESSION:
            self.SESSION = session()
        self.SESSION.headers.update(self.HEADERS)
        self.login()
        self.HTML = self.SESSION.get(url).text
        self.etree = lxmlhtml.fromstring(self.HTML)


################################################################################
################################################################################
################################################################################
################################################################################

### TEMPLATE FOR CREATING A CUSTOM SERIES:
##class [CustomName](SeriesParser):
##  MAKE SURE YOU ADD YOUR NEW PARSER TO THE LIST OF VALID PARSERS OR IT WON'T WORK.
##    SITE = ur'' #url of the homepage, just copy paste.
##    ABBR = ur'' # abbreviated version of site's name, keep it to 2 letters.
        
##    SITE_PARSER = re.compile(ur'') # determines whether the given url matches the site's url, used to enfore correct links so include things like /manga/
##    TITLE_XPATH = "" # Get the title of a series from its main page.

##    CHAPTER_NUMS_XPATH = "" # match all chapter numbers as close as you can, basically just get some text containing them.
##    CHAPTER_URLS_XPATH = "" # match all chapter urls.
        
##    IMAGE_URL_XPATH = "" #parses the image url from a page of the series
##    NEXT_URL_XPATH = "" #parses the link to the next page from a page of the series.

##    IS_COMPLETE_XPATH = "" # matches if the series has been marked complete by the site. omit if the site has no method of doing this.

##    These 2 are optional, you can omit them unless you need to change the defaults.
##    CHAPTER_NUMS = re.compile(ur'') # regex the actual numbers out of the text you get from the xpath, you probably don't actually need this as the default is pretty good.
##    REVERSE = True #indicates if the chapters are listed in reverse order, will be true for most sites


################################################################################
################################################################################
################################################################################
################################################################################
        
class MangaTraders(SeriesParser):
    SITE = ur'http://mangatraders.org'
    ABBR = ur'MT'
    
    SITE_PARSER = re.compile(ur'.*mangatraders.org/read-online/.*')
    TITLE_XPATH = "//link[@rel='alternate']/@title"

    CHAPTER_NUMS_XPATH = "//div[gray]/a/text()" 
    CHAPTER_URLS_XPATH = "//div[gray]/a/@href"

    IS_COMPLETE_XPATH = "//div/text()[preceding-sibling::b[text()='Scanlation Status: '] and starts-with(.,'Completed')]"
##    IS_COMPLETE_XPATH = "//div[b[text()='Scanlation Status: '] and contains(.,'Completed')]"

    # this site has a onepage view so it is extremely ez to get images.
    def get_images(self,chapter):
        number,url = chapter
        url = posixpath.dirname(url)
        html = self.SESSION.get(url).text
        etree = lxmlhtml.fromstring(html)
        IMAGE_XPATH = "//p[@class='imagePage']/img/@src"
        return etree.xpath(IMAGE_XPATH)
    
class MangaHere(SeriesParser):
    SITE = ur'http://www.mangahere.co/'
    ABBR = ur'MH'

    SITE_PARSER=re.compile(ur'.*mangahere.co/manga/.*')
    TITLE_XPATH = "//h1[@class='title']/text()"

    CHAPTER_NUMS_XPATH = "//span[@class='left']/a/text()"
    CHAPTER_URLS_XPATH = "//span[@class='left']/a/@href"

    IS_COMPLETE_XPATH = "//li[label[text()='Status:'] and text()='Completed']"

    NEXT_URL_XPATH = "//a[@onclick='return next_page();']/@href"
    IMAGE_URL_XPATH = "//img[@id='image']/@src"
    
class Batoto(SeriesParser):
    SITE='http://bato.to/'
    ABBR='BT'
    
    SITE_PARSER=re.compile(ur'.*bato.to/comic/_/comics/.*')
##    TITLE_PARSER = re.compile(ur'(?<=ipb.sharelinks.title = ")[^"]*')
    TITLE_XPATH = "//h1[@class='ipsType_pagetitle']/text()" # you may need to revert if you get a ton of whitespace
    
    HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36',
             'Referer':'http://bato.to/reader'}

    CHAPTER_NUMS_XPATH = "//tr[@class='row lang_English chapter_row']/td/a[img]/text()"
    CHAPTER_NUMS = re.compile('Ch\.(\d+\.?\d*)')
    CHAPTER_URLS_XPATH = "//tr[@class='row lang_English chapter_row']/td/a[img]/@href"

    IS_COMPLETE_XPATH = "//tr[td[text()='Status:']]/td[text()='Complete']"

    REQUIRES_CREDENTIALS = True
    
    # =======EVERYTHING BELOW HERE IS BATOTO SPECIFIC DUE TO LOGIN REQUIREMENT=========

    # These 3 are used for sites where all *image* (not page) urls can be obtained from the first page. actually this is only for batoto.
    IMAGE_BASE = re.compile(ur'<img src=[\'"](http://img.bato.to/comics/\d\d[^\'"]*?)(\d+)(\.[^\'"]{3,4})') # 3 parts, prefix, iterative number, and suffix (extension) [0] [1] [2]
    IMAGE_LAST = re.compile(ur'page (\d*)</option>\s*</select>') # the number of the final page/image in the chapter.
    IMAGE_FIRST = 1 # the first image is numbered 1, this will probably be true for every site but we'll leave the option to change it here.
    IMAGE_FIXED_LENGTH = True # if true the image number will be padded with 0s to be the same as the first page (ex: 00001 00010 00015)
    
    JS_TEMPLATE = 'http://bato.to/areader?p=1&id='

    def get_images(self,chapter,delay=0):
        self.login()
        number,url = chapter

        fragment = urlparse.urlsplit(url)[4]
        url = self.JS_TEMPLATE+fragment        

        html = self.SESSION.get(url).text
        pre,num,suf = self.IMAGE_BASE.findall(html)[0]
        return [str(i).zfill(len(num) if self.IMAGE_FIXED_LENGTH else 0).join((pre,suf)) for i in range(self.IMAGE_FIRST, int(next(iter(self.IMAGE_LAST.findall(html)),1)) + 1)] # this iter hack is like list.get(0,'fail')
    
    AUTH_KEY_XPATH = "//input[@name='auth_key']/@value"
    LOGGED_IN_XPATH = "//a[text()='Sign Out']"
    
    QUERY_STRING = {
        'app':'core',
        'module':'global',
        'section':'login',
        'do':'process'
        }
    
    FORM_DATA = {
        'rememberMe': u'1',
        'anonymous': u'1',
        'referer': u'https://bato.to/forums',
        }
    
    def login(self):
        self.FORM_DATA['ips_username'] = self.USERNAME
        self.FORM_DATA['ips_password']= self.PASSWORD
        response = self.SESSION.get(ur'https://bato.to/forums/')
        etree = lxmlhtml.fromstring(response.text)
        if etree.xpath(self.LOGGED_IN_XPATH):
            return
        self.FORM_DATA['auth_key'] = etree.xpath(self.AUTH_KEY_XPATH)[0]
        response = self.SESSION.post('https://bato.to/forums/index.php', params=self.QUERY_STRING, data=self.FORM_DATA)
        if response.text.find(self.USERNAME)<0:
            raise ParserError('Batoto Login Failed')
        
class DynastyScans(SeriesParser):
    SITE='http://dynasty-scans.com/'
    ABBR='DS'

    CHAPTER_NUMS = re.compile(ur'Chapter (\d+\.?\d*)(?:v\d+)?')# chapters are named "Chapter 2: chapter title", sometimes specials have no number but that shouldn't be an issue. actually it is an issue as some have no numbers at all. currently those series just won't work.
    
    SITE_PARSER=re.compile(ur'.*dynasty-scans.com/series/.*')
    TITLE_XPATH = "//b/text()"
    
    CHAPTER_NUMS_XPATH = "//a[@class='name']/text()"
    CHAPTER_URLS_XPATH = "//a[@class='name']/@href"

    IS_COMPLETE_XPATH = "//small[contains(text(),'Completed')]"

    REVERSE=False
    
    def get_images(self,chapter):
        number,url = chapter
        html = self.SESSION.get(url).text
        all_images=re.compile(ur'(?<="image":")[^"]*')
        return [urlparse.urljoin(self.SITE,c) for c in all_images.findall(html)]
    
class AnimeA(SeriesParser):
    SITE = ur'http://manga.animea.net/'
    ABBR = ur'AA'

    SITE_PARSER=re.compile(ur'.*manga.animea.net/.*')
    TITLE_XPATH = "//h1[@class='mp_title']/text()"

    CHAPTER_NUMS_XPATH = "//li[span[@class='float-right date']]/a/text()"
    CHAPTER_URLS_XPATH = "//li[span[@class='float-right date']]/a/@href"

    IS_COMPLETE_XPATH = "//li[text()='Status:']/strong[text()='Completed']"
    
    IMAGE_URL_XPATH = "//img[@id='scanmr']/@src"

    SKIP_MATURE = 'skip=1'

    ALL_PAGES = re.compile(ur'(?<=<option value=")\d*(?=")')
    PAGE_TEMPLATE = re.compile(ur'''(?<=onchange="javascript:window.location=')([^']*)(?:'[^']*')([^']*)''')
    
class MangaReader(SeriesParser):
    SITE = ur'http://www.mangareader.net/'
    ABBR = ur'MR'

    SITE_PARSER=re.compile(ur'.*mangareader.net/.*')
    TITLE_XPATH = "//h2[@class='aname']/text()"
    
    CHAPTER_NUMS_XPATH = "//td[div[@class='chico_manga']]/a/text()"
    CHAPTER_URLS_XPATH = "//td[div[@class='chico_manga']]/a/@href"
    
    IS_COMPLETE_XPATH = "//tr[td[text()='Status:']]/td[text()='Completed']"
    
    NEXT_URL_XPATH = "//span[@class='next']/a/@href"
    IMAGE_URL_XPATH = "//img[@id='img']/@src"

    REVERSE=False
    
class MangaPanda(MangaReader):
    #mangapanda is pretty much an exact copy of mangareader
    SITE = ur'http://www.mangapanda.com/'
    ABBR = ur'MP'

    SITE_PARSER=re.compile(ur'.*mangapanda.com/.*')
    
class MangaPark(SeriesParser):
    SITE=ur'http://mangapark.me/'
    ABBR='PA'
    
    SITE_PARSER=re.compile(ur'.*mangapark.me/manga/.*')
    TITLE_XPATH = "//div[@class='cover']/img/@title"
    
    #for some reason mangapark has multiple "versions" of a series which means tons of dupe chapters
    #to workaround we simply look only at the "default" version (the one that starts expanded)
    #to find that just look for div[@class='stream'] the others are all stream-collapsed or something
    CHAPTER_NUMS_XPATH = "//div[@class='stream']//span/a/text()"
    CHAPTER_URLS_XPATH = "//div[@class='stream']//span/a/@href"

    IS_COMPLETE_XPATH = "//tr[th[text()='Status']]/td[contains(text(),'Completed')]"

    IMAGE_URL_XPATH = "//a[@class='img-num']/@href"
    NEXT_URL_XPATH = "//div[@class='page']/span[last()]/a/@href"

#############################################
########### BROKEN PARSERS/SITES ############
#############################################

# taken over by russian hackers
class MangaPandaNet(SeriesParser):
    #mangapanda is pretty much an exact copy of mangareader
    SITE = ur'http://www.mangapanda.net/'
    ABBR = ur'MPN'

    SITE_PARSER=re.compile(ur'.*mangapanda.net/.*')
    TITLE_PARSER = re.compile(ur'(?<=<span itemprop="itemreviewed">).*?(?=</span>)')

    
    
    CHAPTER_NUMS = re.compile(ur'(\d+\.?\d*)</a>[^<]*?(?=<span)')
    CHAPTER_URLS = re.compile(ur'<a href="([^"]*)">[^<]*?\d+\.?\d*</a>[^<]*?(?=<span)')
    
    NEXT_URL = re.compile(ur'[^"]*(?=" class="nxt")')
    IMAGE_URL = re.compile(ur'(?<=<img id="img_mng_enl" src=")[^"]*')

     # I don't think this applies to the .net version
##    def get_images(self,chapter):
##        if re.match(ur'.*\.com/.*/.*/.*',chapter[1])!=None: # matched the format mangareader.net/103-2402-2/one-piece/chapter-295.html
##            self.CHAPTER_BASE = re.compile(ur'(.*\.com/[^/]*)-')
##        else: # otherwise matches the format mangareader.net/one-piece/295
##            self.CHAPTER_BASE = re.compile(ur'.*')
##        return SeriesParser.get_images(self,chapter)
     
# BANNED IN THE US
class MangaFox(SeriesParser):
    SITE = ur'http://mangafox.me/'
    ABBR=ur'MF'
    SITE_PARSER=re.compile(ur'.*mangafox.me/manga/.*')
    TITLE_PARSER = re.compile(ur'(?<=<title>).*?(?= Manga - Read)')

    CHAPTER_NUMS = re.compile(ur' (\d+\.?\d*)</a>.?\n')
    CHAPTER_URLS = re.compile(ur'(?<=<a href=")([^"]*)"[^>]*class="tips">')

    IMAGE_URL = re.compile(ur'(?<=onclick="return enlarge\(\)"><img src=")([^"]*)')
    NEXT_URL=re.compile(ur'(?<=a href=")([^"]*)" onclick="return enlarge\(\)"><img src="')

    LICENSED_CHECK = re.compile(ur'.*Sorry, its licensed, and not available\..*',re.DOTALL)

    SKIP_MATURE = '?no_warning=1'

# Did some stupid js stuff and site sucks too much to be worth circumventing it.
# well, maybe one day as it does tend to have some series you cant find anywhere else.
class KissManga(SeriesParser):
    SITE='http://kissmanga.com/'#url of the home site.
    ABBR='KS' # abbreviated version of site's name
    
    SITE_PARSER=re.compile(ur'.*kissmanga.com/manga/.*', re.IGNORECASE) # determines whether the given url matches the site's url
    TITLE_PARSER = re.compile(ur'<a Class="bigChar" href="[^"]*">(.*?)</a>')#parses the name of a series from the given url

##    TITLE_XPATH = "//a[@class='bigChar']/text()"
    

    #unique system for kissmanga, also very unstable.
    CHAPTER_NUMS = re.compile(ur'(?<!v|\d)(\d+\.?\d*)')#match all chapter numbers
    CHAPTER_TITLE = re.compile(ur'<tr>\s*<td>\s*<a\s*href="[^"]*"\s*title="([^"]*)')
    
    CHAPTER_URLS = re.compile(ur'<tr>\s*<td>\s*<a\s*href="([^"]*)')#match all chapter urls
    
    IMAGE_URL=re.compile(ur'lstImages\.push\("([^"]*)') #parses the image url from a page of the series

    SKIP_MATURE = 'confirm=yes'
    def get_images(self,chapter):
        # kissmanga uses js to load all the images.
        # we can quickly just parse all the urls from the js.
        number,url = chapter
        url=urlparse.urljoin(url,self.SKIP_MATURE)
        html = self.SESSION.get(url).text
        return self.IMAGE_URL.findall(html)
    def get_chapter_nums(self,html):
        # need to customize this since the naming scheme is all over the place
        titles = self.CHAPTER_TITLE.findall(html)
        urls = []
        for title in titles:
            urls.append(self.CHAPTER_NUMS.findall(unescape(title))[-1])
        return urls
