"""Delete duplicate-content posts, keeping the oldest occurrence of each."""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import defaultdict

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

rows, page, page_size = [], 0, 1000
while True:
    result = client.table("posts").select("id, content, created_at").range(page * page_size, (page + 1) * page_size - 1).execute()
    batch = result.data or []
    rows.extend(batch)
    if len(batch) < page_size:
        break
    page += 1

print(f"Total posts: {len(rows)}")

by_content = defaultdict(list)
for r in rows:
    c = (r.get("content") or "").strip()
    if c:
        by_content[c].append(r)

to_delete = []
for content, dupes in by_content.items():
    if len(dupes) > 1:
        # Keep oldest (earliest created_at), delete the rest
        sorted_dupes = sorted(dupes, key=lambda r: r.get("created_at") or "")
        to_delete.extend(r["id"] for r in sorted_dupes[1:])

print(f"Duplicate extra rows to delete: {len(to_delete)}")

for i, post_id in enumerate(to_delete, 1):
    client.table("posts").delete().eq("id", post_id).execute()
    if i % 10 == 0:
        print(f"  {i}/{len(to_delete)} deleted...")

print(f"Done. {len(to_delete)} duplicate rows removed.")
print(f"Remaining posts: {len(rows) - len(to_delete)}")
