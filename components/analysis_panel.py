import streamlit as st


def render_bias_bar(bias_score: int):
    """
    Render a visual left-right bias bar using Streamlit progress.
    Score ranges from -5 (left) to +5 (right), 0 is centre.
    """
    # Convert -5 to +5 scale to 0 to 100 for progress bar
    normalised = int((bias_score + 5) * 10)

    if bias_score < -2:
        label = f"⬅️ Left-leaning ({bias_score})"
        color = "bias-left"
    elif bias_score > 2:
        label = f"➡️ Right-leaning (+{bias_score})"
        color = "bias-right"
    else:
        label = f"⚖️ Centre / Neutral ({bias_score})"
        color = "bias-centre"

    st.caption(f"**Editorial bias:** {label}")
    st.progress(normalised)


def render_sentiment_badge(sentiment: str):
    """Render a coloured sentiment badge."""
    badges = {
        'positive': '🟢 Positive',
        'negative': '🔴 Negative',
        'neutral':  '⚪ Neutral',
        'mixed':    '🟡 Mixed',
    }
    badge = badges.get(sentiment, '⚪ Unknown')
    st.caption(f"**Sentiment:** {badge}")


def render_analysis_panel(analysis: dict):
    """
    Render the full Sonnet deep analysis panel for an article.
    Called after analysis is retrieved from database or freshly generated.
    """
    if not analysis:
        st.warning("Analysis not available.")
        return

    st.markdown("---")
    st.markdown("#### 🧠 Deep Analysis")

    # Sentiment and bias row
    col1, col2 = st.columns(2)
    with col1:
        render_sentiment_badge(analysis.get('sentiment', 'neutral'))
    with col2:
        bias_score = analysis.get('bias_score', 0)
        if isinstance(bias_score, (int, float)):
            render_bias_bar(int(bias_score))

    # Bias direction
    bias_direction = analysis.get('bias_direction', '')
    if bias_direction and bias_direction.lower() != 'neutral':
        st.caption(f"**Bias direction:** {bias_direction}")

    # Context summary
    context = analysis.get('context_summary', '')
    if context:
        st.markdown("**Context & significance**")
        st.write(context)

    # Key entities
    entities = analysis.get('key_entities', '')
    if entities:
        st.markdown("**Key entities**")
        entity_list = [e.strip() for e in entities.split(',') if e.strip()]
        cols = st.columns(min(len(entity_list), 4))
        for i, entity in enumerate(entity_list[:8]):
            with cols[i % 4]:
                st.markdown(
                    f"<span style='background-color:#1e3a5f;"
                    f"padding:2px 8px;border-radius:12px;"
                    f"font-size:12px;color:#ffffff'>{entity}</span>",
                    unsafe_allow_html=True
                )

    # Analysis metadata
    model = analysis.get('model_used', '')
    analysed_at = analysis.get('analysed_at', '')
    if model or analysed_at:
        st.caption(f"Analysed by {model} · {analysed_at[:10] if analysed_at else ''}")

    st.markdown("---")