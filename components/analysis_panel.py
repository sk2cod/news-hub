import streamlit as st


def render_analysis_panel(analysis: dict):
    """
    Render the full Sonnet deep analysis panel for an article.
    Shows background, significance, implications and perspectives.
    """
    if not analysis:
        st.warning("Analysis not available.")
        return

    st.markdown("---")
    st.markdown("#### 🧠 Deep Analysis")

    context = analysis.get('context_summary', '')
    if context:
        sections = context.split('\n\n')
        for section in sections:
            if not section.strip():
                continue
            clean = section.strip().replace('$', '\\$')
            if clean.startswith('**Background:**'):
                st.markdown('#### 🏛 Background')
                st.markdown(clean.replace('**Background:**', '').strip())
            elif clean.startswith('**Significance:**'):
                st.markdown('#### 🎯 Significance')
                st.markdown(clean.replace('**Significance:**', '').strip())
            elif clean.startswith('**Implications:**'):
                st.markdown('#### 🔮 Implications')
                st.markdown(clean.replace('**Implications:**', '').strip())
            elif clean.startswith('**Perspectives:**'):
                st.markdown('#### 👥 Perspectives')
                st.markdown(clean.replace('**Perspectives:**', '').strip())
            else:
                st.markdown(clean)

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

    # Metadata
    model = analysis.get('model_used', '')
    analysed_at = analysis.get('analysed_at', '')
    if model or analysed_at:
        st.caption(
            f"Analysed by {model} · "
            f"{analysed_at[:10] if analysed_at else ''}"
        )

    st.markdown("---")