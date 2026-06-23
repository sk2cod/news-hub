import re
import hashlib
from simhash import Simhash
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CLUSTER_SIMILARITY_THRESHOLD = 0.35
MAX_CLUSTER_SIZE = 5

# Second-pass meta-clustering — see group_clusters_for_merge()
CATEGORY_OVERLAP_MIN_WORDS = 2
# Empirically calibrated: fitting TF-IDF on a handful of realistic
# 4-bullet Haiku briefings, genuinely same-event pairs scored ~0.15-0.17
# cosine similarity, unrelated pairs ~0.01-0.06. 0.3 (the first guess)
# never fires in practice — briefings are short relative to vocabulary
# size, so absolute scores run much lower than intuition suggests.
BRIEFING_SIMILARITY_THRESHOLD = 0.12
CATEGORY_STOPWORDS = {
    'the', 'a', 'an', 'of', 'in', 'on', 'for', 'and', 'to',
    'with', 'its', 'new', 'over', 'after', 'as', 'at',
}


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


def _category_words(category: str) -> set:
    words = re.findall(r"[a-z0-9']+", category.lower())
    return {w for w in words if w not in CATEGORY_STOPWORDS}


def categories_overlap(
    category_a: str,
    category_b: str,
    min_words: int = CATEGORY_OVERLAP_MIN_WORDS
) -> bool:
    """
    Two category labels signal the same story if they're an exact
    case-insensitive match, or share at least min_words significant
    words after stopword removal. Requiring >=2 shared words (rather
    than just 1) avoids false positives like "Iran" alone matching
    unrelated Iran stories (nuclear talks vs. an earthquake).
    """
    a = category_a.strip().lower()
    b = category_b.strip().lower()
    if a and a == b:
        return True
    return len(_category_words(category_a) & _category_words(category_b)) >= min_words


def group_clusters_for_merge(clusters: list, max_sources: int = MAX_CLUSTER_SIZE) -> list:
    """
    Second-pass meta-clustering — groups already-synthesised clusters
    (from cluster_articles() + synthesise_cluster()) that describe the
    same story event but weren't grouped by the first TF-IDF pass on
    raw article bodies (common with short, sparse Tavily snippets).

    Two independent merge signals, checked pairwise:
      - category overlap: exact match, or >=2 shared significant words
      - briefing similarity: cosine similarity over Haiku-normalised
        briefing text, fit once across all clusters passed in (richer
        corpus than a 2-document pairwise fit, which under-discriminates)

    Either signal alone is enough to flag a candidate pair — but a pair
    must also share the same tab. Cross-tab pairs never merge.

    Non-transitive by design: a candidate only joins a forming group if
    it pairwise-matches EVERY existing member (a clique requirement),
    not just one member via a chain. This avoids the "A matches B, B
    matches C, but A doesn't match C" trap that a union-find/connected-
    components approach would fall into — important here because
    category/briefing overlap is a weaker signal than the first pass's
    direct TF-IDF on full article bodies. The tradeoff: a genuine 3+
    way match can fragment into smaller groups if the weakest pairwise
    link falls just under threshold — accepted in exchange for never
    merging unrelated stories transitively.

    Each cluster dict must include 'tab', 'category', 'briefing', and
    'source_count' (used to enforce max_sources across the merged
    group, same cap as the first pass).

    Returns a list of groups, each a list of the original cluster
    dicts. Clusters with no match return as singleton groups (len 1)
    — callers should skip those, only merging groups of 2+.
    """
    n = len(clusters)
    if n == 0:
        return []
    if n == 1:
        return [clusters]

    briefings = [c.get('briefing', '') for c in clusters]
    try:
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)
        )
        tfidf_matrix = vectorizer.fit_transform(briefings)
        briefing_similarity = cosine_similarity(tfidf_matrix)
    except Exception:
        briefing_similarity = [[0.0] * n for _ in range(n)]

    def matches(i: int, j: int) -> bool:
        if clusters[i].get('tab') != clusters[j].get('tab'):
            return False
        if categories_overlap(clusters[i].get('category', ''), clusters[j].get('category', '')):
            return True
        return briefing_similarity[i][j] >= BRIEFING_SIMILARITY_THRESHOLD

    used = [False] * n
    groups = []

    for i in range(n):
        if used[i]:
            continue
        group_idx = [i]
        used[i] = True
        total_sources = clusters[i].get('source_count', 1)

        for j in range(n):
            if used[j] or i == j:
                continue
            candidate_sources = clusters[j].get('source_count', 1)
            if total_sources + candidate_sources > max_sources:
                continue
            if all(matches(j, k) for k in group_idx):
                group_idx.append(j)
                used[j] = True
                total_sources += candidate_sources

        groups.append([clusters[k] for k in group_idx])

    return groups