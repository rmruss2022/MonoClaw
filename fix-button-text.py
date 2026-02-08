#!/usr/bin/env python3
import sys
import re

filename = sys.argv[1]
with open(filename, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the back button content (multiline)
content = re.sub(
    r'(<a href="http://localhost:18795/hub" class="back-button">)[^<]*\s*[^<]*\s*</a>',
    r'\1Hub</a>',
    content,
    flags=re.DOTALL
)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✓ Fixed {filename}")
