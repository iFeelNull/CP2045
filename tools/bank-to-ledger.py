#!/usr/bin/env python3
"""bank-to-ledger.py: turn a packet's cp-ref-bank-balances.md into the finance dashboard's ledger.json.

The Slipstream books no longer come from an .xlsx workbook. Every day close writes
cp-ref-bank-balances.md into the packet. The model it records:

  * Each company keeps an OPEX account. Every night at 00:00, everything above that
    account's float is swept into SI Main.
  * SI TOTAL = SI Main + the sum of every company's opex account.
  * SI Main(day N) = SI Main(day N-1) + the sweep booked under day N + the SI Main debits of day N.

Usage (dry run first; --apply writes):
  python3 bank-to-ledger.py PACKET_DIR [--ledger ~/projects/payload/public/data/ledger.json] [--packet 121] [--apply]

History accumulates. Each packet's file only covers the most recent days, so the days already
in ledger.json are kept, and days present in the new file replace the stored copy. The raw
per-day figures live in ledger.json under "bank" and every view is rebuilt from them, so a
re-run with the same packet changes nothing.

The first run on an old xlsx-model ledger.json archives it next to it as
ledger-xlsx-day<N>.json. It is not merged, because that model counted company cash, not
opex floats, so the two series do not join.
"""
import argparse, datetime, json, os, pathlib, re, shutil, subprocess, sys

# ---------------------------------------------------------------- command line
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('packet', help='unpacked packet dir (or the cp-ref-bank-balances.md file itself)')
ap.add_argument('--ledger', default=str(pathlib.Path.home() / 'projects/payload/public/data/ledger.json'),
                help='dashboard JSON to update (default: the hobby site\'s public/data/ledger.json)')
ap.add_argument('--packet', dest='packet_no', default='', help='packet number, recorded in the source note')
ap.add_argument('--apply', action='store_true', help='write the file (default is a dry run)')
ap.add_argument('--properties', default='', help='property register (default: the packet\'s cp-ref-property-register.md, '
                'else ~/projects/payload/data/property-register.md)')
A = ap.parse_args()

src = pathlib.Path(A.packet).expanduser()
if src.is_dir():
    src = src / 'cp-ref-bank-balances.md'          # the file name every day close uses
if not src.is_file():
    sys.exit(f'[FAIL] {src} not found')
LEDGER = pathlib.Path(A.ledger).expanduser()

# ---------------------------------------------------------------- entities
# Opex-account label in the bank sheet -> (id, display name, code). The ids match the old
# dashboard where the company is the same, so CSV exports and bookmarks stay comparable.
# A company that is not listed here gets an id made from its name, so a new company in a
# later packet shows up without a code change. Add it here to give it a nicer code.
KNOWN = {
    'SI payroll':                       ('sipay', 'SI payroll',                       'PAY'),
    'Whitehat Technical Services':      ('wts',   'Whitehat Technical Services',      'WTS'),
    'SI TEAB':                          ('teab',  'SI TEAB',                          'TEAB'),
    'Slipstream Medical Complex':       ('smc',   'Slipstream Medical Complex',       'SMC'),
    'IntraCorp Logistics':              ('icl',   'IntraCorp Logistics',              'ICL'),
    'NorTex Exploration':               ('ntx',   'NorTex Exploration',               'NTX'),
    'NorTex Agriculture':               ('nta',   'NorTex Agriculture',               'NTA'),
    'SIVOSS Security Services':         ('svs',   'SIVOSS Security Services',         'SVS'),
    'SIVOSS Veteran Outreach':          ('svo',   'SIVOSS Veteran Outreach',          'SVO'),
    'SI Community Development':         ('scd',   'SI Community Development',         'SCD'),
    'Nightshades (through Aster Vale)': ('nsh',   'Nightshades (through Aster Vale)', 'NSH'),
}
MAIN = ('si', 'SI Main (Slipstream Industries)', 'SI')

