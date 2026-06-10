import hashlib
from simhash import Simhash
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ingester.preprocessor import detect_development_signals


def compute_url_hash(url: str) -> str:
    """
    Compute SHA-256 hash of a URL.
    Used for exact duplicate detection.
    """
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def compute_title_simhash(title: str) -> str:
    """
    Compute SimHash fingerprint of a title.
    Used for near-duplicate headline detection.
    """
    return str(Simhash(title.lower().split()).value)


def is_simhash_duplicate(
    new_hash: str,
    existing_hashes: list,
    threshold: int = 3
) -> bool:
    """
    Compare a new SimHash against a list of existing ones.
    Returns True if Hamming distance <= threshold (near-duplicate).
    threshold=3 means titles are ~95% similar.
    """
    new_val = int(new_hash)
    for existing in existing_hashes:
        existing_val = int(existing)
        xor = new_val ^ existing_val
        hamming_distance = bin(xor).count('1')
        if hamming_distance <= threshold:
            return True
    return False


def compute_tfidf_similarity(
    new_text: str,
    existing_texts: list
) -> float:
    """
    Compute maximum cosine similarity between new article
    and all existing articles using TF-IDF vectors.
    Returns the highest similarity score found (0.0 to 1.0).
    """
    if not existing_texts:
        return 0.0

    all_texts = existing_texts + [new_text]

    try:
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)
        )
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        new_vector = tfidf_matrix[-1]
        existing_vectors = tfidf_matrix[:-1]
        similarities = cosine_similarity(new_vector, existing_vectors)
        return float(similarities.max())
    except Exception:
        return 0.0


def check_duplicate(
    url: str,
    title: str,
    body: str,
    existing_url_hashes: list,
    existing_simhashes: list,
    existing_articles: list
) -> dict:
    """
    Run all three dedup gates against a new article.

    Returns a dict with:
        action: 'drop' | 'keep' | 'update'
        reason: explanation string
        url_hash: computed hash for storage
        title_simhash: computed simhash for storage
        parent_story_id: UUID if action is 'update', else None
    """
    url_hash = compute_url_hash(url)
    title_simhash = compute_title_simhash(title)

    # Gate 1 — exact URL duplicate
    if url_hash in existing_url_hashes:
        return {
            'action': 'drop',
            'reason': 'exact URL duplicate',
            'url_hash': url_hash,
            'title_simhash': title_simhash,
            'parent_story_id': None
        }

    # Gate 2 — near-duplicate headline
    if is_simhash_duplicate(title_simhash, existing_simhashes):
        return {
            'action': 'drop',
            'reason': 'near-duplicate headline',
            'url_hash': url_hash,
            'title_simhash': title_simhash,
            'parent_story_id': None
        }

    # Gate 3 — TF-IDF cosine similarity
    if existing_articles:
        existing_texts = [
            a['title'] + ' ' + a.get('clean_body', '')
            for a in existing_articles
        ]
        new_text = title + ' ' + body
        similarity = compute_tfidf_similarity(new_text, existing_texts)

        # High similarity — check for new developments
        if similarity > 0.85:
            for article in existing_articles:
                article_similarity = compute_tfidf_similarity(
                    new_text,
                    [article['title'] + ' ' + article.get('clean_body', '')]
                )
                if article_similarity > 0.85:
                    has_development = detect_development_signals(
                        title, body,
                        article['title'],
                        article.get('clean_body', '')
                    )
                    if has_development:
                        return {
                            'action': 'update',
                            'reason': 'story development detected',
                            'url_hash': url_hash,
                            'title_simhash': title_simhash,
                            'parent_story_id': article['id']
                        }
            return {
                'action': 'drop',
                'reason': 'duplicate story no new developments',
                'url_hash': url_hash,
                'title_simhash': title_simhash,
                'parent_story_id': None
            }

        # Related but distinct story
        if 0.60 <= similarity <= 0.85:
            return {
                'action': 'keep',
                'reason': 'related but distinct story',
                'url_hash': url_hash,
                'title_simhash': title_simhash,
                'parent_story_id': None
            }

    # Passed all gates — new story
    return {
        'action': 'keep',
        'reason': 'new story',
        'url_hash': url_hash,
        'title_simhash': title_simhash,
        'parent_story_id': None
    }