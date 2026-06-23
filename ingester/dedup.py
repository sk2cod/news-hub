import hashlib
from simhash import Simhash
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CLUSTER_SIMILARITY_THRESHOLD = 0.35
MAX_CLUSTER_SIZE = 5


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
    existing_url_hashes: list,
    existing_simhashes: list
) -> dict:
    """
    Run Gate 1 (URL hash) and Gate 2 (SimHash) against a new article.
    Gate 3 (TF-IDF) is no longer a per-article drop/keep decision in v2.0 —
    see cluster_articles() for story-level grouping instead.

    Returns a dict with:
        action: 'drop' | 'keep'
        reason: explanation string
        url_hash: computed hash for storage
        title_simhash: computed simhash for storage
    """
    url_hash = compute_url_hash(url)
    title_simhash = compute_title_simhash(title)

    # Gate 1 — exact URL duplicate
    if url_hash in existing_url_hashes:
        return {
            'action': 'drop',
            'reason': 'exact URL duplicate',
            'url_hash': url_hash,
            'title_simhash': title_simhash
        }

    # Gate 2 — near-duplicate headline
    if is_simhash_duplicate(title_simhash, existing_simhashes):
        return {
            'action': 'drop',
            'reason': 'near-duplicate headline',
            'url_hash': url_hash,
            'title_simhash': title_simhash
        }

    return {
        'action': 'keep',
        'reason': 'new article',
        'url_hash': url_hash,
        'title_simhash': title_simhash
    }


def cluster_articles(
    articles: list,
    similarity_threshold: float = CLUSTER_SIMILARITY_THRESHOLD,
    max_cluster_size: int = MAX_CLUSTER_SIZE
) -> list:
    """
    Gate 3 — group articles covering the same story event into clusters.

    Articles are compared pairwise via TF-IDF cosine similarity over
    title + clean_body. Any pair scoring >= similarity_threshold is
    joined into the same cluster (transitively, via union-find), so a
    cluster can contain articles that aren't all pairwise similar as
    long as they're chained together by shared neighbours.

    similarity >= 0.35  → same story, grouped
    similarity < 0.35   → different story, stays in its own cluster

    Clusters larger than max_cluster_size keep only the top N articles
    by keyword_score (highest first).

    Returns a list of clusters, each a list of article dicts.
    """
    if not articles:
        return []

    n = len(articles)
    if n == 1:
        return [articles]

    texts = [
        a.get('title', '') + ' ' + a.get('clean_body', a.get('body', ''))
        for a in articles
    ]

    try:
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        similarity_matrix = cosine_similarity(tfidf_matrix)
    except Exception:
        return [[a] for a in articles]

    # Union-find to group articles transitively by similarity
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i

    def union(i, j):
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for i in range(n):
        for j in range(i + 1, n):
            if similarity_matrix[i][j] >= similarity_threshold:
                union(i, j)

    groups = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(articles[i])

    clusters = []
    for group in groups.values():
        if len(group) > max_cluster_size:
            group = sorted(
                group,
                key=lambda a: a.get('keyword_score', 0),
                reverse=True
            )[:max_cluster_size]
        clusters.append(group)

    return clusters