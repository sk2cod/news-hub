import os
import json
import anthropic
from dotenv import load_dotenv
from ingester.budget_guard import record_usage, is_within_budget

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), 'prompts', 'classifier_system.txt'
)
SYNTHESIS_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), 'prompts', 'synthesis_system.txt'
)

with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
    SYSTEM_PROMPT = f.read()

with open(SYNTHESIS_PROMPT_PATH, 'r', encoding='utf-8') as f:
    SYNTHESIS_PROMPT = f.read()

VALID_TABS = [
    'geopolitics', 'top_stories', 'finance',
    'ai_tech', 'sports_ent', 'australia'
]


def classify_article(structured_input: str) -> dict:
    """
    Send a preprocessed article to Claude Haiku for classification.
    Uses prompt caching on the system prompt to reduce token costs.

    Returns a dict with:
        tab, summary, is_noise, is_australia, is_nsw
    """
    if not is_within_budget('haiku'):
        print("BUDGET GUARD: Skipping classification — daily limit reached")
        return {
            'tab': 'top_stories',
            'summary': '',
            'is_noise': True,
            'is_australia': False,
            'is_nsw': False
        }

    try:
        response = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=256,
            system=[
                {
                    'type': 'text',
                    'text': SYSTEM_PROMPT,
                    'cache_control': {'type': 'ephemeral'}
                }
            ],
            messages=[
                {
                    'role': 'user',
                    'content': structured_input
                }
            ]
        )

        # Record token usage for budget tracking
        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        record_usage('haiku', input_tokens, output_tokens)

        # Parse JSON response
        raw = response.content[0].text.strip()
        # Strip markdown code fences if Haiku adds them
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        # Validate required fields
        if result.get('tab') not in VALID_TABS:
            result['tab'] = 'top_stories'

        return {
            'tab': result.get('tab', 'top_stories'),
            'category': result.get('category', ''),
            'summary': result.get('summary', ''),
            'is_noise': result.get('is_noise', False),
            'is_australia': result.get('is_australia', False),
            'is_nsw': result.get('is_nsw', False)
        }

    except json.JSONDecodeError as e:
        print(f"Haiku JSON parse error: {e}")
        return {
            'tab': 'top_stories',
            'summary': '',
            'category': '',
            'is_noise': True,
            'is_australia': False,
            'is_nsw': False
        }
    except Exception as e:
        print(f"Haiku classification error: {e}")
        return {
            'tab': 'top_stories',
            'summary': '',
            'category': '',
            'is_noise': True,
            'is_australia': False,
            'is_nsw': False
        }


def classify_batch(articles: list) -> list:
    """
    Classify a list of preprocessed articles.
    Each article dict must have a 'structured_input' key
    from preprocessor.preprocess_article().

    Returns the same list with classification fields added.
    """
    results = []
    for i, article in enumerate(articles):
        print(f"Classifying {i+1}/{len(articles)}: {article.get('title', '')[:60]}")
        classification = classify_article(article['structured_input'])

        if classification['is_noise']:
            print(f"  → NOISE — skipping")
            continue

        article.update(classification)
        results.append(article)
        print(f"  → {classification['tab']} | {classification['summary'][:60]}")

    return results


def build_cluster_input(cluster: list) -> str:
    """
    Format a cluster of 1-5 articles into a single structured input
    for Haiku, with one SOURCE block per article.
    """
    blocks = []
    for i, article in enumerate(cluster, start=1):
        source_name = article.get('source_name', 'Unknown')
        title = article.get('title', '')
        body = article.get('clean_body', article.get('body', ''))
        blocks.append(
            f"SOURCE {i} ({source_name}):\n"
            f"TITLE: {title}\n"
            f"BODY: {body}"
        )
    return '\n\n'.join(blocks)


def synthesise_cluster(cluster: list) -> dict:
    """
    Send a cluster of 1-5 articles covering the same story to Claude
    Haiku, which synthesises them into one briefing.
    Uses prompt caching on the system prompt to reduce token costs.

    Returns a dict with:
        tab, category, briefing, is_noise, is_australia, is_nsw
    """
    if not is_within_budget('haiku'):
        print("BUDGET GUARD: Skipping synthesis — daily limit reached")
        return {
            'tab': 'top_stories',
            'category': '',
            'briefing': '',
            'is_noise': True,
            'is_australia': False,
            'is_nsw': False
        }

    cluster_input = build_cluster_input(cluster)

    try:
        response = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=512,
            system=[
                {
                    'type': 'text',
                    'text': SYNTHESIS_PROMPT,
                    'cache_control': {'type': 'ephemeral'}
                }
            ],
            messages=[
                {
                    'role': 'user',
                    'content': cluster_input
                }
            ]
        )

        # Record token usage for budget tracking
        usage = response.usage
        record_usage('haiku', usage.input_tokens, usage.output_tokens)

        # Parse JSON response
        raw = response.content[0].text.strip()
        # Strip markdown code fences if Haiku adds them
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        if result.get('tab') not in VALID_TABS:
            result['tab'] = 'top_stories'

        return {
            'tab': result.get('tab', 'top_stories'),
            'category': result.get('category', ''),
            'briefing': result.get('briefing', ''),
            'is_noise': result.get('is_noise', False),
            'is_australia': result.get('is_australia', False),
            'is_nsw': result.get('is_nsw', False)
        }

    except json.JSONDecodeError as e:
        print(f"Haiku synthesis JSON parse error: {e}")
        return {
            'tab': 'top_stories',
            'category': '',
            'briefing': '',
            'is_noise': True,
            'is_australia': False,
            'is_nsw': False
        }
    except Exception as e:
        print(f"Haiku synthesis error: {e}")
        return {
            'tab': 'top_stories',
            'category': '',
            'briefing': '',
            'is_noise': True,
            'is_australia': False,
            'is_nsw': False
        }


def synthesise_batch(clusters: list) -> list:
    """
    Synthesise a list of clusters, each a list of 1-5 article dicts
    covering the same story (see ingester.dedup.cluster_articles).

    Returns a list of dicts, one per non-noise cluster, with:
        tab, category, briefing, is_noise, is_australia, is_nsw, sources
    'sources' is the original list of article dicts in that cluster.
    """
    results = []
    for i, cluster in enumerate(clusters):
        lead_title = cluster[0].get('title', '')[:60]
        print(f"Synthesising cluster {i+1}/{len(clusters)} "
              f"({len(cluster)} sources): {lead_title}")
        synthesis = synthesise_cluster(cluster)

        if synthesis['is_noise']:
            print(f"  → NOISE — skipping")
            continue

        synthesis['sources'] = cluster
        results.append(synthesis)
        print(f"  → {synthesis['tab']} | {synthesis['briefing'][:60]}")

    return results