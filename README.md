# Selenium News API - Lab Assignment 4

**Hussain | SP23-BAI-057 | CSC418 DevOps | COMSATS Islamabad**

Assigned source: **Ars Technica**, because `57 % 20 + 1 = 18`.

## Build and run

```sh
docker build -t hussainturii/selenium-news-api:latest .
docker run -d --name selenium-news-api -p 7000:7000 hussainturii/selenium-news-api:latest
```

The image contains Python, Google Chrome for Testing, matching ChromeDriver, Selenium, the summarization module, and Flask/Gunicorn. The API starts automatically. Chrome and ChromeDriver are installed during the build; no browser download, model download, paid service, or API key is required at container startup.

Open `http://localhost:7000/` for the registration page and search form.

## Required API

```sh
curl --get --data-urlencode 'keyword=space' http://localhost:7000/get
```

Successful responses contain exactly these five fields:

```json
{
  "registration": "SP23-BAI-057",
  "newssource": "Ars Technica",
  "keyword": "space",
  "url": "https://arstechnica.com/science/2026/10/example/",
  "summary": "An extractive summary of the actual retrieved source text."
}
```

The URL above illustrates the response structure; live requests return a real retrieved article URL.

`GET /health` is a quick liveness endpoint. Missing/invalid keywords return 400, no matching public article returns 404, an upstream retrieval failure returns 502, and a concurrent browser request returns 429.

## Selenium retrieval and source availability

1. Selenium starts headless Google Chrome and visits Ars Technica's search page with the requested keyword.
2. It selects the first valid Ars article from the normal search results and extracts its paragraphs.
3. Ars may require human verification. The application does not solve or bypass that check. When native search is unavailable, Chrome reads the source's officially published main, Technology Lab, Gadgets, Science, and Tech Policy RSS feeds and searches their titles and available text. It deduplicates the entries, orders them newest first, and chooses the first matching result.
4. Chrome attempts to read that item's article page. If the article page is blocked, it summarizes the text the publisher made publicly available in RSS.
5. A deterministic sentence-frequency summarizer selects up to three sentences, preserving their source order, and caps the result at 100 words.

The `X-Search-Method` response header identifies whether native search, feed search with article-page extraction, or public RSS text was used. **The feed fallback covers currently published feed entries, not the complete article archive.** A keyword absent from that feed can return 404 while native search is blocked. No result is fabricated or substituted with another news source.

The Selenium browser always closes after the request. Successful results are cached for ten minutes; one browser session runs at a time to bound memory use.

## Tests

API and parsing tests (inside the built image, with the tests mounted):

```sh
docker run --rm -v "$PWD/tests:/tests:ro" hussainturii/selenium-news-api:latest python -m unittest discover -s /tests -v
python tests/smoke_live.py --keyword space
```

The live smoke test calls the real container's API, verifies the registration page and required JSON fields, and checks that a real Ars article URL and non-empty summary were returned.

## Submission

- GitHub repository: `https://github.com/hussainturii/selenium-news-api`
- Docker Hub image with tag: `hussainturii/selenium-news-api:latest`
- Selenium test language: **Python**
- Include the complete `Dockerfile` contents in the form.
- Container/API port: **7000**

This lab's evaluator pulls and runs the image. It does not require a separate EC2 deployment or a Jenkins job.
