"""
Classify 'other + news' posts using content keywords + source-name signals.
Run without --apply to preview; add --apply to write changes to Supabase.
"""
import os, re, sys, argparse
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

result = (
    client.table("posts")
    .select("id, platform_id, source_name, content")
    .eq("topic", "other")
    .eq("source_category", "news")
    .execute()
)
posts = result.data or []
print(f"Total other+news posts: {len(posts)}\n")

# ─────────────────────────────────────────────────────────────────────────────
# Content keywords — tuned for formal news prose.
# Rule: single words only when unambiguous in a news headline/article context.
# ─────────────────────────────────────────────────────────────────────────────
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
        "tech policy", "tech regulation",
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
        "investor", "fundraising", "valuation", "unicorn", "exit",
        "entrepreneur", "founder", "startup", "chief executive",
        "trade deficit", "trade surplus", "economic growth",
        "market share", "profit margin", "layoff", "job cut",
        "subscription", "saas", "b2b",
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
        "us president", "us policy",
    ],
    "hollywood": [
        "box office", "oscars", "academy awards", "golden globes", "emmy",
        "film festival", "movie premiere", "biopic", "film director",
        "streaming service", "netflix", "disney plus", "hbo",
        "hollywood", "michael jackson", "rotten tomatoes", "actors strike",
        "writers guild", "sag-aftra", "movie", "film", "cinema",
        "casting", "box office", "sequel", "remake",
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
        "sea level rise", "carbon tax", "drought", "flooding", "flood",
        "carbon capture", "clean energy", "climate crisis",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Source-name bias — boost topics when a source strongly implies one.
# Bias alone never classifies; content must score >= 1 first.
# ─────────────────────────────────────────────────────────────────────────────
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
    "science_daily":  {},  # stays "other" — science content is not in our topics
}

# Pre-compile all patterns once
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
    # Content must have at least 1 hit — source bias alone is not enough
    if max(content_scores.values(), default=0) == 0:
        return "other"
    final = dict(content_scores)
    for t, boost in SOURCE_BIAS.get(source_name, {}).items():
        final[t] = final.get(t, 0) + boost
    return max(final, key=final.get)


# ─────────────────────────────────────────────────────────────────────────────
# Classify all posts
# ─────────────────────────────────────────────────────────────────────────────
changes = []
tally   = Counter()
details = []

for p in posts:
    new_topic = classify_news(p.get("content", ""), p.get("source_name", ""))
    tally[new_topic] += 1
    if new_topic != "other":
        changes.append({"id": p["id"], "topic": new_topic})
    details.append((p.get("source_name", "?"), new_topic,
                    (p.get("content") or "")[:130].replace("\n", " ").encode("ascii", "ignore").decode()))

print("Proposed reclassification:")
for topic, n in tally.most_common():
    marker = "<-- stays other" if topic == "other" else ""
    print(f"  {n:4d}  {topic}  {marker}")
print(f"  ----")
print(f"  {len(changes):4d}  total would be updated\n")

print("Sample assignments (first 50):")
for src, topic, snippet in details[:50]:
    print(f"  [{src}] -> {topic}")
    print(f"    {snippet}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# Apply
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--apply", action="store_true")
args, _ = parser.parse_known_args()

if not args.apply:
    print("\nRun with --apply to write changes to Supabase.")
else:
    print(f"\nApplying {len(changes)} updates...")
    for i, item in enumerate(changes, 1):
        client.table("posts").update({"topic": item["topic"]}).eq("id", item["id"]).execute()
        if i % 25 == 0:
            print(f"  {i}/{len(changes)} done...")
    print(f"Done. {len(changes)} rows updated.")
