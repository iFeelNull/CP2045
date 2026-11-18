#!/usr/bin/env python3
"""add_bank_finance.py: adapt public/finance.html to the bank-balances ledger model (idempotent).

Usage: python3 add_bank_finance.py ~/projects/payload

v1.3 (wording):
  * Only books that actually have accounts get a slicer button.
  * The flow-slicer wording describes capex purchases and nightly opex sweeps (not the old CR-03 notes).
v1.4 (liquid cash + portfolio):
  * A LIQUID CASH band on every page: SI TOTAL, SI Main, opex accounts, the change on the day and
    tonight's sweep. It reads D.cash, so the slicers never change it.
  * The Positions page becomes the portfolio:
    - KPIs: liquid cash · securities at market · property at cost · total · committed.
    - Charts: allocation (cash / equities / notes / Orbital Air / property, with %), equities by issuer
      (% of equities, tooltip % of the issuer), property by owner (% of property), cash by entity.
    - A holdings table: every equity line (shares, % of issuer, mark, value, % of equities, % of all),
      the indicative Rocklin control block (not in totals), notes presenting, Hakk's Orbital Air, and
      every property in the register (owner, district, status, cost basis, % of property, % of all).
  * The data comes from ledger.json (D.cash, D.portfolio), written by tools/bank-to-ledger.py.
Run `chcon -R --reference=<project> public` afterwards (runbook rule).
"""
import pathlib, sys

P = pathlib.Path(sys.argv[1]).expanduser() / 'public/finance.html'
s = P.read_text(encoding='utf-8')

