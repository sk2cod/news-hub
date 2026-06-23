import os
import json
import anthropic
from dotenv import load_dotenv
from ingester.budget_guard import record_usage, is_within_budget

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

ANALYSIS_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), 'prompts', 'analysis_system.txt'
)

with open(ANALYSIS_PROMPT_PATH, 'r', encoding='utf-8') as f:
    ANALYSIS_SYSTEM_PROMPT = f.read()


def build_cluster_analysis_input(title: str, sources: list) -> str:
    """
    Concatenate all source bodies in a story cluster into one input
    for Sonnet — much richer context than a single article.
    """
    blocks = []
    for i, source in enumerate(sources, start=1):
        source_name = source.get('source_name', 'Unknown')
        body = source.get('clean_body', source.get('body', ''))
        blocks.append(f"SOURCE {i} ({source_name}):\n{body}")

    return f"STORY: {title}\n\n" + '\n\n'.join(blocks)


def analyse_cluster(
    cluster_id: str,
    title: str,
    sources: list
) -> dict:
    """
    Run Claude Sonnet deep analysis on a story cluster.
    Only called when user clicks 'Deep Analysis' button.
    Sonnet receives ALL source bodies in the cluster concatenated,
    not just one article — see build_cluster_analysis_input().

    Returns a dict ready to insert into analysis_results table.
    """
    if not is_within_budget('sonnet'):
        print("BUDGET GUARD: Sonnet daily limit reached")
        return {}

    user_message = build_cluster_analysis_input(title, sources)

    try:
        response = client.messages.create(
            model='claude-sonnet-4-5',
            max_tokens=1024,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {
                    'role': 'user',
                    'content': user_message
                }
            ]
        )

        # Record token usage
        usage = response.usage
        record_usage('sonnet', usage.input_tokens, usage.output_tokens)

        # Parse response
        raw = response.content[0].text.strip()
        # Strip markdown code fences if Sonnet adds them
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        # Validate sentiment
        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed']
        if result.get('sentiment') not in valid_sentiments:
            result['sentiment'] = 'neutral'

        # Validate bias score
        bias_score = result.get('bias_score', 0)
        if not isinstance(bias_score, (int, float)):
            bias_score = 0
        bias_score = max(-5, min(5, int(bias_score)))

        from datetime import datetime, timezone
        context_summary = '\n\n'.join(filter(None, [
            f"**Background:** {result.get('background', '')}",
            f"**Significance:** {result.get('significance', '')}",
            f"**Implications:** {result.get('implications', '')}",
            f"**Perspectives:** {result.get('perspectives', '')}",
        ]))

        return {
            'cluster_id': cluster_id,
            'sentiment': 'neutral',
            'bias_score': 0,
            'bias_direction': 'neutral',
            'context_summary': context_summary,
            'key_entities': result.get('key_entities', ''),
            'analysed_at': datetime.now(timezone.utc).isoformat(),
            'model_used': result.get('model_used', 'claude-sonnet-4-5')
        }

    except json.JSONDecodeError as e:
        print(f"Sonnet JSON parse error: {e}")
        return {}
    except Exception as e:
        import traceback
        print(f"Sonnet analysis error: {e}")
        traceback.print_exc()
        return {}

QUICK_ANALYSIS_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), 'prompts', 'quick_analysis_system.txt'
)

with open(QUICK_ANALYSIS_PROMPT_PATH, 'r', encoding='utf-8') as f:
    QUICK_ANALYSIS_SYSTEM_PROMPT = f.read()


def quick_analyse_article(
    article_id: str,
    title: str,
    body: str,
    source_name: str
) -> dict:
    """
    Run Claude Haiku quick analysis on a borderline article.
    Returns a verdict on whether the article is worth reading.
    Much cheaper than Sonnet — used only for borderline tab.
    """
    if not is_within_budget('haiku'):
        print("BUDGET GUARD: Haiku daily limit reached")
        return {}

    user_message = (
        f"ARTICLE TITLE: {title}\n\n"
        f"SOURCE: {source_name}\n\n"
        f"ARTICLE BODY:\n{body[:800] if body else 'No body text available.'}\n\n"
        f"Please provide a 2-3 sentence summary covering what happened, "
        f"why it matters, and any immediate implications."
    )

    try:
        response = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=256,
            system=QUICK_ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {
                    'role': 'user',
                    'content': user_message
                }
            ]
        )

        usage = response.usage
        record_usage('haiku', usage.input_tokens, usage.output_tokens)

        raw = response.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        valid_verdicts = ['worth reading', 'skip', 'borderline']
        if result.get('verdict') not in valid_verdicts:
            result['verdict'] = 'borderline'

        valid_tabs = [
            'geopolitics', 'top_stories', 'finance',
            'ai_tech', 'sports_ent', 'australia'
        ]
        if result.get('tab') not in valid_tabs:
            result['tab'] = 'top_stories'

        from datetime import datetime, timezone
        return {
            'article_id': article_id,
            'sentiment': 'neutral',
            'bias_score': 0,
            'bias_direction': result.get('verdict', 'borderline'),
            'context_summary': result.get('summary', ''),
            'key_entities': result.get('reason', ''),
            'analysed_at': datetime.now(timezone.utc).isoformat(),
            'model_used': 'claude-haiku-4-5'
        }

    except json.JSONDecodeError as e:
        print(f"Quick analysis JSON parse error: {e}")
        return {}
    except Exception as e:
        print(f"Quick analysis error: {e}")
        return {}


def quick_analyse_cluster(
    cluster_id: str,
    title: str,
    sources: list
) -> dict:
    """
    Run Claude Haiku quick analysis on a story cluster (genuine tabs).
    Returns a verdict on whether the story is worth reading.
    Much cheaper than Sonnet. See quick_analyse_article() for the
    equivalent on a single borderline article.
    """
    if not is_within_budget('haiku'):
        print("BUDGET GUARD: Haiku daily limit reached")
        return {}

    cluster_input = build_cluster_analysis_input(title, sources)
    user_message = (
        f"{cluster_input}\n\n"
        f"Please provide a 2-3 sentence summary covering what happened, "
        f"why it matters, and any immediate implications."
    )

    try:
        response = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=256,
            system=QUICK_ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {
                    'role': 'user',
                    'content': user_message
                }
            ]
        )

        usage = response.usage
        record_usage('haiku', usage.input_tokens, usage.output_tokens)

        raw = response.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        valid_verdicts = ['worth reading', 'skip', 'borderline']
        if result.get('verdict') not in valid_verdicts:
            result['verdict'] = 'borderline'

        valid_tabs = [
            'geopolitics', 'top_stories', 'finance',
            'ai_tech', 'sports_ent', 'australia'
        ]
        if result.get('tab') not in valid_tabs:
            result['tab'] = 'top_stories'

        from datetime import datetime, timezone
        return {
            'cluster_id': cluster_id,
            'sentiment': 'neutral',
            'bias_score': 0,
            'bias_direction': result.get('verdict', 'borderline'),
            'context_summary': result.get('summary', ''),
            'key_entities': result.get('reason', ''),
            'analysed_at': datetime.now(timezone.utc).isoformat(),
            'model_used': 'claude-haiku-4-5'
        }

    except json.JSONDecodeError as e:
        print(f"Cluster quick analysis JSON parse error: {e}")
        return {}
    except Exception as e:
        print(f"Cluster quick analysis error: {e}")
        return {}