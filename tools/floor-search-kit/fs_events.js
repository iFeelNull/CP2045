$("#search").addEventListener("input", e => { S.q = e.target.value; ftSearch(); renderRoster(); });
/* FLOOR-SEARCH v1: the floor's own search bar */
function fbSet(t) {
  const k = t.dataset && t.dataset.fb; if (!k) return;
  const s = FS[S.floor];
  if (k.slice(0, 2) === "f:") s.f[k.slice(2)] = t.value; else s[k] = t.value;
  if (k === "scope" || k === "mode") ftSearch();
  renderRoster();
}
$("#findbar").addEventListener("change", e => fbSet(e.target));
$("#findbar").addEventListener("input", e => { if (e.target.type === "number") fbSet(e.target); });
$("#findbar").addEventListener("click", e => {
  if (!e.target.closest("[data-fb-clear]")) return;
  const s = FS[S.floor]; s.f = {}; s.from = ""; s.to = "";
  S.q = ""; $("#search").value = ""; ftSearch(); renderFind(); renderRoster();
  const f = cur(), r = S.data[f.key].find(x => x.id === S.sel[f.key]);
  if (r && r._tl && !S.editing) (isSheet(f, r) ? mountSheet(r) : loadText(f, r));
});
