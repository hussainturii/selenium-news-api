"""Run against an already running container; test the real Selenium path."""
import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from urllib.parse import quote

parser = argparse.ArgumentParser()
parser.add_argument('--base-url', default='http://localhost:7000')
parser.add_argument('--keyword', default='space')
parser.add_argument('--output')
args = parser.parse_args()
start = time.monotonic()
with urlopen(args.base_url + '/health', timeout=10) as response:
    assert json.load(response)['registration'] == 'SP23-BAI-057'
with urlopen(args.base_url + '/', timeout=10) as response:
    assert 'SP23-BAI-057' in response.read().decode()
try:
    with urlopen(args.base_url + '/get?keyword=' + quote(args.keyword), timeout=110) as response:
        payload = json.load(response)
        method = response.headers.get('X-Search-Method')
except HTTPError as error:
    print(error.read().decode())
    raise
assert set(payload) == {'registration', 'newssource', 'keyword', 'url', 'summary'}
assert payload['registration'] == 'SP23-BAI-057'
assert payload['newssource'] == 'Ars Technica'
assert payload['url'].startswith('https://arstechnica.com/')
assert len(payload['summary'].split()) >= 15
assert len(payload['summary'].split()) <= 100
result = {'payload': payload, 'search_method': method, 'elapsed_seconds': round(time.monotonic() - start, 2)}
if args.output:
    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=2))
print(json.dumps({'registration': payload['registration'], 'keyword': args.keyword, 'url': payload['url'], 'summary_words': len(payload['summary'].split()), 'search_method': method, 'elapsed_seconds': result['elapsed_seconds']}, indent=2))
