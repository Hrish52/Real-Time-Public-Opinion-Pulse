import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Count by topic + source_category
result = client.table("posts").select("topic, source_category").execute()
rows = result.data or []
print(f"Total posts: {len(rows)}\n")

tally = Counter((r["topic"], r["source_category"]) for r in rows)
print("topic                    source_category   count")
print("-" * 55)
for (topic, cat), n in sorted(tally.most_common(40)):
    print(f"  {topic:<24} {cat:<18} {n}")
