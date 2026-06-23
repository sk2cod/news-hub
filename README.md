# 📰 Intelligent News Hub

A production-grade AI-powered personal news briefing system built with Claude, CrewAI, and Streamlit. Fetches news from 17 RSS feeds and Tavily, filters noise deterministically, classifies and summarises using Claude Haiku, and provides on-demand deep analysis using Claude Sonnet.

---

## Vision

A personal news briefing assistant — like a PA preparing a morning brief. The system monitors all sources, filters noise, and presents concise AI-written briefings. The user reads summaries, not raw articles. Sources are available as reference but not the primary content.

---

## Current Version: v1.2

### What it does
- Fetches from 17 RSS feeds + Tavily across 6 topic tabs every run
- Drops duplicates and spam deterministically before any LLM involvement
- Routes articles through a three-tier scoring system
- Uses Claude Haiku to classify, write bullet-point summaries, and assign category labels
- Stores everything in Supabase with 7-day TTL
- Displays a Streamlit UI with 7 tabs
- On-demand Quick Analysis (Haiku) and Deep Analysis (Sonnet) per article — both cached

### Next version: v2.0 (planned)
Story clustering and synthesis — group multiple sources covering the same event into one synthesised briefing card. See V2.0 BRIEF section at the bottom of this file.

---

## Architecture Overview

```
RSS feeds + Tavily (17 sources)
    ↓
Title filter (category pages dropped — free, no LLM)
    ↓
Gate 1: URL SHA-256 hash (exact duplicate check)
    ↓
Gate 2: SimHash title (near-duplicate headline check)
    ↓
Gate 3: TF-IDF cosine similarity (same-story different-source check)
    ↓
Gate 4: Keyword scoring
    score ≤ -5     → BLOCKED completely (spam)
    score -4 to -1 → BORDERLINE tab (raw display, no LLM)
    score ≥ 0      → Claude Haiku (classify + bullet summary)
    ↓
Supabase PostgreSQL (7-day TTL)
    ↓
Streamlit UI (reads only, never triggers ingest)
    ↓
On-demand: Quick Analysis (Haiku) · Deep Analysis (Sonnet)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM framework | CrewAI |
| Classification + summary | Claude Haiku 4.5 |
| Deep analysis | Claude Sonnet 4.5 |
| Quick analysis | Claude Haiku 4.5 |
| Database | Supabase (PostgreSQL) |
| News discovery | Tavily (topic=news, days=1) + RSS feedparser |
| Exact dedup | SHA-256 URL hashing |
| Near-dedup | SimHash (Hamming distance ≤ 3) |
| Semantic dedup | TF-IDF cosine similarity (sklearn) |
| Named entity detection | spaCy en_core_web_sm |
| UI | Streamlit |
| Scheduling | GitHub Actions (7am + 6pm AEST) |
| Hosting | Streamlit Community Cloud (UI) |

---

## Critical Dependency Constraints

These are non-negotiable — changing them breaks the app:

- **Python 3.11** — required
- **supabase==2.3.4** — NOT 2.4.0, breaks with newer httpx
- **httpx==0.24.1** — pinned, newer versions break supabase client
- **gotrue==2.4.2** — pinned for same reason
- **setuptools<81.0.0** — pinned at 80.10.2, newer versions remove pkg_resources which breaks CrewAI
- **crewai==0.80.0** — NOT 0.63.0, too old for Python 3.11
- **spacy model** — installed via wheel URL, NOT `python -m spacy download`
  ```
  en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
  ```

---

## Design Constraints

- **Single user** — no authentication, no per-user tracking
- **Low complexity** — no Docker, no Celery, no Redis
- **Low cost** — Supabase free tier, Streamlit Community Cloud free, GitHub Actions free
- **No SQLAlchemy** — use supabase-py client only for all DB operations
- **No raw SQL from Python** — all DB operations via supabase-py table API
- **Schema changes** — run manually in Supabase SQL Editor, never from Python
- **Async jobs** — use Streamlit BackgroundTasks, not Celery
- **Prompt caching** — Haiku system prompt uses `cache_control: ephemeral`

---

## Project Structure

```
news-hub/
├── app.py                              ← Streamlit entry point (UI only, never triggers ingest)
├── requirements.txt                    ← All pinned dependencies
├── seeds.sql                           ← Supabase source seed data (run once manually)
├── .github/
│   └── workflows/
│       └── cron.yml                    ← GitHub Actions: runs at 7am + 6pm AEST
├── agents/
│   ├── classifier_agent.py             ← Haiku classification with prompt caching
│   ├── analysis_agent.py               ← Sonnet deep analysis + Haiku quick analysis
│   ├── crew.py                         ← CrewAI orchestration functions
│   └── prompts/
│       ├── classifier_system.txt       ← Haiku system prompt (cached, tune here)
│       ├── quick_analysis_system.txt   ← Haiku quick analysis prompt
│       └── analysis_system.txt         ← Sonnet deep analysis prompt
├── components/
│   ├── article_card.py                 ← Compact article card UI component
│   ├── analysis_panel.py               ← Deep analysis display component
│   └── run_dashboard.py                ← Ingestion stats and cost tracker
├── db/
│   └── queries.py                      ← All Supabase operations (read + write)
└── ingester/
    ├── cron.py                         ← Main pipeline orchestrator (entry point)
    ├── fetcher.py                      ← RSS + Tavily fetching
    ├── dedup.py                        ← 3-gate dedup pipeline
    ├── preprocessor.py                 ← Boilerplate strip, truncation, entity detection
    ├── keyword_scores.py               ← Tab keyword scoring (tier1/tier2/blocklist)
    └── budget_guard.py                 ← Token cost protection and tracking
