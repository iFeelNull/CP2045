/* RED character sheet for the Datafort (F01 PCs, F02 NPCs).
 * Reads a pc-*.md / npc-*.md sheet (markdown) into the layout of the official
 * Cyberpunk RED character sheet (R. Talsorian, 3 pages) and renders it.
 * Nothing is invented: a box the sheet does not fill stays empty, and every
 * section the layout has no box for is kept on the "More" page.
 * History: versions come from /api/sheet-history; changes against an older
 * version are marked cell by cell ("was …").
 * Exposes window.RedSheet = { parse, mount, flatten, diff }.
 */
(function () {
  "use strict";
  const STATS = ["INT", "REF", "DEX", "TECH", "COOL", "WILL", "LUCK", "MOVE", "BODY", "EMP"];

  // The official sheet's skill list, in its order (page 1). x2 = Difficult.
  // multi: rows the sheet repeats with a blank to name (Language, Local Expert, Science, Play Instrument).
  const SKILLS = [
    ["Awareness", [["Concentration", "WILL"], ["Conceal/Reveal Object", "INT"], ["Lip Reading", "INT"], ["Perception", "INT"], ["Tracking", "INT"]]],
    ["Body", [["Athletics", "DEX"], ["Contortionist", "DEX"], ["Dance", "DEX"], ["Endurance", "WILL"], ["Resist Torture/Drugs", "WILL"], ["Stealth", "DEX"]]],
    ["Control", [["Drive Land Vehicle", "REF"], ["Pilot Air Vehicle", "REF", 2], ["Pilot Sea Vehicle", "REF"], ["Riding", "REF"]]],
    ["Education", [["Accounting", "INT"], ["Animal Handling", "INT"], ["Bureaucracy", "INT"], ["Business", "INT"], ["Composition", "INT"],
      ["Criminology", "INT"], ["Cryptography", "INT"], ["Deduction", "INT"], ["Education", "INT"], ["Gamble", "INT"],
      ["Language", "INT", 1, 3], ["Library Search", "INT"], ["Local Expert", "INT", 1, 3], ["Science", "INT", 1, 2], ["Tactics", "INT"], ["Wilderness Survival", "INT"]]],
    ["Fighting", [["Brawling", "DEX"], ["Evasion", "DEX"], ["Martial Arts", "DEX", 2], ["Melee Weapon", "DEX"]]],
    ["Performance", [["Acting", "COOL"], ["Play Instrument", "TECH", 1, 2]]],
    ["Ranged Weapon", [["Archery", "REF"], ["Autofire", "REF", 2], ["Handgun", "REF"], ["Heavy Weapons", "REF", 2], ["Shoulder Arms", "REF"]]],
    ["Social", [["Bribery", "COOL"], ["Conversation", "EMP"], ["Human Perception", "EMP"], ["Interrogation", "COOL"], ["Persuasion", "COOL"],
      ["Personal Grooming", "COOL"], ["Streetwise", "COOL"], ["Trading", "COOL"], ["Wardrobe & Style", "COOL"]]],
    ["Technique", [["Air Vehicle Tech", "TECH"], ["Basic Tech", "TECH"], ["Cybertech", "TECH"], ["Demolitions", "TECH", 2], ["Electronics/Security Tech", "TECH", 2],
      ["First Aid", "TECH"], ["Forgery", "TECH"], ["Land Vehicle Tech", "TECH"], ["Paint/Draw/Sculpt", "TECH"], ["Paramedic", "TECH", 2],
      ["Photography/Film", "TECH"], ["Pick Lock", "TECH"], ["Pick Pocket", "TECH"], ["Sea Vehicle Tech", "TECH"], ["Weaponstech", "TECH"]]]
  ];
  const SKILL_INDEX = [];
  SKILLS.forEach(([g, list]) => list.forEach(([name, stat, x2, multi]) => SKILL_INDEX.push({ g, name, stat, x2: x2 === 2, multi: multi || 0, key: norm(name) })));
  const ALIAS = { "conceal reveal": "conceal/reveal object", "resist torture drugs": "resist torture/drugs", "electronics security tech": "electronics/security tech",
    "e s tech": "electronics/security tech", "wardrobe style": "wardrobe & style", "wardrobe and style": "wardrobe & style", "paint draw sculpt": "paint/draw/sculpt",
    "photography film": "photography/film", "pilot air": "pilot air vehicle", "drive": "drive land vehicle", "melee weapons": "melee weapon", "heavy weapon": "heavy weapons",
    "language streetslang": "language", "streetslang": "language", "instrument": "play instrument" };

  // Lifepath boxes on page 2, with the sheet keys that fill them.
  const LIFE = [["Cultural Origins", /cultural|origin/], ["Personality", /^personality/], ["Clothing Style", /clothing/], ["Hairstyle", /hair/],
    ["What Do You Value Most?", /value most\??$|what do you value/], ["Feelings About People?", /feel.*people/], ["Most Valued Person", /valued person|value.*person/],
    ["Most Valued Possession", /possession/], ["Family Background", /family background|^family$/], ["Childhood Environment", /childhood/],
    ["Family Crisis", /family crisis|crisis/], ["Life Goals", /life goal|goals?$/]];
  const CYBER_SLOTS = ["Cyberaudio Suite", "Right Cybereye", "Left Cybereye", "Right Cyberarm", "Left Cyberarm", "Neural Link", "Right Cyberleg", "Left Cyberleg",
    "Internal Cyberware", "External Cyberware", "Fashionware", "Borgware"];

  /* ---------------- text helpers ---------------- */
  function norm(s) { return String(s || "").toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").replace(/\band\b/g, " ").replace(/\s+/g, " ").trim(); }
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // current value of a markdown cell: struck-out (~~old~~) text is history, not the value
  const unstrike = s => String(s || "").replace(/~~[^~]*~~/g, "");
  function plain(s) {
    return unstrike(s).replace(/<br\s*\/?>/gi, " ").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/\*\*|__|`/g, "").replace(/(^|[\s(])\*(?=\S)|(?<=\S)\*(?=[\s).,;:]|$)/g, "$1").replace(/\s+/g, " ").trim();
  }
  function firstInt(s) { const m = /-?\d[\d,]*/.exec(unstrike(s).replace(/\*\*/g, "")); return m ? Number(m[0].replace(/,/g, "")) : null; }
  const has = v => v != null && String(v).trim() !== "" && String(v).trim() !== "—" && String(v).trim() !== "-";
  const titleCase = s => String(s).toLowerCase().replace(/(^|[\s/·(-])([a-z])/g, (m, a, b) => a + b.toUpperCase());
  // inline markdown -> safe HTML (bold, italic, struck, code)
  function mdi(s) {
    let h = esc(String(s || "").replace(/<br\s*\/?>/gi, "\n"));
    h = h.replace(/~~([^~]+)~~/g, "<del>$1</del>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s).,;:]|$)/g, "$1<i>$2</i>").replace(/`([^`]+)`/g, "<code>$1</code>");
    return h.replace(/\n/g, "<br>");
  }
  // block markdown (tables, lists, quotes, headings, paragraphs) -> safe HTML
  function mdb(lines) {
    if (typeof lines === "string") lines = lines.split(/\r?\n/);
    let out = "", i = 0;
    while (i < lines.length) {
      const l = lines[i];
      if (/^\s*\|/.test(l)) {
        const blk = []; while (i < lines.length && /^\s*\|/.test(lines[i])) blk.push(lines[i++]);
        const t = table(blk);
        if (t) out += `<table class="rs-md-t">${t.head.some(has) ? `<thead><tr>${t.head.map(c => `<th>${mdi(c)}</th>`).join("")}</tr></thead>` : ""}<tbody>${t.rows.map(r => `<tr>${r.map(c => `<td>${mdi(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
        continue;
      }
      if (/^\s*[-*+]\s+/.test(l)) {
        const items = []; while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*+]\s+/, ""));
        out += `<ul>${items.map(x => `<li>${mdi(x)}</li>`).join("")}</ul>`; continue;
      }
      if (/^\s*>/.test(l)) {
        const q = []; while (i < lines.length && /^\s*>/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
        out += `<blockquote>${mdb(q)}</blockquote>`; continue;
      }
      const h = /^(#{1,6})\s+(.*)$/.exec(l);
      if (h) { out += `<p class="rs-md-h">${mdi(h[2])}</p>`; i++; continue; }
      if (/^\s*(---|\*\*\*)\s*$/.test(l) || !l.trim()) { i++; continue; }
      const p = []; while (i < lines.length && lines[i].trim() && !/^\s*(\||[-*+]\s|>|#{1,6}\s|---\s*$)/.test(lines[i])) p.push(lines[i++]);
      out += `<p>${mdi(p.join(" "))}</p>`;
    }
    return out;
  }
  function table(blk) {
    const rows = blk.filter(l => !/^\s*\|\s*:?-{2,}/.test(l)).map(l => {
      const cells = l.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map(c => c.trim());
      return cells;
    });
    if (!rows.length) return null;
    const sep = blk.length > 1 && /^\s*\|\s*:?-{2,}/.test(blk[1]);
    return sep ? { head: rows[0], rows: rows.slice(1) } : { head: [], rows };
  }

  /* ---------------- sections ---------------- */
  function sections(text) {
    const out = []; let top = null, cur = { h: "", level: 0, top: "", lines: [] }; out.push(cur);
    for (const l of String(text || "").split(/\r?\n/)) {
      const m = /^(#{1,4})\s+(.*)$/.exec(l);
      if (m) {
        const level = m[1].length, h = plain(m[2]);
        if (level === 1 && /^PAGE\s+\d/i.test(h)) { cur = { h, level, top: h, lines: [], page: true }; out.push(cur); continue; }
        if (level <= 2) top = h;
        cur = { h, level, top: level <= 2 ? h : (top || h), lines: [], raw: m[2] }; out.push(cur); continue;
      }
      cur.lines.push(l);
    }
    return out.filter(s => s.h || s.lines.some(x => x.trim()));
  }
  function tables(sec) {
    const res = []; let blk = [];
    const flush = () => { if (blk.length) { const t = table(blk); if (t) res.push(t); blk = []; } };
    for (const l of sec.lines) { if (/^\s*\|/.test(l)) blk.push(l); else flush(); }
    flush(); return res;
  }
  const col = (head, re) => head.findIndex(h => re.test(plain(h).toLowerCase()));
  function kv(sec) { // key/value from 2-column tables and "- **Key:** value" bullets
    const out = [];
    for (const t of tables(sec)) for (const r of t.rows) // the header row ("| | |", "Field", "Who | What") is never data
      if (r.length >= 2 && has(plain(r[0]))) out.push([plain(r[0]), r.slice(1).join(" · ")]);
    for (const l of sec.lines) {
      const m = /^\s*[-*]\s+\*\*([^*]+?):?\*\*:?\s*(.*)$/.exec(l);
      if (m) out.push([plain(m[1]).replace(/:$/, ""), m[2]]);
    }
    return out;
  }
  const textOf = sec => sec ? sec.lines.join("\n").trim() : "";

  /* ---------------- parse ---------------- */
  function parse(text) {
    const secs = sections(text), used = new Set();
    const find = (re, level) => secs.filter(s => s.h && re.test(s.h) && (!level || s.level <= level));
    const take = s => { if (s) used.add(s); return s; };
    const M = { name: "", kind: "", identity: [], stats: {}, statMax: {}, derived: {}, roles: [], skills: [], skillsNote: "", weapons: [], weaponsText: "",
      armor: {}, armorText: "", rep: null, repText: "", ip: null, ipText: "", lifepath: {}, lifeExtra: [], friends: [], loves: [], enemies: [], cyber: {}, cyberStatus: [], cyberPending: [], cyberSources: [],
      cyberText: "", gear: [], gearText: "", housing: "", lifestyle: "", rent: "", cash: "", more: [] };
    const t0 = secs.find(s => s.level === 1 && !s.page);
    if (t0) { M.name = t0.h.replace(/^NPC( CANON)?\s+[—-]\s+/i, ""); used.add(t0); }
    const sub = secs.find(s => s.level === 3 && /CHARACTER SHEET/i.test(s.h)); if (sub) { M.kind = sub.h; used.add(sub); }

    // identity
    for (const s of find(/^IDENTITY/)) { take(s); M.identity.push(...kv(s)); }

    // stats: the INT..EMP table, else "INT 6 · REF 6 …" anywhere in a STATS section
    for (const s of find(/^STATS/)) {
      take(s);
      for (const t of tables(s)) {
        const hi = t.head.map(h => plain(h).toUpperCase());
        if (hi.includes("INT") && hi.includes("EMP") && t.rows[0]) {
          hi.forEach((h, i) => { if (STATS.includes(h)) statCell(M, h, t.rows[0][i]); });
        }
      }
      if (!Object.keys(M.stats).length) {
        const all = unstrike(textOf(s)).replace(/\*\*/g, "");
        for (const k of STATS) { const m = new RegExp("\\b" + k + "\\s+(\\d+)").exec(all); if (m) M.stats[k] = Number(m[1]); }
        derivedFromProse(M, all);
        skillsFromProse(M, s);
      }
    }
    // derived
    for (const s of find(/^(DERIVED|Derived)/)) {
      take(s);
      for (const [k, v] of kv(s)) derived(M, k, v);
    }
    // role abilities
    for (const s of find(/^(ROLE ABILITY|SECOND ROLE|ROLE\b)/)) {
      take(s);
      const h = s.h.replace(/\(.*$/, "");
      let m = /[—-]\s*(.+?)(?:,\s*RANK\s*|\s+)(\d+)\b/i.exec(h), name, rank;
      if (m && !/GM BUILD/i.test(m[1])) { name = titleCase(m[1].replace(/,\s*$/, "")); rank = Number(m[2]); }
      else for (const l of s.lines) { const b = /^\s*\*\*([A-Za-z][A-Za-z ·/&-]+?)\s+(\d+)\*\*\s*$/.exec(l); if (b) { name = b[1]; rank = Number(b[2]); break; } }
      M.roles.push({ head: s.h, name: name || "", rank: rank == null ? null : rank, text: textOf(s) });
    }
    // skills: every table in the SKILLS section and its sub-sections
    const skillSecs = secs.filter(s => /^SKILLS/i.test(s.top || "") || /^SKILLS/i.test(s.h));
    for (const s of skillSecs) {
      take(s);
      for (const t of tables(s)) {
        const ci = col(t.head, /^skill/); if (ci < 0) continue;
        const cs = col(t.head, /^stat/), cl = col(t.head, /^(lvl|level)/), cb = col(t.head, /^base/), cn = col(t.head, /^notes?/);
        for (const r of t.rows) addSkill(M, r[ci], cs >= 0 ? r[cs] : "", cl >= 0 ? r[cl] : "", cb >= 0 ? r[cb] : "", cn >= 0 ? r.slice(cn).join(" | ") : (r.length > Math.max(ci, cs, cl, cb) + 1 ? r.slice(Math.max(ci, cs, cl, cb) + 1).join(" | ") : ""));
      }
    }
    const sk0 = skillSecs.find(s => /^SKILLS/i.test(s.h)); if (sk0) M.skillsNote = sk0.lines.filter(l => l.trim() && !/^\s*\|/.test(l) && !/^\s*\*\*[A-Z /]+\*\*\s*$/.test(l)).join("\n");

    // weapons and armor
    for (const s of find(/WEAPON|ARMOR|COMBAT/)) {
      if (/^STANDING|^HISTORY/i.test(s.h)) continue;
      take(s); let got = false;
      for (const t of tables(s)) {
        const cw = col(t.head, /^weapon/), cloc = col(t.head, /^location/);
        if (cw >= 0) { got = true; for (const r of t.rows) M.weapons.push(weapon(t.head, r)); }
        else if (cloc >= 0) {
          got = true; const csp = col(t.head, /^sp$/), cty = col(t.head, /^type/), cpe = col(t.head, /^penalty/);
          for (const r of t.rows) { const loc = plain(r[cloc]).toLowerCase(); if (/head|body|shield/.test(loc)) M.armor[loc.match(/head|body|shield/)[0]] = { sp: csp >= 0 ? plain(r[csp]) : "", type: cty >= 0 ? plain(r[cty]) : "", pen: cpe >= 0 ? plain(r[cpe]) : "" }; }
        }
      }
      const rest = s.lines.filter(l => !/^\s*\|/.test(l)).join("\n").trim();
      if (/ARMOR/i.test(s.h) && !/WEAPON/i.test(s.h)) M.armorText += (M.armorText ? "\n\n" : "") + rest;
      else if (rest) M.weaponsText += (M.weaponsText ? "\n\n" : "") + (got ? "" : "") + rest;
    }
    // reputation, IP
    for (const s of find(/^REPUTATION/)) { take(s); const n = firstInt((s.raw || s.h).replace(/^[^—-]*[—-]/, "")); if (n != null) M.rep = n; M.repText = textOf(s); }
    if (M.rep == null && M.derived.rep != null) M.rep = M.derived.rep;
    for (const s of find(/^IMPROVEMENT POINTS/)) { take(s); const t = textOf(s); const m = /Bank:?\**\s*([\d,]+)/i.exec(unstrike(t)); if (m) M.ip = Number(m[1].replace(/,/g, "")); M.ipText = t; }

    // lifepath
    for (const s of find(/^LIFEPATH/)) {
      take(s);
      for (const [k, v] of kv(s)) {
        const kl = k.toLowerCase();
        if (/tragic love|love affair/.test(kl)) { M.loves.push(v); continue; }
        const box = LIFE.find(([, re]) => re.test(kl));
        if (box && !M.lifepath[box[0]]) M.lifepath[box[0]] = v; else M.lifeExtra.push([k, v]);
      }
      if (!kv(s).length && textOf(s)) M.lifeExtra.push(["Lifepath", textOf(s)]);
    }
    for (const s of find(/^FRIENDS/)) { take(s); const p = kv(s); if (p.length) p.forEach(([a, b]) => M.friends.push([a, b])); else if (textOf(s)) M.friends.push(["", textOf(s)]); }
    for (const s of find(/^ENEMIES/)) {
      take(s); let got = false;
      for (const t of tables(s)) { got = true; for (const r of t.rows) M.enemies.push([r[0] || "", r[1] || "", r[2] || "", r.slice(3).join(" · ")]); }
      if (!got && textOf(s)) M.enemies.push(["", textOf(s), "", ""]);
    }
    // cyberware: tables, bullet lists, "**Chrome …:**" lists in other sections, the Humanity line, and
    // "X required / offered" — every item classified against the RED cyberware catalog (CR p. 358–366)
    parseCyber(M, secs, used, take);
    // the "**Chrome (…):**" list some sheets keep inside another section (Dov)
    for (const s of secs) {
      if (/CYBER/i.test(s.h)) continue;
      const i = s.lines.findIndex(l => /^\s*\*\*(Chrome|Cyberware)\b[^*]*\*\*:?\s*$/i.test(l));
      if (i < 0) continue;
      const blk = []; for (let j = i + 1; j < s.lines.length; j++) { const l = s.lines[j]; if (!l.trim() && blk.length) break; if (l.trim()) blk.push(l); }
      const left = cyberLines(M, blk, "the " + plain(s.lines[i]).replace(/:$/, "") + " list under " + s.h);
      if (left.length) M.cyberText += (M.cyberText ? "\n\n" : "") + left.join("\n");
    }
    // nothing installed on a cyberware page? the Humanity line may name the installs (Kade, Banerjee)
    if (!cyberCount(M) && has(M.derived.humText)) {
      const h = unstrike(M.derived.humText);
      if (/no cyberware/i.test(h)) M.cyberStatus.push("Humanity line: " + plain(h));
      else {
        const hits = []; for (const piece of plain(h).split(/\s*[+;,(]\s*|\s+and\s+/)) { const c = catOf(piece); if (!c) continue; const nm = titleCase(plain(piece).match(c.re)[0]); if (!hits.some(x => x.name === nm)) hits.push({ c, name: nm }); }
        if (hits.length) { const ctx = {}; hits.forEach((x, k) => placeCyber(M, x.c, x.name, piece2side(x.name), k ? "" : "From the Humanity line: " + plain(h), ctx)); }
      }
    }
    // "**Internal Agent required**", "**Kiroshis offered**" anywhere on the sheet: not installed
    for (const m of String(text).matchAll(/\*\*([^*\n]{2,60}?)\s+(required|offered)\*\*([^\n]*)/gi)) {
      if (catOf(m[1]) && !M.cyberPending.some(p => norm(p.name) === norm(plain(m[1]))))
        M.cyberPending.push({ name: plain(m[1]), status: titleCase(m[2]) + " — not installed", note: plain(m[3]).replace(/^[\s—–:-]+/, "").slice(0, 400) });
    }
    // gear
    for (const s of find(/^GEAR/)) {
      take(s); let got = false;
      for (const t of tables(s)) { const ci = col(t.head, /^item/); if (ci < 0) continue; got = true; for (const r of t.rows) if (has(plain(r[ci]))) M.gear.push([r[ci], r.filter((_, i) => i !== ci).join(" · ")]); }
      const rest = s.lines.filter(l => !/^\s*\|/.test(l)).join("\n").trim();
      if (rest) { const bul = rest.split(/\n/).filter(l => /^\s*[-*]\s+/.test(l)); if (bul.length && !got) bul.forEach(b => M.gear.push([b.replace(/^\s*[-*]\s+/, ""), ""])); else M.gearText += rest; }
    }
    // housing, money
    for (const s of find(/^HOUSING/)) {
      take(s); M.housing = (s.h.split(/[—-]/).slice(1).join("—").trim() ? s.h.split(/[—-]/).slice(1).join("—").trim() + "\n" : "") + textOf(s);
      for (const [k, v] of kv(s)) { if (/lifestyle/i.test(k) && !M.lifestyle) M.lifestyle = plain(v); if (/rent|note|mortgage/i.test(k) && !M.rent) M.rent = plain(v); }
    }
    for (const s of find(/^(MONEY|PAY)/)) { take(s); M.cash += (M.cash ? "\n\n" : "") + (s.h.match(/^PAY/) ? "**" + s.h + "**\n" : "") + textOf(s); }

    // everything else, in sheet order (top-level sections with their sub-sections)
    let cur = null;
    for (const s of secs) {
      if (s.page || used.has(s) || (s.level === 1 && !s.page && s === t0)) { cur = null; continue; }
      if (s.level >= 3 && cur && s.top === cur.h) { cur.lines.push("### " + s.h, ...s.lines); continue; }
      if (!s.h && !s.lines.some(l => l.trim() && !/^\s*---\s*$/.test(l))) continue;
      cur = { h: s.h || "Header", lines: s.lines.slice() }; M.more.push(cur);
    }
    M.more = M.more.filter(x => x.lines.some(l => l.trim() && !/^\s*---\s*$/.test(l)));
    // derived defaults the sheet itself states elsewhere
    if (M.derived.hp == null && M.derived.hpText) M.derived.hp = firstInt(M.derived.hpText);
    return M;
  }
  function statCell(M, k, cell) {
    const c = unstrike(cell).replace(/\*\*/g, "");
    const v = firstInt(c); if (v == null) return;
    const mx = /max(?:imum)?\s*(\d+)/i.exec(c), cu = /(\d+)\s*current/i.exec(c);
    if (cu) { M.stats[k] = Number(cu[1]); M.statMax[k] = v; } else { M.stats[k] = v; if (mx) M.statMax[k] = Number(mx[1]); }
  }
  function derived(M, k, v) {
    const kl = k.toLowerCase(), c = unstrike(v).replace(/\*\*/g, ""), D = M.derived;
    const pair = /(-?\d+)\s*\/\s*(\d+)/.exec(c);
    if (/hit points|^hp$/.test(kl)) { if (pair) { D.hp = +pair[1]; D.hpMax = +pair[2]; } else { D.hp = D.hpMax = firstInt(c); } D.hpText = v; }
    else if (/seriously/.test(kl)) D.sw = firstInt(c);
    else if (/death save/.test(kl)) D.ds = firstInt(c);
    else if (/^humanity/.test(kl)) { if (pair) { D.hum = +pair[1]; D.humMax = +pair[2]; } else D.hum = firstInt(c); D.humText = v; }
    else if (/^emp/.test(kl)) { D.empText = v; const mx = /max(?:imum)?\s*(\d+)/i.exec(c); if (mx) M.statMax.EMP = M.statMax.EMP || +mx[1]; }
    else if (/luck/.test(kl)) { D.luckText = v; const e = /effective\s*(\d+)|=\s*\**(\d+)/i.exec(c); if (e) D.luck = +(e[1] || e[2]); }
    else if (/^run|^move/.test(kl)) D.run = plain(v);
    else if (/critical/.test(kl)) { D.crit = plain(v); if (/addiction/.test(kl)) D.addict = plain(v); }
    else if (/addiction/.test(kl)) D.addict = plain(v);
    else if (/reputation/.test(kl)) D.rep = firstInt(c);
    else (D.other = D.other || []).push([k, v]);
  }
  function derivedFromProse(M, all) {
    const D = M.derived, g = re => { const m = re.exec(all); return m ? m : null; };
    let m;
    if ((m = g(/\bHP:?\s*(\d+)/))) D.hp = D.hpMax = +m[1];
    if ((m = g(/Seriously Wounded at:?\s*(\d+)/i))) D.sw = +m[1];
    if ((m = g(/Humanity:?\s*~?(\d+)\s*\/\s*(\d+)/i))) { D.hum = +m[1]; D.humMax = +m[2]; }
    if ((m = g(/Death Save:?\s*(?:BODY\s*)?(\d+)/i))) D.ds = +m[1];
  }
  function skillsFromProse(M, s) { // "- **Handgun 12 · Shoulder Arms 10** — …" (bases only)
    for (const l of s.lines) {
      const b = /^\s*[-*]\s+\*\*(.+?)\*\*/.exec(l); if (!b) continue;
      for (const part of b[1].split(/\s*[·/]\s*/)) {
        const m = /^([A-Za-z][A-Za-z &'()\/:—-]*?)\s+(\d+)$/.exec(part.trim());
        if (m && canon(m[1])) addSkill(M, m[1], "", "", m[2], "");
      }
    }
  }
  function canon(name) {
    let n = norm(name.replace(/\((?:x2|×2)\)/gi, ""));
    if (ALIAS[n]) n = norm(ALIAS[n]);
    let best = null;
    for (const s of SKILL_INDEX) if ((n === s.key || n.startsWith(s.key + " ")) && (!best || s.key.length > best.key.length)) best = s;
    if (!best) for (const [a, to] of Object.entries(ALIAS)) if (n.startsWith(a + " ")) { best = SKILL_INDEX.find(s => s.key === norm(to)); break; }
    return best;
  }
  function addSkill(M, rawName, stat, lvl, base, note) {
    // the name cell can carry history in bold parentheses: "Athletics **(Bought 5 → 6 at the Day-109 open, 120)**"
    let name = unstrike(rawName).replace(/\*\*\s*\([^)]*(?:Day|Bought|close|open|corrected|booked|G\d|Shane)[^)]*\)\s*\*\*/gi, "").replace(/\((?:[^()]*\b(?:Day|Bought|close|open|corrected)\b[^()]*)\)/gi, "");
    const hist = (unstrike(rawName).match(/\(([^()]*\b(?:Day|Bought|close|open|corrected)\b[^()]*)\)/gi) || []).join(" ");
    name = plain(name).replace(/\s+/g, " ").trim(); if (!has(name)) return;
    const c = canon(name);
    let variant = "";
    if (c) {
      variant = plain(name).slice(0).replace(new RegExp("^" + c.name.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&"), "i"), "").replace(/^\s*(\(x2\)|×2)?\s*[—:–-]?\s*/i, "").replace(/^\((.*)\)$/, "$1").trim();
      if (!variant && /^streetslang$/i.test(name)) variant = "Streetslang";
    }
    const st = plain(stat).split(/\s+/)[0].toUpperCase();
    M.skills.push({ raw: name, key: c ? c.key : norm(name), name: c ? c.name : name, group: c ? c.g : "Other", multi: c ? c.multi : 0, x2: c ? c.x2 : false,
      variant, stat: STATS.includes(st) ? st : (c ? c.stat : ""), lvl: firstInt(lvl), base: firstInt(base), note: [hist, note].filter(x => has(plain(x))).join(" · ") });
  }
  function weapon(head, r) {
    const g = re => { const i = col(head, re); return i >= 0 ? r[i] || "" : ""; };
    const extra = head.map((h, i) => [plain(h), r[i]]).filter(([h]) => !/^(weapon|dmg|damage|ammo|rof|notes?)$/i.test(h) && h).filter(([, v]) => has(plain(v))).map(([h, v]) => h + ": " + plain(v));
    return { name: g(/^weapon/), dmg: plain(g(/^(dmg|damage)/)), ammo: plain(g(/^ammo/)), rof: plain(g(/^rof/)), notes: [extra.join(" · "), g(/^notes?/)].filter(has).join(" · ") };
  }
  /* ---------------- cyberware (CR p. 358–366) ---------------- */
  // [pattern, slot or group, foundational?]; eye/arm/leg resolve to a side from the text
  const CAT = [
    [/neural link/i, "Neural Link", 1], [/interface plugs?|wrist plugs/i, "Neural Link", 0], [/chipware socket/i, "Neural Link", 0],
    [/kerenzikov|sandevistan|braindance recorder|pain editor|skill ?chip|memory chip|olfactory boost|tactile boost|chemical analy[sz]er/i, "Neural Link", 0],
    [/cyberaudio suite|audio suite|cyberaudio/i, "Cyberaudio Suite", 1],
    [/internal agent|audio recorder|bug detector|level damper|radio communicator|amplified hearing|homing tracer|radio scanner|music player|radar detector|scrambler|voice stress/i, "Cyberaudio Suite", 0],
    [/cybereyes?|kiroshis?/i, "eye", 1],
    [/low[- ]?light|infrared|\buv\b|teleoptics|microoptics|microvideo|chyron|virtuality|colou?r shift|anti-dazzle|image enhance|targeting scope|radiation detector|dartgun/i, "eye", 0],
    [/cyberarms?/i, "arm", 1],
    [/grapple hand|popup|realskinn|tool hand|big knucks|rippers|scratchers|wolvers|slice 'n dice|quick change mount|superchrome|medscanner|techscanner/i, "arm", 0],
    [/cyberlegs?/i, "leg", 1], [/grip foot|jump booster|skate foot|talon foot|web foot/i, "leg", 0],
    [/biomonitor|chemskin|emp threading|light tattoo|shift tacts|skinwatch|techhair/i, "Fashionware", 1],
    [/nasal filters?|toxin binders?|enhanced antibodies|contraceptive implant|cybersnake|\bgills\b|grafted muscle|independent air|midnight lady|mr\.? studd|radar\/sonar|vampyres|audiovox/i, "Internal Cyberware", 1],
    [/hidden holster|skin ?weave|subdermal (armor|pocket|grip)|reinforced knuckles/i, "External Cyberware", 1],
    [/linear frame|artificial shoulder|multioptic mount|sensor array|borgware/i, "Borgware", 1]
  ].map(([re, slot, f]) => ({ re, slot, f: !!f, label: s => plain(s).replace(/^[··—–-]\s*/, "").trim() }));
  function catOf(s) { const p = plain(s).replace(/\([^)]*\)/g, " "); return CAT.find(c => c.re.test(p)) || null; }
  const baseName = (c, name) => SIDED[c.slot] && c.f ? SIDED[c.slot] : plain(name).replace(/^[·\u00b7—–-]\s*/, "").replace(/\s*\([^)]*\)/g, "").replace(/,\s*(left|right)\b.*$/i, "").trim();
  const parens = name => (plain(name).match(/\([^)]*\)/g) || []).join(" ");
  // a table's Notes cell often lists the options: "Low-Light / Infrared / UV · TeleOptics · one slot free"
  function splitOptions(c, notes) {
    const opts = [], left = [];
    for (const seg of plain(notes).split(/\s+·\s+/)) {
      const o = catOf(seg);
      if (o && !o.f && o.slot === c.slot) { const nm = seg.split(/\s*(?:\.\s|\s—\s|\()/)[0].trim(); opts.push({ c: o, name: nm, data: seg.slice(nm.length).replace(/^[\s.—–-]+/, "").replace(/^\((.*)\)$/, "$1") }); }
      else if (has(seg)) left.push(seg);
    }
    return { opts, left: left.join(" · ") };
  }
  function piece2side(s) { const l = plain(s).toLowerCase(); return /\bpaired\b|\bboth\b|cybereyes|kiroshis/.test(l) ? "both" : /\bleft\b/.test(l) ? "Left" : /\bright\b/.test(l) ? "Right" : ""; }
  const SIDED = { eye: "Cybereye", arm: "Cyberarm", leg: "Cyberleg" };
  function cyberCount(M) { return Object.values(M.cyber).reduce((a, l) => a + l.length, 0); }
  // put one item in its slot(s); ctx remembers the last foundational slots per group so options attach to them
  function placeCyber(M, c, name, side, data, ctx) {
    let slots;
    if (SIDED[c.slot]) {
      if (c.f || !ctx[c.slot]) {
        const base = SIDED[c.slot];
        slots = side === "both" ? ["Right " + base, "Left " + base] : side ? [side + " " + base] : [base + " (side not on the sheet)"];
        if (c.f) ctx[c.slot] = slots;
      } else slots = ctx[c.slot];
    } else slots = [c.slot];
    for (const s of slots) (M.cyber[s] = M.cyber[s] || []).push({ name, data, opt: !c.f });
  }
  const NOT_IN = /not installed|declined|not asked|not this week|eventually|scheduled|deferred|offered|pending/i;
  function cyberLines(M, lines, where) { // bullet lists (nested bullets add to the item above)
    const ctx = {}; let last = null, lastIndent = -1; const left = [];
    for (const raw of lines) {
      const b = /^(\s*)[-*+]\s+(.*)$/.exec(raw); if (!b) { left.push(raw); continue; }
      const indent = b[1].length, line = b[2];
      if (last && indent > lastIndent) { last.data = [last.data, plain(line)].filter(has).join(" · "); continue; }
      if (/^\s*(\*\*)?no\s/i.test(line)) { M.cyberStatus.push(plain(line).replace(/[;.]$/, "")); last = null; continue; }
      const segs = [...line.matchAll(/\*\*(.+?)\*\*/g)].map(m => m[1]);
      if (!segs.length || /:\s*$/.test(segs[0]) || /^\*\*[^*]+:\*\*/.test(line.trim())) { left.push(raw); last = null; continue; } // "**Her rule:** …" is a note
      const pieces = []; for (const sg of segs) for (const p of sg.split(/\s+\+\s+/)) { const c = catOf(p); if (c) pieces.push({ c, p }); }
      let rest = plain(segs.length ? line.replace("**" + segs[0] + "**", "") : line).replace(/^[\s,—–:-]+/, "");
      if (/GM's discretion/i.test(line)) rest = "Not settled on the sheet (GM's discretion): " + rest;
      if (NOT_IN.test(line) && !/installed day/i.test(line)) { pieces.forEach(x => M.cyberPending.push({ name: x.c.label(x.p), status: "Not installed", note: plain(line) })); last = null; continue; }
      if (!pieces.length) { (M.cyber["Listed under Cyberware"] = M.cyber["Listed under Cyberware"] || []).push(last = { name: plain(line).split(/[(—,]/)[0].trim(), data: plain(line), opt: false }); lastIndent = indent; continue; }
      const side = piece2side(segs[0] || line) || piece2side(line);
      pieces.forEach((x, k) => placeCyber(M, x.c, baseName(x.c, x.p), side, k ? "" : [parens(x.p), rest].filter(has).join(" · "), ctx));
      const n0 = baseName(pieces[0].c, pieces[0].p);
      const list = M.cyber[Object.keys(M.cyber).find(s => M.cyber[s].some(i => i.name === n0))] || [];
      last = list.find(i => i.name === n0) || null; lastIndent = indent;
    }
    if (where && left.length < lines.length) M.cyberSources.push(where);
    return left;
  }
  function parseCyber(M, secs, used, take) {
    for (const s of secs.filter(s => /CYBER/i.test(s.h))) {
      take(s); const ctx = {};
      for (const t of tables(s)) {
        const c0 = col(t.head, /^(slot|piece|item|cyberware|installed|required)/); if (c0 < 0) continue;
        const cin = col(t.head, /^installed/), cst = col(t.head, /^status/), chl = col(t.head, /^hl$/), cno = col(t.head, /^(notes?|where|data)/);
        for (const r of t.rows) {
          const name = plain(r[c0]); if (!has(name) || /^total$/i.test(name)) continue;
          const inst = cin >= 0 && cin !== c0 ? plain(r[cin]) : "";
          const extra = [chl >= 0 ? "HL " + plain(r[chl]) : "", cno >= 0 ? plain(r[cno]) : ""].filter(has).join(" · ");
          const status = cst >= 0 ? plain(r[cst]) : "";
          if (/^everything else/i.test(name)) { M.cyberStatus.push(`Everything else: ${[inst, extra].filter(has).join(" — ")}`); continue; }
          if (/^(natural|no|none)\b/i.test(inst)) { M.cyberStatus.push(`${name}: ${[inst, extra].filter(has).join(" — ")}`); continue; }
          if ((status && NOT_IN.test(status)) || /^optional/i.test(name)) {
            const full = r.filter((_, i) => i !== c0).map(plain).filter(has).join(" · ");
            for (const p of name.replace(/^optional[^—–-]*[—–-]\s*/i, "").split(/\s+\+\s+/)) M.cyberPending.push({ name: plain(p).replace(/\(.*$/, "").trim(), status: status || "Optional", note: full });
            continue;
          }
          const c = catOf(name);
          if (!c) { (M.cyber["Listed under Cyberware"] = M.cyber["Listed under Cyberware"] || []).push({ name, data: [inst, extra].filter(has).join(" · "), opt: false }); continue; }
          const isOpt = /^[·\u00b7—–-]/.test(name.trim()) || !c.f;
          const cc = isOpt && c.f ? Object.assign({}, c, { f: false }) : c;
          const notes = cno >= 0 ? plain(r[cno]) : "";
          const sp = !isOpt && notes ? splitOptions(c, notes) : { opts: [], left: notes };
          const data = [parens(name), inst && !/^yes$/i.test(inst) ? inst : "", chl >= 0 ? "HL " + plain(r[chl]) : "", sp.left].filter(has).join(" · ");
          const prevSlots = ctx[c.slot];
          placeCyber(M, cc, baseName(cc, name), piece2side(name) || piece2side(inst), data, ctx);
          sp.opts.forEach(o => placeCyber(M, o.c, o.name, "", o.data, ctx));
          // "as above": the other eye's options again
          if (/^as above/i.test(notes) && prevSlots && ctx[c.slot] !== prevSlots) {
            const src = (M.cyber[prevSlots[0]] || []).filter(i => i.opt);
            for (const sl of ctx[c.slot]) { const list = M.cyber[sl]; const f = list[list.length - 1]; f.data = f.data.replace(/(^| · )as above$/i, "").trim() || "as above"; src.forEach(i => list.push(Object.assign({}, i))); }
          }
        }
      }
      const prose = s.lines.filter(l => !/^\s*\|/.test(l));
      const left = cyberLines(M, prose, "");
      for (const l of left) if (/^\s*\*\*(NONE|Not established|No cyberware)/i.test(l)) M.cyberStatus.push(plain(l));
      const rest = left.filter(l => !/^\s*\*\*(NONE|Not established|No cyberware)/i.test(l)).join("\n").trim();
      if (rest) M.cyberText += (M.cyberText ? "\n\n" : "") + rest;
    }
  }

  /* ---------------- flatten + diff (for history) ---------------- */
  function flatten(M) {
    const F = {};
    const put = (k, v) => { if (v != null && String(v).trim() !== "") F[k] = String(v); };
    STATS.forEach(k => { put("stat." + k, M.stats[k]); put("statmax." + k, M.statMax[k]); });
    const D = M.derived; ["hp", "hpMax", "sw", "ds", "hum", "humMax", "luck", "run", "crit", "addict"].forEach(k => put("der." + k, D[k]));
    M.roles.forEach(r => { put("role." + norm(r.name || r.head) + ".rank", r.rank); });
    M.skills.forEach(s => { const k = "skill." + s.key + (s.variant ? "." + norm(s.variant) : ""); put(k + ".lvl", s.lvl); put(k + ".base", s.base); });
    M.weapons.forEach(w => { const k = "weapon." + norm(plain(w.name)).slice(0, 40); put(k + ".dmg", w.dmg); put(k + ".ammo", w.ammo); put(k + ".rof", w.rof); });
    Object.entries(M.armor).forEach(([loc, a]) => { put("armor." + loc + ".sp", a.sp); put("armor." + loc + ".type", a.type); put("armor." + loc + ".pen", a.pen); });
    put("rep", M.rep); put("ip", M.ip);
    Object.entries(M.cyber).forEach(([slot, list]) => list.forEach(c => put("cyber." + norm(slot) + "." + norm(c.name).slice(0, 40), plain(c.data) || "yes")));
    M.cyberPending.forEach(c => put("cyberpending." + norm(c.name).slice(0, 40), c.status));
    M.cyberStatus.forEach(x => put("cyberstatus." + norm(x).slice(0, 60), x));
    M.gear.forEach(([it, n]) => put("gear." + norm(plain(it)).slice(0, 40), plain(n).slice(0, 200) || "yes"));
    Object.entries(M.lifepath).forEach(([k, v]) => put("life." + norm(k), plain(v)));
    put("lifestyle", M.lifestyle);
    return F;
  }
  const LABEL = k => {
    const p = k.split(".");
    if (p[0] === "stat") return p[1]; if (p[0] === "statmax") return p[1] + " max";
    if (p[0] === "der") return ({ hp: "HP", hpMax: "HP max", sw: "Seriously wounded", ds: "Death save", hum: "Humanity", humMax: "Humanity max", luck: "Luck pool", run: "Run", crit: "Critical injuries", addict: "Addictions" })[p[1]] || p[1];
    if (p[0] === "skill") return titleCase(p.slice(1, -1).join(" · ")) + " " + p[p.length - 1].toUpperCase();
    if (p[0] === "role") return "Role " + titleCase(p[1]) + " rank";
    if (p[0] === "rep") return "Reputation"; if (p[0] === "ip") return "IP";
    return titleCase(p.join(" · "));
  };
  function diff(A, B) { // what changed from older flat map A to newer flat map B
    const out = [];
    for (const k of new Set([...Object.keys(A), ...Object.keys(B)])) if ((A[k] || "") !== (B[k] || "")) out.push({ k, was: A[k], now: B[k], label: LABEL(k) });
    return out.sort((a, b) => a.k.localeCompare(b.k));
  }

  /* ---------------- render ---------------- */
  const K = k => ` data-k="${esc(k)}"`;
  const V = x => has(x) ? esc(x) : "";
  function box(label, inner, cls, k) { return `<div class="rs-box ${cls || ""}"${k ? K(k) : ""}><div class="rs-lab">${label}</div><div class="rs-val">${inner || ""}</div></div>`; }
  function longBox(label, md, cls) { return `<div class="rs-box rs-long ${cls || ""}"><div class="rs-lab">${label}</div><div class="rs-val rs-md">${has(md) ? mdb(md) : ""}</div></div>`; }

  function page1(M) {
    const role = M.identity.find(([k]) => /^role/i.test(k));
    const ra = M.roles[0];
    const ident = M.identity.filter(([k]) => !/^(handle|role)/i.test(k));
    const stat = k => `<div class="rs-stat"${K("stat." + k)}><span>${k}</span><b>${V(M.stats[k])}</b>${M.statMax[k] != null ? `<small${K("statmax." + k)}>max ${esc(M.statMax[k])}</small>` : ""}</div>`;
    // skill grid: the sheet's list, with the sheet's own values; multi rows (Language …) get one row per variant
    const by = {}; M.skills.forEach(s => (by[s.key] = by[s.key] || []).push(s));
    const row = (c, s, label) => {
      const k = "skill." + c.key + (s && s.variant ? "." + norm(s.variant) : "");
      const st = s && s.stat || c.stat, sv = M.stats[st];
      return `<tr class="${s ? "on" : ""}" ${s && has(s.note) ? `title="${esc(plain(s.note)).slice(0, 600)}"` : ""}><th>${label}${c.x2 ? " <em>(x2)</em>" : ""} <small>(${st})</small></th><td${K(k + ".lvl")}>${s ? V(s.lvl) : ""}</td><td class="st">${sv != null ? esc(sv) : ""}</td><td class="bs"${K(k + ".base")}>${s ? V(s.base) : ""}</td></tr>`;
    };
    const groups = SKILLS.map(([g, list]) => `<table class="rs-sk"><thead><tr><th>${g} Skills</th><td>LVL</td><td>STAT</td><td>BASE</td></tr></thead><tbody>${list.map(([name, stat, x2, multi]) => {
      const c = SKILL_INDEX.find(x => x.name === name), got = by[c.key] || [];
      if (!multi) return row(c, got[0], esc(name) + (got[0] && got[0].variant ? ` <span class="rs-var">${esc(got[0].variant)}</span>` : ""));
      const rows = got.map(s => row(c, s, `${esc(name)} <span class="rs-var">${esc(s.variant || "")}</span>`));
      for (let i = got.length; i < multi; i++) rows.push(row(c, null, `${esc(name)} <span class="rs-var">&nbsp;</span>`));
      return rows.join("");
    }).join("")}</tbody></table>`);
    const other = M.skills.filter(s => s.group === "Other");
    if (other.length) groups.push(`<table class="rs-sk"><thead><tr><th>Other (as on the sheet)</th><td>LVL</td><td>STAT</td><td>BASE</td></tr></thead><tbody>${other.map(s => `<tr class="on" title="${esc(plain(s.note)).slice(0, 600)}"><th>${esc(s.raw)} <small>${s.stat ? "(" + s.stat + ")" : ""}</small></th><td${K("skill." + s.key + ".lvl")}>${V(s.lvl)}</td><td class="st">${s.stat && M.stats[s.stat] != null ? M.stats[s.stat] : ""}</td><td class="bs"${K("skill." + s.key + ".base")}>${V(s.base)}</td></tr>`).join("")}</tbody></table>`);
    const D = M.derived;
    const weapons = `<table class="rs-tab"><thead><tr><th>Weapon</th><th>DMG</th><th>Ammo</th><th>ROF</th><th>Notes</th></tr></thead><tbody>${M.weapons.map(w => { const k = "weapon." + norm(plain(w.name)).slice(0, 40); return `<tr><td>${mdi(w.name)}</td><td${K(k + ".dmg")}>${esc(w.dmg)}</td><td${K(k + ".ammo")}>${esc(w.ammo)}</td><td${K(k + ".rof")}>${esc(w.rof)}</td><td class="rs-note">${mdi(w.notes)}</td></tr>`; }).join("") || `<tr><td colspan="5" class="rs-none">No weapons table on the sheet</td></tr>`}</tbody></table>${has(M.weaponsText) ? `<details class="rs-more"><summary>Weapons &amp; armor notes from the sheet</summary><div class="rs-md">${mdb(M.weaponsText)}</div></details>` : ""}`;
    const armor = `<table class="rs-tab rs-armor"><thead><tr><th>Armor</th><th>SP</th><th>Penalty</th></tr></thead><tbody>${["head", "body", "shield"].map(l => { const a = M.armor[l] || {}; return `<tr><th>${titleCase(l)}${has(a.type) ? ` <small>${esc(a.type)}</small>` : ""}</th><td${K("armor." + l + ".sp")}>${V(a.sp)}</td><td${K("armor." + l + ".pen")}>${V(a.pen)}</td></tr>`; }).join("")}</tbody><tfoot><tr><td colspan="3">Penalty applies to REF, DEX &amp; MOVE</td></tr></tfoot></table>${has(M.armorText) ? `<details class="rs-more"><summary>Armor notes from the sheet</summary><div class="rs-md">${mdb(M.armorText)}</div></details>` : ""}`;
    return `<div class="rs-p1">
      <div class="rs-ident">
        ${box("Handle", esc(M.name))}
        ${box("Role", role ? `<span>${mdi(role[1])}</span>` : "")}
        ${M.roles.map((r, i) => box(i ? "Second role" : "Role Ability", `${esc(r.name || r.head)}${r.rank != null ? ` <span class="rs-rank"${K("role." + norm(r.name || r.head) + ".rank")}>Rank ${esc(r.rank)}</span>` : ""}`, "", "")).join("") || box("Role Ability", "")}
        <div class="rs-box rs-long rs-notes"><div class="rs-lab">Notes</div><div class="rs-val"><dl>${ident.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdi(v)}</dd>`).join("")}</dl>${has(M.skillsNote) ? `<div class="rs-md rs-sknote">${mdb(M.skillsNote)}</div>` : ""}</div></div>
        ${box("Humanity", `<b${K("der.hum")}>${V(D.hum)}</b>${D.humMax != null ? ` / <span${K("der.humMax")}>${esc(D.humMax)}</span>` : ""}`, "rs-pair", "")}
      </div>
      <div class="rs-stats">${STATS.map(stat).join("")}${D.luck != null ? `<div class="rs-stat rs-luck"${K("der.luck")}><span>Luck pool</span><b>${esc(D.luck)}</b></div>` : ""}</div>
      <div class="rs-skills">${groups.join("")}</div>
      <div class="rs-health">
        ${box("Hit Points", `<b${K("der.hp")}>${V(D.hp)}</b>${D.hpMax != null ? ` / <span${K("der.hpMax")}>${esc(D.hpMax)}</span>` : ""}`, "rs-pair")}
        ${box("Seriously Wounded", V(D.sw), "", "der.sw")}
        ${box("Death Save", V(D.ds), "", "der.ds")}
        ${box("Critical Injuries", V(D.crit), "", "der.crit")}
        ${box("Addictions", V(D.addict), "", "der.addict")}
        ${D.run ? box("Run / Leap", V(D.run), "", "der.run") : ""}
      </div>
      <div class="rs-weapons"><h4 class="rs-bar">Weapons and Armor</h4>${weapons}${armor}</div>
    </div>`;
  }
  function page2(M) {
    const lp = LIFE.map(([k]) => longBox(k, M.lifepath[k] || "", "rs-lp"));
    return `<div class="rs-p2">
      <div class="rs-col">
        ${longBox("Aliases", M.identity.filter(([k]) => /alias|legal|public|says|full name|^name/i.test(k)).map(([k, v]) => `**${k}:** ${v}`).join("\n\n"))}
        <div class="rs-row2">${box("Improvement Points", `<b${K("ip")}>${V(M.ip)}</b>`)}${box("Reputation", `<b${K("rep")}>${V(M.rep)}</b>`)}</div>
        ${longBox("Reputation Events", M.repText, "rs-scroll")}
        ${has(M.ipText) ? `<details class="rs-more"><summary>Improvement point log</summary><div class="rs-md">${mdb(M.ipText)}</div></details>` : ""}
        <h4 class="rs-bar">Lifepath</h4>
        <div class="rs-lpgrid">${lp.join("")}</div>
        ${M.lifeExtra.length ? `<details class="rs-more"><summary>More lifepath from the sheet (${M.lifeExtra.length})</summary><dl class="rs-dl">${M.lifeExtra.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdi(v)}</dd>`).join("")}</dl></details>` : ""}
        <div class="rs-row2">
          <div class="rs-box rs-long"><div class="rs-lab">Friends</div><div class="rs-val"><ul class="rs-ul">${M.friends.map(([a, b]) => `<li>${a ? `<b>${mdi(a)}</b> — ` : ""}${mdi(b)}</li>`).join("")}</ul></div></div>
          <div class="rs-box rs-long"><div class="rs-lab">Tragic Love Affairs</div><div class="rs-val"><ul class="rs-ul">${M.loves.map(x => `<li>${mdi(x)}</li>`).join("")}</ul></div></div>
        </div>
        <div class="rs-box rs-long"><div class="rs-lab">Enemies</div><div class="rs-val"><table class="rs-tab"><thead><tr><th>Who?</th><th>What caused it?</th><th>What can they throw at you?</th><th>What's gonna happen?</th></tr></thead><tbody>${M.enemies.map(r => `<tr>${r.map(c => `<td>${mdi(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>
      </div>
      <div class="rs-col">
        <table class="rs-tab rs-gear"><thead><tr><th>Gear</th><th>Notes</th></tr></thead><tbody>${M.gear.map(([a, b]) => `<tr${K("gear." + norm(plain(a)).slice(0, 40))}><td>${mdi(a)}</td><td class="rs-note">${mdi(b)}</td></tr>`).join("") || `<tr><td colspan="2" class="rs-none">No gear table on the sheet</td></tr>`}</tbody></table>
        ${has(M.gearText) ? `<details class="rs-more"><summary>Gear notes from the sheet</summary><div class="rs-md">${mdb(M.gearText)}</div></details>` : ""}
        ${longBox("Cash", M.cash, "rs-scroll")}
        ${longBox("Fashion", M.lifepath["Clothing Style"] || "")}
        <div class="rs-row3">${box("Housing", M.housing ? esc(plain(M.housing.split("\n")[0])).slice(0, 160) : "")}${box("Rent", esc(M.rent).slice(0, 160))}${box("Lifestyle", esc(M.lifestyle), "", "lifestyle")}</div>
        ${has(M.housing) ? `<details class="rs-more"><summary>Housing from the sheet</summary><div class="rs-md">${mdb(M.housing)}</div></details>` : ""}
        ${longBox("Role Specific Lifepath", M.roles.map(r => `**${r.head}**\n\n${r.text}`).join("\n\n"), "rs-scroll")}
      </div>
    </div>`;
  }
  function page3(M) {
    const slot = s => {
      const list = M.cyber[s] || [];
      return `<div class="rs-cy ${list.length ? "on" : ""}"><table class="rs-tab"><thead><tr><th>${esc(s)}</th><th>Data</th></tr></thead><tbody>${list.map(c => `<tr${K("cyber." + norm(s) + "." + norm(c.name).slice(0, 40))}><td class="${c.opt ? "rs-opt" : "rs-found"}">${c.opt ? "· " : ""}${esc(c.name)}</td><td class="rs-note">${mdi(c.data)}</td></tr>`).join("") || `<tr><td colspan="2" class="rs-none">—</td></tr>`}</tbody></table></div>`;
    };
    const extra = Object.keys(M.cyber).filter(s => !CYBER_SLOTS.includes(s));
    return `<div class="rs-p3">
      <h4 class="rs-bar">Cyberware</h4>
      ${M.cyberStatus.length ? `<div class="rs-box rs-long"><div class="rs-lab">On the sheet</div><div class="rs-val"><ul class="rs-ul">${M.cyberStatus.map(x => `<li${K("cyberstatus." + norm(x).slice(0, 60))}>${mdi(x)}</li>`).join("")}</ul></div></div>` : ""}
      <div class="rs-cygrid">${CYBER_SLOTS.map(slot).join("")}${extra.map(slot).join("")}</div>
      ${M.cyberPending.length ? `<table class="rs-tab rs-pend"><thead><tr><th>Required · scheduled · offered — not installed</th><th>Status</th><th>From the sheet</th></tr></thead><tbody>${M.cyberPending.map(p => `<tr${K("cyberpending." + norm(p.name).slice(0, 40))}><td>${esc(p.name)}</td><td>${esc(p.status)}</td><td class="rs-note">${mdi(p.note)}</td></tr>`).join("")}</tbody></table>` : ""}
      ${M.cyberSources.length ? `<p class="rs-hint">Also read from: ${esc(M.cyberSources.join("; "))}.</p>` : ""}
      ${has(M.cyberText) ? `<div class="rs-box rs-long"><div class="rs-lab">Cyberware notes from the sheet</div><div class="rs-val rs-md">${mdb(M.cyberText)}</div></div>` : ""}
    </div>`;
  }
  function page4(M) {
    if (!M.more.length) return `<p class="rs-none">Everything on this sheet has a place on pages 1–3.</p>`;
    return `<p class="rs-hint">Sections of the sheet the RED layout has no box for, in the sheet's own order.</p>` +
      M.more.map((s, i) => `<details class="rs-more rs-sec" ${i < 2 ? "open" : ""}><summary>${esc(s.h)}</summary><div class="rs-md">${mdb(s.lines)}</div></details>`).join("");
  }

  /* ---------------- mount (the detail pane) ---------------- */
  // host: { http(method, url), text(id) -> Promise<string>, markText(t, terms) -> [html, n], terms() -> [], fmtSize(n) }
  const STATE = new Map(); // entry id -> { page, ver, cmp }
  async function mount(el, r, host) {
    const st = STATE.get(r.id) || { page: host.terms().length ? "text" : "p1", ver: "cur", cmp: "auto" }; STATE.set(r.id, st);
    el.innerHTML = `<div class="rs"><div class="rs-tools"><nav class="rs-tabs" role="tablist">${[["p1", "1 · Stats & skills"], ["p2", "2 · Lifepath & gear"], ["p3", "3 · Cyberware"], ["p4", "4 · More"], ["text", "Full text"]].map(([k, l]) => `<button type="button" role="tab" data-page="${k}" aria-selected="${st.page === k}">${l}</button>`).join("")}</nav>
      <div class="rs-ver"><label>Version <select data-rs="ver"><option value="cur">Current</option></select></label><label>Mark changes since <select data-rs="cmp"><option value="auto">previous version</option><option value="none">— off —</option></select></label></div></div>
      <div class="rs-changes" hidden></div><div class="rs-page"><p class="eyebrow">Loading the sheet…</p></div></div>`;
    let versions = [];
    try { versions = (await host.http("GET", "/api/sheet-history?depth=0&pagination=false&sort=-createdAt&select[text]=false&select[data]=false&where[entry][equals]=" + encodeURIComponent(r.id))).docs || []; } catch (e) { versions = []; }
    if (!el.isConnected) return;
    const vs = el.querySelector('[data-rs="ver"]'), cs = el.querySelector('[data-rs="cmp"]');
    const lab = v => `${v.label || ("Day " + (v.day ?? "?"))} · filed ${new Date(v.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
    vs.innerHTML = `<option value="cur">Current${versions[0] ? " (" + esc(versions[0].label || "") + ")" : ""}</option>` + versions.slice(1).map(v => `<option value="${esc(v.id)}">${esc(lab(v))}</option>`).join("");
    cs.innerHTML = `<option value="auto">previous version</option><option value="none">— off —</option>` + versions.map(v => `<option value="${esc(v.id)}">${esc(lab(v))}</option>`).join("");
    vs.value = st.ver; if (vs.value !== st.ver) st.ver = vs.value = "cur";
    cs.value = st.cmp; if (cs.value !== st.cmp) st.cmp = cs.value = "auto";
    const cache = new Map();
    const getVer = async id => { if (!cache.has(id)) cache.set(id, (await host.http("GET", "/api/sheet-history/" + encodeURIComponent(id) + "?depth=0")).text || ""); return cache.get(id); };
    async function draw() {
      const page = el.querySelector(".rs-page"), chg = el.querySelector(".rs-changes");
      el.querySelectorAll("[data-page]").forEach(b => b.setAttribute("aria-selected", String(b.dataset.page === st.page)));
      let text, idx;
      try {
        if (st.ver === "cur") { text = await host.text(r.id); idx = 0; }
        else { text = await getVer(st.ver); idx = versions.findIndex(v => String(v.id) === String(st.ver)); }
      } catch (e) { page.innerHTML = `<p class="rs-none">Could not load the sheet: ${esc(e.message || e)}</p>`; return; }
      // compare target: "auto" = the version filed before the one shown
      let older = null, olderLabel = "";
      const target = st.cmp === "auto" ? versions[idx + 1] : st.cmp === "none" ? null : versions.find(v => String(v.id) === String(st.cmp));
      if (target && (st.ver === "cur" ? true : String(target.id) !== String(st.ver))) { try { older = await getVer(target.id); olderLabel = target.label || ("Day " + target.day); } catch (e) { older = null; } }
      if (!el.isConnected) return;
      const M = parse(text);
      if (st.page === "text") {
        const [html, n] = host.markText(text, host.terms());
        page.innerHTML = `<p class="eyebrow">Full text · ${host.fmtSize(text.length)}${host.terms().length ? " · " + n + (n === 1 ? " match" : " matches") : ""}</p><pre class="fulltext">${html}</pre>`;
        const m = page.querySelector("mark"); if (m) m.scrollIntoView({ block: "center" });
      } else page.innerHTML = ({ p1: page1, p2: page2, p3: page3, p4: page4 })[st.page](M);
      // changes
      if (older != null) {
        const d = diff(flatten(parse(older)), flatten(M)), map = new Map(d.map(x => [x.k, x]));
        page.querySelectorAll("[data-k]").forEach(n => { const x = map.get(n.dataset.k); if (x) { n.classList.add("rs-chg"); n.title = `was ${x.was == null ? "(none)" : x.was} · ${olderLabel}`; } });
        chg.hidden = false;
        chg.innerHTML = d.length
          ? `<details><summary><b>${d.length} change${d.length === 1 ? "" : "s"}</b> since ${esc(olderLabel)} — marked on the sheet</summary><ul>${d.slice(0, 200).map(x => `<li><span>${esc(x.label)}</span> ${x.was == null ? "<em>added</em>" : `<del>${esc(String(x.was).slice(0, 120))}</del>`} → ${x.now == null ? "<em>removed</em>" : `<b>${esc(String(x.now).slice(0, 120))}</b>`}</li>`).join("")}</ul></details>`
          : `<span>No sheet changes since ${esc(olderLabel)}.</span>`;
      } else {
        chg.hidden = false;
        chg.innerHTML = versions.length <= 1 && st.cmp !== "none" ? `<span>History starts with ${esc(versions[0] ? versions[0].label : "the next filing")}: earlier versions were not kept. Each day filed from now on adds a version when this sheet changes.</span>` : "";
        if (!chg.innerHTML) chg.hidden = true;
      }
      if (st.ver !== "cur") { const v = versions[idx]; chg.hidden = false; chg.insertAdjacentHTML("afterbegin", `<p class="rs-old">Showing the sheet as filed for <b>${esc(v ? v.label : "")}</b>, not the current one.</p>`); }
    }
    el.querySelector(".rs-tabs").addEventListener("click", e => { const b = e.target.closest("[data-page]"); if (!b) return; st.page = b.dataset.page; draw(); });
    vs.addEventListener("change", () => { st.ver = vs.value; draw(); });
    cs.addEventListener("change", () => { st.cmp = cs.value; draw(); });
    await draw();
  }

  window.RedSheet = { parse, mount, flatten, diff, SKILLS };
})();
