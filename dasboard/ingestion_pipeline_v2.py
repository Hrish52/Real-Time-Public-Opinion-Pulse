# ============================================================
# Real-Time Public Opinion Pulse — Phase 1 Ingestion Pipeline
# Version 2: Improved topic classification
# ============================================================
# Changes from v1:
#   - matches_topic() now scores ALL topics and returns the
#     highest-scoring one instead of returning on the first match.
#   - Word-boundary regex (\b) replaces plain substring search,
#     so "tech" inside "biotech" no longer triggers "tech layoffs".
#   - "tech layoffs" keywords now require tech context — generic
#     words like "layoff", "restructuring", "redundancy" removed.
#   - Pre-compiled patterns (_COMPILED_PATTERNS) for performance.
# ============================================================

# Uncomment to install in Colab:
# !pip install praw atproto Mastodon.py supabase beautifulsoup4 lxml feedparser yt-dlp

# ============================================================
# SECTION 1 — CONFIG & API KEYS
# ============================================================

from google.colab import userdata
from datetime import datetime, timezone, timedelta

BLUESKY_HANDLE        = userdata.get("Blue_Sky_Handle")
BLUESKY_APP_PASSWORD  = userdata.get("Blue_Sky_App_Password")
GUARDIAN_API_KEY      = userdata.get("Guardian_Api_key")
MASTODON_HANDLE       = userdata.get("Mastodon_Handle")
MASTODON_APP_PASSWORD = userdata.get("Mastodon_App_Password")

DEVTO_BASE_URL = "https://dev.to/api"

RSS_FEEDS = {
    "bbc":                    "http://feeds.bbci.co.uk/news/rss.xml",
    "reuters":                "http://feeds.reuters.com/reuters/topNews",
    "al_jazeera":             "https://www.aljazeera.com/xml/rss/all.xml",
    "npr":                    "https://feeds.npr.org/1001/rss.xml",
    "techcrunch":             "https://techcrunch.com/feed/",
    "ars_technica":           "https://arstechnica.com/feed/",
    "bloomberg":              "https://www.bloomberg.com/feeds/bpol/news.xml",
    "science_daily":          "https://www.sciencedaily.com/rss/all.xml",
    "nieman_lab":             "https://www.niemanlab.org/feed/",
    "cnn_top_stories":        "http://rss.cnn.com/rss/cnn_topstories.rss",
    "cnn_world":              "http://rss.cnn.com/rss/cnn_world.rss",
    "cnn_us":                 "http://rss.cnn.com/rss/cnn_us.rss",
    "cnn_technology":         "http://rss.cnn.com/rss/cnn_tech.rss",
    "ap_news":                "https://rsshub.app/apnews/topics/world-news",
    "france24":               "https://www.france24.com/en/rss",
    "dw_news":                "https://rss.dw.com/rdf/rss-en-all",
    "japan_times":            "https://www.japantimes.co.jp/feed/",
    "south_china_morning_post":"https://www.scmp.com/rss/91/feed",
    "the_hindu":              "https://www.thehindu.com/news/international/feeder/default.rss",
    "abc_australia":          "https://www.abc.net.au/news/feed/2942460/rss.xml",
    "africa_news":            "https://www.africanews.com/feed/",
}

SUPABASE_URL = userdata.get("Supabase_url")
SUPABASE_KEY = userdata.get("Supabase_Key")

# ============================================================
# SECTION 2 — TRACKED TOPICS
# Key change: "tech layoffs" now requires tech context.
# Generic words like "layoff", "restructuring", "redundancy"
# are removed — they match far too many unrelated articles.
# ============================================================

