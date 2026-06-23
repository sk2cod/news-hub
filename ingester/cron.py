import os
import sys
from dotenv import load_dotenv
from ingester.fetcher import fetch_all_articles
from ingester.dedup import (
    check_duplicate,
    cluster_articles,
    compute_title_simhash,
    group_clusters_for_merge
)
from ingester.preprocessor import preprocess_article
from ingester.keyword_scores import score_article
from ingester.budget_guard import reset_usage, print_usage_summary, get_usage_summary
from agents.classifier_agent import synthesise_cluster
from db.queries import (
    get_existing_url_hashes,
    get_existing_simhashes,
    get_existing_cluster_titles,
    insert_article,
    insert_url_hash,
    insert_story_cluster,
    insert_cluster_source,
    reparent_cluster_sources,
    delete_story_clusters,
    cleanup_old_articles,
    start_cron_run,
    finish_cron_run
)

load_dotenv()

# Fetched article titles can contain arbitrary emoji/unicode that the
# console's default codepage (cp1252 on Windows) can't encode — without
# this, a single odd character in any of 300+ fetched titles crashes
# the whole run on a print() call.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HAIKU_THRESHOLD = 0
BORDERLINE_MIN = -4
BLOCK_THRESHOLD = -5


def run_cron():
    """
    Main cron job entry point.

    Pipeline:
      1. Fetch articles (RSS + Tavily)
      2. Gate 1 + Gate 2 dedup (URL hash + SimHash) per article
      3. Keyword scoring and routing (block / borderline / haiku queue)
      4. cluster_articles() groups the haiku queue into story clusters
      5. synthesise_cluster() sends each cluster to Haiku for one briefing,
         stored immediately (one row in story_clusters, one row per
         source in cluster_sources) so a later failure doesn't discard
         already-synthesised clusters
      6. group_clusters_for_merge() — deferred second pass over this
         run's stored clusters, catching same-event stories the first
         TF-IDF pass missed (short Tavily snippets). Re-synthesises and
         merges matching clusters, with a Haiku confirmation check
         (is_single_event) before committing each merge
      7. finish_cron_run() with token usage
      8. cleanup_old_articles() — 7-day TTL
    """
    print("\n========================================")
    print("NEWS HUB CRON JOB STARTING")
    print("========================================\n")

    run_id = start_cron_run()
    reset_usage()

    articles_fetched = 0
    articles_dropped = 0
    articles_stored = 0
    borderline_queue = []
    haiku_queue = []
    clusters = []
    synthesised = []
    stored_clusters = []
    clusters_before_merge = 0
    clusters_after_merge = 0
    merges_accepted = 0
    merges_rejected = 0

    try:
        # Step 1 — Fetch all raw articles
        raw_articles = fetch_all_articles()
        articles_fetched = len(raw_articles)
        print(f"\nFetched: {articles_fetched} raw articles")

        # Step 2 — Load existing data for Gate 1 + Gate 2 dedup
        print("\nLoading existing data for dedup...")
        existing_url_hashes = get_existing_url_hashes()
        existing_simhashes = get_existing_simhashes()
        existing_simhashes += [
            compute_title_simhash(title)
            for title in get_existing_cluster_titles()
        ]
        print(f"Loaded {len(existing_url_hashes)} url hashes")
        print(f"Loaded {len(existing_simhashes)} simhashes")

        # Step 3 — Gate 1 + Gate 2 dedup, then keyword scoring and routing
        print("\n--- Running dedup, scoring and routing ---")

        for article in raw_articles:
            title = article.get('title', '')
            url = article.get('url', '')
            body = article.get('body', '')
            tab = article.get('tab', 'top_stories')

            if not title or not url:
                articles_dropped += 1
                continue

            # Gate 1 + Gate 2
            dedup_result = check_duplicate(
                url=url,
                title=title,
                existing_url_hashes=existing_url_hashes,
                existing_simhashes=existing_simhashes
            )

            if dedup_result['action'] == 'drop':
                articles_dropped += 1
                print(f"DEDUP DROP ({dedup_result['reason']}): {title[:60]}")
                continue

            # Update in-memory dedup lists so later articles in this batch
            # dedup against ones already seen earlier in the same run
            existing_url_hashes.append(dedup_result['url_hash'])
            existing_simhashes.append(dedup_result['title_simhash'])

            # Keyword score
            score = score_article(title, body, tab)

            if score <= BLOCK_THRESHOLD:
                articles_dropped += 1
                print(f"BLOCKED (score={score}): {title[:60]}")
                continue

            article['keyword_score'] = score
            article['url_hash'] = dedup_result['url_hash']
            article['title_simhash'] = dedup_result['title_simhash']

            if score <= -1:
                article['is_borderline'] = True
                borderline_queue.append(article)
                print(f"BORDERLINE (score={score}): {title[:60]}")
            else:
                preprocessed = preprocess_article(title, body)
                article['clean_body'] = preprocessed['clean_body']
                article['is_borderline'] = False
                haiku_queue.append(article)

        print(f"\nHaiku queue:      {len(haiku_queue)} articles")
        print(f"Borderline queue: {len(borderline_queue)} articles")
        print(f"Blocked/dropped:  {articles_dropped}")

        # Borderline articles bypass clustering and Haiku entirely —
        # stored directly, raw, in the legacy articles table
        print("\n--- Storing borderline articles ---")
        for article in borderline_queue:
            try:
                insert_url_hash(article['url_hash'])
                row = {
                    'url_hash': article['url_hash'],
                    'title_simhash': article['title_simhash'],
                    'tab': article.get('tab', 'top_stories'),
                    'title': article['title'][:512],
                    'summary': '',
                    'url': article['url'],
                    'source_id': article.get('source_id'),
                    'source_name': article.get('source_name', ''),
                    'source_country': article.get('source_country', 'GLOBAL'),
                    'published_at': article.get('published_at'),
                    'is_australia': False,
                    'is_nsw': False,
                    'is_borderline': True,
                    'keyword_score': article.get('keyword_score', 0),
                    'category': '',
                    'cron_run_id': run_id,
                }
                insert_article(row)
                articles_stored += 1
                print(f"BORDERLINE STORED [{article.get('tab')}]: {article['title'][:60]}")
            except Exception as e:
                articles_dropped += 1
                print(f"BORDERLINE STORE ERROR: {e}")

        if haiku_queue:
            # Step 4 — Cluster the haiku queue into story clusters
            print("\n--- Clustering haiku queue into stories ---")
            clusters = cluster_articles(haiku_queue)
            print(f"Grouped {len(haiku_queue)} articles into {len(clusters)} clusters")

            # Step 5, 6, 7 — Synthesise and store each cluster immediately.
            # Each cluster is wrapped in its own try/except so one bad
            # cluster (Haiku error, DB write failure) never discards
            # already-paid-for synthesis work on earlier clusters
            # in this run — see classifier_agent.synthesise_cluster()
            print("\n--- Running Haiku synthesis + storing clusters ---")
            for i, cluster in enumerate(clusters):
                lead_title = cluster[0].get('title', '')[:60]
                print(f"Synthesising cluster {i+1}/{len(clusters)} "
                      f"({len(cluster)} sources): {lead_title}")
                try:
                    synthesis = synthesise_cluster(cluster)

                    if synthesis['is_noise']:
                        print(f"  -> NOISE — skipping")
                        continue

                    # Forced-tab sources (e.g. Financial Times → finance)
                    # override whatever tab Haiku assigned the cluster
                    forced_tab = next(
                        (s['forced_tab'] for s in cluster if s.get('forced_tab')),
                        None
                    )
                    final_tab = forced_tab or synthesis['tab']
                    if forced_tab and forced_tab != synthesis['tab']:
                        print(f"  -> TAB OVERRIDE: Haiku said {synthesis['tab']}, "
                              f"forced to {forced_tab}")

                    top_score = max(s.get('keyword_score', 0) for s in cluster)
                    cluster_row = {
                        'tab': final_tab,
                        'category': synthesis.get('category', ''),
                        'briefing': synthesis.get('briefing', ''),
                        'keyword_score': top_score,
                        'cron_run_id': run_id,
                        'is_borderline': False,
                    }
                    stored_cluster = insert_story_cluster(cluster_row)
                    cluster_id = stored_cluster['id']

                    for source in cluster:
                        insert_url_hash(source['url_hash'])
                        insert_cluster_source({
                            'cluster_id': cluster_id,
                            'title': source['title'][:512],
                            'url': source['url'],
                            'url_hash': source['url_hash'],
                            'source_name': source.get('source_name', ''),
                            'source_country': source.get('source_country', 'GLOBAL'),
                            'published_at': source.get('published_at'),
                            'clean_body': source.get('clean_body', ''),
                        })

                    synthesis['sources'] = cluster
                    synthesised.append(synthesis)
                    stored_clusters.append({
                        'id': cluster_id,
                        'tab': final_tab,
                        'category': synthesis.get('category', ''),
                        'briefing': synthesis.get('briefing', ''),
                        'sources': cluster,
                        'source_count': len(cluster),
                    })
                    articles_stored += len(cluster)
                    print(f"  -> {synthesis['tab']} | {synthesis['briefing'][:60]}")
                except Exception as e:
                    articles_dropped += len(cluster)
                    print(f"CLUSTER SYNTH/STORE ERROR: {e}")
        else:
            print("\nNo articles for Haiku this run")

        # Step 6 — Deferred meta-clustering over THIS run's stored
        # clusters, catching same-event stories the first TF-IDF pass
        # missed. Runs after first-pass storage so a bug here can never
        # discard already-committed clusters.
        clusters_before_merge = len(stored_clusters)
        clusters_after_merge = clusters_before_merge
        try:
            if len(stored_clusters) > 1:
                print("\n--- Meta-clustering: checking for same-event merges ---")
                merge_groups = group_clusters_for_merge(stored_clusters)
                clusters_removed = 0

                for group in merge_groups:
                    if len(group) < 2:
                        continue

                    combined_sources = [s for c in group for s in c['sources']]
                    category_preview = ' + '.join(c['category'] or '(none)' for c in group)
                    print(f"Re-synthesising merge candidate "
                          f"({len(group)} clusters, {len(combined_sources)} sources): "
                          f"{category_preview}")

                    try:
                        resynth = synthesise_cluster(combined_sources)

                        if resynth['is_noise'] or not resynth.get('is_single_event', True):
                            merges_rejected += 1
                            print(f"  -> MERGE REJECTED (not single event) — keeping originals")
                            continue

                        forced_tab = next(
                            (s['forced_tab'] for s in combined_sources if s.get('forced_tab')),
                            None
                        )
                        final_merge_tab = forced_tab or resynth['tab']
                        top_score = max(s.get('keyword_score', 0) for s in combined_sources)

                        merged_row = {
                            'tab': final_merge_tab,
                            'category': resynth.get('category', ''),
                            'briefing': resynth.get('briefing', ''),
                            'keyword_score': top_score,
                            'cron_run_id': run_id,
                            'is_borderline': False,
                        }
                        stored_merged = insert_story_cluster(merged_row)
                        new_cluster_id = stored_merged['id']

                        old_ids = [c['id'] for c in group]
                        reparent_cluster_sources(old_ids, new_cluster_id)
                        delete_story_clusters(old_ids)

                        merges_accepted += 1
                        clusters_removed += len(group) - 1
                        print(f"  -> MERGED into [{final_merge_tab}] "
                              f"{resynth.get('category', '')} "
                              f"({len(group)} clusters -> 1, {len(combined_sources)} sources)")
                    except Exception as e:
                        merges_rejected += 1
                        print(f"MERGE ERROR: {e}")

                clusters_after_merge = clusters_before_merge - clusters_removed
                print(f"\nMeta-clustering: {merges_accepted} merged, "
                      f"{merges_rejected} rejected")
        except Exception as e:
            print(f"META-CLUSTERING FAILED (first-pass clusters unaffected): {e}")

        # Step 7 — Final summary + finish_cron_run with token usage
        noise_dropped = len(haiku_queue) - sum(len(c['sources']) for c in synthesised)

        print("\n========================================")
        print(f"CRON JOB COMPLETE")
        print(f"Fetched:      {articles_fetched}")
        print(f"Dropped:      {articles_dropped}")
        print(f"Stored:       {articles_stored}")
        print(f"  Clusters:   {clusters_after_merge} "
              f"(before merge: {clusters_before_merge})")
        print(f"  Merges:     {merges_accepted} accepted, {merges_rejected} rejected")
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
            noise_dropped=noise_dropped
        )

        # Step 8 — Cleanup old articles/clusters (7-day TTL)
        print("\n--- Running 7-day TTL cleanup ---")
        cleanup_old_articles()

    except Exception as e:
        print(f"\nCRON JOB FAILED: {e}")
        usage = get_usage_summary()
        noise_dropped = len(haiku_queue) - sum(len(c['sources']) for c in synthesised)
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
            noise_dropped=noise_dropped
        )
        raise


if __name__ == '__main__':
    run_cron()
