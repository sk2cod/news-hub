import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_ANON_KEY')
)


# ─── URL Hash Operations ───────────────────────────────────────────────────────

def get_existing_url_hashes() -> list:
    """Fetch all known URL hashes from last 7 days."""
    response = supabase.table('url_hashes').select('url_hash').execute()
    return [row['url_hash'] for row in response.data]


def insert_url_hash(url_hash: str):
    """Insert a new URL hash after an article passes dedup."""
    try:
        supabase.table('url_hashes').insert({
            'url_hash': url_hash
        }).execute()
    except Exception as e:
        print(f"Hash insert error (likely duplicate): {e}")


# ─── Article Operations ────────────────────────────────────────────────────────

def get_existing_articles_for_dedup() -> list:
    """
    Fetch recent articles needed for SimHash and TF-IDF comparison.
    Returns id, title, clean_body, and title_simhash.
    """
    response = (
        supabase.table('articles')
        .select('id, title, summary, title_simhash')
        .order('ingested_at', desc=True)
        .limit(200)
        .execute()
    )
    return response.data


def get_existing_simhashes() -> list:
    """Fetch all title simhashes for near-duplicate detection."""
    response = (
        supabase.table('articles')
        .select('title_simhash')
        .order('ingested_at', desc=True)
        .limit(200)
        .execute()
    )
    return [
        row['title_simhash']
        for row in response.data
        if row['title_simhash']
    ]


def insert_article(article: dict) -> dict:
    """
    Insert a classified article into the database.
    Returns the inserted row including generated id.
    """
    response = (
        supabase.table('articles')
        .insert(article)
        .execute()
    )
    return response.data[0] if response.data else {}


def get_articles_by_tab(tab: str, limit: int = 10) -> list:
    response = (
        supabase.table('articles')
        .select('*')
        .eq('tab', tab)
        .eq('is_borderline', False)
        .order('ingested_at', desc=True)
        .limit(limit)
        .execute()
    )
    return response.data


def get_articles_by_tab_paginated(
    tab: str,
    limit: int = 10,
    offset: int = 0
) -> list:
    """
    Fetch articles with pagination support for 'Load next 10' button.
    Excludes borderline articles — those show in the borderline tab only.
    """
    response = (
        supabase.table('articles')
        .select('*')
        .eq('tab', tab)
        .eq('is_borderline', False)
        .order('ingested_at', desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data


def get_article_by_id(article_id: str) -> dict:
    """Fetch a single article by its UUID."""
    response = (
        supabase.table('articles')
        .select('*')
        .eq('id', article_id)
        .single()
        .execute()
    )
    return response.data


def get_story_updates(parent_story_id: str) -> list:
    """Fetch all updates linked to a parent story."""
    response = (
        supabase.table('articles')
        .select('*')
        .eq('parent_story_id', parent_story_id)
        .order('published_at', desc=True)
        .execute()
    )
    return response.data


def cleanup_old_articles():
    supabase.rpc('cleanup_old_articles', {}).execute()


# ─── Analysis Operations ───────────────────────────────────────────────────────

def get_analysis(article_id: str) -> dict:
    """
    Fetch Sonnet deep analysis only.
    Excludes Haiku quick analysis results.
    """
    response = (
        supabase.table('analysis_results')
        .select('*')
        .eq('article_id', article_id)
        .eq('model_used', 'claude-sonnet-4-5')
        .execute()
    )
    return response.data[0] if response.data else {}


def insert_analysis(analysis: dict) -> dict:
    """
    Save Sonnet deep analysis result to database.
    Uses upsert to handle re-analysis gracefully.
    """
    response = (
        supabase.table('analysis_results')
        .upsert(analysis, on_conflict='article_id')
        .execute()
    )
    return response.data[0] if response.data else {}


# ─── Cron Run Operations ───────────────────────────────────────────────────────

def start_cron_run() -> str:
    """
    Insert a new cron run record with status 'running'.
    Returns the run UUID for updating later.
    """
    response = (
        supabase.table('cron_runs')
        .insert({'status': 'running'})
        .execute()
    )
    return response.data[0]['id']


def finish_cron_run(
    run_id: str,
    articles_fetched: int,
    articles_dropped: int,
    articles_stored: int,
    status: str = 'complete',
    error_msg: str = None,
    haiku_input_tokens: int = 0,
    haiku_output_tokens: int = 0,
    sonnet_input_tokens: int = 0,
    sonnet_output_tokens: int = 0,
    total_cost_usd: float = 0.0,
    borderline_stored: int = 0,
    noise_dropped: int = 0
):
    """Update a cron run record when the job finishes."""
    from datetime import datetime, timezone
    supabase.table('cron_runs').update({
        'finished_at':         datetime.now(timezone.utc).isoformat(),
        'articles_fetched':    articles_fetched,
        'articles_dropped':    articles_dropped,
        'articles_stored':     articles_stored,
        'status':              status,
        'error_msg':           error_msg,
        'haiku_input_tokens':  haiku_input_tokens,
        'haiku_output_tokens': haiku_output_tokens,
        'sonnet_input_tokens': sonnet_input_tokens,
        'sonnet_output_tokens':sonnet_output_tokens,
        'total_cost_usd':      total_cost_usd,
        'borderline_stored':   borderline_stored,
        'noise_dropped':       noise_dropped
    }).eq('id', run_id).execute()


def get_last_cron_run() -> dict:
    """
    Fetch the most recent completed cron run.
    Used by Streamlit UI to show last updated time.
    """
    response = (
        supabase.table('cron_runs')
        .select('*')
        .eq('status', 'complete')
        .order('finished_at', desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}

def get_recent_cron_runs(limit: int = 10) -> list:
    """Fetch recent cron runs for the dashboard."""
    response = (
        supabase.table('cron_runs')
        .select('*')
        .order('started_at', desc=True)
        .limit(limit)
        .execute()
    )
    return response.data

# ─── Borderline Article Operations ────────────────────────────────────────────

def get_borderline_articles() -> dict:
    """
    Fetch all borderline articles grouped by tab.
    Returns a dict keyed by tab name with list of articles as values.
    Ordered by published_at DESC within each tab.
    """
    response = (
        supabase.table('articles')
        .select('*')
        .eq('is_borderline', True)
        .order('published_at', desc=True)
        .limit(200)
        .execute()
    )

    grouped = {
        'geopolitics': [],
        'top_stories': [],
        'finance': [],
        'ai_tech': [],
        'sports_ent': [],
        'australia': [],
    }

    for article in response.data:
        tab = article.get('tab', 'top_stories')
        if tab in grouped:
            grouped[tab].append(article)

    return grouped


def get_borderline_analysis(article_id: str) -> dict:
    """
    Fetch Haiku quick analysis only.
    Excludes Sonnet deep analysis results.
    """
    response = (
        supabase.table('analysis_results')
        .select('*')
        .eq('article_id', article_id)
        .eq('model_used', 'claude-haiku-4-5')
        .execute()
    )
    return response.data[0] if response.data else {}


def insert_borderline_analysis(analysis: dict) -> dict:
    """
    Save Haiku quick analysis for a borderline article.
    Uses upsert to handle re-analysis gracefully.
    """
    response = (
        supabase.table('analysis_results')
        .upsert(analysis, on_conflict='article_id')
        .execute()
    )
    return response.data[0] if response.data else {}