TRACKED_TOPICS = {

    "artificial intelligence": [
        # Companies / models — specific enough standalone
        "openai", "chatgpt", "anthropic",
        "google gemini", "gemini ai",
        "gpt-4", "gpt-3", "gpt-4o",
        "github copilot", "microsoft copilot",
        "midjourney", "stable diffusion", "dall-e", "sora ai",
        "nvidia ai", "nvidia cuda",
        # Technical terms — compound required
        "large language model", "llm",
        "generative ai", "ai-generated",
        "foundation model", "diffusion model",
        "transformer model", "multimodal ai",
        "artificial general intelligence", "agi",
        "neural network architecture",
        # Policy / ethics — compound required
        "ai safety", "ai alignment",
        "ai ethics", "ai bias",
        "ai governance", "ai regulation",
        "eu ai act", "ai act",
        "ai deepfake", "deepfake detection",
        # Industry
        "ai chip", "ai startup", "ai investment",
        "artificial intelligence",
    ],

    "climate policy": [
        # Policy instruments — specific compound
        "climate policy", "climate legislation",
        "climate summit", "climate agreement",
        "paris agreement", "paris climate accord",
        "cop29", "cop28", "unfccc",
        "carbon tax", "carbon pricing",
        "carbon emissions target",
        "net zero target", "net zero commitment",
        "carbon neutral pledge",
        "renewable energy policy", "clean energy policy",
        "fossil fuel subsidy", "fossil fuel ban",
        "coal phase out", "oil phase out",
        "carbon capture technology",
        "greenhouse gas target",
        "green new deal",
        "climate refugee", "climate migration",
        "sea level rise",
        "deforestation policy", "amazon deforestation",
        "methane emissions target",
        "climate crisis", "climate emergency",
        "global warming",
        "carbon offset scheme",
    ],

    "data privacy": [
        # Regulation — specific
        "gdpr", "ccpa",
        "data privacy", "data protection law",
        "privacy law", "privacy regulation",
        "right to be forgotten",
        # Breaches — compound required
        "data breach", "personal data leak",
        "user data exposed", "data harvesting policy",
        # Surveillance — compound required
        "mass surveillance", "government surveillance",
        "surveillance capitalism",
        "facial recognition ban", "facial recognition law",
        "biometric surveillance",
        "location tracking ban", "phone tracking law",
        # Encryption / tools — specific
        "end-to-end encryption",
        "encrypted messaging",
        "pegasus spyware", "spyware attack",
        "cookie consent law", "online tracking ban",
        "vpn ban", "vpn law",
        "zero-knowledge proof",
    ],

    "tech layoffs": [
        "tech layoff", "tech layoffs",
        "technology layoff", "technology layoffs",
        "tech job cut", "tech job cuts",
        "tech worker laid off", "tech worker fired",
        "tech worker let go",
        "silicon valley layoff",
        "tech company cut",
        "software engineer laid off",
        "developer laid off", "engineer layoff",
        "startup layoff", "big tech layoff",
        "tech industry job loss",
        "tech hiring freeze",
        "tech workforce reduction",
        "google layoff", "amazon layoff",
        "meta layoff", "microsoft layoff",
        "apple layoff", "netflix layoff",
        "twitter layoff", "salesforce layoff",
        "intel layoff", "ibm layoff",
        "cisco layoff", "zoom layoff",
        "snap layoff", "lyft layoff",
        "uber layoff", "airbnb layoff",
        "stripe layoff",
    ],

    "business": [
        # Funding — compound required
        "series a funding", "series b funding",
        "series c funding", "seed funding round",
        "venture capital funding", "vc backed startup",
        "startup funding round",
        # M&A — compound required
        "company acquisition", "corporate acquisition",
        "hostile takeover", "company merger",
        "private equity buyout",
        # IPO — compound required
        "ipo filing", "ipo listing",
        "stock market debut", "going public ipo",
        # Earnings — compound required
        "quarterly earnings report", "earnings per share",
        "revenue guidance", "profit warning",
        "earnings beat", "earnings miss",
        # Antitrust — compound required
        "antitrust lawsuit", "antitrust investigation",
        "ftc lawsuit", "monopoly lawsuit",
        # Market / valuation — compound required
        "company valuation", "market valuation",
        "unicorn startup", "startup unicorn",
        "chapter 11 bankruptcy", "corporate bankruptcy",
        # Macro — compound required
        "supply chain disruption",
        "federal reserve rate", "interest rate hike",
        "inflation report", "inflation data",
    ],

    "us politics": [
        # Named leaders — specific enough standalone
        "donald trump", "joe biden", "kamala harris",
        "ron desantis",
        # Institutions + US qualifier — compound required
        "us congress", "us senate", "us house representatives",
        "white house", "oval office",
        "republican party", "democratic party",
        # Policy acts / events — compound or specific phrase
        "executive order",
        "supreme court ruling", "supreme court decision",
        "us midterm election", "presidential election",
        "us government shutdown", "debt ceiling crisis",
        "us tariff", "american tariff",
        "us immigration policy", "us border policy",
        "senate filibuster",
        "electoral college",
        "impeachment trial",
        "january 6 committee",
        "voter suppression law",
        "gerrymandering case",
        "us attorney general",
        "department of justice investigation",
        "us foreign policy", "us presidential race",
    ],

    "hollywood": [
        # Awards — specific
        "box office", "oscars", "academy awards",
        "oscar nomination", "oscar winner",
        "golden globes", "emmy awards", "bafta awards",
        # Industry disputes — specific
        "sag-aftra", "writers guild", "wga strike",
        "hollywood strike", "actors strike", "writers strike",
        # Festivals — compound required
        "cannes film festival", "sundance film festival",
        "toronto international film festival",
        # Industry metrics — compound required
        "box office record", "box office flop",
        "box office opening weekend",
        "movie premiere", "film release date",
        "film industry revenue", "rotten tomatoes score",
        # Platforms — compound required
        "netflix original series", "hbo original series",
        "disney plus original", "streaming rights deal",
        "paramount plus series", "peacock original",
        # Production news — compound required
        "casting announcement", "film director announced",
        "movie sequel announced", "film remake announced",
        "studio acquisition", "production deal",
    ],

    "world news": [
        # Specific active conflicts
        "israel hamas", "israel hamas war",
        "gaza ceasefire", "gaza war", "west bank settlement",
        "russia ukraine war", "ukraine war",
        "russia ukraine ceasefire",
        "taiwan strait tension", "taiwan china tension",
        "iran nuclear deal", "iran nuclear program",
        "north korea missile", "north korea nuclear",
        "south china sea dispute",
        # International bodies + action — compound required
        "united nations resolution", "un security council vote",
        "nato summit", "nato expansion",
        "european union summit", "eu parliament vote",
        "g7 summit", "g20 summit", "brics summit",
        # Diplomacy — compound required
        "ceasefire agreement", "peace negotiations",
        "international sanctions",
        # Crises — compound required
        "humanitarian crisis",
        "global refugee crisis",
        "global recession warning",
        "imf warning", "world bank report",
        "military offensive",
        "coup attempt",
        "terror attack",
        "assassination attempt",
        "nuclear treaty",
        "missile strike",
        "natural disaster death toll",
        "who declares health emergency",
        "disease outbreak warning",
    ],

    "tech news": [
        # Apple — product/event compound
        "apple iphone", "apple macbook", "apple mac",
        "apple vision pro", "apple watch", "apple tv",
        "apple earnings", "apple event", "wwdc",
        "apple silicon", "apple chip",
        # Google — product/event compound
        "google pixel", "google chrome update",
        "google search algorithm", "google earnings",
        "google io", "google cloud",
        # Microsoft — product/event compound
        "microsoft windows", "microsoft surface",
        "microsoft azure", "microsoft earnings",
        "microsoft teams update",
        # Amazon — tech compound
        "amazon aws", "amazon web services",
        "amazon alexa", "amazon echo",
        "amazon tech", "amazon earnings",
        # Meta — tech compound
        "meta quest", "meta earnings",
        "meta ai", "facebook algorithm",
        "instagram algorithm update",
        # Other hardware
        "samsung galaxy", "samsung chip",
        "intel chip", "amd chip",
        "qualcomm chip", "arm processor",
        # Industry events/topics — compound required
        "tech product launch", "tech conference",
        "cybersecurity breach", "ransomware attack",
        "semiconductor shortage", "chip shortage",
        "5g network rollout", "quantum computing breakthrough",
        "self-driving car", "autonomous vehicle",
        "tech antitrust", "app store policy",
        "data center investment",
    ],
}

