"""Check for duplicates and nulls across all posts."""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Paginate all rows
rows, page, page_size = [], 0, 1000
while True:
    result = client.table("posts").select("*").range(page * page_size, (page + 1) * page_size - 1).execute()
    batch = result.data or []
    rows.extend(batch)
    if len(batch) < page_size:
        break
    page += 1

print(f"Total posts: {len(rows)}\n")

# ── 1. Duplicates ─────────────────────────────────────────────
print("=== DUPLICATES ===")

# By platform_id (exact same article)
pid_counter = Counter(r.get("platform_id") for r in rows)
dup_pids = {pid: n for pid, n in pid_counter.items() if n > 1}
print(f"Duplicate platform_ids: {len(dup_pids)}")
for pid, n in list(dup_pids.items())[:10]:
    short = (pid or "")[:80]
    print(f"  x{n}  {short}")

# By content (same text from different sources)
content_counter = Counter(r.get("content") for r in rows if r.get("content"))
dup_content = {c: n for c, n in content_counter.items() if n > 1}
print(f"\nDuplicate content (same text): {len(dup_content)}")
for c, n in list(dup_content.items())[:5]:
    print(f"  x{n}  {c[:80].encode('ascii','ignore').decode()}")

print()

# ── 2. Nulls in key columns ───────────────────────────────────
print("=== NULLS IN KEY COLUMNS ===")
key_cols = ["platform_id", "content", "topic", "source_category",
            "source_name", "created_at", "sentiment_score", "stance"]
for col in key_cols:
    null_count = sum(1 for r in rows if r.get(col) is None or r.get(col) == "")
    pct = null_count / len(rows) * 100
    flag = "  <-- !" if null_count > 0 else ""
    print(f"  {col:<20} null/empty: {null_count:4d}  ({pct:.1f}%){flag}")

print()

# ── 3. Empty content breakdown ────────────────────────────────
print("=== EMPTY CONTENT BREAKDOWN ===")
empty = [r for r in rows if not r.get("content")]
by_src = Counter(r.get("source_name") for r in empty)
print(f"Total empty content: {len(empty)}")
for src, n in by_src.most_common():
    print(f"  {n:4d}  {src}")

print()

# ── 4. Null sentiment/stance ──────────────────────────────────
print("=== NULL SENTIMENT / STANCE BREAKDOWN ===")
no_sent  = [r for r in rows if r.get("sentiment_score") is None]
no_stance = [r for r in rows if not r.get("stance")]
print(f"Null sentiment_score: {len(no_sent)}")
print(f"Null/empty stance:    {len(no_stance)}")
if no_sent:
    by_cat = Counter(r.get("source_category") for r in no_sent)
    print("  by source_category:")
    for cat, n in by_cat.most_common():
        print(f"    {n:4d}  {cat}")
