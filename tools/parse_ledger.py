"""Parse a Slipstream accounts workbook into dashboard JSON.

Usage: python3 parse_ledger.py <workbook.xlsx> public/data/ledger.json

Needs openpyxl (pip install openpyxl). The workbook must keep its formulas' cached values,
so save it in Excel/LibreOffice before running this (files written by scripts may not have them).
After writing the JSON it reconciles every entity: posted lines must equal the change in the
Reconciliation sheet's closes, and pending lines must equal the Dashboard sheet's Pending column.
"""
import json, re, sys, datetime
import openpyxl

SRC, OUT = sys.argv[1], sys.argv[2]
wb = openpyxl.load_workbook(SRC, data_only=True)

# tab -> (id, display name, short code, book)
TABS = {
    'Whitehat': ('wts', 'Whitehat Technical Services', 'WTS', 'corporate'),
    'Slipstream Industries': ('si', 'Slipstream Industries', 'SI', 'corporate'),
    'SI TEAB': ('teab', 'SI TEAB', 'TEAB', 'corporate'),
    'SMC': ('smc', 'Slipstream Medical Complex', 'SMC', 'corporate'),
    'IntraCorp': ('icl', 'IntraCorp Logistics', 'ICL', 'corporate'),
    'NorTex Exploration': ('ntx', 'NorTex Exploration', 'NTX', 'corporate'),
    'NorTex Agriculture': ('nta', 'NorTex Agriculture', 'NTA', 'corporate'),
    'SIVOSS Security': ('svs', 'SIVOSS Security Services', 'SVS', 'corporate'),
    'SIVOSS Outreach': ('svo', 'SIVOSS Veteran Outreach', 'SVO', 'corporate'),
    'Nightshades': ('nsh', 'Club Nightshades', 'NSH', 'corporate'),
    'Aster Vale': ('avr', 'Aster Vale reserve', 'AVR', 'reserve'),
    'HAKK': ('hakk', 'Hakk (personal)', 'HAKK', 'personal'),
}
# Dashboard-sheet row label -> entity id
SUMMARY_ROWS = {
    'Whitehat Technical Services': 'wts', 'Slipstream Industries': 'si', 'SI TEAB': 'teab',
    'Slipstream Medical Complex': 'smc', 'IntraCorp Logistics': 'icl', 'NorTex Exploration': 'ntx',
    'NorTex Agriculture': 'nta', 'SIVOSS Security': 'svs', 'SIVOSS Veteran Outreach': 'svo',
    'Nightshades': 'nsh', 'Aster Vale reserve': 'avr', 'HAKK - personal (bank)': 'hakk',
}
ENTITY_NAMES = ['Whitehat', 'Slipstream Industries', 'SI TEAB', 'IntraCorp', 'NorTex', 'SIVOSS', 'Nightshades']

# ---- as-of and day anchor ----
dash = wb['Dashboard']
title = str(dash['A1'].value or 'Slipstream accounts')
as_of = str(dash['A2'].value or '')
m = re.search(r'([A-Z][a-z]{2}) ([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) \(Day (\d+)\)', as_of)
if not m:
    raise SystemExit('Could not find "As of <date> (Day N)" in Dashboard!A2')
anchor_date = datetime.datetime.strptime(f'{m.group(2)} {m.group(3)} {m.group(4)}', '%b %d %Y').date()
anchor_day = int(m.group(5))
YEAR = anchor_date.year

def day_from_text(*texts):
    for t in texts:
        if not t:
            continue
        mm = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})', str(t))
        if mm:
            d = datetime.datetime.strptime(f'{mm.group(2)} {mm.group(3)} {YEAR}', '%b %d %Y').date()
            return anchor_day + (d - anchor_date).days
    return None

def label_for_day(day):
    d = anchor_date + datetime.timedelta(days=day - anchor_day)
    return d.strftime('%a %b ') + str(d.day)

def num(v):
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return None

# ---- categorisation (fixed list, fixed order = fixed colour) ----
CATEGORIES = ['Hardware & equipment', 'Service revenue', 'Club takings', 'Commissions', 'Payroll',
              'Facilities & property', 'Capital & investment', 'Services & logistics', 'Other', 'Intra-group']

