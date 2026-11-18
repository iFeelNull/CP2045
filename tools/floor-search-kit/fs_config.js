
/* ================= FLOOR-SEARCH v1: each floor's own search kit ================= */
// scopes: where the query looks (catalogue fields, the server-side full text, or both);
// filters: per-floor narrowing from the floor's own data; days: canon's play-day range.
const monthOf = w => { const m = String(w || "").match(/([A-Z][a-z]+)\s+\d{1,2},\s*(\d{4})/); return m ? m[1] + " " + m[2] : ""; };
const npcNote = (r, re) => { const m = String(r.notes || "").match(re); return m ? m[1] : ""; };
const FIND = {
  pc: { scopes: [["all", "Name & sheet"], ["text", "Sheet text only"], ["fields", "Name & role only"]],
    filters: [{ k: "status", label: "Status", get: r => r.status }] },
  npc: { scopes: [["all", "Name & sheet"], ["text", "Sheet text only"], ["fields", "Name & role only"]],
    filters: [
      { k: "sex", label: "Sex", get: r => npcNote(r, /Sex:\s*([A-Za-z]+)/) },
      { k: "life", label: "State", get: r => npcNote(r, /^(Living|Dead|Deceased|Flatlined|Missing|Unknown)\b/) },
      { k: "status", label: "Status", get: r => r.status }] },
  sheets: { scopes: [["all", "Title & text"], ["text", "Sheet text only"], ["fields", "Title & note only"]],
    filters: [{ k: "category", label: "Category", get: r => r.category }] },
  sourcebooks: { scopes: [["all", "Shelf & book text"], ["text", "Inside the books"], ["fields", "Shelf only"]],
    filters: [{ k: "book", label: "Book", get: r => r.title, order: "first" }, { k: "format", label: "Format", get: r => r.format }] },
  dlc: { scopes: [["all", "List & DLC text"], ["text", "Inside the DLCs"], ["fields", "List only"]],
    filters: [{ k: "type", label: "Type", get: r => r.type }, { k: "book", label: "DLC", get: r => r.title, order: "first" }, { k: "status", label: "Status", get: r => r.status }] },
  canon: { scopes: [["all", "Title & day text"], ["text", "Day text only"], ["fields", "Title & date only"]],
    filters: [{ k: "month", label: "Month", get: r => monthOf(r.when), order: "first" }, { k: "kind", label: "Kind", get: r => r.kind }],
    days: true }
};
const FS = {};
FLOORS.forEach(f => { f.find = FIND[f.key]; FS[f.key] = { scope: "all", mode: "all", sort: "hits", f: {}, from: "", to: "" }; });