PF_JS = r"""/* ---------- liquid cash + portfolio (bank-sheet model; add_bank_finance v1.4) ---------- */
const PF = D.portfolio || null;
function renderCash(){
  const el = document.getElementById('cashband'); if (!el || !D.cash) return;
  const c = D.cash, dlt = c.prevTotal == null ? null : c.total - c.prevTotal;
  el.innerHTML = [
    kpi('Liquid cash · SI total', c.total, `<b>${full(c.total)}</b>`, 'cash'),
    kpi('SI Main', c.main, `${pct(c.main / c.total)} of the total`),
    kpi('Opex accounts', c.opex, `<b>${Math.max(0, D.positions.length - 1)}</b> companies · swept nightly`),
    kpi('Change on the day', dlt == null ? '—' : dlt, dlt == null ? 'first day on file' : `vs ${esc(dayLong(c.day - 1))} · debits ${short(c.debits)}`, dlt != null && dlt < 0 ? 'neg' : ''),
    kpi("Tonight's sweep", c.sweep, esc(c.sweepMemo || '—'))
  ].join('');
}
const pfOwned = () => (PF && PF.properties ? PF.properties.filter(p => p.status === 'Owned' && p.cost) : []);
const pfCommitted = () => (PF && PF.properties ? PF.properties.filter(p => p.status === 'Committed' && p.cost) : []);
function allocRows(){
  return [
    { name:'Liquid cash (SI)', value:D.cash ? D.cash.total : 0, color:'#ffb21a' },
    { name:'Equities (CR-03)', value:PF ? PF.equityTotal : 0, color:'#408fba' },
    { name:'Notes presenting', value:PF ? sum(PF.debt, r => r.value) : 0, color:'#6e67bd' },
    { name:'Orbital Air (Hakk)', value:PF ? sum(PF.personal, r => r.value) : 0, color:'#12a7a7' },
    { name:'Property at cost', value:sum(pfOwned(), p => p.cost), color:'#9d3d8d' }
  ].filter(r => r.value > 0);
}
const allTotal = () => sum(allocRows(), r => r.value);
function allocation(el){
  const rows = allocRows(); if (!rows.length) return emptyState(el, 'No holdings', 'Nothing on file.');
  const total = sum(rows, r => r.value);
  chart(el, {
    tooltip:{ trigger:'item', formatter:p => tipHead('Holdings') + tipRow(p.color, p.name, p.value) + `<div style="color:${C.dim};margin-top:4px;font-family:Share Tech Mono,monospace">${pct(p.value / total)} of the total</div>` },
    graphic:[{ type:'group', left:'center', top:'middle', children:[
      { type:'text', left:'center', top:-20, style:{ text:short(total), fill:C.fg, font:'800 34px "Big Shoulders Stencil Display", Impact, sans-serif', textAlign:'center' } },
      { type:'text', left:'center', top:18, style:{ text:'TOTAL · ' + rows.length + ' CLASSES', fill:C.dim, font:'11px "Share Tech Mono", monospace', textAlign:'center' } } ] }],
    series:[{ type:'pie', radius:['54%','76%'], center:['50%','52%'], padAngle:1.5, minAngle:4, avoidLabelOverlap:true,
      itemStyle:{ borderRadius:4, borderColor:C.bg, borderWidth:2 },
      label:{ show:el.clientWidth > 420, color:C.dim, fontSize:12, formatter:p => `${p.name}\n{v|${pct(p.value / total)}}`, rich:{ v:{ color:C.fg, fontFamily:'Share Tech Mono, monospace', fontSize:12, padding:[3,0,0,0] } } },
      labelLine:{ show:el.clientWidth > 420, length:8, length2:10, lineStyle:{ color:C.lineHi } },
      data:rows.map(r => ({ name:r.name, value:r.value, itemStyle:{ color:r.color } })) }]
  });
}
function allocLegend(){ const rows = allocRows(), t = sum(rows, r => r.value); return `<div class="legend">${rows.map(r => `<span><i style="background:${r.color}"></i>${esc(r.name)} · ${pct(r.value / t)}</span>`).join('')}</div>`; }
function hbar(el, g, tot, color, what, extra, log){
  chart(el, {
    grid:{ left:12, right:112, top:8, bottom:log ? 26 : 8, containLabel:true },
    tooltip:{ trigger:'item', formatter:p => { const r = g[p.dataIndex]; return tipHead(r.name) + tipRow(color, what, r.value) + `<div style="color:${C.dim};margin-top:4px;font-family:Share Tech Mono,monospace">${extra(r)}</div>`; } },
    xAxis:log ? { type:'log', logBase:10, min:v => Math.pow(10, Math.floor(Math.log10(Math.max(1, v.min)))), axisLabel:Object.assign({ formatter:v => short(v) }, axisLabel), splitLine:{ lineStyle:{ color:C.line, type:[2,4] } },
      name:'log scale', nameLocation:'end', nameGap:-40, nameTextStyle:{ color:C.faint, fontFamily:'Share Tech Mono, monospace', fontSize:10, padding:[34,0,0,0] } } : valueAxis(),
    yAxis:catAxis(g.map(r => r.name.length > 30 ? r.name.slice(0, 29) + '…' : r.name), { axisLabel:{ color:C.fg, fontSize:12, fontFamily:'Barlow Semi Condensed, sans-serif' } }),
    series:[{ type:'bar', data:g.map(r => r.value), barMaxWidth:14, itemStyle:{ color, borderRadius:[0,4,4,0] },
      label:{ show:true, position:'right', color:C.dim, fontFamily:'Share Tech Mono, monospace', fontSize:11, formatter:p => pct(p.value / tot) + ' · ' + short(p.value) } }]
  });
}
function equityByIssuer(el){
  if (!PF || !PF.equity.length) return emptyState(el, 'No equity', 'cp-ref-si-portfolio.md was not in the packet.');
  const g = [...group(PF.equity, r => r.issuer).entries()].map(([k, v]) => ({ name:k, value:sum(v, r => r.value), pi:sum(v, r => r.pctIssuer || 0), n:v.length })).sort((a,b) => a.value - b.value);
  hbar(el, g, PF.equityTotal, '#408fba', 'At market', r => `${pct(r.value / PF.equityTotal)} of equities · ${r.pi ? '≈' + r.pi.toFixed(1) + '% of the issuer' : 'preferred'}${r.n > 1 ? ' · ' + r.n + ' lines' : ''}`);
}
function propertyByOwner(el){
  const P = pfOwned(); if (!P.length) return emptyState(el, 'No priced property', 'Add rows to the property register.');
  const tot = sum(P, p => p.cost);
  const g = [...group(P, p => p.owner).entries()].map(([k, v]) => ({ name:k, value:sum(v, p => p.cost), n:v.length })).sort((a,b) => a.value - b.value);
  hbar(el, g, tot, '#9d3d8d', 'At cost', r => `${pct(r.value / tot)} of owned property · ${r.n} propert${r.n > 1 ? 'ies' : 'y'}`, true);
}
function renderPortfolio(){
  const host = document.getElementById('ptable'); if (!host) return;
  const ALL = allTotal(), num = v => v == null ? '—' : Number(v).toLocaleString('en-US');
  const sec = (t, n) => `<tr class="sec"><th colspan="8">${t}${n ? ` <span>${n}</span>` : ''}</th></tr>`;
  const row = (ref, hold, size, pi, mark, val, pc, pa, cls = '') => `<tr class="${cls}"><td><span class="code">${esc(ref)}</span></td><td>${hold}</td><td class="amt">${size}</td><td class="amt">${pi}</td><td class="amt">${mark}</td><td class="amt">${val}</td><td class="amt">${pc}</td><td class="amt">${pa}</td></tr>`;
  let h = `<thead><tr><th scope="col">Ref</th><th scope="col">Holding</th><th class="amt" scope="col">Shares</th><th class="amt" scope="col">% of issuer · status</th><th class="amt" scope="col">Mark</th><th class="amt" scope="col">Value</th><th class="amt" scope="col">% of class</th><th class="amt" scope="col">% of all</th></tr></thead><tbody>`;
  if (D.cash){
    h += sec('Liquid cash', 'bank-now · ' + esc(dayLong(D.cash.day)));
    h += row('SI', 'SI TOTAL — SI Main + every opex account', '—', '—', '—', full(D.cash.total), '100.0%', pct(D.cash.total / ALL));
  }
  if (PF && PF.equity.length){
    const E = PF.equity.slice().sort((a,b) => b.value - a.value), T = PF.equityTotal;
    h += sec('Equities — the CR-03 register, Hakk’s name', 'a price, not cash · ' + E.length + ' lines');
    for (const r of E) h += row(r.code, `<b>${esc(r.issuer)}</b> <span class="dim">${esc(r.cls)}</span>${r.note ? `<div class="sub">${esc(r.note.slice(0, 140))}</div>` : ''}`, num(r.shares), r.pctIssuer == null ? 'pref.' : '≈' + r.pctIssuer.toFixed((String(r.pctIssuer).split('.')[1] || '').length > 1 ? 2 : 1) + '%', r.mark == null ? '—' : r.mark.toFixed(2), full(r.value), pct(r.value / T), pct(r.value / ALL));
    h += row('', `<b>Equities at market</b>${PF.equityStated != null ? ` <span class="dim">· matches the register's ${full(PF.equityStated)}</span>` : ''}`, '', '', '', full(T), '100.0%', pct(T / ALL), 'subtotal');
    if (PF.rocklin){ const r = PF.rocklin; h += row(r.code, `<b>${esc(r.issuer)}</b> <span class="dim">${esc(r.cls)} · indicative, not in any total</span><div class="sub">${esc(r.pctNote)}</div>`, num(r.shares), r.pctIssuer == null ? '—' : r.pctIssuer.toFixed(1) + '% of B', r.mark == null ? '—' : r.mark.toFixed(2), full(r.value), '—', '—', 'muted'); }
  }
  if (PF && PF.debt.length){
    const T = sum(PF.debt, r => r.value);
    h += sec('Notes presenting at face', 'cash when the agent pays');
    for (const r of PF.debt) h += row(r.code, `<b>${esc(r.issuer)}</b><div class="sub">${esc(r.status)}</div>`, '—', 'presenting', '—', full(r.value), pct(r.value / T), pct(r.value / ALL));
  }
  if (PF && PF.personal.length){
    h += sec('Hakk’s own name — outside the register');
    for (const r of PF.personal) h += row(r.code, `<b>${esc(r.issuer)}</b> <span class="dim">${esc(r.cls)}</span><div class="sub">cost ${full(r.cost)} · ${esc(r.note)}</div>`, num(r.shares), '≈' + r.pctIssuer.toFixed(2) + '%', (r.value / r.shares).toFixed(2), full(r.value), '100.0%', pct(r.value / ALL));
  }
  if (PF && PF.properties && PF.properties.length){
    const O = pfOwned(), T = sum(O, p => p.cost), order = { Owned:0, Verify:1, Committed:2 };
    const L = PF.properties.slice().sort((a,b) => (order[a.status] ?? 3) - (order[b.status] ?? 3) || (b.cost || 0) - (a.cost || 0));
    h += sec('Property — at cost basis', `${O.length} owned & priced · ${PF.properties.length} on the register (${esc(PF.propertySource || '')})`);
    for (const p of L){
      const inT = p.status === 'Owned' && p.cost;
      h += row(p.owner.replace(/^(Slipstream Industries)$/, 'SI'), `<b>${esc(p.name)}</b>${p.district ? ` <span class="dim">· ${esc(p.district)}</span>` : ''}<div class="sub">${esc(p.source)}</div>`, '—', `<span class="st st-${esc(p.status.toLowerCase())}">${esc(p.status)}</span>`, '—',
        p.cost ? full(p.cost) : 'unpriced', inT ? pct(p.cost / T) : '—', inT ? pct(p.cost / ALL) : '—', inT ? '' : 'muted');
    }
    h += row('', '<b>Owned property at cost</b>', '', '', '', full(T), '100.0%', pct(T / ALL), 'subtotal');
    const Cm = pfCommitted(); if (Cm.length) h += row('', `<b>Committed, not deeded</b> <span class="dim">· not in any total</span>`, '', '', '', full(sum(Cm, p => p.cost)), '—', '—', 'muted');
  }
  h += `</tbody><tfoot><tr><td></td><td>Total holdings · cash + securities + owned property</td><td></td><td></td><td></td><td class="amt">${full(ALL)}</td><td></td><td class="amt">100.0%</td></tr></tfoot>`;
  host.innerHTML = h;
}

/* ---------- page layouts ---------- */"""

