import feedparser
import os
from datetime import datetime, timezone
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

RSS_SOURCES = {
    'geopolitics': [
        {
            'id': 'reuters-world',
            'name': 'Reuters World',
            'url': 'https://news.google.com/rss/search?q=world+news+site:reuters.com&hl=en-US&gl=US&ceid=US:en',
            'country': 'GLOBAL'
        },
        {
            'id': 'bbc-world',
            'name': 'BBC World News',
            'url': 'https://feeds.bbci.co.uk/news/world/rss.xml',
            'country': 'GLOBAL'
        },
        {
            'id': 'aljazeera',
            'name': 'Al Jazeera English',
            'url': 'https://www.aljazeera.com/xml/rss/all.xml',
            'country': 'GLOBAL'
        },
    ],
    'top_stories': [
        {
            'id': 'reuters-top',
            'name': 'Reuters Top News',
            'url': 'https://news.google.com/rss/search?q=top+news+site:reuters.com&hl=en-US&gl=US&ceid=US:en',
            'country': 'GLOBAL'
        },
        {
            'id': 'bbc-top',
            'name': 'BBC Top Stories',
            'url': 'https://feeds.bbci.co.uk/news/rss.xml',
            'country': 'GLOBAL'
        },
        {
            'id': 'ap-top',
            'name': 'AP News Top Stories',
            'url': 'https://news.google.com/rss/search?q=breaking+news+site:apnews.com&hl=en-US&gl=US&ceid=US:en',
            'country': 'GLOBAL'
        },
    ],
    'finance': [
        {
            'id': 'reuters-business',
            'name': 'Reuters Business',
            'url': 'https://news.google.com/rss/search?q=reuters+markets+economy+earnings&hl=en-US&gl=US&ceid=US:en',
            'country': 'GLOBAL'
        },
        {
            'id': 'cnbc-top',
            'name': 'CNBC Top News',
            'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
            'country': 'GLOBAL'
        },
        {
            'id': 'ft-world',
            'name': 'Financial Times',
            'url': 'https://www.ft.com/rss/home/uk',
            'country': 'GLOBAL'
        },
    ],
    'ai_tech': [
        {
            'id': 'mit-tech',
            'name': 'MIT Technology Review',
            'url': 'https://www.technologyreview.com/feed/',
            'country': 'GLOBAL'
        },
        {
            'id': 'ars-tech',
            'name': 'Ars Technica',
            'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
            'country': 'GLOBAL'
        },
        {
            'id': 'wired-ai',
            'name': 'Wired',
            'url': 'https://www.wired.com/feed/rss',
            'country': 'GLOBAL'
        },
    ],
    'sports_ent': [
        {
            'id': 'variety',
            'name': 'Variety',
            'url': 'https://variety.com/feed/',
            'country': 'GLOBAL'
        },
    ],
    'australia': [
        {
            'id': 'abc-au',
            'name': 'ABC News Australia',
            'url': 'https://www.abc.net.au/news/feed/51120/rss.xml',
            'country': 'AU'
        },
        {
            'id': 'guardian-au',
            'name': 'The Guardian Australia',
            'url': 'https://www.theguardian.com/australia-news/rss',
            'country': 'AU'
        },
        {
            'id': 'smh',
            'name': 'Sydney Morning Herald',
            'url': 'https://www.smh.com.au/rss/feed.xml',
            'country': 'AU'
        },
        {
            'id': 'sbs',
            'name': 'SBS News',
            'url': 'https://www.sbs.com.au/news/feed',
            'country': 'AU'
        },
    ],
}

TAVILY_QUERIES = {
    'geopolitics': 'geopolitics diplomacy sanctions NATO UN security council war conflict',
    'top_stories': 'breaking news major world events today',
    'finance':     'markets economy inflation interest rates ASX earnings recession',
    'ai_tech':     'AI model release artificial intelligence regulation safety research',
    'sports_ent':  'film music awards entertainment celebrity news',
    'australia':   'Australia news NSW Sydney government policy today',
}


