"""Conservative keyword fallbacks and title scoring without dropping results."""
import re
import unicodedata
from difflib import SequenceMatcher


def words(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', str(text or '')).casefold() if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+(?:[+#]+)?', text)


def relevance(query, title):
    query_words, title_words = words(query), words(title)
    if not query_words or not title_words:
        return 0
    coverage = sum(any(word == candidate or (len(word) >= 4 and SequenceMatcher(None, word, candidate).ratio() >= 0.8)
                       for candidate in title_words) for word in query_words) / len(query_words)
    phrase = ' '.join(query_words) in ' '.join(title_words)
    return round(coverage * 0.8 + int(phrase) * 0.2, 4)


def query_variants(query):
    original = ' '.join(query.strip().split())
    if not original:
        return []
    variants = [original]
    if '"' in original:
        return variants
    broader = re.sub(r'(?<=\w)[._-](?=\w)', ' ', original)
    broader = re.sub(r'\b(?:480p|720p|1080p|2160p|4k|bluray|blu-ray|webrip|web-dl|x264|x265)\b', ' ', broader, flags=re.I)
    broader = re.sub(r'\b(?:19|20)\d{2}\s*$', '', broader)
    broader = ' '.join(broader.split())
    if broader and broader.casefold() != original.casefold():
        variants.append(broader)
    return variants
