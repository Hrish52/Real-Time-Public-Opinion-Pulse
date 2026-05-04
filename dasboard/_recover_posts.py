"""
Recover the 81 deleted news posts.
Strategy:
  1. Re-fetch all RSS feeds — picks up recent (2026) articles.
  2. Directly fetch specific older URLs captured before deletion.
  3. Classify everything with the news-specific classifier.
  4. Upsert to Supabase (safe to re-run — won't duplicate).
"""
import os, re, sys, time, calendar
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
import feedparser
import requests
from bs4 import BeautifulSoup

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# ── RSS feeds (same as ingestion pipeline) ───────────────────────────────────
RSS_FEEDS = {
    "bbc":           "http://feeds.bbci.co.uk/news/rss.xml",
    "reuters":       "http://feeds.reuters.com/reuters/topNews",
    "al_jazeera":    "https://www.aljazeera.com/xml/rss/all.xml",
    "npr":           "https://feeds.npr.org/1001/rss.xml",
    "techcrunch":    "https://techcrunch.com/feed/",
    "ars_technica":  "https://arstechnica.com/feed/",
    "bloomberg":     "https://www.bloomberg.com/feeds/bpol/news.xml",
    "nieman_lab":    "https://www.niemanlab.org/feed/",
    "cnn_top_stories": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "cnn_world":     "http://rss.cnn.com/rss/cnn_world.rss",
    "cnn_us":        "http://rss.cnn.com/rss/cnn_us.rss",
    "cnn_technology":"http://rss.cnn.com/rss/cnn_tech.rss",
    "ap_news":       "https://rsshub.app/apnews/topics/world-news",
    "france24":      "https://www.france24.com/en/rss",
    "dw_news":       "https://rss.dw.com/rdf/rss-en-all",
    "japan_times":   "https://www.japantimes.co.jp/feed/",
    "south_china_morning_post": "https://www.scmp.com/rss/91/feed",
    "the_hindu":     "https://www.thehindu.com/news/international/feeder/default.rss",
    "abc_australia": "https://www.abc.net.au/news/feed/2942460/rss.xml",
    "africa_news":   "https://www.africanews.com/feed/",
}

# ── Specific old URLs captured from the pre-deletion fetch ───────────────────
# These are 2022-2023 articles that won't appear in current RSS feeds.
DIRECT_URLS = {
    "cnn_us": [
        "https://www.cnn.com/2023/04/18/politics/groff-dejoy-supreme-court-religious-liberty/index.html",
        "https://www.cnn.com/2023/04/17/tech/google-ai-search-engine-stock-drop/index.html",
    ],
    "cnn_world": [
        "https://www.cnn.com/2023/04/13/business/silicon-valley-bank-entrepreneurs-of-color-reaj/index.html",
        "https://www.cnn.com/2022/03/21/us/lake-powell-capacity-shrinking-drought-climate/index.html",
        "https://www.cnn.com/2022/03/22/world/air-pollution-2021-iqair-report-climate/index.html",
        "https://www.cnn.com/2022/03/20/us/solar-power-on-big-box-store-rooftops-climate/index.html",
        "https://www.cnn.com/2023/04/14/economy/march-retail-sales/index.html",
    ],
    "cnn_top_stories": [
        "https://www.cnn.com/2023/04/17/health/rise-type-2-diabetes-global-wellness/index.html",
    ],
    "cnn_technology": [
        "https://www.cnn.com/videos/tech/2024/01/26/gps-gates-web-extra-on-work-life-balance.cnn",
        "https://www.cnn.com/videos/tech/2024/01/11/meta-social-media-protection-orig-contd-nn.cnn",
    ],
}

