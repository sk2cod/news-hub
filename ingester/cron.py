import os
from dotenv import load_dotenv
from ingester.fetcher import fetch_all_articles
from ingester.dedup import check_duplicate
from ingester.preprocessor import preprocess_article
from ingester.keyword_scores import score_article
from ingester.budget_guard import reset_usage, print_usage_summary, get_usage_summary
from agents.crew import run_classification_crew
from db.queries import (
    get_existing_url_hashes,
    get_existing_simhashes,
    get_existing_articles_for_dedup,
    insert_article,
    insert_url_hash,
    cleanup_old_articles,
    start_cron_run,
    finish_cron_run
)

load_dotenv()

HAIKU_THRESHOLD = 0
BORDERLINE_MIN = -4
BLOCK_THRESHOLD = -5


def run_cron():
    """
    Main cron job entry point.
    Three-tier article routing:
      score >= 0    → Haiku classification → genuine tabs
      score -4 to -1 → stored as borderline, shown raw in borderline tab
      score <= -5   → blocked completely
    """
    print("\n========================================")
    print("NEWS HUB CRON JOB STARTING")
    print("========================================\n")

    run_id = start_cron_run()
    reset_usage()

    articles_fetched = 0
    articles_dropped = 0
    articles_stored = 0

    try:
        # Step 1 — Fetch all raw articles
        raw_articles = fetch_all_articles()
        articles_fetched = len(raw_articles)
        print(f"\nFetched: {articles_fetched} raw articles")

        # Step 2 — Load existing data for dedup
        print("\nLoading existing data for dedup...")
        existing_url_hashes = get_existing_url_hashes()
        existing_simhashes = get_existing_simhashes()
        existing_articles = get_existing_articles_for_dedup()
        print(f"Loaded {len(existing_url_hashes)} url hashes")
        print(f"Loaded {len(existing_simhashes)} simhashes")
        print(f"Loaded {len(existing_articles)} recent articles")

        # Step 3 — Dedup + score + route
        print("\n--- Running dedup, scoring and routing ---")
        haiku_queue = []
        borderline_queue = []

        for article in raw_articles:
            title = article.get('title', '')
            url = article.get('url', '')
            body = article.get('body', '')
            tab = article.get('tab', 'top_stories')

            if not title or not url:
                articles_dropped += 1
                continue

            # Keyword score
            score = score_article(title, body, tab)

            # Block completely
            if score <= BLOCK_THRESHOLD:
                articles_dropped += 1
                print(f"BLOCKED (score={score}): {title[:60]}")
                continue

            # Dedup gates
            dedup_result = check_duplicate(
                url=url,
                title=title,
                body=body,
                existing_url_hashes=existing_url_hashes,
                existing_simhashes=existing_simhashes,
                existing_articles=existing_articles
            )

            if dedup_result['action'] == 'drop':
                articles_dropped += 1
                print(f"DEDUP DROP ({dedup_result['reason']}): {title[:60]}")
                continue

            # Update in-memory dedup lists
            existing_url_hashes.append(dedup_result['url_hash'])
            existing_simhashes.append(dedup_result['title_simhash'])

            # Route to borderline or Haiku queue
            if score <= -1:
                article['keyword_score'] = score
                article['url_hash'] = dedup_result['url_hash']
                article['title_simhash'] = dedup_result['title_simhash']
                article['parent_story_id'] = dedup_result.get('parent_story_id')
                article['is_borderline'] = True
                borderline_queue.append(article)
                print(f"BORDERLINE (score={score}): {title[:60]}")
            else:
                preprocessed = preprocess_article(title, body)
                article['structured_input'] = preprocessed['structured_input']
                article['clean_body'] = preprocessed['clean_body']
                article['url_hash'] = dedup_result['url_hash']
                article['title_simhash'] = dedup_result['title_simhash']
                article['parent_story_id'] = dedup_result.get('parent_story_id')
                article['is_borderline'] = False
                article['keyword_score'] = score
                haiku_queue.append(article)

        print(f"\nHaiku queue:     {len(haiku_queue)} articles")
        print(f"Borderline queue: {len(borderline_queue)} articles")
        print(f"Blocked/dropped:  {articles_dropped}")

        # Step 4 — Store borderline articles directly (no Haiku)
        print("\n--- Storing borderline articles ---")
        for article in borderline_queue:
            try:
                insert_url_hash(article['url_hash'])
                row = {
                    'url_hash':        article['url_hash'],
                    'title_simhash':   article['title_simhash'],
                    'tab':             article.get('tab', 'top_stories'),
                    'title':           article['title'][:512],
                    'summary':         '',
                    'url':             article['url'],
                    'source_id':       article.get('source_id'),
                    'source_name':     article.get('source_name', ''),
                    'source_country':  article.get('source_country', 'GLOBAL'),
                    'published_at':    article.get('published_at'),
                    'is_australia':    False,
                    'is_nsw':          False,
                    'parent_story_id': article.get('parent_story_id'),
                    'is_borderline':   True,
                    'keyword_score':   article.get('keyword_score', 0),
                }
                insert_article(row)
                articles_stored += 1
                print(f"BORDERLINE STORED [{article.get('tab')}]: {article['title'][:60]}")
            except Exception as e:
                articles_dropped += 1
                print(f"BORDERLINE STORE ERROR: {e}")

        # Step 5 — Haiku classification
        if haiku_queue:
            print("\n--- Running Haiku classification ---")
            classified_articles = run_classification_crew(haiku_queue)

            # Step 6 — Store classified articles
            print("\n--- Storing classified articles ---")
            for article in classified_articles:
                try:
                    insert_url_hash(article['url_hash'])
                    row = {
                        'url_hash':        article['url_hash'],
                        'title_simhash':   article['title_simhash'],
                        'tab':             article['tab'],
                        'title':           article['title'][:512],
                        'summary':         article.get('summary', ''),
                        'url':             article['url'],
                        'source_id':       article.get('source_id'),
                        'source_name':     article.get('source_name', ''),
                        'source_country':  article.get('source_country', 'GLOBAL'),
                        'published_at':    article.get('published_at'),
                        'is_australia':    article.get('is_australia', False),
                        'is_nsw':          article.get('is_nsw', False),
                        'parent_story_id': article.get('parent_story_id'),
                        'is_borderline':   False,
                        'keyword_score':   article.get('keyword_score', 0),
                    }
                    insert_article(row)
                    articles_stored += 1
                    print(f"STORED [{article['tab']}]: {article['title'][:60]}")
                except Exception as e:
                    articles_dropped += 1
                    print(f"STORE ERROR: {e}")
        else:
            print("\nNo articles for Haiku this run")

        # Step 7 — Cleanup old articles
        print("\n--- Running 7-day TTL cleanup ---")
        cleanup_old_articles()

        # Step 8 — Final summary
        print("\n========================================")
        print(f"CRON JOB COMPLETE")
        print(f"Fetched:      {articles_fetched}")
        print(f"Dropped:      {articles_dropped}")
        print(f"Stored:       {articles_stored}")
        print(f"  Genuine:    {len(classified_articles) if haiku_queue else 0}")
        print(f"  Borderline: {len(borderline_queue)}")
        print("========================================\n")
        print_usage_summary()

        usage = get_usage_summary()
        finish_cron_run(
            run_id,
            articles_fetched,
            articles_dropped,
            articles_stored,
            status='complete',
            haiku_input_tokens=usage['haiku_input_tokens'],
            haiku_output_tokens=usage['haiku_output_tokens'],
            sonnet_input_tokens=usage['sonnet_input_tokens'],
            sonnet_output_tokens=usage['sonnet_output_tokens'],
            total_cost_usd=usage['total_cost_usd'],
            borderline_stored=len(borderline_queue),
            noise_dropped=len(haiku_queue) - len(classified_articles) if haiku_queue else 0
        )

    except Exception as e:
        print(f"\nCRON JOB FAILED: {e}")
        usage = get_usage_summary()
        finish_cron_run(
            run_id,
            articles_fetched,
            articles_dropped,
            articles_stored,
            status='failed',
            error_msg=str(e),
            haiku_input_tokens=usage['haiku_input_tokens'],
            haiku_output_tokens=usage['haiku_output_tokens'],
            sonnet_input_tokens=usage['sonnet_input_tokens'],
            sonnet_output_tokens=usage['sonnet_output_tokens'],
            total_cost_usd=usage['total_cost_usd'],
            borderline_stored=len(borderline_queue),
            noise_dropped=len(haiku_queue) - len(classified_articles) if haiku_queue else 0
        )
        raise


if __name__ == '__main__':
    run_cron()