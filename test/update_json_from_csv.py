import json
import csv
from pathlib import Path

# Load JSON data
with open("data/generated.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Load CSV data into a dict keyed by blog_id
csv_map = {}
with open("data/blogs_latest.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # blog_id may be string, convert to int for matching
        try:
            blog_id = int(row["blog_id"])
            csv_map[blog_id] = {
                "title": row["title"],
                "content": row["content"]
            }
        except Exception:
            continue

# Update articles in JSON
for article in data.get("Articles", []):
    aid = article.get("id")
    if aid in csv_map:
        article["title"] = csv_map[aid]["title"]
        article["content"] = csv_map[aid]["content"]
        article["summary"] = csv_map[aid]["content"][:200]  # Update summary to first 200 chars

# Save to new file
with open("data/generated_updated_1308.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    
    
    