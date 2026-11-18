/* full-text search (FLOOR-SEARCH v1): /api/entries/search returns hits and snippets per entry for the current floor */
const FT = { floor: null, key: "", ids: new Set(), res: new Map(), timer: 0, seq: 0, busy: false };
const ftKey = () => S.q.trim().toLowerCase() + "\u0001" + (FS[S.floor] ? FS[S.floor].mode : "all");
function qTerms() {
  const q = S.q.trim().toLowerCase(); if (!q) return [];
  return FS[S.floor] && FS[S.floor].mode === "phrase" ? [q] : q.split(/\s+/).filter(w => w.length > 1);
}
function filtersOn(f) { const s = FS[f.key]; return Object.values(s.f).some(has) || has(s.from) || has(s.to); }
function passFilters(f, r) {
  const s = FS[f.key], fd = f.find || {};
  for (const x of fd.filters || []) { const want = s.f[x.k]; if (has(want) && String(x.get(r) || "") !== want) return false; }
  if (fd.days && (has(s.from) || has(s.to))) {
    const d = parseInt(r.day, 10); if (!isFinite(d)) return false;
    if (has(s.from) && d < +s.from) return false;
    if (has(s.to) && d > +s.to) return false;
  }
  return true;
}
function renderFind() {
  const f = cur(), fd = f.find, el = $("#findbar"); if (!el) return;
  const list = S.data[f.key];
  if (!fd || !list.length) { el.hidden = true; el.innerHTML = ""; return; }
  const s = FS[f.key], ft = list.some(r => r._tl);
  const sel = (id, label, val, opts) => `<label class="fb-f"><span>${esc(label)}</span><select data-fb="${esc(id)}">${opts.map(([v, t]) => `<option value="${esc(v)}" ${v === val ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
  let h = "";
  if (ft) h += sel("scope", "Look in", s.scope, fd.scopes) + sel("mode", "Match", s.mode, [["all", "All words"], ["phrase", "Exact phrase"]]) + sel("sort", "Order", s.sort, [["hits", "Most hits first"], ["seq", "Filed order"]]);
  for (const x of fd.filters || []) {
    const cnt = new Map(); list.forEach(r => { const v = String(x.get(r) || ""); if (v) cnt.set(v, (cnt.get(v) || 0) + 1); });
    if (cnt.size < 2 && !has(s.f[x.k])) continue;
    const vals = [...cnt.keys()]; if (x.order !== "first") vals.sort((a, b) => a.localeCompare(b));
    h += sel("f:" + x.k, x.label, s.f[x.k] || "", [["", "All"], ...vals.map(v => [v, v + " (" + cnt.get(v) + ")"])]);
  }
  if (fd.days) {
    const ds = list.map(r => parseInt(r.day, 10)).filter(isFinite);
    if (ds.length) {
      const lo = Math.min(...ds), hi = Math.max(...ds);
      h += `<label class="fb-f fb-n"><span>From day</span><input type="number" inputmode="numeric" data-fb="from" min="${lo}" max="${hi}" placeholder="${lo}" value="${esc(s.from)}"></label>` +
        `<label class="fb-f fb-n"><span>To day</span><input type="number" inputmode="numeric" data-fb="to" min="${lo}" max="${hi}" placeholder="${hi}" value="${esc(s.to)}"></label>`;
    }
  }
  h += `<button type="button" class="btn ghost sm fb-clear" data-fb-clear hidden>Clear</button><p class="fb-stat" id="fb-stat" aria-live="polite"></p>`;
  el.innerHTML = h; el.hidden = false;
  renderStat();
}
function renderStat() {
  const el = $("#fb-stat"), f = cur(), q = S.q.trim();
  const c = $("#findbar [data-fb-clear]"); if (c) c.hidden = !(filtersOn(f) || q);
  if (!el) return;
  if (FT.busy && q) { el.textContent = "Searching the text…"; return; }
  if (q && FT.floor === f.key && FT.key === ftKey()) {
    let h = 0, n = 0; FT.res.forEach((d, id) => { const r = S.data[f.key].find(x => x.id === id); if (r && passFilters(f, r)) { h += d.hits || 0; n++; } });
    el.textContent = `In the text: ${h} ${h === 1 ? "hit" : "hits"} across ${n} ${n === 1 ? "entry" : "entries"}${FS[f.key].mode === "phrase" ? " (exact phrase)" : ""}.`;
    return;
  }
  el.textContent = q && q.length < 3 && S.data[f.key].some(r => r._tl) && FS[f.key].scope !== "fields" ? "Type 3 or more characters to search inside the text." : "";
}
function ftSearch() {
  clearTimeout(FT.timer);
  const f = cur(), q = S.q.trim(), s = FS[f.key];
  if (S.mode !== "net" || q.length < 3 || s.scope === "fields" || !S.data[f.key].some(r => r._tl)) {
    FT.floor = null; FT.key = ""; FT.ids = new Set(); FT.res = new Map(); FT.busy = false; ++FT.seq; return;
  }
  FT.busy = true;
  FT.timer = setTimeout(async () => {
    const my = ++FT.seq, key = ftKey(), fk = f.key;
    try {
      const j = await API.http("GET", "/api/entries/search?floor=" + encodeURIComponent(fk) + "&q=" + encodeURIComponent(q) + "&mode=" + encodeURIComponent(s.mode));
      if (my !== FT.seq) return;
      FT.floor = fk; FT.key = key; FT.busy = false;
      FT.res = new Map((j.docs || []).map(d => [String(d.id), d])); FT.ids = new Set(FT.res.keys());
      if (S.floor !== fk) return;
      renderRoster();
      const r = S.data[fk].find(x => x.id === S.sel[fk]);
      if (r && r._tl && !S.editing) (isSheet(f, r) ? mountSheet(r) : loadText(f, r));
    } catch (e) { if (my === FT.seq) { FT.busy = false; renderStat(); toast(errMsg(e), true); } }
  }, 300);
}
function fieldHit(f, r, q) {
  const hay = [r[f.primary], ...(f.sub(r) || []), r.name, f.badge(r), code(f, r), ...((f.search && f.search(r)) || [])].filter(has).join(" ").toLowerCase();
  if (FS[f.key].mode === "phrase") return hay.includes(q);
  return q.split(/\s+/).filter(Boolean).every(w => hay.includes(w));
}
function matches(f, r, q) {
  if (!passFilters(f, r)) return false;
  if (!q) return true;
  const sc = FS[f.key].scope, inText = FT.floor === f.key && FT.key === ftKey() && FT.ids.has(r.id);
  if (sc === "text") return inText;
  if (sc === "fields") return fieldHit(f, r, q);
  return inText || fieldHit(f, r, q);
}
function snipHTML(s) { const [h] = markText(s, qTerms()); return `<span class="snip-t">…${h}…</span>`; }

function renderRoster() {
  const f = cur(), q = S.q.trim().toLowerCase(), s = FS[f.key];
  let list = S.data[f.key].filter(r => matches(f, r, q));
  const live = !!q && FT.floor === f.key && FT.key === ftKey();
  if (live && s.sort === "hits") list = list.slice().sort((a, b) => ((FT.res.get(b.id) || {}).hits || 0) - ((FT.res.get(a.id) || {}).hits || 0));
  const narrowed = !!q || filtersOn(f);
  const head = `<div class="roster-head"><span>Index</span><span>${narrowed ? pad(list.length) + " of " : ""}${pad(S.data[f.key].length)} on file</span></div>`;
  renderStat();
  if (!list.length) {
    $("#roster").innerHTML = head + `<p class="no-match">${FT.busy && q ? "Searching the text…" : q ? `No matches for “${esc(S.q.trim())}”.` : "Nothing on this floor fits those filters."}</p>`;
    return;
  }
  if (f.cover && !narrowed) {
    $("#roster").innerHTML = head + `<ul class="rows covers">${list.map(r => `<li><button type="button" class="cover-btn" data-id="${esc(r.id)}" ${S.sel[f.key] === r.id ? 'aria-current="true"' : ""}>
      ${coverHTML(f, r)}<span class="row-main"><span class="row-name">${esc(r.title || "Untitled")}</span><span class="row-sub">${esc((f.sub(r) || []).filter(has).join(" · ")) || "&nbsp;"}</span></span>
    </button></li>`).join("")}</ul>`;
    return;
  }
  $("#roster").innerHTML = head + `<ul class="rows">${list.map(r => {
    const name = r[f.primary] || "Unnamed";
    const sub = (f.sub(r) || []).filter(has).join(" · ");
    const lead = f.thumb ? thumbHTML(r[f.thumb], name, "th") : `<span class="row-tag">${pad(r.seq || 0, 3)}</span>`;
    const hit = live ? FT.res.get(r.id) : null;
    const snips = hit && hit.snips && hit.snips.length
      ? `<div class="snips">${hit.snips.map(sn => `<button type="button" class="snip" data-id="${esc(r.id)}" data-at="${+sn.at || 0}">${has(sn.ctx) ? `<b>${esc(sn.ctx)}</b>` : ""}${snipHTML(sn.s)}</button>`).join("")}</div>` : "";
    return `<li><button type="button" class="row" data-id="${esc(r.id)}" ${S.sel[f.key] === r.id ? 'aria-current="true"' : ""}>
      ${lead}
      <span class="row-main"><span class="row-code">${code(f, r)}</span><span class="row-name">${esc(name)}</span><span class="row-sub">${esc(sub) || "&nbsp;"}</span></span>
      ${hit ? `<span class="row-hits" title="${hit.hits} ${hit.hits === 1 ? "hit" : "hits"} in the text">${hit.hits}×</span>` : pill(f.badge(r))}
    </button>${snips}</li>`;
  }).join("")}</ul>`;
}

