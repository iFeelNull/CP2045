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
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            head = cells[0].lower()
            # Section headers are the first row of each table.
            if head == 'si' and cells[1].lower() == 'balance':             sec = 'si';    continue
            if head == 'company':                                         sec = 'opex';  continue
            if head.startswith('sweep'):                                  sec = 'sweep'; continue
            if head.startswith('~time'):                                  sec = 'debit'; continue
            if set(cells[0]) <= set('-: '):                               continue      # |---| separator
            if sec == 'si':
                (rec.__setitem__('total', num(cells[1])) if 'TOTAL' in cells[0].upper() else rec.__setitem__('main', num(cells[1])))
            elif sec == 'opex':
                rec['opex'][cells[0]] = num(cells[1])
            elif sec == 'sweep':
                rec['sweeps'].append({'memo': cells[0], 'amount': num(cells[1])})
            elif sec == 'debit':
                rec['debits'].append({'time': cells[0], 'memo': cells[1], 'amount': num(cells[-1])})
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
    'source': src_note, 'bank': bank,
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