def classify(entity_tab, cp, memo, amount):
    c, mo = (cp or '').lower(), (memo or '').lower()
    both = c + ' ' + mo
    # flow type first
    intra = ('intra-group' in both or 're-level' in both
             or (entity_tab != 'HAKK' and any(c.startswith(n.lower()) for n in ENTITY_NAMES) and 'commission' not in c))
    if intra:
        return 'Intra-group', 'intra'
    if re.search(r'capital|cr-03|paying agent|investment|orbital air|rio bravo|sweep|the business \(signed', both):
        return 'Capital & investment', 'capital'
    if 'commission' in both:
        return 'Commissions', 'operating'
    if 'payroll' in both:
        return 'Payroll', 'operating'
    if c.startswith('installation customers') or c.startswith('new live sites'):
        return 'Service revenue', 'operating'
    if '1stnc merchant' in c:
        return 'Club takings', 'operating'
    if re.search(r'northline|wardell|guard shack|land & title|escrow|the land under|tower', both):
        return 'Facilities & property', 'operating'
    if re.search(r'vendor cost|caldera|asterion|vanta|bastion|ironwood|mesa verde|tsunami arms|gibson battlegear|militech|'
                 r'tailwind|aerodyne|herakles|brightcoat|seamline|talus|dozer|woodchipper|sunwell|coldspring|kettle rock|'
                 r'rocklin augmentics.*cyber|cyberarm|fa-12', both):
        return 'Hardware & equipment', 'operating'
    if re.search(r'backhaul|round trip|airlift|fuel|aldecaldo|vidal|maison vesper|afterlife|torrell|fauchard|harbor mutual|'
                 r'standing order|rogue|lunch|bar ', both):
        return 'Services & logistics', 'operating'
    return 'Other', 'operating'

# ---- walk every entity tab ----
lines, receivables, payables = [], [], []
for tab, (eid, ename, ecode, book) in TABS.items():
    ws = wb[tab]
    rows = list(ws.iter_rows(values_only=True))
    mode = None
    for i, r in enumerate(rows, 1):
        r = list(r) + [None] * 8
        a = r[0]
        head = a.split('(')[0].strip() if isinstance(a, str) else ''
        if head and re.match(r'(ACCOUNTS |BANK MOVEMENTS|CASH|NON-CASH|PAYABLES ADDED|PENDING|PHYSICAL CASH|RECEIVABLE ADDED|RECURRING|SETTLED OR STRUCK)', head) and r[2] is None:
            if 'MOVEMENTS SINCE' in a:
                mode = 'posted'
            elif a.startswith('PENDING'):
                mode = 'pending'
            elif a.startswith('ACCOUNTS RECEIVABLE') or a.startswith('RECEIVABLE ADDED'):
                mode = 'ar'
            elif a.startswith('ACCOUNTS PAYABLE') or a.startswith('PAYABLES ADDED'):
                mode = 'ap'
            else:
                mode = None
            continue
        if mode is None or a in (None, '') or a in ('Counterparty', 'Account', 'Item'):
            continue
        amt = num(r[2])
        if mode in ('posted', 'pending'):
            if amt is None or amt == 0 or str(a).startswith('(none'):
                continue
            day = r[7] if isinstance(r[7], (int, float)) else num(r[7])
            if day is None:
                day = day_from_text(r[1]) if mode == 'pending' else day_from_text(r[3], r[1])
            if day is None:
                day = anchor_day
            cat, flow = classify(tab, str(a), str(r[1] or ''), amt)
            lines.append({
                'id': f'{eid}-{i}', 'entity': eid, 'book': book,
                'counterparty': str(a).strip(), 'memo': str(r[1] or '').strip(),
                'amount': round(amt, 2), 'day': int(day),
                'status': 'pending' if mode == 'pending' else 'posted',
                'ledger': str(r[6]).strip() if mode == 'posted' and r[6] else (str(r[6]).strip() if r[6] else 'Main'),
                'category': cat, 'flow': flow,
                'posts': str(r[3]).strip() if mode == 'pending' and r[3] else None,
            })
        elif mode == 'ar':
            if str(a).strip() == '' or (r[1] is None and amt is None):
                continue
            receivables.append({'entity': eid, 'counterparty': str(a).strip(), 'what': str(r[1] or '').strip(),
                                'amount': amt, 'status': str(r[4] or '').strip()})
        elif mode == 'ap':
            if r[1] is None and amt is None:
                continue
            payables.append({'entity': eid, 'counterparty': str(a).strip(), 'what': str(r[1] or '').strip(),
                             'amount': amt, 'class': str(r[3] or '').strip(), 'status': str(r[4] or '').strip()})

# normalise ledger names
for ln in lines:
    l = ln['ledger'].lower()
    ln['ledger'] = ('Payroll' if 'payroll' in l else 'Investment capital' if 'investment' in l
                    else 'Operating reserve' if 'operating reserve' in l else 'Main')

