"""Small deterministic extractive summarizer; no model downloads or API keys."""
import math
import re
from collections import Counter

STOP_WORDS = set('a an and are as at be been but by can could did do does for from had has have he her his how i if in into is it its may more most not of on one or our out said says she so some than that the their them then there these they this to up was we were what when which who will with would you your'.split())


def summarize(text: str, max_sentences: int = 3, max_words: int = 100) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        raise ValueError('No article text was available to summarize.')
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"\[])', text) if s.strip()]
    if not sentences:
        sentences = [text]
    words = lambda s: re.findall(r"[a-zA-Z][a-zA-Z'-]*", s.lower())
    frequencies = Counter(word for word in words(text) if word not in STOP_WORDS and len(word) > 2)
    scores = []
    for index, sentence in enumerate(sentences):
        tokens = words(sentence)
        score = sum(frequencies[word] for word in tokens if word not in STOP_WORDS) / math.sqrt(max(len(tokens), 1))
        if index == 0:
            score *= 1.2
        scores.append((score, index))
    chosen = sorted(index for _, index in sorted(scores, reverse=True)[:max_sentences])
    result = ' '.join(sentences[index] for index in chosen)
    tokens = result.split()
    if len(tokens) > max_words:
        result = ' '.join(tokens[:max_words]).rstrip('.,;:') + '…'
    return result