# ============================================================
# SECTION 3 — SUPABASE SETUP
# ============================================================

from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

response = supabase.table("posts").select("*").limit(1).execute()
print("Connected!" if response else "Connection failed.")

# ============================================================
# SECTION 4 — HELPER FUNCTIONS
# Key change: matches_topic() completely rewritten.
# ============================================================

import hashlib
import re
import requests
from bs4 import BeautifulSoup
import time


def hash_author(username):
    if not username:
        return "anonymous"
    return hashlib.sha256(username.encode()).hexdigest()[:16]


def _make_pattern(keyword: str) -> re.Pattern:
    """Compile a keyword into a word-boundary regex pattern."""
    escaped = re.escape(keyword)
    # Only add \b where the keyword starts/ends with a word character,
    # otherwise the boundary anchor itself is a syntax error.
    prefix = r"\b" if keyword and keyword[0].isalnum() else ""
    suffix = r"\b" if keyword and keyword[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


# Pre-compile every keyword once at import time
_COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    topic: [_make_pattern(kw) for kw in keywords]
    for topic, keywords in TRACKED_TOPICS.items()
}


def matches_topic(text: str, topics) -> str | None:
    """
    Score-based topic classifier with word-boundary regex matching.

    Scores every eligible topic by counting how many of its keyword
    patterns appear in `text`, then returns the highest-scoring one.
    Returns None if no topic reaches a score of 1.

    `topics` may be:
      - a list of topic-name strings  e.g. ["tech layoffs"]
      - a dict whose keys are topic names  e.g. TRACKED_TOPICS
    """
    if not text:
        return None

    candidate_topics = topics.keys() if isinstance(topics, dict) else topics
    scores: dict[str, int] = {}

    for topic in candidate_topics:
        patterns = _COMPILED_PATTERNS.get(topic, [])
        score = sum(1 for p in patterns if p.search(text))
        if score > 0:
            scores[topic] = score

    if not scores:
        return None
    return max(scores, key=scores.get)


def clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    return BeautifulSoup(html_text, "lxml").get_text()


def truncate_content(text: str, max_chars: int = 2000) -> str:
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def build_post(platform, platform_id, author, content, topic,
               created_at, engagement, source_category, source_name, **kwargs):
    return {
        "platform":        platform,
        "platform_id":     str(platform_id),
        "author_hash":     hash_author(author),
        "content":         truncate_content(content),
        "topic":           topic,
        "source_category": source_category,
        "source_name":     source_name,
        "created_at":      created_at if isinstance(created_at, str) else created_at.isoformat(),
        "ingested_at":     datetime.now(timezone.utc).isoformat(),
        "engagement":      engagement or 0,
        "raw_metadata":    kwargs.get("metadata", {}),
    }


def safe_request(url: str, params=None, retries: int = 3):
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                time.sleep(2 ** attempt)
            else:
                print(f"HTTP {response.status_code} from {url}")
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
    return None

# ============================================================
# SECTION 5 — BLUESKY ADAPTER
# ============================================================

from atproto import Client


def fetch_bluesky(handle, password, topics, limit=50):
    posts = []
    client = Client()
    try:
        client.login(handle, password)
    except Exception as e:
        print(f"Bluesky login failed: {e}")
        return posts

    for topic in topics:
        try:
            response = client.app.bsky.feed.search_posts({"q": topic, "limit": limit})
            for feed_post in response.posts:
                record      = feed_post.record
                post_text   = record.text
                matched     = matches_topic(post_text, [topic])
                if not matched:
                    continue
                created_at = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
                like_count  = feed_post.like_count
                reply_count = feed_post.reply_count
                posts.append(build_post(
                    platform="bluesky",
                    platform_id=feed_post.uri.split("/")[-1],
                    author=feed_post.author.handle,
                    content=post_text,
                    topic=matched,
                    source_category="social",
                    source_name="bluesky",
                    created_at=created_at,
                    engagement=like_count + reply_count,
                    metadata={
                        "uri": str(feed_post.uri),
                        "cid": str(feed_post.cid),
                        "indexed_at": feed_post.indexed_at,
                        "like_count": like_count,
                        "reply_count": reply_count,
                        "repost_count": feed_post.repost_count,
                    },
                ))
        except Exception as e:
            print(f"Bluesky error for topic '{topic}': {e}")

    return posts

