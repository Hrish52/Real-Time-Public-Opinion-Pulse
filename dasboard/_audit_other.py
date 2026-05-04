"""
Show a sample of 'other' posts grouped by source to spot patterns
that could be added to keywords.
"""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

result = client.table("posts").select("source_category, source_name, content").eq("topic", "other").execute()
rows = result.data or []
print(f"Total 'other' posts: {len(rows)}\n")

by_cat = Counter(r["source_category"] for r in rows)
print("By source_category:")
for cat, n in by_cat.most_common():
    print(f"  {n:4d}  {cat}")
print()

# Show 10 samples per source_category
for cat in ["social", "forum"]:
    samples = [r for r in rows if r["source_category"] == cat][:10]
    if not samples:
        continue
    print(f"=== {cat} samples (10) ===")
    for r in samples:
        snippet = (r.get("content") or "")[:120].replace("\n", " ")
        print(f"  [{r.get('source_name','?')}] {snippet}".encode("ascii", "ignore").decode())
    print()
