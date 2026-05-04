"""Full paginated summary of all posts by topic + source_category."""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

rows, page, page_size = [], 0, 1000
while True:
    result = client.table("posts").select("topic, source_category, is_processed").range(page * page_size, (page + 1) * page_size - 1).execute()
    batch = result.data or []
    rows.extend(batch)
    if len(batch) < page_size:
        break
    page += 1

print(f"Total posts in DB: {len(rows)}\n")

tally = Counter((r["topic"], r["source_category"]) for r in rows)
print(f"{'topic':<26} {'source_cat':<12} count")
print("-" * 45)
for (topic, cat), n in sorted(tally.most_common(50)):
    print(f"  {topic:<24} {cat:<12} {n}")

print()
proc = Counter(r.get("is_processed") for r in rows)
print("is_processed breakdown:")
for k, v in proc.most_common():
    print(f"  {str(k):<8} {v}")
