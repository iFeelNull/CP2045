"""Add the searchable Canon floor to the Datafort. Usage: python3 add_canon_floor.py <project-dir>
Idempotent: skips any step already applied."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])

def patch(path, old, new, marker):
    s = path.read_text(encoding="utf-8")
    if marker in s:
        print(f"skip  {path.name}: already has {marker!r}"); return
    assert s.count(old) == 1, f"{path}: anchor not found exactly once: {old[:60]!r}"
    path.write_text(s.replace(old, new), encoding="utf-8"); print(f"patch {path.name}")

# 1. Payload: allow floor = 'canon'
patch(P / "src/collections/Entries.ts",
      "        { label: 'Campaign (meta)', value: 'meta' },",
      "        { label: 'Canon', value: 'canon' },\n        { label: 'Campaign (meta)', value: 'meta' },",
      "value: 'canon'")

# 2. Page: the Canon floor definition (after DLCs)
CANON = '''    {
      key: "canon", code: "CAN", title: "Canon", short: "Canon", noun: "canon entry", newLabel: "Add canon", ph: "Search canon (full text)",
      desc: "What is true in this campaign: events, people, places and rulings, as fixed at each day's close.",
      empty: ["No canon filed", "Canon is filed from each play day's close: one entry per fact, event or ruling."],
      primary: "title",
      sub: r => [r.kind, r.day && "Day " + r.day], badge: r => r.status,
      chips: r => [r.kind, r.day && "Day " + r.day, r.when, ...String(r.tags || "").split(",").map(t => t.trim()).filter(Boolean)],
      search: r => [r.summary, r.body, r.tags, r.when, r.source, r.day && "day " + r.day],
      fields: [
        { k: "title", label: "Title", type: "text", req: true, ph: "Short, specific: 'Hakk buys the SI TEAB stake'" },
        { k: "kind", label: "Kind", type: "select", opts: ["Event", "Person", "Place", "Faction", "Item", "Ruling", "Lore", "Thread"] },
        { k: "status", label: "Status", type: "select", opts: ["Canon", "Rumor", "Retconned"] },
        { k: "day", label: "Play day", type: "text", ph: "112" },
        { k: "when", label: "In-game date", type: "text", ph: "Mon Oct 16, 2045" },
        { k: "tags", label: "Tags", type: "text", ph: "comma, separated" },
        { k: "summary", label: "Summary", type: "textarea" },
        { k: "body", label: "Full text", type: "textarea", rows: 14 },
        { k: "source", label: "Source", type: "text", ph: "cp-day-112-complete.md §3" },
        { k: "file", label: "Attached file", type: "file" }
      ]
    }
'''
patch(P / "public/index.html",
      '        { k: "notes", label: "Changes & notes", type: "textarea" }\n      ]\n    }\n  ];',
      '        { k: "notes", label: "Changes & notes", type: "textarea" }\n      ]\n    },\n' + CANON + '  ];',
      'key: "canon"')

# 3. Page: search also looks at a floor's optional search(r) list (full text for Canon)
patch(P / "public/index.html",
      "    const hay = [r[f.primary], ...(f.sub(r) || []), r.name, f.badge(r), code(f, r)].filter(has).join(\" \").toLowerCase();",
      "    const hay = [r[f.primary], ...(f.sub(r) || []), r.name, f.badge(r), code(f, r), ...((f.search && f.search(r)) || [])].filter(has).join(\" \").toLowerCase();",
      "f.search && f.search(r)")

# 3b. Page: how a canon entry reads in the detail pane (every floor needs a READ renderer)
patch(P / "public/index.html",
      "  const READ = {\n",
      "  const READ = {\n"
      "    canon(f, r) {\n"
      "      return headHTML(f, r, { sub: [r.when, r.day && \"Play day \" + r.day].filter(has).join(\" · \")}) +\n"
      "        readouts([[\"Kind\", r.kind], [\"Play day\", r.day], [\"In-game date\", r.when], [\"Tags\", r.tags]]) +\n"
      "        blockHTML(\"Summary\", r.summary) + blockHTML(\"Full text\", r.body) +\n"
      "        fileHTML(r, \"File\") + (has(r.source) ? blockHTML(\"Source\", r.source) : \"\");\n"
      "    },\n",
      "    canon(f, r) {")

# 3c. Page: badge colours for the canon statuses
patch(P / "public/index.html",
      '    Ally: "ok", Friendly: "ok", Neutral: "dim", Wary: "warn", Hostile: "bad"\n  };',
      '    Ally: "ok", Friendly: "ok", Neutral: "dim", Wary: "warn", Hostile: "bad",\n    Canon: "ok", Rumor: "warn", Retconned: "bad"\n  };',
      'Retconned: "bad"')

# 4. cosmetic: floor count in the ticker log
s = (P / "public/index.html").read_text(encoding="utf-8")
s2 = s.replace("Datafort mapped · 5 floors", "Datafort mapped · 6 floors").replace("`Floors 05`", "`Floors ${pad(FLOORS.length)}`")
if s2 != s:
    (P / "public/index.html").write_text(s2, encoding="utf-8"); print("patch ticker text")

# 5. Payload: API keys for the users collection (for scripted uploads)
patch(P / "src/collections/Users.ts",
      "    tokenExpiration: 60 * 60 * 24 * 7,\n",
      "    tokenExpiration: 60 * 60 * 24 * 7,\n    // Lets tools/datafort-sync.py sign in with an API key (header: users API-Key <key>).\n    useAPIKey: true,\n",
      "useAPIKey")
