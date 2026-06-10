import os
import json
import anthropic
from dotenv import load_dotenv
from ingester.budget_guard import record_usage, is_within_budget

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

ANALYSIS_SYSTEM_PROMPT = """
You are a senior investigative journalist and editorial analyst.
Your job is to provide deep, balanced analysis of a news article.

## YOUR ANALYSIS MUST INCLUDE

1. SENTIMENT — Overall tone of the news event itself (not the article's writing style).
   Choose exactly one: positive, negative, neutral, mixed

2. BIAS SCORE — Rate the article's editorial bias on a scale of -5 to +5.
   -5 = strongly left-leaning
    0 = neutral/centrist
   +5 = strongly right-leaning
   Base this on word choice, framing, and what is omitted.

3. BIAS DIRECTION — One short phrase describing the bias if score is not 0.
   Examples: "pro-government", "anti-corporate", "Western-centric", "neutral"

4. CONTEXT SUMMARY — 2-3 paragraphs providing:
   - What led to this event (background)
   - Why it matters (significance)
   - What happens next (implications)

5. KEY ENTITIES — List the most important people, organisations, and places
   mentioned. Comma separated.

## RULES
- Be factual and balanced.
- Do not insert your own political opinion.
- If the article lacks enough information for deep analysis, say so clearly
  in the context summary.
- Respond ONLY with a valid JSON object. No preamble, no markdown.

{
  "sentiment": "positive|negative|neutral|mixed",
  "bias_score": 0,
  "bias_direction": "neutral",
  "context_summary": "paragraph 1\n\nparagraph 2\n\nparagraph 3",
  "key_entities": "entity1, entity2, entity3"
}
"""


def analyse_article(
    article_id: str,
    title: str,
    body: str,
    source_name: str
) -> dict:
    """
    Run Claude Sonnet deep analysis on a single article.
    Only called when user clicks 'Deep Analysis' button.

    Returns a dict ready to insert into analysis_results table.
    """
    if not is_within_budget('sonnet'):
        print("BUDGET GUARD: Sonnet daily limit reached")
        return {}

    user_message = (
        f"ARTICLE TITLE: {title}\n\n"
        f"SOURCE: {source_name}\n\n"
        f"ARTICLE BODY:\n{body}"
    )

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

        return {
            'article_id':      article_id,
            'sentiment':       result.get('sentiment', 'neutral'),
            'bias_score':      bias_score,
            'bias_direction':  result.get('bias_direction', 'neutral'),
            'context_summary': result.get('context_summary', ''),
            'key_entities':    result.get('key_entities', ''),
            'model_used':      'claude-sonnet-4-5'
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