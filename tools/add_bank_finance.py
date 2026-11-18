#!/usr/bin/env python3
"""add_bank_finance.py: adapt public/finance.html to the bank-balances ledger model (idempotent).

Usage: python3 add_bank_finance.py ~/projects/payload

* Only books that actually have accounts get a slicer button. The bank sheet has no Aster
  Vale reserve or Hakk personal accounts, so the old buttons would select nothing.
* The flow-slicer wording describes capex purchases and nightly opex sweeps instead of the
  old CR-03 workbook notes.
Run `chcon -R --reference=<project> public` afterwards (runbook rule).
"""
import pathlib, sys

P = pathlib.Path(sys.argv[1]).expanduser() / 'public/finance.html'
s = P.read_text(encoding='utf-8')
EDITS = [
    ("const BOOKS = [['corporate','Corporate'],['reserve','Aster Vale reserve'],['personal','Hakk personal']];",
     "const BOOKS = [['corporate','Corporate'],['reserve','Aster Vale reserve'],['personal','Hakk personal']].filter(([b]) => D.entities.some(e => e.book === b));"),
    ("flows hidden — the CR-03 capital and transfers between our own entities dwarf trading",
     "flows hidden — capex purchases and the nightly opex sweeps dwarf day-to-day spending"),
    ("Capital: CR-03, paying agents, sweeps, acquisitions. Intra-group: moves between our own entities.",
     "Capital: capex-tagged purchases and property. Intra-group: the nightly opex sweeps into SI Main."),
]
changed = 0
for old, new in EDITS:
    if new in s:
        print('skip (already applied):', new[:60]); continue
    assert s.count(old) == 1, f'anchor not found once: {old[:60]}'
    s = s.replace(old, new); changed += 1; print('patch finance.html:', new[:60])
if changed:
    P.write_text(s, encoding='utf-8')
print(f'[OK] {changed} change(s)')