```

---

## Data Flow Detail

### Ingest pipeline (cron.py orchestrates)

```
1. fetcher.py
   - fetch_rss_articles() → 17 RSS feeds, 15 entries each, title filter applied
   - fetch_tavily_articles() → 6 queries (one per tab), 10 results each
   - Returns flat list of raw article dicts with: title, url, body, source_id, tab

2. For each article:
   a. keyword_scores.score_article(title, body, tab) → integer score
      - score ≤ -5  → BLOCKED, never stored
      - score -4 to -1 → BORDERLINE queue
      - score ≥ 0  → continue to dedup

   b. dedup.check_duplicate(url, title, body, existing_*) → {action, reason, url_hash, title_simhash, parent_story_id}
      - Gate 1: SHA-256 URL hash → drop if seen
      - Gate 2: SimHash title → drop if Hamming distance ≤ 3
      - Gate 3: TF-IDF cosine similarity
          > 0.85 → check for development signals → keep as update OR drop
          0.60-0.85 → keep as related story
          < 0.60 → new story, keep

   c. preprocessor.preprocess_article(title, body) → {clean_body, structured_input, entities}
      - Strip boilerplate (regex)
      - Truncate to 500 tokens
      - Extract named entities (spaCy)
      - Format structured input for Haiku

3. BORDERLINE articles → stored directly with is_borderline=True, no Haiku

4. Haiku queue → classifier_agent.classify_batch()
   - Sends structured_input to Haiku
   - System prompt cached via cache_control: ephemeral
   - Returns: tab, category, summary (bullet points), is_noise, is_australia, is_nsw
   - Noise articles dropped

5. Classified articles → stored to Supabase articles table

6. finish_cron_run() → writes token usage and cost to cron_runs table

