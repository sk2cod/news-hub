from agents.classifier_agent import classify_batch
from agents.analysis_agent import analyse_article, quick_analyse_article
from db.queries import (
    insert_analysis,
    get_analysis,
    get_borderline_analysis,
    insert_borderline_analysis
)
from ingester.budget_guard import print_usage_summary


def run_classification_crew(preprocessed_articles: list) -> list:
    """
    Run the Haiku classification crew on a batch of
    preprocessed articles.

    Input:  list of dicts with 'structured_input' key
    Output: list of dicts with classification fields added
    """
    print(f"\n=== Classification Crew starting ===")
    print(f"Articles to classify: {len(preprocessed_articles)}")

    classified = classify_batch(preprocessed_articles)

    print(f"Articles after noise filter: {len(classified)}")
    print_usage_summary()
    print(f"=== Classification Crew done ===\n")

    return classified


def run_analysis_crew(
    article_id: str,
    title: str,
    body: str,
    source_name: str
) -> dict:
    """
    Run the Sonnet deep analysis crew on a single article.
    Checks cache first — never calls Sonnet twice for same article.

    Returns analysis dict or empty dict if budget exceeded.
    """
    print(f"\n=== Analysis Crew starting ===")
    print(f"Article: {title[:60]}")

    existing = get_analysis(article_id)
    if existing:
        print(f"Cache hit — returning stored analysis")
        print(f"=== Analysis Crew done (cached) ===\n")
        return existing

    print(f"Cache miss — running Sonnet analysis")
    result = analyse_article(article_id, title, body, source_name)

    if not result:
        print(f"Analysis failed or budget exceeded")
        print(f"=== Analysis Crew done (failed) ===\n")
        return {}

    saved = insert_analysis(result)
    print_usage_summary()
    print(f"=== Analysis Crew done ===\n")

    return saved


def run_quick_analysis_crew(
    article_id: str,
    title: str,
    body: str,
    source_name: str
) -> dict:
    """
    Run Haiku quick analysis on a borderline article.
    Checks cache first — never calls Haiku twice for same article.

    Returns analysis dict or empty dict if budget exceeded.
    """
    print(f"\n=== Quick Analysis Crew starting ===")
    print(f"Article: {title[:60]}")

    existing = get_borderline_analysis(article_id)
    if existing:
        print(f"Cache hit — returning stored quick analysis")
        print(f"=== Quick Analysis Crew done (cached) ===\n")
        return existing

    print(f"Cache miss — running Haiku quick analysis")
    result = quick_analyse_article(article_id, title, body, source_name)

    if not result:
        print(f"Quick analysis failed or budget exceeded")
        print(f"=== Quick Analysis Crew done (failed) ===\n")
        return {}

    saved = insert_borderline_analysis(result)
    print_usage_summary()
    print(f"=== Quick Analysis Crew done ===\n")

    return saved