# ============================================================
# SECTION 6 — YOUTUBE ADAPTER
# ============================================================

import subprocess
import json
import tempfile
import os

YOUTUBE_CHANNELS = {
    "artificial intelligence": [
        "https://www.youtube.com/@matthew_berman",
        "https://www.youtube.com/@AIExplained-official",
        "https://www.youtube.com/@Fireship",
    ],
    "climate policy": [
        "https://www.youtube.com/@ClimateAdam",
        "https://www.youtube.com/@DWNews",
    ],
    "data privacy": [
        "https://www.youtube.com/@Techlore",
        "https://www.youtube.com/@TheHatedOne",
    ],
    "tech layoffs": [
        "https://www.youtube.com/@CNBCtelevision",
        "https://www.youtube.com/@TechLinked",
    ],
    "business": [
        "https://www.youtube.com/@YahooFinance",
        "https://www.youtube.com/@CNBCtelevision",
    ],
    "us politics": [
        "https://www.youtube.com/@CNN",
        "https://www.youtube.com/@ABCNews",
        "https://www.youtube.com/@NBCNews",
    ],
    "hollywood": [
        "https://www.youtube.com/@hollywoodreporter",
        "https://www.youtube.com/@EntertainmentTonight",
    ],
    "world news": [
        "https://www.youtube.com/@BBCNews",
        "https://www.youtube.com/@AlJazeeraEnglish",
        "https://www.youtube.com/@DWNews",
    ],
    "tech news": [
        "https://www.youtube.com/@mkbhd",
        "https://www.youtube.com/@Fireship",
        "https://www.youtube.com/@TheVerge",
    ],
}


