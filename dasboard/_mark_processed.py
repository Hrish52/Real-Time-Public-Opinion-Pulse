"""
Set is_processed=True for all news posts that are still False/NULL.
Uses neutral sentiment defaults so they show up in the dashboard.
"""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Fetch one processed post to see which sentiment/stance columns exist
sample = client.table("posts").select("*").eq("is_processed", True).limit(1).execute()
if sample.data:
    print("Columns in a processed post:")
    print([k for k in sample.data[0].keys()])
    print()

# Fetch all unprocessed news posts
result = client.table("posts").select("id").eq("is_processed", False).eq("source_category", "news").execute()
ids = [r["id"] for r in (result.data or [])]
print(f"Unprocessed news posts: {len(ids)}")

if not ids:
    print("Nothing to update.")
else:
    # Update in batches
    batch_size = 100
    updated = 0
    for i in range(0, len(ids), batch_size):
        chunk = ids[i:i+batch_size]
        for post_id in chunk:
            client.table("posts").update({
                "is_processed": True,
                "sentiment_score": 0.0,
                "stance": "neutral",
            }).eq("id", post_id).execute()
        updated += len(chunk)
        print(f"  {updated}/{len(ids)} updated...")
    print(f"Done. {updated} posts marked as processed.")
