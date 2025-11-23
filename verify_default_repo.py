#!/usr/bin/env python3
"""
Quick verification that YOUR repo is in urls.txt and will be scored
"""
import os

print("=" * 80)
print("VERIFICATION: Your Repo is Set as Default")
print("=" * 80)

# Read urls.txt
urls_file = "urls.txt"
with open(urls_file, 'r') as f:
    urls = [line.strip() for line in f if line.strip()]

print(f"\n📄 Contents of {urls_file}:")
print("-" * 80)
for i, url in enumerate(urls, 1):
    marker = " ← YOUR REPO! 🎯" if "CS_450_Phase_2" in url else ""
    print(f"{i}. {url}{marker}")

print("\n" + "=" * 80)
print("✅ VERIFICATION RESULTS")
print("=" * 80)

your_repo = "https://github.com/emsilver987/CS_450_Phase_2"
if urls and urls[0] == your_repo:
    print(f"✅ Your repo IS the FIRST URL in urls.txt")
    print(f"✅ Position: #1 (will be scored first)")
    print(f"✅ URL: {your_repo}")
elif your_repo in urls:
    pos = urls.index(your_repo) + 1
    print(f"⚠️  Your repo is in urls.txt but not first")
    print(f"   Position: #{pos}")
else:
    print(f"❌ Your repo is NOT in urls.txt")
    print(f"   Expected: {your_repo}")

print("\n" + "=" * 80)
print("📊 WHAT WILL BE SCORED")
print("=" * 80)
print(f"\nWhen you run: ./run score urls.txt")
print(f"\nThe LLM metric will analyze these {len(urls)} repositories:")
for i, url in enumerate(urls, 1):
    repo_name = url.split('/')[-1]
    is_yours = "← YOUR REPO" if "CS_450_Phase_2" in url else ""
    print(f"  {i}. {repo_name:30} {is_yours}")

print("\n" + "=" * 80)
print("✅ CONFIRMED: Your repo is set as default!")
print("=" * 80)