def fetch_youtube(topics, max_videos_per_channel=5, max_comments=50):
    posts = []
    for topic_name in topics:
        channels = YOUTUBE_CHANNELS.get(topic_name, [])
        for channel_url in channels:
            try:
                result = subprocess.run(
                    [
                        "yt-dlp", "--flat-playlist",
                        "--playlist-end", str(max_videos_per_channel),
                        "--print", "%(id)s|||%(title)s|||%(description)s|||%(upload_date)s|||%(view_count)s",
                        f"{channel_url}/videos",
                    ],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    continue

                for line in result.stdout.strip().split("\n"):
                    if not line or "|||" not in line:
                        continue
                    parts = line.split("|||")
                    if len(parts) < 4:
                        continue

                    video_id    = parts[0].strip()
                    title       = parts[1].strip()
                    description = parts[2].strip() if len(parts) > 2 else ""
                    upload_date = parts[3].strip() if len(parts) > 3 else ""
                    view_count  = parts[4].strip() if len(parts) > 4 else "0"

                    matched = matches_topic(f"{title} {description}", [topic_name])
                    if not matched:
                        continue

                    try:
                        created_at = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
                    except Exception:
                        created_at = datetime.now(timezone.utc)

                    views = int(view_count) if view_count and view_count.isdigit() else 0

                    posts.append(build_post(
                        platform="youtube",
                        platform_id=f"video_{video_id}",
                        author=channel_url.split("@")[-1] if "@" in channel_url else "unknown",
                        content=truncate_content(f"{title}. {description}"),
                        topic=matched,
                        source_category="social",
                        source_name="youtube",
                        created_at=created_at,
                        engagement=views,
                        metadata={"type": "video", "video_id": video_id, "channel": channel_url},
                    ))

                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            info_file = os.path.join(tmpdir, "video")
                            subprocess.run(
                                [
                                    "yt-dlp", "--skip-download",
                                    "--write-comments",
                                    "--extractor-args", f"youtube:max_comments={max_comments}",
                                    "-o", info_file,
                                    "--write-info-json",
                                    f"https://www.youtube.com/watch?v={video_id}",
                                ],
                                capture_output=True, text=True, timeout=90,
                            )
                            info_path = info_file + ".info.json"
                            if not os.path.exists(info_path):
                                continue
                            with open(info_path) as f:
                                info = json.load(f)
                            for comment in info.get("comments", [])[:max_comments]:
                                comment_text = comment.get("text", "")
                                if len(comment_text) < 15:
                                    continue
                                likes     = comment.get("like_count", 0) or 0
                                timestamp = comment.get("timestamp")
                                try:
                                    comment_time = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else created_at
                                except Exception:
                                    comment_time = created_at
                                posts.append(build_post(
                                    platform="youtube",
                                    platform_id=f"comment_{video_id}_{comment.get('id', '')}",
                                    author=comment.get("author", "anonymous"),
                                    content=comment_text,
                                    topic=matched,
                                    source_category="social",
                                    source_name="youtube",
                                    created_at=comment_time,
                                    engagement=likes,
                                    metadata={"type": "comment", "video_id": video_id, "video_title": title},
                                ))
                    except Exception as e:
                        print(f"Comment extraction failed for {video_id}: {e}")

            except Exception as e:
                print(f"YouTube channel error ({channel_url}): {e}")

    return posts

# ============================================================
# SECTION 7 — DEV.TO ADAPTER
# ============================================================


def fetch_devto(topics, limit=30):
    posts = []
    topic_to_tags = {
        "artificial intelligence": ["ai", "machinelearning", "openai"],
        "climate policy":          ["climate", "sustainability", "environment"],
        "data privacy":            ["privacy", "security", "gdpr"],
        "tech layoffs":            ["layoffs", "career", "jobs"],
        "business":                ["startup", "entrepreneurship", "business"],
        "us politics":             ["politics", "government", "policy"],
        "hollywood":               ["entertainment", "streaming", "media"],
        "world news":              ["news", "world", "geopolitics"],
        "tech news":               ["technology", "webdev", "programming", "devops"],
    }

    for topic in topics:
        tags_for_topic = topic_to_tags.get(topic.lower(), [topic.replace(" ", "")])
        per_tag = max(1, limit // len(tags_for_topic))

        for tag in tags_for_topic:
            articles = safe_request(f"{DEVTO_BASE_URL}/articles", params={"tag": tag, "per_page": per_tag, "top": 1})
            if not articles:
                continue
            for article in articles:
                combined = f"{article.get('title', '')} {article.get('description', '')} {article.get('body_markdown', '')}"
                matched  = matches_topic(combined, [topic])
                if not matched:
                    continue
                engagement    = article.get("positive_reactions_count", 0) + article.get("comments_count", 0)
                published_str = article.get("published_at", "")
                published_at  = datetime.fromisoformat(published_str.replace("Z", "+00:00")) if published_str else datetime.now(timezone.utc)
                posts.append(build_post(
                    platform="devto",
                    platform_id=article.get("id"),
                    author=article.get("user", {}).get("username", "anonymous"),
                    content=truncate_content(article.get("body_markdown", "")),
                    topic=matched,
                    source_category="forum",
                    source_name="devto",
                    created_at=published_at,
                    engagement=engagement,
                    metadata=article,
                ))

    return posts

# ============================================================
# SECTION 8 — GUARDIAN ADAPTER
# ============================================================


def fetch_guardian(api_key, topics, limit=20):
    posts = []
    GUARDIAN_URL = "https://content.guardianapis.com/search"
    yesterday    = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    for topic in topics:
        params = {
            "q":           topic,
            "api-key":     api_key,
            "page-size":   limit,
            "order-by":    "newest",
            "show-fields": "bodyText,headline,byline,webUrl,trailText",
            "from-date":   yesterday,
        }
        data = safe_request(GUARDIAN_URL, params=params)
        if not data or "response" not in data or "results" not in data["response"]:
            continue

        for article in data["response"]["results"]:
            fields      = article.get("fields", {})
            combined    = f"{article.get('webTitle', '')} {fields.get('trailText', '')} {fields.get('bodyText', '')}"
            matched     = matches_topic(combined, [topic])
            if not matched:
                continue

            pub_str    = article.get("webPublicationDate", "")
            created_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00")) if pub_str else datetime.now(timezone.utc)

            headline = article.get("webTitle", "")
            trail    = fields.get("trailText", "")
            body     = fields.get("bodyText", "")

            if trail and "live blog" not in trail.lower():
                content = truncate_content(f"{headline}. {trail}")
            elif body:
                content = truncate_content(f"{headline}. {body}")
            else:
                content = headline

            posts.append(build_post(
                platform="guardian",
                platform_id=article.get("webUrl"),
                author=fields.get("byline", "anonymous"),
                content=content,
                topic=matched,
                source_category="news",
                source_name="guardian",
                created_at=created_at,
                engagement=0,
                metadata=article,
            ))

    return posts

# ============================================================
# SECTION 9 — RSS ADAPTER
# ============================================================

import feedparser
import calendar


def fetch_rss_feeds(feeds_dict, topics, limit_per_feed=20):
    posts = []
    for feed_name, feed_url in feeds_dict.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:limit_per_feed]:
                title        = entry.get("title", "")
                summary      = clean_html(entry.get("summary", ""))
                content_full = ""
                if "content" in entry and entry["content"]:
                    content_full = clean_html(entry["content"][0].get("value", ""))

                combined = f"{title} {summary} {content_full}"
                topic    = matches_topic(combined, topics)
                if not topic:
                    continue

                if entry.get("published_parsed"):
                    created_at = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), tz=timezone.utc)
                else:
                    created_at = datetime.now(timezone.utc)

                posts.append(build_post(
                    platform="rss",
                    platform_id=entry.get("link"),
                    author=entry.get("author", "anonymous"),
                    content=truncate_content(content_full if content_full else f"{title} {summary}"),
                    topic=topic,
                    source_category="news",
                    source_name=feed_name,
                    created_at=created_at,
                    engagement=0,
                    metadata=entry,
                ))
        except Exception as e:
            print(f"RSS error for {feed_name}: {e}")

    return posts

