
from selenium.webdriver.firefox.options import Options as ffoptions
from selenium.webdriver.chrome.options import Options as croptions
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
from time import sleep
import http.cookiejar
import requests
from collections import OrderedDict
from requests.compat import urlparse, urlunparse
import re
import copy
from cloudscraper import CloudScraper
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context, DEFAULT_CIPHERS
# from cloudscraper.exceptions import CloudflareChallengeError
def set_cookies(cookies, s):
    for cookie in cookies:
        if 'httpOnly' in cookie:
            httpO = cookie.pop('httpOnly')
            cookie['rest'] = {'httpOnly': httpO}
        if 'expiry' in cookie:
            cookie['expires'] = cookie.pop('expiry')
        if 'sameSite' in cookie:
            cookie.pop('sameSite')
        s.cookies.set(**cookie)
    return s

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
DEFAULT_HEADERS = OrderedDict(
    (
        ("Host", None),
        ("Connection", "keep-alive"),
        ("Upgrade-Insecure-Requests", "1"),
        ("User-Agent", DEFAULT_USER_AGENT),
        (
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        ),
        ("Accept-Language", "en-US,en;q=0.9"),
        ("Accept-Encoding", "gzip, deflate"),
    )
)
DEFAULT_CIPHERS += ":!ECDHE+SHA:!AES128-SHA:!AESCCM:!DHE:!ARIA"
class CloudflareAdapter(HTTPAdapter):
    """ HTTPS adapter that creates a SSL context with custom ciphers """

    def get_connection(self, *args, **kwargs):
        conn = super(CloudflareAdapter, self).get_connection(*args, **kwargs)

        if conn.conn_kw.get("ssl_context"):
            conn.conn_kw["ssl_context"].set_ciphers(DEFAULT_CIPHERS)
        else:
            context = create_urllib3_context(ciphers=DEFAULT_CIPHERS)
            conn.conn_kw["ssl_context"] = context

        return conn
class CloudflareBypass(CloudScraper):
    def __init__(self, *args, **kwargs):
        self.delay = kwargs.pop("delay", None)
        # Use headers with a random User-Agent if no custom headers have been set
        headers = OrderedDict(kwargs.pop("headers", DEFAULT_HEADERS))

        # Set the User-Agent header if it was not provided
        headers.setdefault("User-Agent", DEFAULT_USER_AGENT)

        super(CloudflareBypass, self).__init__(*args, **kwargs)

        # Define headers to force using an OrderedDict and preserve header order
        self.headers = headers
        self.challenge_solved = False

        self.mount("https://", CloudflareAdapter())
    @staticmethod
    def is_cloudflare_iuam_challenge(resp):
        return (
            resp.status_code in (503, 429)
            and resp.headers.get("Server", "").startswith("cloudflare")
            and b"jschl_vc" in resp.content
            and b"jschl_answer" in resp.content
        )

    @staticmethod
    def is_cloudflare_captcha_challenge(resp):
        return (
            resp.status_code == 403
            and resp.headers.get("Server", "").startswith("cloudflare")
            and b"/cdn-cgi/l/chk_captcha" in resp.content
        )

    def request(self, method, url, *args, **kwargs):
        try:
            resp = super(CloudflareBypass, self).request(method, url, *args, **kwargs)
        except:#CloudflareChallengeError:
            resp = super(CloudScraper, self).request(method, url, *args, **kwargs)
        
        # Check if Cloudflare captcha challenge is presented
        if self.is_cloudflare_captcha_challenge(resp):
            raise Exception('Cloudflare Captcha Detected')

        # Check if Cloudflare anti-bot "I'm Under Attack Mode" is enabled
        if self.is_cloudflare_iuam_challenge(resp):
            'challenge detected, solving via selenium'
            resp = self._selenium_bypass(resp, **kwargs)
            
        return resp
    
    def _selenium_bypass(self,resp, **original_kwargs):
        browser = None
        for cls,opt in ((webdriver.Chrome, croptions), (webdriver.Firefox, ffoptions)):
            try:
                options = opt()
                options.headless = True
                browser = cls(options=options)
            except WebDriverException:
                pass
        if not browser:
            raise Exception('Selenium Driver Missing')
        browser.get(resp.url)
        for i in range(10):
            sleep(1)
            a = browser.get_cookies()
            if 'cf_clearance' in [c['name'] for c in a]:
                break
        sleep(1)
        useragent = browser.execute_script("return navigator.userAgent")
        self.headers["User-Agent"] = useragent
        browser.quit()
        set_cookies(a,self)

        body = resp.text
        parsed_url = urlparse(resp.url)
        domain = parsed_url.netloc
        challenge_form = re.search(r'\<form.*?id=\"challenge-form\".*?\/form\>',body, flags=re.S).group(0) # find challenge form
        # method = re.search(r'method=\"(.*?)\"', challenge_form, flags=re.S).group(1)
        self.org_method = resp.request.method
        submit_url = "%s://%s%s" % (parsed_url.scheme,
                                     domain,
                                    re.search(r'action=\"(.*?)\"', challenge_form, flags=re.S).group(1).split('?')[0])
        cloudflare_kwargs = copy.deepcopy(original_kwargs)
        
        self.challenge_solved = True
        resp = super(CloudflareBypass, self).request(self.org_method, submit_url, **cloudflare_kwargs)
        if self.is_cloudflare_captcha_challenge(resp):
            raise Exception('Failed to solve Cloudflare Challenge')
        return resp
# url = 'https://kissmanga.com/Message/PrivacyPolicy'
# s = CloudflareBypass()
# r= s.get(url)
# print(r.text)