# ---- positions (Dashboard sheet) ----
positions = []
for r in dash.iter_rows(min_row=4, max_row=20, values_only=True):
    label = str(r[0] or '')
    eid = next((v for k, v in SUMMARY_ROWS.items() if label.startswith(k)), None)
    if not eid:
        continue
    positions.append({'entity': eid, 'cash': num(r[1]) or 0, 'receivable': num(r[2]) or 0, 'payableFirm': num(r[3]) or 0,
                      'payableContingent': num(r[4]) or 0, 'unpriced': int(num(r[5]) or 0), 'net': num(r[6]) or 0,
                      'pending': num(r[7]) or 0, 'afterPosting': num(r[8]) or 0})
pocket = next((num(r[1]) for r in dash.iter_rows(values_only=True) if str(r[0] or '').startswith('HAKK - pocket')), None)

# checks: every "CHECK" row on the dashboard should be zero
checks = [(str(r[0]).strip(), num(r[1])) for r in dash.iter_rows(values_only=True)
          if isinstance(r[0], str) and 'CHECK:' in r[0]]
recon = wb['Reconciliation']
rrows = list(recon.iter_rows(values_only=True))
hdr = next(r for r in rrows if r and r[0] == 'Entity')
close_cols = [(j, int(re.match(r'D(\d+) close', h).group(1))) for j, h in enumerate(hdr) if isinstance(h, str) and re.match(r'D\d+ close$', h)]
check_cols = [j for j, h in enumerate(hdr) if isinstance(h, str) and h.endswith('CHECK')]
closes = {}
recon_check_cells = 0
recon_check_fail = 0
for r in rrows:
    label = str(r[0] or '')
    eid = next((v for k, v in SUMMARY_ROWS.items() if label.startswith(k)), None)
    if label.startswith('HAKK - personal'):
        eid = 'hakk'
    if not eid:
        continue
    series = {str(anchor_day - 7): num(r[1])}  # Day-104 close sits in column B
    for j, d in close_cols:
        series[str(d)] = num(r[j])
    closes[eid] = series
    for j in check_cols:
        recon_check_cells += 1
        if abs(num(r[j]) or 0) > 0.005:
            recon_check_fail += 1
first_day = min(int(k) for k in next(iter(closes.values())))

data = {
    'title': title,
    'asOf': as_of,
    'day': anchor_day,
    'dayLabels': {str(d): label_for_day(d) for d in range(first_day, anchor_day + 1)},
    'entities': [{'id': e, 'name': n, 'code': c, 'book': b} for (e, n, c, b) in TABS.values()],
    'categories': CATEGORIES,
    'lines': lines,
    'positions': positions,
    'pocketCash': pocket,
    'closes': closes,
    'receivables': receivables,
    'payables': payables,
    'checks': {
        'dashboard': len(checks), 'dashboardFailing': sum(1 for _, v in checks if abs(v or 0) > 0.005),
        'reconciliation': recon_check_cells, 'reconciliationFailing': recon_check_fail,
    },
    'source': SRC.split('/')[-1],
}
with open(OUT, 'w') as f:
    json.dump(data, f, separators=(',', ':'))

from collections import Counter, defaultdict
print(f'{len(lines)} lines ({sum(l["status"] == "pending" for l in lines)} pending) -> {OUT}')
print('by flow:', dict(Counter(l['flow'] for l in lines)))
print('by category:', dict(Counter(l['category'] for l in lines)))

posted, pend = defaultdict(float), defaultdict(float)
for l in lines:
    (posted if l['status'] == 'posted' else pend)[l['entity']] += l['amount']
problems = []
for eid, c in closes.items():
    first, last = c.get(str(first_day)), c.get(str(anchor_day))
    if first is not None and last is not None and abs((last - first) - posted[eid]) > 0.01:
        problems.append(f'{eid}: posted lines {posted[eid]:,.2f} vs close change {last - first:,.2f}')
for p in positions:
    if abs(p['pending'] - pend[p['entity']]) > 0.01:
        problems.append(f"{p['entity']}: pending lines {pend[p['entity']]:,.2f} vs Dashboard pending {p['pending']:,.2f}")
if data['checks']['dashboardFailing'] or data['checks']['reconciliationFailing']:
    problems.append(f"workbook CHECK cells failing: {data['checks']}")
if problems:
    print('\nRECONCILIATION FAILED - the JSON was written, but check these before publishing:')
    for x in problems: print('  -', x)
    sys.exit(2)
print('reconciled: every entity matches the workbook to the cent')