# ============================================================
# SECTION 10 — DEDUPLICATION
# ============================================================

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def deduplicate(new_posts, existing_posts):
    if not existing_posts:
        return new_posts

    url_pattern      = re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+")
    seen_platform_ids = {p["platform_id"] for p in existing_posts}
    seen_urls         = set()

    for post in existing_posts:
        for url in url_pattern.findall(post["content"]):
            seen_urls.add(url)

    unique               = []
    posts_for_similarity = []

    for post in new_posts:
        if post["platform_id"] in seen_platform_ids:
            continue
        urls = url_pattern.findall(post["content"])
        if any(u in seen_urls for u in urls):
            continue
        if len(post["content"]) > 50:
            posts_for_similarity.append(post)
        else:
            unique.append(post)
            seen_platform_ids.add(post["platform_id"])
            for u in urls:
                seen_urls.add(u)

    if not posts_for_similarity:
        return unique

    existing_long = [p["content"] for p in existing_posts if len(p["content"]) > 50]
    if not existing_long:
        return new_posts

    all_texts  = existing_long + [p["content"] for p in posts_for_similarity]
    vectorizer = TfidfVectorizer().fit(all_texts)
    ex_vectors = vectorizer.transform(existing_long)

    for post in posts_for_similarity:
        vec  = vectorizer.transform([post["content"]])
        sims = cosine_similarity(vec, ex_vectors)
        if ex_vectors.shape[0] > 0 and sims.max() > 0.85:
            continue
        unique.append(post)
        seen_platform_ids.add(post["platform_id"])
        for u in url_pattern.findall(post["content"]):
            seen_urls.add(u)

    return unique

# ============================================================
# SECTION 11 — SUPABASE SAVE / HEALTH
# ============================================================

from collections import Counter


def save_posts(client, posts):
    if not posts:
        return 0
    seen, unique = set(), []
    for post in posts:
        key = (post["platform"], post["platform_id"])
        if key not in seen:
            seen.add(key)
            unique.append(post)
    try:
        client.table("posts").upsert(unique, on_conflict="platform,platform_id").execute()
        print(f"Upserted {len(unique)} posts.")
        return len(unique)
    except Exception as e:
        print(f"Error saving posts: {e}")
        return 0


def get_recent_posts(client, hours=6):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    try:
        result = client.table("posts").select("platform,platform_id,content").gte("ingested_at", cutoff).execute()
        return result.data or []
    except Exception as e:
        print(f"Error fetching recent posts: {e}")
        return []


