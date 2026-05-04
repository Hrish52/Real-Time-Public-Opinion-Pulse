"""Data quality audit: summary breakdown, duplicates, and nulls."""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

rows, page, page_size = [], 0, 1000
while True:
    result = client.table("posts").select("*").range(page * page_size, (page + 1) * page_size - 1).execute()
    batch = result.data or []
    rows.extend(batch)
    if len(batch) < page_size:
        break
    page += 1

print(f"Total posts: {len(rows)}\n")

# ── 1. Topic + source breakdown ───────────────────────────────
print("=== TOPIC BREAKDOWN ===")
tally = Counter((r["topic"], r["source_category"]) for r in rows)
print(f"{'topic':<26} {'source_cat':<12} count")
print("-" * 45)
for (topic, cat), n in sorted(tally.most_common(50)):
    print(f"  {topic:<24} {cat:<12} {n}")

proc = Counter(r.get("is_processed") for r in rows)
print(f"\nis_processed: {dict(proc)}\n")

# ── 2. Duplicates ─────────────────────────────────────────────
print("=== DUPLICATES ===")
pid_counter = Counter(r.get("platform_id") for r in rows)
dup_pids = {pid: n for pid, n in pid_counter.items() if n > 1}
print(f"Duplicate platform_ids:        {len(dup_pids)}")

content_counter = Counter(r.get("content") for r in rows if r.get("content"))
dup_content = {c: n for c, n in content_counter.items() if n > 1}
extra = sum(n - 1 for n in dup_content.values())
print(f"Duplicate content strings:     {len(dup_content)}  ({extra} extra rows)")
for c, n in sorted(dup_content.items(), key=lambda x: -x[1])[:5]:
    print(f"  x{n}  {c[:80].encode('ascii','ignore').decode()}")

print()

# ── 3. Nulls in key columns ───────────────────────────────────
print("=== NULLS IN KEY COLUMNS ===")
key_cols = ["platform_id", "content", "topic", "source_category",
            "source_name", "created_at", "sentiment_score", "stance"]
for col in key_cols:
    null_count = sum(1 for r in rows if r.get(col) is None or r.get(col) == "")
    pct = null_count / len(rows) * 100
    flag = "  <-- !" if null_count > 0 else ""
    print(f"  {col:<20} null/empty: {null_count:4d}  ({pct:.1f}%){flag}")

print()

# ── 4. Null sentiment/stance detail ───────────────────────────
print("=== NULL SENTIMENT / STANCE ===")
no_sent   = [r for r in rows if r.get("sentiment_score") is None]
no_stance = [r for r in rows if not r.get("stance")]
print(f"Null sentiment_score: {len(no_sent)}")
print(f"Null/empty stance:    {len(no_stance)}")
if no_sent:
    by_cat = Counter(r.get("source_category") for r in no_sent)
    for cat, n in by_cat.most_common():
        print(f"  {n:4d}  {cat}")