7. cleanup_old_articles() → deletes articles + url_hashes older than 7 days
```

### UI layer (app.py)

```
- Reads from Supabase only — never triggers ingest
- get_articles_by_tab_paginated(tab, limit=10, offset) → articles for each tab
- get_borderline_articles() → grouped by tab for borderline tab
- Refresh Feed button → calls run_cron() directly on Streamlit server
- Quick Analysis button → run_quick_analysis_crew() → Haiku → cached in analysis_results
- Deep Analysis button → run_analysis_crew() → Sonnet → cached in analysis_results
```

---

## Database Schema

### articles table (main)
```sql
id               UUID PRIMARY KEY
url_hash         TEXT UNIQUE (references url_hashes)
title_simhash    TEXT
tab              tab_name ENUM (geopolitics|top_stories|finance|ai_tech|sports_ent|australia)
title            VARCHAR(512)
summary          TEXT (bullet points: "- bullet1\n- bullet2\n- bullet3")
clean_body       TEXT (preprocessed article body for Sonnet)
url              TEXT
source_id        VARCHAR(64) (references sources)
source_name      VARCHAR(128)
source_country   VARCHAR(8)
published_at     TIMESTAMPTZ
ingested_at      TIMESTAMPTZ DEFAULT NOW()
is_australia     BOOLEAN
is_nsw           BOOLEAN
is_borderline    BOOLEAN DEFAULT FALSE
keyword_score    INTEGER
category         VARCHAR(64) (1-3 word label e.g. "Iran War", "Critical Minerals")
parent_story_id  UUID (references articles, for story updates)
cron_run_id      UUID (references cron_runs)
```

### analysis_results table
```sql
id               UUID PRIMARY KEY
article_id       UUID UNIQUE (references articles)
sentiment        TEXT (positive|negative|neutral|mixed) -- legacy, not used in v1.2
bias_score       SMALLINT -- legacy, not used in v1.2
bias_direction   TEXT -- repurposed: stores quick analysis verdict (worth reading|skip|borderline)
context_summary  TEXT -- stores formatted sections: **Background:**\n\n**Significance:**\n\n etc
key_entities     TEXT -- comma separated for Sonnet, reason phrase for Haiku quick analysis
analysed_at      TIMESTAMPTZ
model_used       VARCHAR(64) -- 'claude-sonnet-4-5' or 'claude-haiku-4-5'
```

Note: analysis_results is shared between Deep Analysis (Sonnet) and Quick Analysis (Haiku).
Distinguished by model_used field. get_analysis() filters by claude-sonnet-4-5.
get_borderline_analysis() filters by claude-haiku-4-5.

### url_hashes table
```sql
url_hash    TEXT PRIMARY KEY
seen_at     TIMESTAMPTZ DEFAULT NOW()
```

### sources table
```sql
id              VARCHAR(64) PRIMARY KEY
name            VARCHAR(128)
country         VARCHAR(8)
feed_url        TEXT
tab_affinity    tab_name
active          BOOLEAN DEFAULT TRUE
last_fetched_at TIMESTAMPTZ
```

### cron_runs table
```sql
id                   UUID PRIMARY KEY
started_at           TIMESTAMPTZ
finished_at          TIMESTAMPTZ
articles_fetched     INTEGER
articles_dropped     INTEGER
articles_stored      INTEGER
borderline_stored    INTEGER
noise_dropped        INTEGER
status               VARCHAR(16) (running|complete|failed)
error_msg            TEXT
haiku_input_tokens   INTEGER
haiku_output_tokens  INTEGER
sonnet_input_tokens  INTEGER
sonnet_output_tokens INTEGER
total_cost_usd       NUMERIC(10,6)
```

---

## Prompts

### classifier_system.txt (Haiku — runs every cron job)
Located: `agents/prompts/classifier_system.txt`
Purpose: Classify article into tab, write bullet summary, assign category label
Output JSON: `{tab, category, summary, is_noise, is_australia, is_nsw}`
Cached via: `cache_control: ephemeral` — saves ~90% input tokens per batch

### quick_analysis_system.txt (Haiku — on demand)
Located: `agents/prompts/quick_analysis_system.txt`
Purpose: Add context beyond summary, give worth reading/skip/borderline verdict
Output JSON: `{summary, verdict, tab, reason}`
Stored in: analysis_results with model_used='claude-haiku-4-5'

### analysis_system.txt (Sonnet — on demand)
Located: `agents/prompts/analysis_system.txt`
Purpose: Deep background briefing — Background, Significance, Implications, Perspectives
Input: article title + clean_body (full preprocessed text)
Output JSON: `{background, significance, implications, perspectives, key_entities}`
Stored in: analysis_results with model_used='claude-sonnet-4-5'

---

## Keyword Scoring System

Located: `ingester/keyword_scores.py`

Each tab has three lists:
- **tier1** keywords → +3 points each (strong signal)
- **tier2** keywords → +1 point each (moderate signal)
- **blocklist** keywords → -5 points each (spam/noise signal)

Routing thresholds in `ingester/cron.py`:
```python
HAIKU_THRESHOLD = 0      # score ≥ 0 → Haiku
BORDERLINE_MIN = -4      # score -4 to -1 → borderline tab
BLOCK_THRESHOLD = -5     # score ≤ -5 → blocked completely
```

---

## RSS Sources (17 feeds)

| Tab | Sources |
|---|---|
| geopolitics | Reuters World (Google News), BBC World, Al Jazeera |
| top_stories | Reuters Top (Google News), BBC Top, AP News (Google News) |
| finance | Reuters Business (Google News), CNBC, Financial Times |
| ai_tech | MIT Technology Review, Ars Technica, Wired |
| sports_ent | Variety |
| australia | ABC News AU, The Guardian AU, Sydney Morning Herald, SBS News |

Plus Tavily queries for each tab (10 results per query per run).

---

## Tabs

| Tab | Key | Content |
|---|---|---|
| 🌍 Geopolitics | geopolitics | International relations, wars, diplomacy |
| 📰 Top Stories | top_stories | Major global breaking news |
| 💹 Finance | finance | Markets, central banks, earnings |
| 🤖 AI & Tech | ai_tech | Frontier models, AI policy, chips |
| 🏆 Entertainment | sports_ent | Film, music, awards, celebrity culture — no sports |
| 🇦🇺 Australia | australia | National + NSW/Sydney news |
| ⚠️ Borderline | borderline | Low-score articles, raw display, no Haiku |

Tab priority order (if story fits multiple): australia > ai_tech > geopolitics > finance > top_stories > sports_ent

---

## Budget Guard

Located: `ingester/budget_guard.py`

Daily limits:
```python
DAILY_LIMITS = {
    'haiku_input_tokens':  400_000,
    'haiku_output_tokens': 100_000,
    'sonnet_input_tokens':  20_000,
    'sonnet_output_tokens': 10_000,
}
```

Approximate costs per run (twice daily):
- Haiku classification: ~$0.04-0.07 per run
- Sonnet deep analysis: ~$0.015 per click (cached after first)
- Monthly total: ~$3-5

---

## Deployment

### GitHub Actions (cron scheduling)
File: `.github/workflows/cron.yml`
Schedule: `0 21 * * *` (7am AEST) and `0 8 * * *` (6pm AEST)
Also supports manual trigger via workflow_dispatch

### Streamlit Community Cloud (UI)
Repository: sk2cod/news-hub
Branch: main
Entry point: app.py
Secrets: Set in Streamlit Cloud dashboard (same 5 keys as .env)

### Environment Variables Required
```
SUPABASE_URL=https://qbedmqnnazmnwunvfaws.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://postgres:password@db.qbedmqnnazmnwunvfaws.supabase.co:5432/postgres
ANTHROPIC_API_KEY=your-anthropic-key
TAVILY_API_KEY=your-tavily-key
```

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run cron job manually
python -m ingester.cron

# Run Streamlit UI
streamlit run app.py
```