def get_health_stats(client):
    try:
        print("\n--- Supabase Health Stats ---")
        total = client.table("posts").select("*", count="exact").execute()
        print(f"Total posts in DB: {total.count}")

        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = client.table("posts").select("source_name,source_category,topic").gte("ingested_at", one_hour_ago).execute()
        rows   = recent.data or []
        if rows:
            print("\nPosts in last hour:")
            for name, n in Counter(p["source_name"] for p in rows).most_common():
                print(f"  {name}: {n}")
            print("\nTopics in last hour:")
            for topic, n in Counter(p["topic"] for p in rows).most_common():
                print(f"  '{topic}': {n}")
        else:
            print("No posts ingested in the last hour.")
        print("-----------------------------")
    except Exception as e:
        print(f"Error getting health stats: {e}")

# ============================================================
# SECTION 12 — MAIN PIPELINE
# ============================================================


def run_pipeline(cycles=10, interval_seconds=300):
    total_ingested = 0

    for cycle in range(cycles):
        print(f"\n{'='*60}")
        print(f"  CYCLE {cycle+1}/{cycles} — {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
        print(f"{'='*60}")

        all_posts, source_counts = [], {}

        for name, fn, args in [
            ("youtube", fetch_youtube,    (TRACKED_TOPICS,)),
            ("devto",   fetch_devto,      (TRACKED_TOPICS,)),
            ("bluesky", fetch_bluesky,    (BLUESKY_HANDLE, BLUESKY_APP_PASSWORD, TRACKED_TOPICS)),
            ("guardian",fetch_guardian,   (GUARDIAN_API_KEY, TRACKED_TOPICS)),
            ("rss",     fetch_rss_feeds,  (RSS_FEEDS, TRACKED_TOPICS)),
        ]:
            try:
                result = fn(*args)
                source_counts[name] = len(result)
                all_posts.extend(result)
            except Exception as e:
                source_counts[name] = f"ERROR: {e}"

        print("\n  Source breakdown:")
        for src, count in source_counts.items():
            icon = "✓" if isinstance(count, int) else "✗"
            print(f"    {icon} {src}: {count}")
        print(f"\n  Total collected: {len(all_posts)}")

        recent = get_recent_posts(supabase)
        unique = deduplicate(all_posts, recent)
        print(f"  After dedup: {len(unique)}  (removed {len(all_posts) - len(unique)})")

        saved           = save_posts(supabase, unique)
        total_ingested += saved
        print(f"  Saved: {saved}  |  Running total: {total_ingested}")

        get_health_stats(supabase)

        if cycle < cycles - 1:
            print(f"\n  Next cycle in {interval_seconds}s...")
            time.sleep(interval_seconds)

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — {total_ingested} total posts ingested")
    print(f"{'='*60}")


run_pipeline(cycles=6, interval_seconds=300)

# ============================================================
# SECTION 13 — PHASE 1 VERIFICATION
# ============================================================


def verify_phase1():
    print("\n--- Phase 1 Verification ---")
    try:
        all_posts = supabase.table("posts").select("source_name,source_category,topic,content,created_at,engagement").execute()
        posts = all_posts.data or []
        if not posts:
            print("No posts in database yet.")
            return

        print("\n1. Posts per Source:")
        for name, n in Counter(p["source_name"] for p in posts).most_common():
            print(f"   {name}: {n}")

        print("\n2. Posts per Category:")
        for cat, n in Counter(p["source_category"] for p in posts).most_common():
            print(f"   {cat}: {n}")

        print("\n3. Posts per Topic:")
        for topic, n in Counter(p["topic"] for p in posts).most_common():
            print(f"   '{topic}': {n}")

        null_count = sum(1 for p in posts if not p.get("content"))
        print(f"\n4. Posts with null content: {null_count}")

        timestamps = sorted(p["created_at"] for p in posts if p.get("created_at"))
        print(f"\n5. Oldest: {timestamps[0] if timestamps else 'N/A'}")
        print(f"   Newest: {timestamps[-1] if timestamps else 'N/A'}")

        print(f"\n6. Total rows: {len(posts)}")
    except Exception as e:
        print(f"Verification error: {e}")
    print("----------------------------")


verify_phase1()
