import streamlit as st
from dotenv import load_dotenv
from db.queries import (
    get_story_clusters_by_tab_paginated,
    get_analysis,
    get_cluster_quick_analysis,
    get_last_cron_run,
    get_borderline_articles,
    get_recent_cron_runs,
    get_borderline_analysis
)
from components.briefing_card import render_briefing_card
from components.analysis_panel import render_analysis_panel
from agents.crew import run_analysis_crew, run_quick_analysis_crew, run_cluster_quick_analysis_crew
from components.run_dashboard import render_run_dashboard
from ingester.cron import run_cron

load_dotenv()

st.set_page_config(
    page_title="Intelligent News Hub",
    page_icon="📰",
    layout="wide"
)

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("📰 Intelligent News Hub")

last_run = get_last_cron_run()
latest_run_id = last_run.get('id') if last_run else None
col_header, col_button = st.columns([4, 1])

with col_header:
    if last_run:
        from datetime import datetime, timezone, timedelta
        sydney_tz = timezone(timedelta(hours=10))
        finished_utc = last_run.get('finished_at', '')
        if finished_utc:
            dt = datetime.fromisoformat(finished_utc.replace('Z', '+00:00'))
            dt_sydney = dt.astimezone(sydney_tz)
            formatted = dt_sydney.strftime('%d %b %Y %I:%M %p AEST')
        else:
            formatted = 'Unknown'
        st.caption(
            f"Last updated: {formatted} · "
            f"{last_run.get('articles_stored', 0)} new articles stored"
        )
    else:
        st.caption("Feed not yet populated — run the cron job first")

with col_button:
    if st.button("🔄 Refresh Feed", help="Fetch latest news from all sources"):
        with st.spinner("Fetching latest news..."):
            try:
                run_cron()
                st.success("Feed refreshed successfully")
                st.rerun()
            except Exception as e:
                st.error(f"Refresh failed: {e}")

with st.expander("📊 Ingestion Dashboard & Cost Tracker", expanded=False):
    cron_runs = get_recent_cron_runs(limit=10)
    render_run_dashboard(cron_runs)

st.divider()

# ─── Tab definitions ──────────────────────────────────────────────────────────

TABS = {
    '🌍 Geopolitics':  'geopolitics',
    '📰 Top Stories':  'top_stories',
    '💹 Finance':      'finance',
    '🤖 AI & Tech':    'ai_tech',
    '🏆 Sports & Ent': 'sports_ent',
    '🇦🇺 Australia':   'australia',
    '⚠️ Borderline':   'borderline',
}

TAB_LABELS = {
    'geopolitics': '🌍 Geopolitics',
    'top_stories': '📰 Top Stories',
    'finance':     '💹 Finance',
    'ai_tech':     '🤖 AI & Tech',
    'sports_ent':  '🏆 Sports & Ent',
    'australia':   '🇦🇺 Australia',
}

tabs = st.tabs(list(TABS.keys()))

# ─── Genuine tabs — one briefing card per story cluster ───────────────────────

