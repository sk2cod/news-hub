import streamlit as st
from datetime import datetime, timezone


def time_ago(published_at: str) -> str:
    """Convert a UTC timestamp to a human-readable 'X ago' string."""
    if not published_at:
        return 'Unknown time'
    try:
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(
                published_at.replace('Z', '+00:00')
            )
        now = datetime.now(timezone.utc)
        diff = now - published_at
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
        return 'Unknown time'


def render_article_card(article: dict, show_analysis_button: bool = True):
    """
    Render a compact single article card in Streamlit.
    """
    article_id = article['id']
    url = article.get('url', '#')
    title = article.get('title', 'No title')
    summary = article.get('summary', '')
    source = article.get('source_name', 'Unknown source')
    timestamp = time_ago(article.get('published_at'))

    # Badges inline
    badges = []
    if article.get('is_australia'):
        badges.append('🇦🇺')
    if article.get('is_nsw'):
        badges.append('📍 NSW')
    if article.get('parent_story_id'):
        badges.append('🔄 Update')
    badge_str = ' '.join(badges)

    # Meta line — source · time · badges
    score = article.get('keyword_score', 0)
    meta = f"🔸 {source} · {timestamp} · score {score}"
    if badge_str:
        meta += f" · {badge_str}"
    st.caption(meta)

    # Title as clickable link
    st.markdown(f"**[{title}]({url})**")

    # Summary — smaller text
    if summary:
        st.caption(summary)

        # Analysis buttons — side by side
        if show_analysis_button:
            btn_col1, btn_col2 = st.columns([1, 1])
            with btn_col1:
                if st.button(
                        "⚡ Quick Analysis",
                        key=f"btn_quick_{article_id}",
                        help="Run Haiku quick analysis — fast and cheap"
                ):
                    st.session_state[f"quick_{article_id}"] = True
            with btn_col2:
                if st.button(
                        "🔍 Deep Analysis",
                        key=f"btn_analyse_{article_id}",
                        help="Run Sonnet deep analysis — detailed and thorough"
                ):
                    st.session_state[f"analyse_{article_id}"] = True

    # Thin divider
    st.markdown(
        "<hr style='margin: 6px 0; border: none; "
        "border-top: 1px solid #e0e0e0;'>",
        unsafe_allow_html=True
    )