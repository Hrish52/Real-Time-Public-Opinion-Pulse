"""
Reclassify topic labels for existing Supabase rows.

Fetches every row, re-scores against the same keyword rules used by
ingestion_pipeline_v2.py, then batch-updates only the rows that changed.

Usage:
    python reclassify_topics.py --dry-run   # preview without writing
    python reclassify_topics.py             # apply changes (asks for confirmation)
    python reclassify_topics.py --table posts --dry-run

Requirements:
    pip install supabase python-dotenv
    .env file with SUPABASE_URL and SUPABASE_KEY
"""

import re
import os
import argparse
from collections import Counter
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ─────────────────────────────────────────────────────────────
# TOPIC KEYWORDS  ← must match ingestion_pipeline_v2.py exactly
# Topic names are the dict keys; they must match what is already
# stored in the `topic` column so we don't create new labels.
# ─────────────────────────────────────────────────────────────

TRACKED_TOPICS: dict[str, list[str]] = {

    # Rule applied per keyword:
    #   STANDALONE OK  — proper noun or technical acronym unambiguous in news
    #                    (openai, iphone, nato, trump, nasdaq, ransomware …)
    #   COMPOUND NEEDED — common English word that fires on unrelated articles
    #                    (apple→"apple iphone", google→"google search", flood→removed)

    "artificial intelligence": [
        # Named models / companies (unambiguous standalone)
        "openai", "chatgpt", "anthropic",
        "google gemini", "gemini ai",
        "gpt-4", "gpt-3", "gpt-4o",
        "github copilot", "microsoft copilot",
        "midjourney", "stable diffusion", "dall-e", "sora ai",
        "nvidia ai",
        # Technical terms (unambiguous standalone in news)
        "large language model", "llm",
        "generative ai", "ai-generated",
        "foundation model", "diffusion model",
        "transformer model",
        "artificial general intelligence", "agi",
        "neural network",       # specific enough in news context
        "deepfake",             # unambiguous
        "machine learning model",
        # Policy / ethics
        "ai safety", "ai alignment",
        "ai ethics", "ai bias",
        "ai governance", "ai regulation",
        "eu ai act", "ai act",
        # Industry
        "ai chip", "ai startup", "ai investment",
        "artificial intelligence",
    ],

    "climate policy": [
        # Unambiguous compound phrases
        "climate policy", "climate legislation",
        "climate summit", "climate agreement",
        "paris agreement", "paris climate accord",
        "cop29", "cop28", "unfccc",
        "carbon tax", "carbon pricing",
        "carbon emissions",     # specific enough compound
        "net zero",             # unambiguous in policy context
        "carbon neutral",
        "renewable energy policy", "clean energy transition",
        "fossil fuel subsidy", "fossil fuel ban",
        "greenhouse gas",       # unambiguous compound
        "carbon capture",
        "green new deal",
        "climate refugee", "climate migration",
        "sea level rise",
        "amazon deforestation", "deforestation policy",
        "methane emissions",
        "climate crisis", "climate emergency",
        "global warming",
        "carbon offset",
    ],

    "data privacy": [
        # Regulation (unambiguous standalone)
        "gdpr", "ccpa",
        "data privacy", "data protection law",
        "privacy law", "privacy regulation",
        "right to be forgotten",
        # Breaches
        "data breach",          # specific enough compound
        "personal data leak",
        "user data exposed",
        # Surveillance (compound required — "surveillance" alone too broad)
        "mass surveillance", "government surveillance",
        "surveillance capitalism",
        "facial recognition",   # specific enough in tech/policy news
        "biometric data",       # specific enough
        "location tracking",    # specific enough as compound
        # Encryption / tools
        "end-to-end encryption",
        "encrypted messaging",
        "pegasus spyware", "spyware",
        "cookie consent",
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
        # Funding
        "venture capital",      # specific enough compound
        "series a", "series b", "series c",
        "seed round", "seed funding",
        "startup funding",
        # M&A
        "company acquisition", "corporate acquisition",
        "hostile takeover", "company merger",
        "private equity",
        # IPO (unambiguous acronym)
        "ipo",
        "stock market debut",
        # Earnings
        "quarterly earnings", "earnings report",
        "earnings per share", "revenue guidance",
        "profit warning", "earnings beat", "earnings miss",
        # Finance / markets (specific enough)
        "nasdaq",               # unambiguous
        "antitrust lawsuit", "antitrust investigation",
        "ftc lawsuit",
        "unicorn startup", "startup valuation",
        "chapter 11 bankruptcy", "corporate bankruptcy",
        # Macro (compound required — "inflation" alone too broad)
        "supply chain disruption",
        "federal reserve rate", "interest rate hike",
        "inflation report", "inflation data",
    ],

    "us politics": [
        # Named leaders (unambiguous standalone)
        "trump",                # overwhelming association with US politics
        "donald trump", "joe biden", "kamala harris",
        "ron desantis",
        # Institutions (US qualifier makes these specific)
        "us congress", "us senate", "us house",
        "white house",          # unambiguous for US context
        "republican party", "democratic party",
        # Policy / events
        "executive order",
        "supreme court ruling", "supreme court decision",
        "us election", "presidential election", "us midterm",
        "government shutdown", "debt ceiling",
        "us tariff", "american tariff",
        "us immigration policy", "border policy",
        "senate filibuster", "electoral college",
        "impeachment",
        "january 6",
        "voter suppression",
        "gerrymandering",
        "department of justice",
        "us foreign policy", "us presidential race",
    ],

    "hollywood": [
        # Unambiguous standalone
        "hollywood",
        "oscars", "academy awards",
        "oscar nomination", "oscar winner",
        "golden globes", "emmy awards", "bafta",
        "box office",           # specific enough
        "sag-aftra", "writers guild", "wga strike",
        "actors strike", "writers strike",
        # Festivals (compound required — "cannes" alone could be Cannes Lions)
        "cannes film festival", "sundance film festival",
        "film festival",
        # Industry
        "box office record", "box office flop",
        "movie premiere", "film release",
        "rotten tomatoes",
        "netflix original", "hbo series",
        "disney plus", "streaming deal",
        "casting announcement",
        "film remake", "movie sequel",
    ],

    "world news": [
        # Active conflicts (compound required — single country names too broad)
        "israel hamas", "israel hamas war",
        "gaza ceasefire", "gaza war", "west bank",
        "russia ukraine war", "ukraine war", "ukraine conflict",
        "taiwan strait", "taiwan china",
        "iran nuclear deal", "iran nuclear",
        "north korea missile", "north korea nuclear",
        "south china sea",
        # International bodies (unambiguous)
        "united nations", "un security council",
        "nato",                 # unambiguous proper noun
        "european union summit", "eu parliament",
        "g7 summit", "g20 summit", "brics",
        # Diplomacy
        "ceasefire",            # specific enough in news context
        "peace negotiations",
        "international sanctions", "economic sanctions",
        # Crises / events (compound required for generic words)
        "humanitarian crisis", "humanitarian aid",
        "refugee crisis",
        "military offensive", "military strike",
        "missile strike", "missile launch",
        "coup attempt",
        "terror attack", "terrorist attack",
        "assassination attempt",
        "nuclear threat", "nuclear deal",
        "imf report", "world bank",
        "disease outbreak",     # compound specific enough
        "global health emergency",
    ],

    "tech news": [
        # Apple (compound required — "apple" alone matches fruit/records)
        "iphone",               # unambiguous standalone
        "apple iphone", "apple mac", "apple watch",
        "apple vision pro", "apple earnings", "wwdc",
        "apple silicon",
        # Google (compound required)
        "google pixel", "google search", "google chrome",
        "google cloud", "google earnings", "google io",
        # Microsoft (compound required)
        "microsoft windows", "microsoft azure",
        "microsoft surface", "microsoft earnings",
        # Amazon (compound required — "amazon" alone matches rainforest)
        "amazon aws", "amazon web services",
        "amazon alexa", "amazon earnings",
        # Meta (compound required — "meta" alone is a prefix)
        "meta quest", "meta ai", "meta earnings",
        "facebook algorithm", "instagram algorithm",
        # Hardware (unambiguous standalone)
        "samsung galaxy",
        "semiconductor",        # unambiguous in tech news
        "chip shortage",
        "intel processor", "amd processor",
        # Cybersecurity (unambiguous standalone)
        "ransomware",           # unambiguous
        "cybersecurity breach", "data center",
        # Other tech topics
        "5g network", "quantum computing",
        "self-driving car", "autonomous vehicle",
        "tech antitrust", "app store policy",
        "tech product launch", "tech conference",
    ],
}