# Sources whose tab assignment must never be overridden by downstream
# Haiku classification — cron.py enforces this when storing each cluster.
FORCED_TAB_OVERRIDES = {
    'ft-world': 'finance',
}


def parse_rss_entry(entry: dict, source: dict, tab: str) -> dict:
    """Convert a feedparser entry into our standard article dict."""
    title = entry.get('title', '').strip()
    url = entry.get('link', '').strip()

    body = ''
    if 'summary' in entry:
        body = entry.summary
    elif 'content' in entry:
        body = entry.content[0].value

    published_at = None
    if 'published_parsed' in entry and entry.published_parsed:
        published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()

    forced_tab = FORCED_TAB_OVERRIDES.get(source['id'])

    return {
        'title': title,
        'url': url,
        'body': body,
        'source_id': source['id'],
        'source_name': source['name'],
        'source_country': source['country'],
        'tab': forced_tab or tab,
        'forced_tab': forced_tab,
        'published_at': published_at,
    }


def fetch_rss_articles() -> list:
    """
    Fetch articles from all RSS sources.
    Returns a flat list of raw article dicts.
    """
    articles = []

    for tab, sources in RSS_SOURCES.items():
        for source in sources:
            try:
                feed = feedparser.parse(source['url'])
                SKIP_TITLE_PATTERNS = [
                    'Reuters |', 'AP News |', '| Reuters',
                    'Breaking News |', 'Latest News |',
                    'Top Stories |', "Today's Latest",
                    'News Headlines |', 'Market Headlines |',
                    'Latest Breaking News', 'Latest Top Stories',
                    'Latest Headlines', '| Breaking Stock Market',
                    'War: Latest', 'Latest News Today',
                    'Top headlines from', 'photojournalists',
                    'Associated Press News:', 'AP News:',
                    '| AP News', 'Full-length Replay',
                ]

                for entry in feed.entries[:15]:
                    article = parse_rss_entry(entry, source, tab)
                    if not article['title'] or not article['url']:
                        continue
                    if any(pattern in article['title'] for pattern in SKIP_TITLE_PATTERNS):
                        print(f"TITLE FILTER DROP: {article['title'][:60]}")
                        continue
                    articles.append(article)
                print(f"RSS OK: {source['name']} — {len(feed.entries[:15])} entries")
            except Exception as e:
                print(f"RSS ERROR: {source['name']} — {e}")

    return articles


def fetch_tavily_articles() -> list:
    """
    Fetch articles from Tavily for each tab query.
    Returns a flat list of raw article dicts.
    """
    articles = []

    for tab, query in TAVILY_QUERIES.items():
        try:
            response = tavily_client.search(
                query=query,
                topic='news',
                days=1,
                max_results=10,
                include_raw_content=False
            )
            for result in response.get('results', []):
                article = {
                    'title': result.get('title', '').strip(),
                    'url': result.get('url', '').strip(),
                    'body': result.get('content', '').strip(),
                    'source_id': 'tavily',
                    'source_name': result.get('source', 'Tavily'),
                    'source_country': 'GLOBAL',
                    'tab': tab,
                    'published_at': None,
                }
                if article['title'] and article['url']:
                    articles.append(article)
            print(f"Tavily OK: {tab} — {len(response.get('results', []))} results")
        except Exception as e:
            print(f"Tavily ERROR: {tab} — {e}")

    return articles


def fetch_all_articles() -> list:
    """
    Fetch from all sources and return combined list.
    RSS runs first, Tavily fills gaps.
    """
    print("--- Fetching RSS feeds ---")
    rss_articles = fetch_rss_articles()

    print("--- Fetching Tavily ---")
    tavily_articles = fetch_tavily_articles()

    all_articles = rss_articles + tavily_articles
    print(f"--- Total fetched: {len(all_articles)} articles ---")

    return all_articles