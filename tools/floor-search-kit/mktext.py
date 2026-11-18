#!/usr/bin/env python3
"""mktext.py PDF OUT.md TITLE -- page-marked text from a PDF (pdftotext -layout): one '## PDF Page N' section per page."""
import re, subprocess, sys
pdf, out, title = sys.argv[1:4]
t = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
parts = [f"# {title}\n\nText extracted from the PDF (pdftotext -layout), one section per PDF page.\n"]
for i, p in enumerate(t.split("\f"), 1):
    p = re.sub(r"[ \t]+\n", "\n", p).strip("\n")
    if p.strip():
        parts.append(f"\n## PDF Page {i}\n\n{p}\n")
open(out, "w", encoding="utf-8").write("".join(parts))
print(out, sum(len(x) for x in parts))
