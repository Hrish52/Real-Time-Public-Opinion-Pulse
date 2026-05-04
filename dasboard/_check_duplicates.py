"""Detailed duplicate check across all sources."""
import os, sys
sys.path.insert(0, r"C:\Users\hirshikesh\AppData\Roaming\Python\Python313\site-packages")
from dotenv import load_dotenv
from supabase import create_client
from collections import defaultdict

load_dotenv()
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

rows, page, page_size = [], 0, 1000
while True:
    result = client.table("posts").select("id, platform_id, platform, source_name, source_category, content, topic, created_at").range(page * page_size, (page + 1) * page_size - 1).execute()
    batch = result.data or []
    rows.extend(batch)
    if len(batch) < page_size:
        break
    page += 1

print(f"Total posts: {len(rows)}\n")

# ── 1. Exact platform_id duplicates ──────────────────────────
print("=== 1. DUPLICATE platform_id ===")
by_pid = defaultdict(list)
for r in rows:
    by_pid[r.get("platform_id")].append(r)
dup_pid = {pid: rs for pid, rs in by_pid.items() if len(rs) > 1}
print(f"Count: {len(dup_pid)} duplicate platform_ids\n")
for pid, rs in list(dup_pid.items())[:10]:
    print(f"  platform_id: {(pid or '')[:70]}")
    for r in rs:
        print(f"    id={r['id']}  source={r.get('source_name')}  topic={r.get('topic')}")
    print()

# ── 2. Exact content duplicates ───────────────────────────────
print("=== 2. DUPLICATE content (exact) ===")
by_content = defaultdict(list)
for r in rows:
    c = (r.get("content") or "").strip()
    if c:
        by_content[c].append(r)
dup_content = {c: rs for c, rs in by_content.items() if len(rs) > 1}
print(f"Count: {len(dup_content)} duplicate content strings\n")
for content, rs in sorted(dup_content.items(), key=lambda x: -len(x[1])):
    print(f"  x{len(rs)}  [{rs[0].get('source_category')}] {content[:90].encode('ascii','ignore').decode()}")
    for r in rs:
        print(f"    id={r['id']}  source={r.get('source_name')}  topic={r.get('topic')}  created={str(r.get('created_at',''))[:10]}")
    print()

# ── 3. Same source + same content ────────────────────────────
print("=== 3. SAME source_name + same content ===")
by_src_content = defaultdict(list)
for r in rows:
    key = (r.get("source_name"), (r.get("content") or "").strip()[:200])
    if key[1]:
        by_src_content[key].append(r)
dup_src = {k: rs for k, rs in by_src_content.items() if len(rs) > 1}
print(f"Count: {len(dup_src)} same-source duplicate content\n")
for (src, content), rs in sorted(dup_src.items(), key=lambda x: -len(x[1])):
    print(f"  x{len(rs)}  [{src}] {content[:80].encode('ascii','ignore').decode()}")
    for r in rs:
        print(f"    id={r['id']}  topic={r.get('topic')}  created={str(r.get('created_at',''))[:10]}")
    print()

# ── Summary ───────────────────────────────────────────────────
total_dup_ids = [r["id"] for rs in dup_content.values() for r in rs[1:]]
print(f"=== SUMMARY ===")
print(f"  Duplicate platform_ids:          {len(dup_pid)}")
print(f"  Duplicate content strings:       {len(dup_content)}  ({sum(len(rs)-1 for rs in dup_content.values())} extra rows)")
print(f"  Same source+content duplicates:  {len(dup_src)}  ({sum(len(rs)-1 for rs in dup_src.values())} extra rows)")
