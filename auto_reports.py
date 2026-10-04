"""Safe best-effort discovery of annual report PDFs on identified corporate hosts.

Discovery suggestions are NOT authenticated filings and don't imply source financial
figures have been audited or reconciled to Yahoo Finance.
"""
import re
from urllib.parse import urlparse, urljoin, parse_qs, unquote
from html.parser import HTMLParser

import requests

HEADERS={'User-Agent':'FinSight-AI research prototype/1.0 (public annual reports)'}
MAX_BYTES=30*1024*1024
# Known official investor-relations entry points. Other tickers use the website supplied
# by Yahoo metadata and the search engine; a user must verify returned source.
OFFICIAL = {
 'INFY.NS': ('infosys.com','https://www.infosys.com/investors/reports-filings/annual-report/annual-reports.html'),
 'TCS.NS': ('tcs.com','https://www.tcs.com/investor-relations'),
 'RELIANCE.NS': ('ril.com','https://www.ril.com/investors/financial-reporting/annual-reports'),
 'MSFT': ('microsoft.com','https://www.microsoft.com/en-us/Investor/annual-reports.aspx'),
 'AAPL': ('apple.com','https://investor.apple.com/sec-filings/default.aspx'),
}

def host_ok(url, domain):
    p=urlparse(url)
    return p.scheme=='https' and p.hostname is not None and (p.hostname==domain or p.hostname.endswith('.'+domain)) and p.username is None and p.password is None and p.port in (None,443)

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.link=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.link={'href':dict(attrs).get('href',''),'text':''}
    def handle_data(self,data):
        if self.link is not None:self.link['text']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.link is not None:
            self.links.append(self.link);self.link=None

def landing(ticker):
    t=ticker.strip().upper()
    if t in OFFICIAL:return OFFICIAL[t]
    import yfinance as yf
    website=yf.Ticker(t).info.get('website','')
    p=urlparse(website)
    host=(p.hostname or '').lower()
    if not host or not re.fullmatch(r'[a-z0-9.-]+',host):
        raise ValueError('No corporate website in Yahoo Finance metadata. Upload a filing manually.')
    if host.startswith('www.'):host=host[4:]
    # Block private/local hosts even if Yahoo metadata is compromised.
    if host=='localhost' or host.endswith(('.local','.internal')) or '.' not in host:
        raise ValueError('Untrusted company website host.')
    return host,'https://'+host+'/'

def discover(ticker, year=None, timeout=9):
    domain,root=landing(ticker)
    options=[]
    def add(url,description,source):
        if host_ok(url,domain) and url not in {x['url'] for x in options}:
            options.append({'url':url,'label':description[:140],'host':domain,'discovered_from':source,
                            'is_pdf':urlparse(url).path.lower().endswith('.pdf')})
    if ticker.upper()=='INFY.NS' and year==2026:
        add('https://www.infosys.com/investors/reports-filings/annual-report/annual/documents/infosys-ar-26.pdf','Infosys Integrated Annual Report FY2026','Known corporate URL')
    add(root,'Official investor-relations starting page' if ticker.upper() in OFFICIAL else 'Yahoo Finance corporate website','Corporate website')
    # First inspect official investor-relations entry page for PDF links.
    try:
        if host_ok(root,domain):
            res=requests.get(root,headers=HEADERS,timeout=timeout,allow_redirects=False)
            if res.status_code==200 and 'html' in res.headers.get('Content-Type','').lower() and len(res.content)<3_000_000:
                parser=Links();parser.feed(res.text)
                for link in parser.links:
                    href=urljoin(root,link['href']);label=link['text'].strip()
                    if host_ok(href,domain) and ('annual' in (href+' '+label).lower() or href.lower().endswith('.pdf')):
                        add(href,label or href.rsplit('/',1)[-1],root)
    except (requests.RequestException,ValueError):pass
    # Third-party search result is a discovery hint, NEVER authority by itself.
    query=f'site:{domain} {year or "latest"} annual report filetype:pdf'
    try:
        from bs4 import BeautifulSoup
        resp=requests.get('https://www.google.com/search',params={'q':query,'num':8},headers={'User-Agent':'Mozilla/5.0'},timeout=timeout)
        if resp.ok:
            soup=BeautifulSoup(resp.text,'html.parser')
            for anchor in soup.find_all('a',href=True):
                u=anchor['href']
                if u.startswith('/url?'):u=parse_qs(urlparse(u).query).get('q',[''])[0]
                if host_ok(u,domain) and ('.pdf' in urlparse(u).path.lower()):
                    add(u,anchor.get_text(' ',strip=True) or 'Annual report PDF','Search engine discovery; verify year')
    except (requests.RequestException,ImportError,ValueError):pass
    pdfs=[x for x in options if x['is_pdf']]
    others=[x for x in options if not x['is_pdf']]
    return pdfs[:12]+others[:5]

def fetch_official_pdf(url, corporate_domain, timeout=18):
    """Downloads PDF from a corporate domain, no redirects. Excludes local/private resolution."""
    from ipaddress import ip_address
    import socket
    if not host_ok(url,corporate_domain):raise ValueError('Report URL is not on the selected corporate domain.')
    host=urlparse(url).hostname
    addresses={row[4][0] for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)}
    if not addresses or any(not ip_address(x).is_global for x in addresses):
        raise ValueError('Report host did not resolve to a public address.')
    with requests.get(url,headers=HEADERS,stream=True,timeout=timeout,allow_redirects=False) as res:
        res.raise_for_status()
        if 300<=res.status_code<400:raise ValueError('Redirect blocked; use a direct HTTPS corporate PDF URL.')
        size=int(res.headers.get('Content-Length') or 0)
        if size>MAX_BYTES:raise ValueError('Report exceeds 30 MB.')
        content=bytearray()
        for block in res.iter_content(131072):
            content.extend(block)
            if len(content)>MAX_BYTES:raise ValueError('Report exceeds 30 MB.')
    if not content.startswith(b'%PDF-'):raise ValueError('Selected link did not return a PDF. Open the investor-relations page and select a PDF link.')
    return bytes(content)