---

## Known Issues and Workarounds

1. **Paywalled sources (FT, GuruFocus)** — return thin body text, summaries will be short
2. **Video articles (Sky News AU)** — no body text, summary based on title only
3. **Reuters RSS** — original feeds return 0 entries, using Google News site: queries instead
4. **spaCy model download** — use wheel URL in requirements.txt, not `python -m spacy download`
5. **Tavily time_range parameter** — use `days=1` not `time_range='day'`
6. **analysis_results shared table** — Sonnet and Haiku both write here, distinguished by model_used

---

## V2.0 BRIEF — Intelligent News Briefing Digest

### The Problem with v1.2
The same news event appears as multiple separate cards from different sources. Three articles about "Trump loves inflation" appear as three separate cards. The user has to read multiple cards to get the full picture.

### The Vision
One synthesised briefing per news event. Multiple sources combined by Haiku into one concise bullet-point briefing. Sources listed as small clickable chips. No need to visit individual articles.

### Example Output (v2.0 briefing card)
```
🆕 NEW · 34m ago · Finance

US Inflation: Trump declares "I love the inflation"

- Trump stated he "loves the inflation" despite US prices rising at 
  fastest rate in three years — 4.2% year-on-year in May
- Federal Reserve officials now expected to hold rates higher for longer 
  with cuts pushed to late 2026
- American households facing estimated $510 additional annual costs from 
  current inflation trajectory  
- Markets reacted with mixed signals as geopolitical tensions from Iran 
  war compound inflation concerns

📰 BBC  📰 CNBC  📰 Sydney Morning Herald

⚡ Quick Analysis    🔍 Deep Analysis
```