FALLBACK_TOPIC = "other"


# ─────────────────────────────────────────────────────────────
# Pre-compile patterns once
# ─────────────────────────────────────────────────────────────

def _make_pattern(keyword: str) -> re.Pattern:
    escaped = re.escape(keyword)
    prefix  = r"\b" if keyword and keyword[0].isalnum() else ""
    suffix  = r"\b" if keyword and keyword[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


_COMPILED: dict[str, list[re.Pattern]] = {
    topic: [_make_pattern(kw) for kw in keywords]
    for topic, keywords in TRACKED_TOPICS.items()
}


def classify(text: str) -> str:
    """Return the highest-scoring topic, or FALLBACK_TOPIC if nothing matches."""
    if not isinstance(text, str) or not text.strip():
        return FALLBACK_TOPIC
    scores: dict[str, int] = {}
    for topic, patterns in _COMPILED.items():
        score = sum(1 for p in patterns if p.search(text))
        if score:
            scores[topic] = score
    if not scores:
        return FALLBACK_TOPIC
    return max(scores, key=scores.get)


# ─────────────────────────────────────────────────────────────
# Supabase helpers
# ─────────────────────────────────────────────────────────────

def fetch_all(client, table: str, exclude_news: bool = True) -> list[dict]:
    """Page through the table and return rows, excluding news source_category by default."""
    rows, page, page_size = [], 0, 1000
    while True:
        q = client.table(table).select("id, content, topic, source_category")
        if exclude_news:
            q = q.neq("source_category", "news")
        result = q.range(page * page_size, (page + 1) * page_size - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return rows


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reclassify topic labels in Supabase.")
    parser.add_argument("--dry-run",      action="store_true", help="Preview changes without writing")
    parser.add_argument("--table",        default="posts",     help="Supabase table name (default: posts)")
    parser.add_argument("--include-news", action="store_true", help="Also reclassify news source posts (not recommended)")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")

    client = create_client(url, key)

    exclude_news = not args.include_news
    scope = "social + forum only" if exclude_news else "all posts (including news)"
    print(f"Fetching rows from '{args.table}' ({scope})...")
    rows = fetch_all(client, args.table, exclude_news=exclude_news)
    print(f"  {len(rows):,} rows fetched\n")

    changes:    list[dict] = []
    topic_diff: Counter    = Counter()

    for row in rows:
        text      = row.get("content") or ""
        new_topic = classify(text)
        old_topic = (row.get("topic") or FALLBACK_TOPIC).strip()
        if new_topic != old_topic:
            changes.append({"id": row["id"], "topic": new_topic})
            topic_diff[f"{old_topic}  ->  {new_topic}"] += 1

    # ── Summary ──
    if not changes:
        print("All rows already have correct topics. Nothing to update.")
        return

    print(f"{len(changes):,} rows would change (out of {len(rows):,}):\n")
    for transition, count in topic_diff.most_common(30):
        print(f"  {count:5d}  {transition}")

    if args.dry_run:
        print("\n--dry-run active: no writes performed.")
        return

    confirm = input(f"\nApply {len(changes):,} updates to Supabase? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted — no changes made.")
        return

    # ── Write in chunks to avoid rate limits ──
    updated    = 0
    batch_size = 200
    for i in range(0, len(changes), batch_size):
        chunk = changes[i : i + batch_size]
        for item in chunk:
            client.table(args.table).update({"topic": item["topic"]}).eq("id", item["id"]).execute()
        updated += len(chunk)
        print(f"  {updated:,} / {len(changes):,} updated...")

    print(f"\nDone. {updated:,} rows updated.")


if __name__ == "__main__":
    main()