for tab_ui, (tab_label, tab_key) in zip(tabs[:6], list(TABS.items())[:6]):
    with tab_ui:

        offset_key = f"offset_{tab_key}"
        if offset_key not in st.session_state:
            st.session_state[offset_key] = 0

        clusters = get_story_clusters_by_tab_paginated(
            tab=tab_key,
            limit=10,
            offset=st.session_state[offset_key]
        )

        if not clusters:
            st.info(f"No stories yet for {tab_label}. Run the cron job to populate.")
        else:
            st.caption(
                f"Showing {len(clusters)} stories · "
                f"Page {st.session_state[offset_key] // 10 + 1}"
            )

            for cluster in clusters:
                cluster_id = cluster['id']
                sources = cluster.get('sources', [])
                lead_title = sources[0]['title'] if sources else cluster.get('category', 'Untitled story')

                render_briefing_card(cluster, latest_run_id=latest_run_id)

                # Quick Analysis — Haiku
                quick_key = f"quick_{cluster_id}"
                if st.session_state.get(quick_key):
                    existing_quick = get_cluster_quick_analysis(cluster_id)
                    if existing_quick:
                        verdict = existing_quick.get('bias_direction', 'borderline')
                        summary = existing_quick.get('context_summary', '')
                        reason = existing_quick.get('key_entities', '')
                        if verdict == 'worth reading':
                            st.success(f"✅ Worth reading — {summary}")
                        elif verdict == 'skip':
                            st.warning(f"⏭️ Skip — {reason}")
                        else:
                            st.info(f"🔶 Borderline — {summary}")
                    else:
                        with st.spinner("Running quick analysis with Haiku..."):
                            quick_analysis = run_cluster_quick_analysis_crew(
                                cluster_id=cluster_id,
                                title=lead_title,
                                sources=sources
                            )
                        if quick_analysis:
                            verdict = quick_analysis.get('bias_direction', 'borderline')
                            summary = quick_analysis.get('context_summary', '')
                            reason = quick_analysis.get('key_entities', '')
                            if verdict == 'worth reading':
                                st.success(f"✅ Worth reading — {summary}")
                            elif verdict == 'skip':
                                st.warning(f"⏭️ Skip — {reason}")
                            else:
                                st.info(f"🔶 Borderline — {summary}")
                        else:
                            st.error("Quick analysis failed.")

                # Deep Analysis — Sonnet
                analyse_key = f"analyse_{cluster_id}"
                if st.session_state.get(analyse_key):
                    existing = get_analysis(cluster_id)
                    if existing:
                        render_analysis_panel(existing)
                    else:
                        with st.spinner("Running deep analysis with Claude Sonnet..."):
                            analysis = run_analysis_crew(
                                cluster_id=cluster_id,
                                title=lead_title,
                                sources=sources
                            )
                        if analysis:
                            render_analysis_panel(analysis)
                        else:
                            st.error("Analysis failed or budget limit reached.")

            st.divider()
            col1, col2, col3 = st.columns([1, 2, 1])

            with col1:
                if st.session_state[offset_key] > 0:
                    if st.button("⬅️ Previous 10", key=f"prev_{tab_key}"):
                        st.session_state[offset_key] -= 10
                        st.rerun()

            with col2:
                current_page = (st.session_state[offset_key] // 10) + 1
                st.caption(
                    f"Page {current_page} · "
                    f"showing {st.session_state[offset_key] + 1}–"
                    f"{st.session_state[offset_key] + len(clusters)}"
                )

            with col3:
                if len(clusters) == 10:
                    if st.button("Next 10 ➡️", key=f"next_{tab_key}"):
                        st.session_state[offset_key] += 10
                        st.rerun()

# ─── Borderline tab ───────────────────────────────────────────────────────────

with tabs[6]:
    st.caption(
        "Articles that scored between -4 and -1 on the relevance filter. "
        "Not processed by Haiku. Raw titles only. "
        "Click 'Quick Analysis' to get a Haiku relevance verdict."
    )

    borderline_grouped = get_borderline_articles()
    total_borderline = sum(len(v) for v in borderline_grouped.values())

    if total_borderline == 0:
        st.info("No borderline articles yet. Run the cron job to populate.")
    else:
        st.caption(f"{total_borderline} borderline articles across all categories")

        for tab_key, articles in borderline_grouped.items():
            if not articles:
                continue

            st.markdown(f"#### {TAB_LABELS.get(tab_key, tab_key)} — {len(articles)} articles")

            for article in articles:
                article_id = article['id']
                url = article.get('url', '#')
                title = article.get('title', 'No title')
                source = article.get('source_name', 'Unknown source')
                score = article.get('keyword_score', 0)
                published = article.get('published_at', '')[:10] if article.get('published_at') else ''

                # Compact raw display
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**[{title}]({url})**")
                    st.caption(f"🔸 {source} · score {score} · {published}")
                with col2:
                    if st.button(
                        "⚡ Quick Analysis",
                        key=f"btn_quick_{article_id}",
                        help="Run Haiku quick relevance check"
                    ):
                        st.session_state[f"quick_{article_id}"] = True

                # Show quick analysis if triggered
                quick_key = f"quick_{article_id}"
                if st.session_state.get(quick_key):
                    existing = get_borderline_analysis(article_id)
                    if existing:
                        verdict = existing.get('bias_direction', 'borderline')
                        summary = existing.get('context_summary', '')
                        reason = existing.get('key_entities', '')
                        if verdict == 'worth reading':
                            st.success(f"✅ Worth reading — {summary}")
                        elif verdict == 'skip':
                            st.warning(f"⏭️ Skip — {reason}")
                        else:
                            st.info(f"🔶 Borderline — {summary}")
                    else:
                        with st.spinner("Running quick analysis with Haiku..."):
                            analysis = run_quick_analysis_crew(
                                article_id=article_id,
                                title=title,
                                body='',
                                source_name=source
                            )
                        if analysis:
                            verdict = analysis.get('bias_direction', 'borderline')
                            summary = analysis.get('context_summary', '')
                            reason = analysis.get('key_entities', '')
                            if verdict == 'worth reading':
                                st.success(f"✅ Worth reading — {summary}")
                            elif verdict == 'skip':
                                st.warning(f"⏭️ Skip — {reason}")
                            else:
                                st.info(f"🔶 Borderline — {summary}")
                        else:
                            st.error("Quick analysis failed.")

                st.markdown(
                    "<hr style='margin: 4px 0; border: none; "
                    "border-top: 1px solid #e0e0e0;'>",
                    unsafe_allow_html=True
                )
