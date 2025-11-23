#!/usr/bin/env python3
"""
Test LLM metric on YOUR repository: CS_450_Phase_2
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 80)
print("ANALYZING YOUR REPOSITORY: CS_450_Phase_2")
print("=" * 80)

repo_url = "https://github.com/emsilver987/CS_450_Phase_2"
print(f"\n📍 Repository: {repo_url}")

print("\n[Step 1/4] Fetching YOUR README from GitHub...")
try:
    from acmecli.github_handler import GitHubHandler
    
    handler = GitHubHandler()
    meta = handler.fetch_meta(repo_url)
    
    if meta and meta.get('readme_text'):
        readme = meta['readme_text']
        print(f"✅ README fetched successfully!")
        print(f"   Repository: {meta.get('name', 'N/A')}")
        print(f"   Stars: {meta.get('stars', 0)}")
        print(f"   License: {meta.get('license', 'N/A')}")
        print(f"   README length: {len(readme)} characters")
        print(f"\n   First 200 chars of YOUR README:")
        print(f"   {readme[:200]}...")
    else:
        print("⚠️  Could not fetch README (rate limit?)")
        print("   Using local README instead...")
        # Read local README
        readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
        with open(readme_path, 'r') as f:
            readme = f.read()
        meta = {
            'name': 'CS_450_Phase_2',
            'readme_text': readme,
            'stars': 0,
            'license': ''
        }
        print(f"✅ Local README loaded ({len(readme)} characters)")
        
except Exception as e:
    print(f"⚠️  Error: {e}")
    # Fallback to local README
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    with open(readme_path, 'r') as f:
        readme = f.read()
    meta = {
        'name': 'CS_450_Phase_2',
        'readme_text': readme,
        'stars': 0,
        'license': ''
    }
    print(f"✅ Using local README ({len(readme)} characters)")

print("\n[Step 2/4] Running LLM analysis on YOUR README...")
try:
    from acmecli.metrics.llm_summary_metric import LLMSummaryMetric
    
    metric = LLMSummaryMetric()
    result = metric.score(meta)
    
    print(f"✅ Analysis complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("📊 LLM ANALYSIS OF YOUR REPOSITORY")
print("=" * 80)

print(f"\n🎯 SCORE: {result.value}")
print(f"⏱️  LATENCY: {result.latency_ms}ms")

print(f"\n📝 SUMMARY:")
print(f"   {meta.get('llm_summary', 'N/A')}")

print(f"\n⚠️  RISK FLAGS:")
flags = meta.get('llm_risk_flags', [])
if flags:
    for flag in flags:
        print(f"   - {flag}")
else:
    print(f"   None - Great job! ✅")

print("\n" + "=" * 80)
print("🔍 WHAT THE LLM FOUND IN YOUR README")
print("=" * 80)

readme_lower = readme.lower()

checks = [
    ("License Information", any(lic in readme_lower for lic in ['license', 'mit', 'apache', 'gpl'])),
    ("Installation Instructions", any(word in readme_lower for word in ['install', 'pip install', 'setup'])),
    ("Usage Examples", any(word in readme_lower for word in ['usage', 'example', 'demo'])),
    ("API Documentation", any(word in readme_lower for word in ['api', 'endpoint', 'route'])),
    ("Testing Information", any(word in readme_lower for word in ['test', 'pytest', 'testing'])),
    ("AWS/Cloud Info", any(word in readme_lower for word in ['aws', 'cloud', 'terraform', 'ecs'])),
    ("Security/Safety", any(word in readme_lower for word in ['security', 'safety', 'stride', 'threat'])),
]

for check_name, found in checks:
    status = "✅ Found" if found else "❌ Missing"
    print(f"{status:12} {check_name}")

print("\n" + "=" * 80)
print("💡 INTERPRETATION")
print("=" * 80)

if result.value >= 0.7:
    print("🌟 EXCELLENT! Your README is well-documented.")
elif result.value >= 0.5:
    print("👍 GOOD! Your README has decent documentation.")
else:
    print("⚠️  NEEDS IMPROVEMENT. Consider adding more documentation.")

print(f"\nYour README scored {result.value} out of 1.0")
print(f"This contributes {result.value * 0.05:.3f} to your net score (5% weight)")

print("\n" + "=" * 80)
print("✅ ANALYSIS COMPLETE!")
print("=" * 80)
