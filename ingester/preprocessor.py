import re
import spacy

nlp = spacy.load('en_core_web_sm')

BOILERPLATE_PATTERNS = [
    r'subscribe to our newsletter.*',
    r'sign up for.*newsletter.*',
    r'click here to.*',
    r'follow us on.*',
    r'share this article.*',
    r'read more:.*',
    r'related:.*',
    r'advertisement.*',
    r'sponsored content.*',
    r'terms of service.*',
    r'privacy policy.*',
    r'all rights reserved.*',
    r'copyright \d{4}.*',
    r'cookie policy.*',
    r'accept cookies.*',
    r'\d+ min read',
    r'originally published.*',
    r'this article first appeared.*',
]


def strip_boilerplate(text: str) -> str:
    """Remove common boilerplate patterns from article text."""
    if not text:
        return ''
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def truncate_to_tokens(text: str, max_tokens: int = 500) -> str:
    """
    Approximate token truncation.
    1 token is roughly 4 characters for English text.
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind('.')
    if last_period > max_chars * 0.8:
        return truncated[:last_period + 1]
    return truncated


def extract_entities(text: str) -> list:
    """Extract named entities from text using spacy."""
    doc = nlp(text[:1000])
    entities = []
    for ent in doc.ents:
        if ent.label_ in ('PERSON', 'ORG', 'GPE', 'EVENT', 'LAW'):
            entities.append(ent.text)
    return list(set(entities))


def detect_development_signals(
    new_title: str,
    new_body: str,
    existing_title: str,
    existing_body: str
) -> bool:
    """
    Returns True if new article contains meaningful new developments
    compared to an existing similar story.
    Checks for: new named entities, new numbers, outcome/time language.
    """
    new_text = (new_title + ' ' + new_body).lower()
    existing_text = (existing_title + ' ' + existing_body).lower()

    new_entities = set(extract_entities(new_title + ' ' + new_body))
    existing_entities = set(extract_entities(existing_title + ' ' + existing_body))
    new_entity_found = bool(new_entities - existing_entities)

    new_numbers = set(re.findall(r'\b\d+\.?\d*\b', new_text))
    existing_numbers = set(re.findall(r'\b\d+\.?\d*\b', existing_text))
    new_number_found = bool(new_numbers - existing_numbers)

    outcome_signals = [
        'sentenced', 'confirmed', 'signed', 'passed', 'rejected',
        'collapsed', 'resigned', 'arrested', 'charged', 'convicted',
        'announced', 'reversed', 'approved', 'denied', 'launched',
        'deployed', 'released', 'updated', 'upgraded'
    ]
    time_signals = [
        'today', 'tonight', 'this morning', 'this evening',
        'just in', 'breaking', 'now', 'hours ago', 'minutes ago'
    ]

    signal_found = any(s in new_text for s in outcome_signals + time_signals)

    return new_entity_found or new_number_found or signal_found


def preprocess_article(title: str, body: str) -> dict:
    """
    Full preprocessing pipeline for a single article.
    Returns a clean structured dict ready for Haiku.
    """
    clean_body = strip_boilerplate(body)
    truncated_body = truncate_to_tokens(clean_body, max_tokens=500)
    entities = extract_entities(title + ' ' + truncated_body)

    structured = (
        f"TITLE: {title}\n"
        f"BODY: {truncated_body}\n"
        f"ENTITIES: {', '.join(entities) if entities else 'none detected'}"
    )

    return {
        'clean_body': truncated_body,
        'entities': entities,
        'structured_input': structured,
        'original_length': len(body),
        'processed_length': len(truncated_body)
    }