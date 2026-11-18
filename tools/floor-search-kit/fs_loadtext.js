async function loadText(f, r) {
  let t = TEXT.get(r.id);
  if (t === undefined) {
    try { t = (await API.http("GET", "/api/entries/" + encodeURIComponent(r.id) + "?depth=0&select[text]=true")).text || ""; }
    catch (e) { const b = $("#detail .d-text"); if (b) b.innerHTML = `<p class="eyebrow">Full text</p><p>${esc(errMsg(e))}</p>`; return; }
    TEXT.set(r.id, t); if (TEXT.size > 12) TEXT.delete(TEXT.keys().next().value);
  }
  const box = $("#detail .d-text");
  if (!box || S.sel[f.key] !== r.id) return; // the reader moved on while it loaded
  const terms = qTerms();
  const [html, n] = markText(t, terms);
  box.innerHTML = `<p class="eyebrow">Full text · ${fmtSize(t.length)}${terms.length ? " · " + n + (n === 1 ? " match" : " matches") : ""}</p><pre class="fulltext">${html}</pre>`;
  const ms = box.querySelectorAll("mark");
  let k = 0;
  if (S.jump && S.jump.id === r.id && terms.length) { // a snippet was clicked: go to that hit
    const re = new RegExp(terms.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "gi");
    k = (t.slice(0, S.jump.at).match(re) || []).length;
  }
  S.jump = null;
  const m = ms[k] || ms[0]; if (m) { m.classList.add("hot"); m.scrollIntoView({ block: "center" }); }
}

