"""Use Selenium/Chrome to search and read the assigned Ars Technica source."""
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import logging
import os
import re
from urllib.parse import quote_plus, urlparse, urlunparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

LOGGER = logging.getLogger(__name__)
NEWS_SOURCE = 'Ars Technica'
FEED_URL = 'https://feeds.arstechnica.com/arstechnica/index'
FEED_URLS = [
    FEED_URL,
    'https://feeds.arstechnica.com/arstechnica/technology-lab',
    'https://feeds.arstechnica.com/arstechnica/gadgets',
    'https://feeds.arstechnica.com/arstechnica/science',
    'https://feeds.arstechnica.com/arstechnica/tech-policy',
]
ARTICLE_PATH = re.compile(r'^/[^/]+/\d{4}/\d{2}/[^/]+/?$')


class SourceError(RuntimeError):
    pass


class ArticleNotFound(SourceError):
    pass


@dataclass(frozen=True)
class Article:
    url: str
    title: str
    text: str
    search_method: str


def clean_html(markup: str) -> str:
    soup = BeautifulSoup(markup, 'html.parser')
    for element in soup.select('script,style,nav,aside,footer,form,.ad,.advertisement'):
        element.decompose()
    paragraphs = [p.get_text(' ', strip=True) for p in soup.select('p')]
    if not paragraphs:
        paragraphs = [soup.get_text(' ', strip=True)]
    result, seen = [], set()
    for paragraph in paragraphs:
        paragraph = re.sub(r'\s+', ' ', paragraph).strip()
        if paragraph and paragraph not in seen and not paragraph.lower().startswith(('read full article', 'read more', 'comments')):
            seen.add(paragraph)
            result.append(paragraph)
    return '\n'.join(result)


def canonical_article(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname not in ('arstechnica.com', 'www.arstechnica.com') or not ARTICLE_PATH.match(parsed.path):
        return None
    return urlunparse(('https', 'arstechnica.com', parsed.path, '', '', ''))


def matches_keyword(article: Article, keyword: str) -> bool:
    terms = re.findall(r'\w+', keyword.casefold())
    haystack = (article.title + ' ' + article.text).casefold()
    return bool(terms) and all(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', haystack) for term in terms)


def create_driver():
    options = Options()
    options.binary_location = os.environ.get('CHROME_BINARY', '/opt/chrome/chrome-linux64/chrome')
    for argument in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--window-size=1365,900'):
        options.add_argument(argument)
    options.page_load_strategy = 'eager'
    options.add_experimental_option('prefs', {'profile.managed_default_content_settings.images': 2})
    driver = webdriver.Chrome(service=Service(os.environ.get('CHROMEDRIVER', '/usr/local/bin/chromedriver')), options=options)
    driver.set_page_load_timeout(20)
    driver.set_script_timeout(20)
    return driver


def blocked(driver) -> bool:
    title = driver.title.lower()
    body = driver.find_element(By.TAG_NAME, 'body').text[:4000].lower()
    return any(text in title + body for text in ('human verification', 'confirm you are human', 'verify you are human', 'access denied', 'just a moment'))


def source_search(driver, keyword: str) -> str | None:
    """Select the first article in the source's normal search results."""
    driver.get('https://arstechnica.com/search/?q=' + quote_plus(keyword))
    if blocked(driver):
        return None

    def first_link(browser):
        for selector in ('.gsc-webResult .gs-title a', '.gsc-result a.gs-title', 'main article h2 a', 'main article h3 a'):
            for element in browser.find_elements(By.CSS_SELECTOR, selector):
                url = canonical_article(element.get_attribute('href') or '')
                if url:
                    return url
        return False

    try:
        return WebDriverWait(driver, 10).until(first_link)
    except TimeoutException:
        return None


def read_article(driver, url: str) -> tuple[str, str]:
    driver.get(url)
    if blocked(driver):
        raise SourceError('The article page requires human verification.')
    WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.CSS_SELECTOR, 'article p, .article-content p, .post-content p'))
    for selector in ('.article-content', '.post-content', '[itemprop="articleBody"]', 'article'):
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            text = clean_html(element.get_attribute('outerHTML'))
            if len(text.split()) >= 30:
                title = driver.find_elements(By.TAG_NAME, 'h1')
                return (title[0].text if title else driver.title), text
    raise SourceError('The article did not contain enough readable text.')


def read_feed(driver) -> list[Article]:
    """Read publicly published RSS through Chrome; no CAPTCHA bypass."""
    driver.get(FEED_URL)
    payloads = driver.execute_async_script('''
        const urls = arguments[0];
        const done = arguments[arguments.length - 1];
        Promise.all(urls.map(url =>
          fetch(url, {signal: AbortSignal.timeout(12000)})
            .then(response => { if (!response.ok) throw new Error('RSS HTTP ' + response.status); return response.text(); })
            .then(text => ({text: text}))
            .catch(error => ({error: String(error)}))
        )).then(done);
    ''', FEED_URLS)
    if not isinstance(payloads, list):
        raise SourceError('The public Ars Technica RSS feeds could not be read.')
    articles = {}
    for payload in payloads:
        if payload.get('error'):
            continue
        try:
            root = ET.fromstring(payload.get('text', ''))
        except ET.ParseError:
            continue
        for item in root.findall('./channel/item'):
            url = canonical_article(item.findtext('link') or '')
            title = item.findtext('title') or ''
            content = item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or item.findtext('description') or ''
            if url and content and url not in articles:
                try:
                    published = parsedate_to_datetime(item.findtext('pubDate') or '').timestamp()
                except (ValueError, TypeError, OverflowError):
                    published = 0
                articles[url] = (published, Article(url, title, clean_html(content), 'public-rss'))
    if not articles:
        raise SourceError('The source did not return any readable public RSS entries.')
    return [article for _, article in sorted(articles.values(), key=lambda entry: entry[0], reverse=True)]


def search_and_read(keyword: str) -> Article:
    driver = None
    try:
        driver = create_driver()
        normal_url = None
        try:
            normal_url = source_search(driver, keyword)
            if normal_url:
                title, text = read_article(driver, normal_url)
                return Article(normal_url, title, text, 'source-search')
        except (WebDriverException, SourceError) as error:
            LOGGER.info('Normal source search unavailable: %s', type(error).__name__)

        articles = read_feed(driver)
        if normal_url:
            matching = [a for a in articles if a.url == normal_url]
            if not matching:
                raise SourceError('The first search result is blocked and is not available in the public RSS feed.')
        else:
            matching = [a for a in articles if matches_keyword(a, keyword)]
        if not matching:
            raise ArticleNotFound('No matching article was found in the currently available public source feed. Native search may require human verification.')
        article = matching[0]
        try:
            title, text = read_article(driver, article.url)
            return Article(article.url, title, text, 'public-rss-search/article-page')
        except (WebDriverException, SourceError):
            if len(article.text.split()) < 20:
                raise SourceError('The available source excerpt is too short to summarize.')
            return article
    except ArticleNotFound:
        raise
    except (WebDriverException, ET.ParseError) as error:
        raise SourceError('Chrome could not retrieve the assigned news source. Try again shortly.') from error
    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                LOGGER.warning('Chrome had already exited during cleanup.')
