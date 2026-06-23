import streamlit as st
from datetime import datetime, timezone


def time_ago(cluster: dict) -> str:
    """Use ingested_at for consistent recency display."""
    timestamp = cluster.get('ingested_at')
    if not timestamp:
        return 'Recently'
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(
                timestamp.replace('Z', '+00:00')
            )
        now = datetime.now(timezone.utc)
        diff = now - timestamp
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
    except Exception:
        return 'Recently'


def render_source_chips(sources: list):
    """Render small clickable chips, one per source article in the cluster."""
    chips = [
        f"📰 [{source.get('source_name', 'Unknown')}]({source.get('url', '#')})"
        for source in sources
    ]
    st.markdown('&nbsp;&nbsp;'.join(chips))


def render_briefing_card(
    cluster: dict,
    show_analysis_button: bool = True,
    latest_run_id: str = None
):
    """
    Render a synthesised story briefing card — one card per news event,
    combining 1-5 sources into a single Haiku-written briefing.
    Replaces the v1.2 per-article card (article_card.py).

    Expects a story_clusters row with an attached 'sources' list
    (cluster_sources rows for that cluster).
    """
    cluster_id = cluster['id']
    sources = cluster.get('sources', [])
    category = cluster.get('category', '')
    briefing = cluster.get('briefing', '')
    score = cluster.get('keyword_score', 0)
    cluster_run_id = cluster.get('cron_run_id')
    timestamp = time_ago(cluster)

    lead_source = sources[0] if sources else {}
    lead_title = lead_source.get('title', 'No title')
    lead_url = lead_source.get('url', '#')

    # Badges
    badges = []
    if latest_run_id and cluster_run_id and str(cluster_run_id) == str(latest_run_id):
        badges.append('🆕 NEW')
    if cluster.get('is_australia'):
        badges.append('🇦🇺')
    if cluster.get('is_nsw'):
        badges.append('📍 NSW')
    badge_str = ' '.join(badges)

    # Meta line — source count replaces the single source name from v1.2
    source_count = len(sources)
    meta = (
        f"📰 {source_count} source{'s' if source_count != 1 else ''} · "
        f"{timestamp} · score {score}"
    )
    if badge_str:
        meta += f" · {badge_str}"
    st.caption(meta)

    # Headline with category prefix — links to the lead source article
    if category:
        st.markdown(f"**{category}:** **[{lead_title}]({lead_url})**")
    else:
        st.markdown(f"**[{lead_title}]({lead_url})**")

    # Synthesised briefing bullets
    if briefing:
        st.markdown(briefing)

    # Source chips
    if sources:
        render_source_chips(sources)

    # Analysis buttons
    if show_analysis_button:
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            if st.button(
                "⚡ Quick Analysis",
                key=f"btn_quick_{cluster_id}",
                help="Run Haiku quick analysis — fast and cheap"
            ):
                st.session_state[f"quick_{cluster_id}"] = True
        with btn_col2:
            if st.button(
                "🔍 Deep Analysis",
                key=f"btn_analyse_{cluster_id}",
                help="Run Sonnet deep analysis — detailed and thorough"
            ):
                st.session_state[f"analyse_{cluster_id}"] = True

    # Thin divider
    st.markdown(
        "<hr style='margin: 6px 0; border: none; "
        "border-top: 1px solid #e0e0e0;'>",
        unsafe_allow_html=True
    )
