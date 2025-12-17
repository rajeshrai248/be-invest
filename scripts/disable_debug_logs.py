#!/usr/bin/env python3
"""Script to disable all debug logging in server.py"""

import re
from pathlib import Path

filePath = Path(__file__).parent.parent / "src" / "be_invest" / "api" / "server.py"

with open(filePath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Process each line and comment out logger.debug statements
new_lines = []
for line in lines:
    stripped = line.lstrip()
    # Only comment out if not already commented
    if stripped.startswith('logger.debug(') and not line.lstrip().startswith('# logger.debug'):
        # Preserve indentation
        indent = len(line) - len(stripped)
        new_lines.append(' ' * indent + '# ' + line[indent:])
    else:
        new_lines.append(line)

with open(filePath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ All logger.debug calls have been commented out")

