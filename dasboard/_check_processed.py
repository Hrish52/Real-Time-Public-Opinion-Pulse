import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

result = client.table("posts").select("topic, source_category, is_processed").execute()
rows = result.data or []

tally = Counter((r["topic"], r["source_category"], r.get("is_processed")) for r in rows)
print(f"{'topic':<24} {'source_cat':<12} {'is_processed':<14} count")
print("-" * 60)
for (topic, cat, proc), n in sorted(tally.most_common(50)):
    print(f"  {topic:<22} {cat:<12} {str(proc):<14} {n}")
