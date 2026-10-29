import logging
import threading
import time
from collections import OrderedDict

from flask import Flask, jsonify, make_response, render_template, request
from scraper import ArticleNotFound, NEWS_SOURCE, SourceError, search_and_read
from summarizer import summarize

REGISTRATION = 'SP23-BAI-057'
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
browser_slot = threading.BoundedSemaphore(1)
cache_lock = threading.Lock()
cache = OrderedDict()
CACHE_SECONDS = 600


@app.get('/')
def index():
    return render_template('index.html', registration=REGISTRATION, source=NEWS_SOURCE)


@app.get('/health')
def health():
    return jsonify(status='ok', registration=REGISTRATION, newssource=NEWS_SOURCE)


@app.get('/get')
def get_article():
    keyword = request.args.get('keyword', '').strip()
    if not keyword or len(keyword) > 200 or not any(character.isalnum() for character in keyword) or any(ord(character) < 32 for character in keyword):
        return jsonify(error='Provide a non-empty keyword of at most 200 characters.', registration=REGISTRATION), 400
    cache_key = keyword.casefold()
    with cache_lock:
        cached = cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            payload = dict(cached[1], keyword=keyword)
            response = make_response(jsonify(payload))
            response.headers['X-Search-Method'] = cached[2]
            return response
    if not browser_slot.acquire(blocking=False):
        return jsonify(error='The browser is busy. Retry shortly.', registration=REGISTRATION), 429, {'Retry-After': '10'}
    try:
        article = search_and_read(keyword)
        payload = {'registration': REGISTRATION, 'newssource': NEWS_SOURCE, 'keyword': keyword, 'url': article.url, 'summary': summarize(article.text)}
        with cache_lock:
            cache[cache_key] = (time.monotonic(), payload, article.search_method)
            while len(cache) > 100:
                cache.popitem(last=False)
        response = make_response(jsonify(payload))
        response.headers['X-Search-Method'] = article.search_method
        return response
    except ArticleNotFound as error:
        return jsonify(error=str(error), registration=REGISTRATION, newssource=NEWS_SOURCE, keyword=keyword), 404
    except SourceError as error:
        return jsonify(error=str(error), registration=REGISTRATION, newssource=NEWS_SOURCE, keyword=keyword), 502
    except Exception:
        app.logger.exception('Article processing failed')
        return jsonify(error='The article could not be processed.', registration=REGISTRATION), 500
    finally:
        browser_slot.release()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)