# ── News-specific classifier (same as _classify_other.py) ───────────────────
KEYWORDS = {
    "artificial intelligence": [
        r"\bai\b", "openai", "chatgpt", "anthropic", "machine learning",
        "large language model", "generative ai", "neural network", "deepfake",
        "gpt-4", "gpt-3", "gpt-4o", "llm", "gemini ai", "stable diffusion",
        "midjourney", "ai model", "ai tool", "ai chip", "nvidia ai",
        "copilot", "ai-generated", "foundation model",
    ],
    "tech news": [
        "iphone", "android", "samsung galaxy", "semiconductor", "cybersecurity",
        "ransomware", "security vulnerability", "exploit code", "app store",
        "silicon valley", "cloud computing", "data center", "chip shortage",
        "google search", "quantum computing", "self-driving", "autonomous vehicle",
        "linux", "ubuntu", "tech company", "big tech", "apple inc",
        "microsoft windows", "microsoft azure", "amazon web services",
        "software update", "operating system", "open source",
        "canonical", "infrastructure outage", "security flaw",
        "tech policy", "tech regulation", "microsoft", "google",
    ],
    "data privacy": [
        "data privacy", "gdpr", "data breach", "mass surveillance",
        "facial recognition", "biometric", "end-to-end encryption", "spyware",
        "user tracking", "personal data", "data protection", "privacy law",
        "nudif", "sexualiz", "intimate image", "cookie consent",
        "zero-knowledge", "surveillance capitalism", "location tracking",
    ],
    "business": [
        "venture capital", "startup funding", "ipo", "acquisition",
        "company merger", "quarterly earnings", "earnings report", "revenue",
        "profit warning", "nasdaq", "stock market", "wall street",
        "federal reserve", "inflation", "interest rate", "gdp",
        "bankruptcy", "antitrust", "ftc", "supply chain", "retail sales",
        "silicon valley bank", "series a", "series b", "seed round",
        "bill gates", "elon musk", "warren buffett", "private equity",
        "fintech", "acquired by", "sold to", "funding round",
        "investor", "fundraising", "valuation", "unicorn",
        "entrepreneur", "founder", "startup", "chief executive",
        "trade deficit", "trade surplus", "economic growth",
        "market share", "profit margin", "subscription", "saas",
    ],
    "us politics": [
        "supreme court", "white house", "executive order",
        "trump", "biden", "kamala harris", "desantis",
        "republican", "democrat", "us immigration", "government shutdown",
        "electoral college", "voter", "us election", "federal legislation",
        "january 6", "impeach", "attorney general", "postal service",
        "religious freedom", "abortion", "us border",
        "senate", "congress", "house of representatives",
        "federal court", "legislation", "signed into law",
        "us politics", "american politics", "us government",
    ],
    "hollywood": [
        "box office", "oscars", "academy awards", "golden globes", "emmy",
        "film festival", "movie premiere", "biopic", "film director",
        "streaming service", "netflix", "disney plus", "hbo",
        "hollywood", "michael jackson", "rotten tomatoes", "actors strike",
        "writers guild", "sag-aftra", "movie", "cinema", "casting",
    ],
    "world news": [
        "nato", "united nations", "ceasefire", "international sanctions",
        "humanitarian", "refugee", "military", "war", "invasion",
        "protest", "coup", "iran", "ukraine", "russia", "china",
        "north korea", "middle east", "gaza", "israel", "hamas",
        "west bank", "mali", "jihadist", "terrorism", "migration",
        "foreign minister", "prime minister", "parliament",
        "general election", "g7", "g20", "brics",
        "geopolitical", "foreign policy", "diplomatic",
        "sanctions", "blockade", "airstrike", "missile",
    ],
    "climate policy": [
        "climate change", "carbon emissions", "fossil fuel", "renewable energy",
        "solar panel", "wind energy", "greenhouse gas", "net zero",
        "climate policy", "global warming", "deforestation", "air pollution",
        "air quality", "energy transition", "paris agreement", "wildfire",
        "sea level rise", "carbon tax", "drought", "flooding",
        "carbon capture", "clean energy", "climate crisis",
    ],
}

SOURCE_BIAS = {
    "techcrunch":     {"tech news": 2, "business": 2, "artificial intelligence": 1},
    "ars_technica":   {"tech news": 3, "data privacy": 2, "artificial intelligence": 2},
    "cnn_us":         {"us politics": 3, "business": 1},
    "cnn_technology": {"tech news": 3, "artificial intelligence": 2, "data privacy": 1},
    "cnn_world":      {"world news": 2, "climate policy": 1, "business": 1},
    "cnn_top_stories":{"world news": 1, "us politics": 1},
    "bbc":            {"world news": 2, "us politics": 1},
    "al_jazeera":     {"world news": 3},
    "npr":            {"us politics": 2, "world news": 1},
    "reuters":        {"business": 2, "world news": 2},
    "bloomberg":      {"business": 3},
    "france24":       {"world news": 3},
    "africa_news":    {"world news": 3},
    "dw_news":        {"world news": 3},
    "japan_times":    {"world news": 3},
    "the_hindu":      {"world news": 3},
    "abc_australia":  {"world news": 2},
    "south_china_morning_post": {"world news": 3},
    "ap_news":        {"world news": 2},
    "nieman_lab":     {"tech news": 1},
}

COMPILED = {}
for topic, kws in KEYWORDS.items():
    pats = []
    for kw in kws:
        try:
            prefix = r"\b" if kw[0].isalnum() else ""
            suffix = r"\b" if kw[-1].isalnum() else ""
            pats.append(re.compile(prefix + re.escape(kw) + suffix, re.IGNORECASE))
        except Exception:
            pass
    COMPILED[topic] = pats


