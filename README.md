# 📰 Intelligent News Hub

A production-grade, AI-powered personal news aggregator built with CrewAI, Claude, and Streamlit. Fetches news from 19 RSS feeds and Tavily, filters junk deterministically, classifies stories using Claude Haiku, and provides on-demand deep analysis using Claude Sonnet.

## What it does

- Aggregates news from 19 RSS feeds + Tavily across 6 topic tabs
- Drops duplicates and spam before any LLM sees them (4-gate pipeline)
- Uses Claude Haiku to classify, summarise, and filter noise
- Stores everything in Supabase with a 7-day TTL
- Displays a clean Streamlit UI with 7 tabs including a Borderline safety net
- On-demand Quick Analysis (Haiku) and Deep Analysis (Sonnet) per article — both cached

## Architecture

```
RSS feeds + Tavily
    ↓
Title filter (category pages dropped free)
    ↓
4-gate dedup pipeline (URL hash → SimHash → TF-IDF → keyword score)
    ↓
Score ≤ -5     → blocked (spam)
Score -4 to -1 → borderline tab (raw, no LLM)
Score ≥ 0      → Claude Haiku (classify + summarise)
    ↓
Supabase PostgreSQL
    ↓
Streamlit UI (reads only, never triggers ingest)
    ↓
On-demand: Quick Analysis (Haiku) · Deep Analysis (Sonnet)
```

## Tabs

| Tab | Coverage |
|---|---|
| 🌍 Geopolitics | International relations, wars, diplomacy |
| 📰 Top Stories | Major breaking news globally |
| 💹 Finance | Markets, central banks, earnings |
| 🤖 AI & Tech | Frontier models, AI policy, research |
| 🏆 Sports & Ent | Sports, film, music, awards |
| 🇦🇺 Australia | National + NSW/Sydney news |
| ⚠️ Borderline | Borderline articles grouped by category |

## Stack

| Layer | Technology |
|---|---|
| LLM framework | CrewAI |
| Classification | Claude Haiku 4.5 |
| Deep analysis | Claude Sonnet 4.5 |
| Database | Supabase (PostgreSQL) |
| News discovery | Tavily + RSS (feedparser) |
| Deduplication | SHA-256 + SimHash + TF-IDF cosine |
| Named entity detection | spaCy en_core_web_sm |
| UI | Streamlit |
| Scheduling | GitHub Actions (7am + 6pm AEST) |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/sk2cod/news-hub.git
cd news-hub
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Environment variables

Create a `.env` file in the root:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres
ANTHROPIC_API_KEY=your-anthropic-key
TAVILY_API_KEY=your-tavily-key
```

### 3. Supabase schema

In Supabase SQL Editor run the full schema from `alembic/versions/001_init.sql` then seed sources:

```sql
-- Run seeds.sql to populate the sources table
```

### 4. Run the cron job

```bash
python -m ingester.cron
```

### 5. Run the UI

```bash
streamlit run app.py
```

## Deployment

- **UI**: Streamlit Community Cloud (free) — connect GitHub repo, set environment variables in secrets
- **Cron**: GitHub Actions — runs `.github/workflows/cron.yml` at 7am and 6pm AEST daily

## Cost

| Component | Cost |
|---|---|
| Supabase | Free tier |
| Streamlit Cloud | Free |
| GitHub Actions | Free |
| Claude Haiku (per cron run) | ~$0.03-0.06 |
| Claude Sonnet (per deep analysis click) | ~$0.015 |
| Tavily | Free tier |
| **Total fixed cost** | **~$0/month** |
| **Variable (API usage)** | **~$2-4/month** |

## Project structure

```
news-hub/
├── app.py                           ← Streamlit entry point
├── requirements.txt
├── seeds.sql                        ← Supabase source seed data
├── agents/
│   ├── classifier_agent.py          ← Haiku classification with prompt caching
│   ├── analysis_agent.py            ← Sonnet deep + Haiku quick analysis
│   ├── crew.py                      ← CrewAI orchestration
│   └── prompts/
│       ├── classifier_system.txt    ← Cached Haiku system prompt
│       └── quick_analysis_system.txt
├── components/
│   ├── article_card.py              ← Compact article card UI
│   └── analysis_panel.py           ← Deep analysis display
├── db/
│   └── queries.py                   ← All Supabase operations
└── ingester/
    ├── cron.py                      ← Main pipeline orchestrator
    ├── fetcher.py                   ← RSS + Tavily fetching
    ├── dedup.py                     ← 3-gate dedup pipeline
    ├── preprocessor.py              ← Boilerplate strip + truncation
    ├── keyword_scores.py            ← Tab keyword scoring
    └── budget_guard.py              ← Token cost protection
```

## Key design decisions

**Why Haiku for classification, Sonnet only on demand?**
Haiku processes hundreds of articles per day at ~$0.05/run. Sonnet is reserved for user-triggered deep analysis at ~$0.015/click. This keeps daily costs under $0.15 regardless of volume.

**Why deterministic dedup before any LLM?**
SHA-256 URL hashing and SimHash title comparison drop ~40% of articles for free before Haiku sees them. TF-IDF cosine similarity catches same-story duplicates with different headlines. Only genuinely new content reaches the LLM.

**Why a borderline tab instead of dropping low-scoring articles?**
Articles scoring -4 to -1 are not spam but lack strong keyword signals. Showing them raw gives a safety net without paying LLM costs — you can glance at titles and click Quick Analysis only if something looks interesting.

**Why prompt caching?**
The Haiku system prompt (~800 tokens) is cached via Anthropic's `cache_control: ephemeral`. For a batch of 168 articles, the system prompt is paid once and read from cache 167 times — saving ~90% of input tokens for that portion.