EDITS = [
    # v1.3
    ("const BOOKS = [['corporate','Corporate'],['reserve','Aster Vale reserve'],['personal','Hakk personal']];",
     "const BOOKS = [['corporate','Corporate'],['reserve','Aster Vale reserve'],['personal','Hakk personal']].filter(([b]) => D.entities.some(e => e.book === b));"),
    ("flows hidden — the CR-03 capital and transfers between our own entities dwarf trading",
     "flows hidden — capex purchases and the nightly opex sweeps dwarf day-to-day spending"),
    ("Capital: CR-03, paying agents, sweeps, acquisitions. Intra-group: moves between our own entities.",
     "Capital: capex-tagged purchases and property. Intra-group: the nightly opex sweeps into SI Main."),
    # v1.4 — markup: the cash band above the KPIs, the portfolio table under the ledger
    ('    <section class="kpis" id="kpis" aria-label="Key figures"></section>',
     '    <section class="kpis cashband" id="cashband" aria-label="Liquid cash"></section>\n    <section class="kpis" id="kpis" aria-label="Key figures"></section>'),
    ('    <section class="panel ledger" id="ledgerPanel" aria-labelledby="ledgerTitle">',
     '    <section class="panel ledger" id="portfolioPanel" aria-labelledby="pfTitle" hidden>\n'
     '      <div class="phead"><span class="idx">05</span><h2 id="pfTitle">Holdings</h2><span class="note">cash · securities · property — % of class and of all</span></div>\n'
     '      <div class="tablewrap pf"><table id="ptable"></table></div>\n    </section>\n'
     '    <section class="panel ledger" id="ledgerPanel" aria-labelledby="ledgerTitle">'),
    # v1.4 — styles
    (".kpi .val.neg{color:var(--neg)} .kpi .val.pos{color:var(--fg)}",
     ".kpi .val.neg{color:var(--neg)} .kpi .val.pos{color:var(--fg)}\n"
     ".kpis.cashband{grid-template-columns:1.7fr repeat(4,minmax(0,1fr))}\n"
     ".kpis.cashband .kpi:first-child{border-color:var(--line-hi)}\n"
     ".kpi .val.cash{color:#ffb21a;font-size:clamp(34px,3.4vw,56px)}\n"
     ".grid.g-pf{grid-template-columns:1fr 1.25fr;grid-template-areas:\"a b\" \"c d\"}\n"
     ".tablewrap.pf{max-height:760px}\n"
     "#ptable tr.sec th{position:static;background:transparent;color:var(--accent-2);padding-top:18px;border-bottom:1px solid var(--line-hi)}\n"
     "#ptable tr.sec th span{color:var(--dim);letter-spacing:.06em;text-transform:none;font-weight:400;margin-left:8px}\n"
     "#ptable tr.subtotal td{font-weight:600;border-top:1px solid var(--line-hi)}\n"
     "#ptable th,#ptable td{padding:7px 9px} #ptable td:nth-child(2){min-width:30ch} #ptable td:nth-child(4){white-space:nowrap}\n"
     "#ptable tr.muted td{opacity:.62}\n"
     "#ptable .dim{color:var(--dim);font-weight:400}\n"
     "#ptable .sub{color:var(--faint);font-size:12px;margin-top:3px;max-width:70ch}\n"
     "#ptable .st{font:400 11px/1 var(--f-mono);letter-spacing:.08em;text-transform:uppercase;padding:3px 6px;border:1px solid var(--line-hi)}\n"
     "#ptable .st-committed{color:var(--accent-2)} #ptable .st-verify{color:#ff8a70}\n"
     "@media (max-width:1100px){.kpis.cashband{grid-template-columns:repeat(2,minmax(0,1fr))}.kpis.cashband .kpi:first-child{grid-column:1 / -1}.grid.g-pf{grid-template-columns:1fr;grid-template-areas:none}}"),
    # v1.4 — script: helpers before the layouts
    ("/* ---------- page layouts ---------- */", PF_JS),
    # v1.4 — Positions KPIs
    ("""  const P = posRows(), cash = sum(P, p => p.cash), ar = sum(P, p => p.receivable), ap = sum(P, p => p.payableFirm), cont = sum(P, p => p.payableContingent);
  return [kpi('Cash now', cash, `<b>${P.length}</b> accounts`), kpi('Receivable', ar, `<b>${D.receivables.filter(r => entityVisible(r.entity)).length}</b> lines`),
    kpi('Payable, firm', -ap, `contingent ${short(cont)}`, 'neg'), kpi('Net position', sum(P, p => p.net), 'cash + AR − firm AP'),
    kpi('After posting', sum(P, p => p.afterPosting), `pending ${short(sum(P, p => p.pending))}`)];""",
     """  const ALL = allTotal(), cashT = D.cash ? D.cash.total : 0;
  const secT = PF ? PF.equityTotal + sum(PF.debt, r => r.value) + sum(PF.personal, r => r.value) : 0;
  const propT = sum(pfOwned(), p => p.cost), comT = sum(pfCommitted(), p => p.cost);
  return [kpi('Equities at market', PF ? PF.equityTotal : 0, `${pct((PF ? PF.equityTotal : 0) / ALL)} of holdings · <b>${PF ? PF.equity.length : 0}</b> lines`),
    kpi('Securities, all', secT, `${pct(secT / ALL)} · + notes & Orbital Air`),
    kpi('Property at cost', propT, `${pct(propT / ALL)} · <b>${pfOwned().length}</b> priced`),
    kpi('Total holdings', ALL, 'cash + securities + property'),
    kpi('Committed', comT ? -comT : '—', comT ? `${pfCommitted().length} not yet deeded` : 'nothing pending', comT ? 'neg' : '')];"""),
    # v1.4 — Positions layout
    ("""  positions:{ cls:'g-pos', panels:[
    { area:'a', title:'Cash by entity', note:'as of close', draw:el => cashByEntity(el), tall:true },
    { area:'b', title:'Closing balance by book', note:'own scale per row', multiples:true },
    { area:'c', title:'Receivables & payables', note:'by entity', draw:el => arAp(el) } ] }""",
     """  positions:{ cls:'g-pf', panels:[
    { area:'a', title:'Allocation', note:'% of total holdings', draw:el => allocation(el), legend:() => allocLegend(), tall:true },
    { area:'b', title:'Equities by issuer', note:'% of equities · at market', draw:el => equityByIssuer(el), tall:true },
    { area:'c', title:'Property by owner', note:'% of owned property · at cost', draw:el => propertyByOwner(el), tall:true },
    { area:'d', title:'Cash by entity', note:'SI Main + opex · as of close', draw:el => cashByEntity(el), tall:true } ] }"""),
    # v1.4 — show the holdings table on Positions only
    ("""  if (page === 'positions') return renderPositionsTable(tbl);""",
     """  const pfp = document.getElementById('portfolioPanel'); if (pfp){ pfp.hidden = page !== 'positions'; if (page === 'positions') renderPortfolio(); }
  if (page === 'positions'){ document.getElementById('ledgerIdx').textContent = '06'; renderPositionsTable(tbl); document.getElementById('ledgerTitle').textContent = 'Accounts'; return; }"""),
    # v1.4 — number the accounts panel after the holdings panel on Positions
    ("  document.getElementById('ledgerIdx').textContent = '0' + (lay.panels.length + 1);",
     "  document.getElementById('ledgerIdx').textContent = '0' + (lay.panels.length + (page === 'positions' ? 2 : 1));"),
    # v1.4 — draw the cash band once the data is in
    ("document.getElementById('asof').textContent = D.asOf.replace(/\\s+/g, ' ');",
     "document.getElementById('asof').textContent = D.asOf.replace(/\\s+/g, ' ');\nrenderCash();"),
]
changed = 0
for old, new in EDITS:
    if new in s:
        print('skip (already applied):', new.strip().splitlines()[0][:60]); continue
    assert s.count(old) == 1, f'anchor not found once: {old[:70]}'
    s = s.replace(old, new); changed += 1; print('patch finance.html:', new.strip().splitlines()[0][:60])
if changed:
    P.write_text(s, encoding='utf-8')
print(f'[OK] {changed} change(s)')