def ent_for(label):
    """Map an opex row label to (id, name, code); invent a stable one for unknown companies."""
    if label in KNOWN:
        return KNOWN[label]
    slug = re.sub(r'[^a-z0-9]+', '', label.lower())[:10] or 'x'
    code = ''.join(w[0] for w in re.findall(r'[A-Za-z]+', label)).upper()[:5] or slug.upper()
    return (slug, label, code)

# ---------------------------------------------------------------- parsing
def num(s):
    """'−1,234.50' / '+422,484.42' / '**20,790,277,332.31**' -> float (the sheet uses U+2212 minus)."""
    s = s.replace('*', '').replace(',', '').replace('−', '-').replace('+', '').strip()
    return float(s)

DAY_RE = re.compile(r'^## DAY (\d+)\s*[—-]\s*(\w+),\s*(\w+)\s+(\d+),\s*(\d{4})', re.M)

# HAKK-POSITIONS v1: the bank sheet's Hakk sections (personal accounts; stock positions moved that day)
_HM = re.compile(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+')
def _hnum(cell):
    m = _HM.search(cell.replace('*', ''))
    return float(m.group().replace(',', '')) if m else None
def _htable(block, heading_re):
    m = re.search(heading_re, block, re.M)
    if not m:
        return []
    rows, started = [], False
    for line in block[m.end():].splitlines():
        if line.startswith('|'):
            started = True
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not re.fullmatch(r':?-{3,}:?', cells[0]):
                rows.append(cells)
        elif started and line.strip():
            break
    return rows[1:]
def hakk_accounts(block):
    """{'Main': close, 'Investment Capital': close, 'PERSONAL TOTAL': close} from the HAKK — PERSONAL table."""
    out = {}
    for c in _htable(block, r'^\*\*HAKK\s*[—-]\s*PERSONAL'):
        if len(c) >= 4 and _hnum(c[-1]) is not None:
            out[re.sub(r'\*', '', c[0]).strip()] = _hnum(c[-1])
    return out
def hakk_stocks(block):
    """Rows of the HAKK — STOCK POSITIONS MOVED table: issuer, codes, shares, % of class, mark, value."""
    out = []
    for c in _htable(block, r'^\*\*HAKK\s*[—-]\s*STOCK POSITIONS'):
        if len(c) < 5:
            continue
        name = re.sub(r'\*', '', c[0]).strip()
        short = re.split(r'\s+[—–]\s+|\(', name)[0].strip()
        cls = 'preferred' if 'preferred' in short.lower() else 'common'
        issuer = re.sub(r'\s+(common|preferred)$', '', short, flags=re.I).strip()
        pct = re.search(r'(\d+(?:\.\d+)?)%', c[2])
        mark = _hnum(c[3]) if re.search(r'\d', c[3]) else None
        value = _hnum(c[4]) if re.search(r'\d', c[4]) else None
        out.append({'issuer': issuer, 'cls': cls, 'codes': '+'.join(dict.fromkeys(re.findall(r'\b[A-D]\d{2}\b', name))),
                    'shares': _hnum(c[1]) or 0, 'pct': float(pct.group(1)) if pct else None,
                    'mark': mark, 'value': value, 'label': name[:200]})
    return out

def parse(text):
    """Return {day: {...}} for every '## DAY N' block in the bank sheet."""
    out = {}
    heads = list(DAY_RE.finditer(text))
    for i, h in enumerate(heads):
        block = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        day = int(h.group(1))
        wd, mon, dd, yy = h.group(2), h.group(3), int(h.group(4)), int(h.group(5))
        rec = {'label': f'{wd[:3].title()} {mon[:3].title()} {dd}', 'date': f'{wd.title()} {mon.title()} {dd}, {yy}',
               'total': None, 'main': None, 'opex': {}, 'sweeps': [], 'debits': []}
        sec = None
        for line in block.splitlines():
            if re.match(r'\*\*HAKK\b', line.strip()):  # HAKK-POSITIONS v1: Hakk's sections follow; not SI Main
                sec = 'hakk'; continue
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            head = cells[0].lower()
            # Section headers are the first row of each table.
            if head == 'si' and cells[1].lower() == 'balance':             sec = 'si';    continue
            if head == 'company':                                         sec = 'opex';  continue
            if head.startswith('sweep'):                                  sec = 'sweep'; continue
            if head.startswith('~time'):                                  sec = 'debit'; continue
            if re.fullmatch(r':?-{3,}:?', cells[0]):                       continue      # |---| separator
            if sec == 'si':
                (rec.__setitem__('total', num(cells[1])) if 'TOTAL' in cells[0].upper() else rec.__setitem__('main', num(cells[1])))
            elif sec == 'opex':
                rec['opex'][cells[0]] = num(cells[1])
            elif sec == 'sweep':
                rec['sweeps'].append({'memo': cells[0], 'amount': num(cells[1])})
            elif sec == 'debit':
                rec['debits'].append({'time': cells[0], 'memo': cells[1], 'amount': num(cells[-1])})
        rec['hakk'] = hakk_accounts(block)
        rec['stocks'] = hakk_stocks(block)
        if rec['total'] is None or rec['main'] is None:
            sys.exit(f'[FAIL] Day {day}: no SI TOTAL / SI Main row; the sheet layout changed')
        out[day] = rec
    if not out:
        sys.exit(f'[FAIL] no "## DAY N" blocks in {src}')
    return out

# ---------------------------------------------------------------- classifying debits
# Keyword rules for the dashboard's category slicer, first match wins. They only drive
# colours and grouping; the amounts always come straight from the sheet.
RULES = [
    ('Payroll',               r'\bpayroll\b'),
    ('Capital & investment',  r'\bdeeds?\b|\btax lot\b|\bCLOSED:|company-housing|cube hotel|conapt|\blot C\b|\bparcels?\b'),
    ('Hardware & equipment',  r'\b(rental|cranes?|gensets?|rigs?|dumps?|loaders?|plants?|skids?|trucks?|monitors?|suits|badges|FA-12s?|equipment|chrome|cyberaudio|AmeriCar|Villefort)\b'),
    ('Facilities & property', r'\bLED\b|\bfloors? \d|\blobby\b|\bfit-?out\b'),
    ('Services & logistics',  r'\bcharter\b|\binspection\b|radioanalytical|\bjars?\b|\bclerk\b|\bfreight\b|\breport\b|\bbreakfasts?\b'),
]
def classify(memo):
    for cat, pat in RULES:
        if re.search(pat, memo, re.I):
            return cat
    return 'Other'

def split_memo(memo):
    """'Talus Equipment Rental TL-45… - 3 rigs…' -> ('Talus Equipment Rental TL-45…', '3 rigs…')."""
    m = re.split(r'\s+[—–-]\s+', memo, maxsplit=1)
    cp = re.sub(r'\s+[A-Z]{2,4}-[\w-]+.*$', '', m[0]).strip() or m[0]        # drop quote/invoice numbers
    return cp[:80], (m[1] if len(m) > 1 else m[0])

# ---------------------------------------------------------------- load + merge history
old = None
if LEDGER.is_file():
    try:
        old = json.loads(LEDGER.read_text())
    except ValueError:
        sys.exit(f'[FAIL] {LEDGER} is not valid JSON; fix or move it first')

bank = {}                                            # day(str) -> raw record
archive = None
if old and old.get('model') == 'bank-balances':
    bank = dict(old.get('bank', {}))
elif old:
    archive = LEDGER.with_name(f"ledger-xlsx-day{old.get('day', 'old')}.json")

new = parse(src.read_text(encoding='utf-8'))
replaced = [d for d in new if str(d) in bank and bank[str(d)] != new[d]]
added = [d for d in new if str(d) not in bank]
for d, rec in new.items():
    bank[str(d)] = rec
DAYS = sorted(int(d) for d in bank)
last = DAYS[-1]

# ---------------------------------------------------------------- entities across all days
labels = []
for d in DAYS:
    for lab in bank[str(d)]['opex']:
        if lab not in labels:
            labels.append(lab)
ents = [MAIN] + [ent_for(l) for l in labels]
ID = {l: ent_for(l)[0] for l in labels}
entities = [{'id': i, 'name': n, 'code': c, 'book': 'corporate'} for i, n, c in ents]

# ---------------------------------------------------------------- lines
lines = []
for d in DAYS:
    r = bank[str(d)]
    for k, s in enumerate(r['sweeps']):          # sweep into SI Main: intra-group inflow
        lines.append({'id': f'sw-{d}-{k}', 'entity': 'si', 'book': 'corporate', 'counterparty': 'Nightly opex sweep',
                      'memo': s['memo'], 'amount': round(s['amount'], 2), 'day': d, 'status': 'posted',
                      'ledger': 'Main', 'category': 'Intra-group', 'flow': 'intra', 'posts': None})
    for k, x in enumerate(r['debits']):          # SI Main debits, one line each
        cp, memo = split_memo(x['memo'])
        capital = bool(re.search(r'capex', x['memo'], re.I))
        cat = classify(x['memo'])
        lines.append({'id': f'si-{d}-{k}', 'entity': 'si', 'book': 'corporate', 'counterparty': cp,
                      'memo': f"{x['time']} · {memo}", 'amount': round(x['amount'], 2), 'day': d, 'status': 'posted',
                      'ledger': 'Main', 'category': 'Capital & investment' if capital and cat == 'Other' else cat,
                      'flow': 'capital' if capital or cat == 'Capital & investment' else 'operating', 'posts': None})
    prev = bank.get(str(d - 1))                  # the change in each opex balance vs. the previous day
    if prev:
        for lab, bal in r['opex'].items():
            if lab in prev['opex']:
                delta = round(bal - prev['opex'][lab], 2)
                if delta:
                    lines.append({'id': f'ox-{ID[lab]}-{d}', 'entity': ID[lab], 'book': 'corporate',
                                  'counterparty': 'Opex account, net change',
                                  'memo': 'Change in the opex balance after the nightly sweep (the bank sheet has no line detail)',
                                  'amount': delta, 'day': d, 'status': 'posted', 'ledger': 'Opex',
                                  'category': 'Other', 'flow': 'operating', 'posts': None})

# ---------------------------------------------------------------- closes + positions
closes = {'si': {str(d): bank[str(d)]['main'] for d in DAYS}}
for lab in labels:
    closes[ID[lab]] = {str(d): bank[str(d)]['opex'][lab] for d in DAYS if lab in bank[str(d)]['opex']}
lr = bank[str(last)]
positions = [{'entity': 'si', 'cash': lr['main']}] + [{'entity': ID[l], 'cash': lr['opex'][l]} for l in labels if l in lr['opex']]
for p in positions:
    p.update({'receivable': 0, 'payableFirm': 0, 'payableContingent': 0, 'unpriced': 0, 'net': p['cash'], 'pending': 0, 'afterPosting': p['cash']})

# ---------------------------------------------------------------- reconciliation checks
fails, recon = [], 0
for d in DAYS:
    r = bank[str(d)]
    recon += 1                                   # 1) total = main + every opex account
    if abs(r['main'] + sum(r['opex'].values()) - r['total']) > 0.005:
        fails.append(f"Day {d}: SI TOTAL {r['total']:,.2f} ≠ SI Main + opex {r['main'] + sum(r['opex'].values()):,.2f}")
    p = bank.get(str(d - 1))
    if p:                                        # 2) main rolls: prev main + sweep + debits
        recon += 1
        want = p['main'] + sum(s['amount'] for s in r['sweeps']) + sum(x['amount'] for x in r['debits'])
        if abs(want - r['main']) > 0.005:
            fails.append(f"Day {d}: SI Main {r['main']:,.2f} ≠ Day {d-1} main + sweep + debits {want:,.2f} (off {r['main']-want:+,.2f})")
dash = 2
dash_fail = 0
if abs(sum(p['cash'] for p in positions) - lr['total']) > 0.005:   # 3) positions add up to SI TOTAL
    dash_fail += 1; fails.append('positions do not add up to SI TOTAL')
if any(str(d) not in closes['si'] for d in DAYS):                  # 4) a close for SI Main every day
    dash_fail += 1; fails.append('missing SI Main close')

# ---------------------------------------------------------------- portfolio (Positions page)
# Stocks and notes come from the packet's cp-ref-si-portfolio.md. Properties come from the property
# register. Prices are marks, not cash; the page keeps them apart from the bank figures.
PKT = src.parent
MONEY = re.compile(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+')
def money(cell):
    m = MONEY.search(cell.replace('*', ''))
    return float(m.group().replace(',', '')) if m else None
def table_after(text, heading_re):
    """Rows (lists of cells) of the first markdown table after the heading that matches heading_re."""
    m = re.search(heading_re, text, re.M)
    if not m:
        return []
    rows, started = [], False
    for line in text[m.end():].splitlines():
        if line.startswith('|'):
            started = True
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not re.fullmatch(r':?-{3,}:?', cells[0]):     # skip only the |---| separator
                rows.append(cells)
        elif started and line.strip():
            break
    return rows[1:]                                   # drop the header row

portfolio, pfails = None, []
pf = PKT / 'cp-ref-si-portfolio.md'
if pf.is_file():
    pt = pf.read_text(encoding='utf-8')
    equity, rocklin, stated = [], None, None
    for c in table_after(pt, r'^## 1 · ACTUAL — EQUITY'):
        if len(c) < 7:
            continue
        name = re.sub(r'\*', '', c[2])
        if not c[0].strip():                          # the EQUITY AT MARKET total row
            stated = money(c[-1]); continue
        short = re.split(r'\s+[—–]\s+|:', name)[0].strip()
        cls = 'preferred' if 'preferred' in short.lower() else 'Class B (control)' if 'Class B' in name else 'common'
        issuer = re.sub(r'\s+(common|preferred|—.*|Class B.*)$', '', short).strip()
        pct = re.search(r'(\d+(?:\.\d+)?)%', c[4])
        row = {'code': c[1], 'issuer': issuer, 'cls': cls, 'shares': money(c[3]) or 0,
               'pctIssuer': float(pct.group(1)) if pct else None, 'pctNote': re.sub(r'\*', '', c[4]),
               'mark': money(c[5]), 'value': money(c[6]) or 0, 'note': name if len(name) > len(short) + 3 else ''}
        if 'INDICATIVE' in c[6].upper():
            rocklin = row
        else:
            equity.append(row)
    debt = []
    for c in table_after(pt, r'^## 2 · ACTUAL — DEBT'):
        if len(c) >= 5 and 'STILL PRESENTING' in c[4].upper():
            debt.append({'code': c[1], 'issuer': re.sub(r'\*', '', c[2]), 'value': money(c[3]) or 0,
                         'status': re.sub(r'\*', '', c[4])[:160]})
    personal = []                                     # §9: Orbital Air common in Hakk's own name
    m9 = re.search(r'Holding at the Day-\d+ close:\*\*\s*([\d,]+) Orbital Air common at cost \*\*([\d,.]+)\*\*;.*?close[^*]*\*\*([\d,.]+)\*\*', pt)
    if m9:
        sh = float(m9.group(1).replace(',', ''))
        personal.append({'code': 'OF-1006-A', 'issuer': 'Orbital Air', 'cls': 'common', 'shares': sh,
                         'pctIssuer': round(sh / 1_960_000_000 * 100, 2), 'cost': float(m9.group(2).replace(',', '')),
                         'value': float(m9.group(3).replace(',', '')), 'note': "Hakk's own name; not CR-03"})
    # HAKK-POSITIONS v1: positions moved on the bank sheet (latest row per issuer), unless §1 or §9 lists the issuer
    moved = {}
    for _d in DAYS:
        for _s in bank[str(_d)].get('stocks', []):
            moved[_s['issuer'].lower()] = dict(_s, day=_d)
    _have = {r['issuer'].lower() for r in equity} | {p['issuer'].lower() for p in personal}
    for _k, _s in moved.items():
        if _k in _have:
            continue
        personal.append({'code': _s['codes'] or '—', 'issuer': _s['issuer'], 'cls': _s['cls'], 'shares': _s['shares'],
                         'pctIssuer': _s['pct'], 'mark': _s['mark'], 'cost': None, 'value': _s['value'] or 0,
                         'note': f"from the bank sheet, Day {_s['day']}" + ('' if _s['value'] else ' · unmarked') + " · not in the portfolio's §1 table"})
    eq_total = round(sum(r['value'] for r in equity), 2)
    if stated is not None and abs(eq_total - stated) > 0.5:
        pfails.append(f'portfolio: equity lines add to {eq_total:,.2f}, the file states {stated:,.2f}')
    portfolio = {'source': pf.name, 'equity': equity, 'rocklin': rocklin, 'debt': debt, 'personal': personal,
                 'equityTotal': eq_total, 'equityStated': stated}
else:
    print(f'     (no {pf.name} in the packet: Positions shows cash only)')

reg = pathlib.Path(A.properties).expanduser() if A.properties else (
    PKT / 'cp-ref-property-register.md' if (PKT / 'cp-ref-property-register.md').is_file()
    else pathlib.Path.home() / 'projects/payload/data/property-register.md')
properties = []
if reg.is_file():
    rows = [l for l in reg.read_text(encoding='utf-8').splitlines() if l.startswith('| ') and not l.startswith('| Property') and not l.startswith('|---')]
    for l in rows:
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        if len(c) >= 6:
            properties.append({'name': c[0], 'owner': c[1], 'district': c[2] if c[2] not in ('—', '') else '',
                               'status': c[3], 'cost': money(c[4]), 'source': c[5]})
    if portfolio is None:
        portfolio = {'source': '', 'equity': [], 'rocklin': None, 'debt': [], 'personal': [], 'equityTotal': 0, 'equityStated': None}
    portfolio['properties'] = properties
    portfolio['propertySource'] = reg.name
else:
    print(f'     (no property register at {reg}: Positions shows no properties)')
if portfolio is not None:
    owned = [p for p in properties if p['status'] == 'Owned' and p['cost']]
    portfolio['propertyOwnedTotal'] = round(sum(p['cost'] for p in owned), 2)
    print(f"     portfolio: {len(portfolio['equity'])} equity lines {portfolio['equityTotal']:,.2f}"
          f" (stated {portfolio['equityStated'] or 0:,.2f}) · {len(portfolio['debt'])} note(s) presenting"
          f" · {len(properties)} properties, owned at cost {portfolio['propertyOwnedTotal']:,.2f} ({reg.name})")
fails += pfails
dash += 1 if portfolio else 0
dash_fail += len(pfails)

src_note = f"{src.name}" + (f" (packet {A.packet_no})" if A.packet_no else '')
D = {
    'model': 'bank-balances',
    'title': 'Slipstream accounts: SI Main and opex accounts',
    'asOf': (f"As of {lr['date']} (Day {last}): SI TOTAL {lr['total']:,.2f} = SI Main {lr['main']:,.2f} + "
             f"{len(lr['opex'])} opex accounts. Every opex account sweeps to SI Main at 00:00; the sweep shown under a day is already in that day's SI Main."),
    'day': last,
    'dayLabels': {str(d): bank[str(d)]['label'] for d in DAYS},
    'entities': entities,
    'categories': ['Hardware & equipment', 'Service revenue', 'Club takings', 'Commissions', 'Payroll',
                   'Facilities & property', 'Capital & investment', 'Services & logistics', 'Other', 'Intra-group'],
    'lines': lines, 'positions': positions, 'pocketCash': 0, 'closes': closes,
    'receivables': [], 'payables': [],
    'totals': {str(d): bank[str(d)]['total'] for d in DAYS},
    'checks': {'dashboard': dash, 'dashboardFailing': dash_fail, 'reconciliation': recon, 'reconciliationFailing': len(fails) - dash_fail},
    'source': src_note, 'bank': bank, 'portfolio': portfolio,
    'cash': {'day': last, 'total': lr['total'], 'main': lr['main'], 'opex': round(sum(lr['opex'].values()), 2),
             'prevTotal': bank[str(last - 1)]['total'] if str(last - 1) in bank else None,
             'sweep': round(sum(s['amount'] for s in lr['sweeps']), 2), 'sweepMemo': lr['sweeps'][0]['memo'] if lr['sweeps'] else '',
             'debits': round(sum(x['amount'] for x in lr['debits']), 2)},
}

# ---------------------------------------------------------------- report
print(f"[..] {src}: days {min(new)}–{max(new)} ({len(new)}); ledger now holds Day {DAYS[0]}–{last} ({len(DAYS)} days)")
print(f"     new days {added or '—'} · replaced {replaced or '—'} · {len(lines)} lines · {len(entities)} accounts")
print(f"     SI TOTAL Day {last}: {lr['total']:,.2f} · checks {recon + dash}, failing {len(fails)}")
for f in fails:
    print('     [FAIL]', f)
if archive:
    print(f"     old xlsx-model ledger (Day {old.get('day')}) will be archived to {archive.name}")
same = old is not None and old.get('model') == 'bank-balances' and json.dumps(old, sort_keys=True) == json.dumps(D, sort_keys=True)
if same:
    print('[OK] no change'); sys.exit(0)
if not A.apply:
    print('Dry run. Nothing written. Re-run with --apply.'); sys.exit(1 if fails else 0)
if fails:
    sys.exit('[FAIL] not writing: the sheet does not reconcile (fix the close, or file the sheet as-is in the Datafort only)')

# ---------------------------------------------------------------- write (SELinux-safe)
# Files created from the host shell get the label s0 without the project's MCS categories,
# and the rootless web container cannot read them. So relabel the temp file from its
# folder before renaming it into place, and keep a timestamped copy of the old file.
ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
if old is not None:
    bk = pathlib.Path.home() / 'backups'
    bk.mkdir(exist_ok=True)
    shutil.copyfile(LEDGER, bk / f'ledger-pre-day{last}-{ts}.json')
    print(f'[OK] backup ~/backups/ledger-pre-day{last}-{ts}.json')
# selinuxenabled exits 0 only when SELinux is on (hades: Enforcing). Off, or missing: skip.
SELINUX = bool(shutil.which('selinuxenabled')) and subprocess.run(['selinuxenabled']).returncode == 0
def relabel(path):
    """Copy the folder's label (container_file_t:s0:c369,c692 on hades) onto a new file."""
    if not SELINUX:
        return
    r = subprocess.run(['chcon', '--reference', str(LEDGER.parent), str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        path.unlink(missing_ok=True); sys.exit('[FAIL] chcon: ' + r.stderr.strip())
if archive and not archive.exists():
    shutil.copyfile(LEDGER, archive)
    relabel(archive)
    print(f'[OK] archived the xlsx-model ledger as {archive.name}')
tmp = LEDGER.with_name('.ledger.json.tmp')
tmp.write_text(json.dumps(D, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
relabel(tmp)                                   # label first, then the rename keeps it
os.replace(tmp, LEDGER)
print(f'[OK] wrote {LEDGER} (Day {last})')
