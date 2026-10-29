import unittest
from unittest.mock import patch

import app as service
from scraper import Article, SourceError, ArticleNotFound, canonical_article, clean_html, matches_keyword
from summarizer import summarize


class NewsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = service.app.test_client()
        service.cache.clear()

    def test_homepage_displays_registration(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'SP23-BAI-057', response.data)

    @patch('app.search_and_read')
    def test_invalid_input_never_starts_browser(self, scrape):
        for query in ['', '?keyword=', '?keyword=%20%20', '?keyword=!!!', '?keyword=' + 'x' * 201, '?keyword=x%00']:
            self.assertEqual(self.client.get('/get' + query).status_code, 400)
        scrape.assert_not_called()

    @patch('app.search_and_read')
    def test_exact_response_contract_and_case_insensitive_cache(self, scrape):
        scrape.return_value = Article('https://arstechnica.com/science/2026/10/example/', 'Example', 'NASA launched a spacecraft. The mission will collect new data about space.', 'source-search')
        response = self.client.get('/get?keyword=NASA')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json), {'registration', 'newssource', 'keyword', 'url', 'summary'})
        self.assertEqual(response.json['registration'], 'SP23-BAI-057')
        self.assertEqual(response.headers['X-Search-Method'], 'source-search')
        second = self.client.get('/get?keyword=nasa')
        self.assertEqual(second.json['keyword'], 'nasa')
        scrape.assert_called_once_with('NASA')

    @patch('app.search_and_read')
    def test_upstream_failures_are_honest_and_release_browser_slot(self, scrape):
        scrape.side_effect = [SourceError('Source unavailable'), ArticleNotFound('No matching article')]
        self.assertEqual(self.client.get('/get?keyword=space').status_code, 502)
        self.assertEqual(self.client.get('/get?keyword=space').status_code, 404)

    def test_busy_browser_does_not_launch_another_session(self):
        service.browser_slot.acquire()
        try:
            response = self.client.get('/get?keyword=space')
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '10')
        finally:
            service.browser_slot.release()

    def test_article_urls_cannot_escape_assigned_source(self):
        self.assertIsNone(canonical_article('https://arstechnica.com.evil.example/science/2026/10/test/'))
        self.assertIsNone(canonical_article('https://arstechnica.com/civis/threads/test/'))
        self.assertEqual(canonical_article('https://arstechnica.com/science/2026/10/test/?utm_source=rss'), 'https://arstechnica.com/science/2026/10/test/')

    def test_summary_removes_navigation_and_respects_word_limit(self):
        text = clean_html('<nav>Menu and subscribe</nav><p>NASA launched its new spacecraft.</p><p>NASA launched its new spacecraft.</p><p>Scientists will study Mars.</p>')
        self.assertNotIn('Menu', text)
        self.assertEqual(text.count('NASA launched'), 1)
        result = summarize(text, max_words=8)
        self.assertLessEqual(len(result.split()), 8)
        self.assertIn('NASA', result)

    def test_feed_keyword_matching_uses_whole_words(self):
        article = Article('https://arstechnica.com/ai/2026/10/example/', 'AI software', 'Email and security details.', 'public-rss')
        self.assertTrue(matches_keyword(article, 'AI'))
        self.assertTrue(matches_keyword(article, 'AI security'))
        self.assertFalse(matches_keyword(article, 'mail'))
        self.assertFalse(matches_keyword(article, 'NASA'))


if __name__ == '__main__':
    unittest.main()
