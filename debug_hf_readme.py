import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from acmecli.hf_handler import HFHandler

url = "https://huggingface.co/gpt2"
print(f"Fetching metadata for: {url}")

handler = HFHandler()
meta = handler.fetch_meta(url)

print("\nMetadata Keys:", list(meta.keys()))
print(f"README Text Length: {len(meta.get('readme_text', ''))}")
print(f"README Text Preview: {meta.get('readme_text', '')[:100]}")

if not meta.get('readme_text'):
    print("\n❌ No README text found!")
else:
    print("\n✅ README text found!")