def classify_news(content, source_name):
    text = content or ""
    content_scores = {t: sum(1 for p in COMPILED[t] if p.search(text)) for t in KEYWORDS}
    if max(content_scores.values(), default=0) == 0:
        return None  # don't insert if no topic signal
    final = dict(content_scores)
    for t, boost in SOURCE_BIAS.get(source_name, {}).items():
        final[t] = final.get(t, 0) + boost
    return max(final, key=final.get)


def clean_html(html):
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text(separator=" ")


def truncate(text, n=2000):
    return text[:n] + "..." if text and len(text) > n else text


def build_post(platform_id, source_name, content, topic, created_at, engagement=0):
    return {
        "platform": "rss",
        "platform_id": platform_id,
        "author_hash": "anonymous",
        "content": truncate(content),
        "topic": topic,
        "source_category": "news",
        "source_name": source_name,
        "created_at": created_at,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "engagement": engagement,
        "raw_metadata": {},
    }


# ── 1. Re-fetch RSS feeds ────────────────────────────────────────────────────
print("=== Step 1: Re-fetching RSS feeds ===")
rss_posts = []
for feed_name, feed_url in RSS_FEEDS.items():
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:30]:
            title   = entry.get("title", "")
            summary = clean_html(entry.get("summary", ""))
            content_full = ""
            if "content" in entry and entry["content"]:
                content_full = clean_html(entry["content"][0].get("value", ""))
            combined = f"{title} {summary} {content_full}"
            topic = classify_news(combined, feed_name)
            if not topic:
                continue
            url = entry.get("link", "")
            if not url:
                continue
            if entry.get("published_parsed"):
                ts = datetime.fromtimestamp(
                    calendar.timegm(entry.published_parsed), tz=timezone.utc
                ).isoformat()
            else:
                ts = datetime.now(timezone.utc).isoformat()
            rss_posts.append(build_post(
                platform_id=url,
                source_name=feed_name,
                content=truncate(content_full if content_full else f"{title} {summary}"),
                topic=topic,
                created_at=ts,
            ))
        print(f"  {feed_name}: {sum(1 for p in rss_posts if p['source_name']==feed_name)} matched")
        time.sleep(0.3)
    except Exception as e:
        print(f"  {feed_name}: ERROR - {e}")

print(f"RSS total: {len(rss_posts)} posts to upsert\n")

# ── 2. Directly fetch specific older URLs ────────────────────────────────────
print("=== Step 2: Fetching specific older URLs ===")
direct_posts = []
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

for source_name, urls in DIRECT_URLS.items():
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"  {url[:60]}... HTTP {resp.status_code}")
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            # Extract title
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else ""
            # Extract article text
            article = soup.find("article") or soup.find(class_=re.compile(r"article|story|body|content", re.I))
            if article:
                body = article.get_text(separator=" ").strip()
            else:
                body = soup.get_text(separator=" ").strip()
            combined = f"{title} {body[:1000]}"
            topic = classify_news(combined, source_name)
            if not topic:
                print(f"  {url[:60]}... no topic match")
                continue
            direct_posts.append(build_post(
                platform_id=url,
                source_name=source_name,
                content=truncate(f"{title}. {body}"),
                topic=topic,
                created_at=datetime.now(timezone.utc).isoformat(),
                engagement=0,
            ))
            print(f"  {source_name} -> {topic}: {title[:60]}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  {url[:60]}... ERROR: {e}")

print(f"Direct fetch total: {len(direct_posts)} posts\n")

# ── 3. Upsert everything ─────────────────────────────────────────────────────
all_posts = rss_posts + direct_posts
# Deduplicate within batch
seen, unique = set(), []
for p in all_posts:
    if p["platform_id"] not in seen:
        seen.add(p["platform_id"])
        unique.append(p)

print(f"=== Step 3: Upserting {len(unique)} unique posts to Supabase ===")
batch_size = 50
inserted = 0
for i in range(0, len(unique), batch_size):
    chunk = unique[i:i+batch_size]
    try:
        client.table("posts").upsert(chunk, on_conflict="platform,platform_id").execute()
        inserted += len(chunk)
        print(f"  {inserted}/{len(unique)} upserted...")
    except Exception as e:
        print(f"  Batch error: {e}")

print(f"\nDone. {inserted} posts upserted.")

# ── 4. Summary ───────────────────────────────────────────────────────────────
from collections import Counter
tally = Counter(p["topic"] for p in unique)
print("\nTopic breakdown:")
for topic, n in tally.most_common():
    print(f"  {n:4d}  {topic}")
