import streamlit as st
from datetime import datetime, timezone, timedelta


def format_sydney_time(utc_str: str) -> str:
    """Convert UTC string to Sydney time."""
    if not utc_str:
        return 'Unknown'
    try:
        sydney_tz = timezone(timedelta(hours=10))
        dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        dt_sydney = dt.astimezone(sydney_tz)
        return dt_sydney.strftime('%d %b %Y %I:%M %p')
    except Exception:
        return utc_str[:16]


def render_run_dashboard(cron_runs: list):
    """
    Render ingestion summary and cost tracker dashboard.
    Shows last 10 cron runs with full stats.
    """
    if not cron_runs:
        st.info("No cron runs recorded yet.")
        return

    # ── Latest run summary ────────────────────────────────────────────
    latest = cron_runs[0]

    st.markdown("### 📊 Latest Run Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Fetched", latest.get('articles_fetched', 0))
    with col2:
        st.metric("Stored", latest.get('articles_stored', 0))
    with col3:
        st.metric("Dropped", latest.get('articles_dropped', 0))
    with col4:
        status = latest.get('status', 'unknown')
        icon = '✅' if status == 'complete' else '❌'
        st.metric("Status", f"{icon} {status.capitalize()}")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        genuine = latest.get('articles_stored', 0) - latest.get('borderline_stored', 0)
        st.metric("Genuine", genuine)
    with col6:
        st.metric("Borderline", latest.get('borderline_stored', 0))
    with col7:
        st.metric("Noise dropped", latest.get('noise_dropped', 0))
    with col8:
        cost = latest.get('total_cost_usd', 0)
        st.metric("Cost", f"${cost:.4f}")

    st.caption(f"Run started: {format_sydney_time(latest.get('started_at', ''))} AEST")

    # ── Cost breakdown ────────────────────────────────────────────────
    st.markdown("### 💰 Cost Breakdown")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Claude Haiku**")
        haiku_in = latest.get('haiku_input_tokens', 0)
        haiku_out = latest.get('haiku_output_tokens', 0)
        haiku_cost = (haiku_in / 1000 * 0.00025) + (haiku_out / 1000 * 0.00125)
        st.caption(f"Input tokens: {haiku_in:,}")
        st.caption(f"Output tokens: {haiku_out:,}")
        st.caption(f"Cost: ${haiku_cost:.4f}")

    with col2:
        st.markdown("**Claude Sonnet**")
        sonnet_in = latest.get('sonnet_input_tokens', 0)
        sonnet_out = latest.get('sonnet_output_tokens', 0)
        sonnet_cost = (sonnet_in / 1000 * 0.003) + (sonnet_out / 1000 * 0.015)
        st.caption(f"Input tokens: {sonnet_in:,}")
        st.caption(f"Output tokens: {sonnet_out:,}")
        st.caption(f"Cost: ${sonnet_cost:.4f}")

    # ── Run history table ─────────────────────────────────────────────
    st.markdown("### 📋 Run History (last 10)")

    rows = []
    cumulative_cost = 0.0
    for run in cron_runs:
        cost = float(run.get('total_cost_usd', 0) or 0)
        cumulative_cost += cost
        genuine = (run.get('articles_stored', 0) or 0) - (run.get('borderline_stored', 0) or 0)
        rows.append({
            'Time (AEST)':  format_sydney_time(run.get('started_at', '')),
            'Fetched':      run.get('articles_fetched', 0),
            'Genuine':      genuine,
            'Borderline':   run.get('borderline_stored', 0),
            'Noise':        run.get('noise_dropped', 0),
            'Dropped':      run.get('articles_dropped', 0),
            'Cost ($)':     f"${cost:.4f}",
            'Status':       '✅' if run.get('status') == 'complete' else '❌',
        })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True
    )

    st.caption(f"Cumulative cost across last {len(cron_runs)} runs: **${cumulative_cost:.4f}**")