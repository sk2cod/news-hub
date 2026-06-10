KEYWORD_SCORES = {
    'geopolitics': {
        'tier1': [
            'sanctions', 'NATO', 'treaty', 'diplomacy', 'ceasefire',
            'invasion', 'missile', 'nuclear', 'UN security council',
            'foreign minister', 'prime minister', 'president', 'coup',
            'referendum', 'war', 'conflict', 'alliance', 'veto',
            'airstrike', 'air strike', 'bombardment', 'troops',
            'bilateral', 'multilateral', 'summit', 'G7', 'G20',
        ],
        'tier2': [
            'election', 'parliament', 'government', 'military',
            'embassy', 'diplomat', 'protest', 'trade war', 'tariff',
            'refugee', 'border', 'minister', 'secretary of state',
            'foreign policy', 'geopolitical', 'international',
        ],
        'blocklist': [
            'sponsored', 'advertisement', 'buy now', 'subscribe',
            'promo code', 'coupon', 'discount code', '% off',
            'save up to', 'deal of the day', 'click here',
        ]
    },

    'top_stories': {
        'tier1': [
            'breaking', 'urgent', 'major', 'crisis', 'disaster',
            'earthquake', 'flood', 'hurricane', 'cyclone', 'bushfire',
            'shooting', 'attack', 'killed', 'dead', 'explosion',
            'collapse', 'emergency', 'mass shooting', 'riot', 'riots',
            'stabbing', 'bomb', 'fire', 'deaths', 'fatalities',
        ],
        'tier2': [
            'announces', 'confirmed', 'official', 'government', 'police',
            'investigation', 'arrest', 'charged', 'verdict', 'sentenced',
            'protest', 'protests', 'violence', 'attack', 'injured',
            'survivors', 'rescue', 'evacuation',
        ],
        'blocklist': [
            'sponsored', 'advertisement', 'buy now', 'subscribe',
            'promo code', 'coupon', 'discount code', '% off',
            'save up to', 'best of', 'top 10', 'ranked',
            'click here', 'sign up now', 'free trial',
        ]
    },

    'finance': {
        'tier1': [
            'RBA', 'federal reserve', 'interest rate', 'inflation',
            'GDP', 'recession', 'ASX', 'S&P 500', 'earnings',
            'quarterly results', 'central bank', 'rate hike', 'rate cut',
            'bankruptcy', 'acquisition', 'merger', 'IPO',
            'Wall Street', 'S&P', 'Nasdaq', 'FTSE', 'Dow Jones',
        ],
        'tier2': [
            'market', 'stocks', 'shares', 'bond', 'yield', 'currency',
            'dollar', 'economy', 'fiscal', 'monetary', 'budget',
            'deficit', 'surplus', 'trade', 'export', 'import',
            'JPMorgan', 'Goldman Sachs', 'Morgan Stanley', 'Citigroup',
            'Bank of America', 'Wells Fargo', 'HSBC', 'Barclays',
            'profit', 'revenue', 'earnings beat', 'trading revenue',
            'oil price', 'gold price', 'crude oil', 'Brent',
            'SoftBank', 'Super Micro', 'SpaceX IPO',
            'BYD', 'Vinted', 'Revolut', 'fintech',
        ],
        'blocklist': [
            'sponsored', 'advertisement', 'crypto pump', 'get rich',
            'investment advice', 'buy now', 'subscribe', 'forex signal',
            'promo code', 'coupon', 'discount code', '% off',
            'save up to', 'click here', 'sign up now',
        ]
    },

    'ai_tech': {
        'tier1': [
            'foundation model', 'large language model', 'LLM', 'GPT',
            'Claude', 'Gemini', 'Anthropic', 'OpenAI', 'DeepMind',
            'model release', 'AI regulation', 'AI policy',
            'AI safety', 'alignment', 'benchmark', 'AGI',
            'EU AI act', 'deepfake legislation',
            'nvidia', 'semiconductor', 'chip', 'compute',
            'AI model', 'language model', 'AI system',
            'Mistral', 'Meta AI', 'Llama', 'Grok', 'xAI',
            'AI research', 'AI development', 'AI company',
        ],
        'tier2': [
            'artificial intelligence', 'machine learning', 'neural network',
            'deep learning', 'transformer', 'open source model',
            'AI startup', 'funding round', 'research paper',
            'AI tool', 'AI assistant', 'chatbot', 'generative AI',
            'AI industry', 'AI lab', 'AI application',
            'Apple', 'Siri', 'Apple Intelligence', 'Google', 'Microsoft',
            'AI features', 'AI chip', 'AI stocks', 'AI investment',
            'quantum computing', 'robotics', 'autonomous',
        ],
        'blocklist': [
            'sponsored', 'advertisement',
            'top 10 AI tools', 'AI writes your emails',
            'buy now', 'promo code', 'discount code', '% off',
            'save up to', 'click here', 'sign up now',
        ]
    },

    'sports_ent': {
        'tier1': [
            'AFL', 'NRL', 'cricket Australia', 'Ashes', 'A-League',
            'grand final', 'premiership', 'world cup', 'Olympics',
            'championship', 'title', 'Oscar', 'Grammy', 'Emmy',
            'box office', 'album release', 'tour announced',
            'Wallabies', 'Socceroos', 'Matildas', 'Boomers',
            'State of Origin', 'Origin', 'Super Rugby',
            'BBL', 'WBBL', 'NBL', 'WNBL',
        ],
        'tier2': [
            'match', 'game', 'season', 'player', 'coach', 'transfer',
            'signing', 'injury', 'film', 'series', 'streaming',
            'celebrity', 'award', 'concert', 'festival',
            'quarterback', 'touchdown', 'NBA', 'NFL', 'NHL', 'MLB',
            'tennis', 'golf', 'Formula 1', 'F1', 'MotoGP',
            'Wimbledon', 'US Open', 'French Open', 'Australian Open',
        ],
        'blocklist': [
            'sponsored', 'advertisement', 'unconfirmed',
            'buy tickets', 'paparazzi', 'gossip',
            'promo code', 'coupon', 'discount code', '% off',
            'save up to', 'click here', 'sign up now',
        ]
    },

    'australia': {
        'tier1': [
            'Australia', 'Australian', 'NSW', 'New South Wales',
            'Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide',
            'Canberra', 'ABC News', 'Albanese', 'Anthony Albanese',
            'RBA', 'ASIO', 'ALP', 'Liberal Party', 'Greens',
            'bushfire', 'flooding NSW', 'cost of living Australia',
            'Dutton', 'Peter Dutton', 'Penny Wong',
        ],
        'tier2': [
            'federal government', 'state government', 'parliament house',
            'Medicare', 'Centrelink', 'NDIS', 'housing crisis',
            'immigration Australia', 'visa', 'citizenship',
            'Aussie', 'Aussies', 'Oz', 'Down Under',
            'Woolworths', 'Coles', 'Bunnings', 'Telstra', 'Qantas',
            'Jetstar', 'ANZ', 'Westpac', 'Commonwealth Bank', 'NAB',
            'Socceroos', 'Wallabies', 'Boomers', 'Matildas',
            'Cricket Australia', 'AFL', 'NRL',
            'petrol', 'cost of living', 'superannuation', 'super fund',
            'ACCC', 'ATO', 'Fair Work', 'Airservices',
        ],
        'blocklist': [
            'sponsored', 'advertisement', 'real estate listing',
            'property for sale', 'buy now', 'subscribe',
            'promo code', 'coupon', 'discount code', '% off',
            'save up to', 'click here', 'sign up now',
        ]
    }
}


def score_article(title: str, body: str, tab: str) -> int:
    """
    Score an article against keyword tiers for a given tab.
    Positive score = relevant signal detected.
    Negative score = spam/noise signal detected.
    Articles scoring >= 0 go to Haiku.
    Articles scoring -4 to -1 go to borderline tab.
    Articles scoring <= -5 are blocked completely.
    """
    if tab not in KEYWORD_SCORES:
        return 0

    text = (title + ' ' + body).lower()
    scores = KEYWORD_SCORES[tab]
    total = 0

    for keyword in scores['tier1']:
        if keyword.lower() in text:
            total += 3

    for keyword in scores['tier2']:
        if keyword.lower() in text:
            total += 1

    for keyword in scores['blocklist']:
        if keyword.lower() in text:
            total -= 5

    return total