### What Changes in v2.0

**1. Story clustering in dedup.py**
- Current: TF-IDF similarity > 0.85 → DROP
- v2.0: TF-IDF similarity 0.5-0.85 → GROUP into cluster (not drop)
- Similarity < 0.5 → genuinely different story, single-article cluster

**2. Haiku task changes**
- Current: classify one article at a time
- v2.0: receive cluster of 2-5 articles, synthesise one briefing
- New prompt: `agents/prompts/synthesis_system.txt`
- New function: `agents/classifier_agent.synthesise_cluster()`

**3. New database tables (keep articles table for reference)**

```sql
-- One row per story event
CREATE TABLE story_clusters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tab             tab_name NOT NULL,
    category        VARCHAR(64),
    briefing        TEXT,  -- bullet point synthesis
    keyword_score   INTEGER,
    cron_run_id     UUID REFERENCES cron_runs(id),
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    is_borderline   BOOLEAN DEFAULT FALSE
);

-- One row per source article within a cluster
CREATE TABLE cluster_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id      UUID REFERENCES story_clusters(id) ON DELETE CASCADE,
    title           VARCHAR(512),
    url             TEXT,
    url_hash        TEXT UNIQUE,
    source_name     VARCHAR(128),
    source_country  VARCHAR(8),
    published_at    TIMESTAMPTZ,
    clean_body      TEXT
);
```

**4. New UI component: `components/briefing_card.py`**
- Replaces article_card.py
- Shows: category label, synthesised briefing bullets, source chips
- Source chips are small clickable links to original articles
- Quick Analysis and Deep Analysis buttons unchanged

**5. Deep Analysis in v2.0**
- Sonnet receives ALL source clean_body texts concatenated
- Much richer input than current single-article approach
- Prompt in analysis_system.txt updated to handle multiple sources

### What Stays the Same in v2.0
- All RSS + Tavily fetching logic
- URL hash dedup (Gate 1)
- SimHash dedup (Gate 2)
- Keyword scoring and blocking
- Budget guard
- Borderline tab concept (raw display, no synthesis)
- 7 tab structure
- GitHub Actions scheduling
- Streamlit Cloud deployment
- All 5 environment variables

### Files Changed in v2.0
```
ingester/dedup.py          → add cluster grouping logic
ingester/cron.py           → rebuild pipeline around clusters
agents/prompts/synthesis_system.txt  → NEW Haiku synthesis prompt
agents/classifier_agent.py → add synthesise_cluster() function
agents/analysis_agent.py   → update Sonnet to receive all source bodies
db/queries.py              → add queries for story_clusters + cluster_sources
components/briefing_card.py → NEW replaces article_card.py
app.py                     → update to use briefing cards
```

### Branch Strategy
```bash
git checkout -b v2.0-briefing-digest
# All v2.0 work on this branch
# main stays at v1.2 — deployed and stable
# Merge to main only when v2.0 confirmed working
```

### Cluster Size Limits
- Maximum 5 sources per cluster
- If >5 articles cover same story, keep top 5 by keyword score
- Single-source stories still go through synthesis pipeline (consistent)

### Cost Impact
- v1.2: ~100-150 Haiku calls per run → ~$0.06
- v2.0: ~50-80 cluster calls per run → ~$0.04
- Cost decreases because many articles merge into fewer cluster calls

---

## Version History

| Version | Description |
|---|---|
| v1.0 | Base working version — ingest, classify, Streamlit UI |
| v1.1 | Category labels, NEW badge, dashboard, cost tracker, borderline tab |
| v1.2 | Bullet summaries, deep analysis redesign, clean_body storage |
| v2.0 | Story clustering and synthesis (planned) |
