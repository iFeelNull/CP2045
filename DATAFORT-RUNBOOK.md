# DATAFORT RUNBOOK — for Claude

How to file each Cyberpunk RED 2045 play day (entries, canon and files) into the NXROOT Datafort on hades, and how to change the site safely. Written for Claude. Follow it as written; when something here conflicts with what you find on the machine, stop and tell the owner instead of improvising.

Version 1.4 · 2026-11-18 · lives in the repo as `~/projects/payload/DATAFORT-RUNBOOK.md` and in the claude.ai Project.

---

## 0. The system at a glance

| What | Where |
|---|---|
| Datafort (5 floors + Canon, full-text search) | http://localhost:8087/ |
| Finance dashboard | http://localhost:8087/finance |
| Payload admin | http://localhost:8087/admin (always `localhost`, not `127.0.0.1`) |
| Project (source of truth, git) | `~/projects/payload` → `git@github-iFeelNull:iFeelNull/CP2045.git` (private) |
| Stack | `~/projects/webstack-payload` (rootless podman-compose), containers `ws-payload-web`, `ws-payload-db` (Postgres 18) |
| Start/stop | `systemctl --user start\|stop\|restart webstack-payload.service` |
| Entries | Postgres table `entries` (floor + JSON `data`) — **not in git** |
| Images / PDFs | `~/projects/payload/media/datafort-images`, `media/datafort-files` — **not in git** |
| Ledger | `~/projects/payload/public/data/ledger.json` (in git), built from each packet's `cp-ref-bank-balances.md`; the old Day-111 workbook ledger is archived as `public/data/ledger-xlsx-day111.json` |
| Property register | `~/projects/payload/data/property-register.md` (in git): every property with owner, status and cost basis; feeds Positions. A packet's own `cp-ref-property-register.md` wins if one ever ships |
| Filing log | `~/datafort-days/FILING-LOG.md` on hades and `claude/datafort-filing-log.md` in the Project: one row per packet filed |
| Tools | `~/projects/payload/tools/`: `packet-to-bundle.py` (packet → bundle), `datafort-sync.py` (bundle → Datafort), `add_canon_floor.py` + `add_fulltext.py` + `add_bank_finance.py` (site patches), `bank-to-ledger.py` (bank sheet → finance dashboard); `parse_ledger.py` is retired (no more workbooks) |
| Backups | `~/backups/` (mode 700): `payload-db-*.dump` (pg_dump -Fc), `payload-pre-*.tar.gz` |
| Logs | `~/system-logs/` |
| Host / user | hades, RHEL 10.2, SELinux Enforcing, user `cerberus` |

Data model, one row per entry: `{ floor, data, owner }`. `floor` is one of `pc npc sheets sourcebooks dlc canon meta`. `data` is free-form JSON whose keys are the field keys in §8. Files are referenced from `data` as `pl:<collection>/<id>/<filename>`.

## 1. Rules (never break these)

1. **This site never leaves the laptop.** No hosting, deploy, domain, tunnel or cloud storage. Only the code goes to the private GitHub repo.
2. **Never type a password, passphrase or API key**, in a terminal or a form. The owner types them. Never print the API key (`cat` it, `echo` it, put it in a URL).
3. **Back up before writing.** `datafort-sync.py --apply` takes a `pg_dump` by itself; for anything else run the backup in §6.1 first.
4. **Dry run first, then go ahead.** Owner's standing instruction (2026-11-17): Claude runs the routine steps itself without asking - dry run, apply, install a package the owner downloaded, commit, push. Still stop and ask on any `[FAIL]`, an unexpected UPDATE/DELETE count, anything irreversible outside the backups, or a change to the stack.
5. **Canon is only what the day's close made canon.** File it from the close documents; never invent, embellish or "fill in". Uncertain → `status: "Rumor"` and say so. GM-only material goes in an NPC's `secrets` field, never in canon `body`.
6. **SELinux:** files copied into `~/projects/payload` from elsewhere arrive with the wrong label and the container gets `EACCES` (HTTP 500). Never `cp -a` or `mv` into the project; after copying, run `chcon -R --reference=$HOME/projects/payload <paths>`.
7. **Customer separation:** lcfrw is a paid customer site. Never touch `~/projects/lcfrw`, `webstack-lcfrw`, its token or its Render service from this runbook.
8. Don't change the stack (`webstack-payload/`), ports, firewalld, or the Payload/Next versions as part of a game day.

## 2. How Claude reaches hades

Claude works in its own cloud workspace. hades is reached only through **Claude in Chrome → Cockpit terminal**:

1. `tabs_context_mcp`; open or reuse the Claude-group tab at **http://localhost:9090/system/terminal** (`http`, not `https`: the cert isn't trusted for localhost).
2. If it shows a login page, **stop and ask the owner to log in**. Cockpit logs out when idle; expect to ask again after long pauses.
3. Click into the terminal, `type` one command line ending in `\n`, `wait`, then `zoom` on the terminal area to read output. Start commands with `clear;` and keep output short (`| tail -20`, `| cut -c1-150`). For long output, write it to a file and read it in pieces.
4. **Files from Claude's workspace → hades:** send with SendUserFile; the owner downloads it in Chrome on hades (lands in `~/Downloads`). Claude cannot push files to the laptop. Verify arrival and size: `ls -l ~/Downloads/<name>` against the size Claude built.
5. Unzip into a **fresh** folder (`rm -rf ~/datafort-days/day-X && mkdir -p …`), never over an old one.

## 3. One-time setup (do once; skip any step already done)

Check what's done:

```bash
clear; cd ~/projects/payload; grep -c 'key: "canon"' public/index.html; grep -c useAPIKey src/collections/Users.ts; grep -c 'String(row.id)' public/index.html; ls -l ~/.config/datafort/api-key tools/datafort-sync.py 2>&1 | cut -c1-90; cd ~
```

### 3.1 Theme v1.1 (fixes: clicking a list entry showed an empty detail pane)

Owner downloads `nxroot-datafort-2045.zip` (v1.1). Then:

```bash
clear; rm -rf ~/Downloads/datafort-theme && mkdir ~/Downloads/datafort-theme && unzip -q ~/Downloads/nxroot-datafort-2045.zip -d ~/Downloads/datafort-theme && cd ~/Downloads/datafort-theme/nxroot-datafort-2045 && ./install-datafort-theme.sh 2>&1 | tee ~/system-logs/install-datafort-theme-$(date +%Y%m%d-%H%M).log | tail -25; cd ~
```

It backs up, copies the overlay (incl. `tools/` and this runbook), fixes SELinux labels, restarts and verifies. Re-installing replaces `public/index.html` and `Users.ts`, so **always run 3.2 again after any re-install**.

### 3.2 Canon floor, full text, API keys

```bash
clear; cd ~/projects/payload && python3 tools/add_canon_floor.py . && python3 tools/add_fulltext.py . && chcon -R --reference=. public src/collections && systemctl --user restart webstack-payload.service; cd ~
```

Both scripts are idempotent (`skip` for anything already there) and must run in this order. `add_canon_floor.py` adds the Canon floor and API keys; `add_fulltext.py` adds the server-side full text (`Entries.text`, up to 5,000,000 characters, kept out of list loads, fetched when an entry is opened, searched in Postgres), makes form saves merge instead of replace, and adds the packet categories (Campaign state, Architecture, Vehicle, Arc, Board, Master list, Financial…; canon kind "Day log"). Payload's dev push adds the columns on restart (non-destructive). Wait ~1 minute: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8087/admin` → `200`.

### 3.3 API key for scripted uploads (owner does the secret parts)

1. **Owner:** http://localhost:8087/admin → Users → their account → tick **Enable API Key** → copy the key → **Save**.
2. **Owner, in the terminal.** Claude may type this line; it prompts silently, the owner pastes the key and presses Enter. Nothing is echoed, so the key never appears on screen or in a screenshot. (Never use `cat >` for this: it echoes the paste.) The owner must never paste the key into chat; if that happens, untick/re-tick **Enable API Key** + Save to replace it, then repeat this step.
   ```bash
   install -d -m 700 ~/.config/datafort && ( umask 077; read -rsp 'Paste API key (hidden), then Enter: ' k && printf '%s' "$k" > ~/.config/datafort/api-key; unset k; echo; stat -c 'saved perm=%a size=%s' ~/.config/datafort/api-key )
   ```
3. **Claude** checks without revealing it:
   ```bash
   clear; stat -c '%a %s' ~/.config/datafort/api-key; curl -s -H "Authorization: users API-Key $(cat ~/.config/datafort/api-key)" http://localhost:8087/api/users/me | grep -o '"email":"[^"]*"'
   ```
   Expect `600` and the owner's email. Entries filed with the key belong to that user, exactly as if they'd typed them.

### 3.4 Git (if not done yet)

`setup-payload-git.sh --user iFeelNull --repo CP2045 --email <owner's noreply address>` — the owner types the SSH key passphrase and adds the public key at github.com/settings/ssh/new (signed in as iFeelNull). The script refuses to push over a non-empty remote; if it says so, stop and ask.

## 4. Every game day

Run this **after** the day is closed with `cp-close-day` and the packet for the next day exists (`<X>.zip`, X = the day it opens; it holds `cp-campaign-state-day-[X−1].md` and every `canon/day-*.md` up to X−1). The whole packet is filed every time; `datafort-sync.py` matches each entry and only writes what changed, so a game day typically creates the new day's canon parts and updates the state, the boards and the NPCs that moved.

### 4.1 Get the packet onto hades

The owner downloads `<X>.zip` (Drive `zips/`, or the zip attached in chat) in Chrome on hades → `~/Downloads/<X>.zip`. Check: `clear; ls -l ~/Downloads/<X>.zip`.

### 4.2 Build the bundle from the packet (on hades)

```bash
clear; X=121; D=~/datafort-days/$X; rm -rf $D && mkdir -p $D/packet && unzip -q ~/Downloads/$X.zip -d $D/packet && python3 ~/projects/payload/tools/packet-to-bundle.py $D/packet $D/bundle
```

`packet-to-bundle.py` maps the packet (it prints the counts and the sealed files it skipped):

| Packet | Datafort |
|---|---|
| `canon/day-*.md` (via the canon-index FILE REGISTER) | Canon: "Day 120 · part 2", kind Day log, date, full text |
| `cp-ref-npc-master-list.md` §A (NPCs in play) | NPCs: one per row (status, role, look, chrome, days, voice in Notes); `npc-<name>.md` becomes that NPC's full text |
| `pc-*.md` | PCs: the sheet as full text |
| `cp-ref-*`, `cp-arc-*`, `cp-homebrew-*`, the state, kickoff, `CHARACTER-SHEETS.md`, deck sheet, `canon-index.md` | Reference sheets: category by kind (Financial = bank balances, WSE, portfolio, dividends, Whitehat mechanics), manifest description, full text; matched on the file name (the state as "live board") |
| manifest §4 source layer | Sourcebooks (rules/, world/) and DLCs (dlc/, homebrew/, errata) as catalogue rows; the files stay in Drive/Project |
| campaign name, last closed day | campaign header |
| **never**: `gm-arc-*` (sealed, GM-only), engine/, scripts/, proof files, name pools, manifest, close prompt, engine config | — |

If it stops with "two bundle items share …" or "canon-index names …", the packet has a problem: report it, don't edit the packet.

### 4.3 Dry run, then apply

```bash
clear; python3 ~/projects/payload/tools/datafort-sync.py ~/datafort-days/$X/bundle
```

Prints per-floor counts (`CREATE` / `UPDATE` / `SAME`) and up to 40 changed items (`--verbose` for all). A normal game day: a few `CREATE canon:Day …`, `UPDATE` on the live board, boards, bank balances, canon-index and the NPCs who moved. If it looks like a normal day, apply (rule 4):

```bash
clear; python3 ~/projects/payload/tools/datafort-sync.py ~/datafort-days/$X/bundle --apply 2>&1 | tee ~/system-logs/datafort-day-$X-$(date +%H%M).log | tail -12
```

It takes `~/backups/payload-db-pre-sync-day*.dump` first. The first full import (Days 1–120, 886 entries, ~51 MB of text) took ~15 s in testing. Re-running is safe.

**Extras the packet doesn't carry** (handout PDFs, portraits, a canon fact the owner wants as its own entry): build a small bundle by hand (§7) in Claude's workspace, send it, and sync it the same way. Never put sealed `gm-arc` content in it.

### 4.4 Finance dashboard (every game day, from the same packet)

There is no `.xlsx` any more: the bank balances come in the packet as `cp-ref-bank-balances.md`. The model it records: every company keeps an **opex account**; at 00:00 every night everything outside the opex float is **swept into SI Main**. So SI TOTAL = SI Main + all opex accounts, and SI Main(day N) = SI Main(N−1) + the sweep listed under day N + day N's SI Main debits. `bank-to-ledger.py` checks both identities for every day and refuses to write if either fails.

```bash
clear; python3 ~/projects/payload/tools/bank-to-ledger.py ~/datafort-days/$X/packet --packet $X
```

Dry run: prints the days in the sheet, how many days the ledger now holds (history accumulates; each packet's sheet only covers the last few days, and days already stored are kept), the line count and `checks N, failing 0`. Then:

```bash
clear; python3 ~/projects/payload/tools/bank-to-ledger.py ~/datafort-days/$X/packet --packet $X --apply; ls -Z ~/projects/payload/public/data/ledger.json | cut -c1-70
```

It backs up the old file to `~/backups/ledger-pre-day*.json`, relabels the new one (must read `container_file_t:s0:c369,c692`) and swaps it in. `[OK] no change` on a re-run is normal. **Any `[FAIL]` line = the sheet doesn't reconcile:** report the day and the difference it prints to the owner and stop; never edit the sheet or the ledger by hand. The Datafort still gets the sheet itself (Reference sheets → Bank balances) through §4.3.

**What the page shows.** A **liquid cash** band on every page (SI TOTAL, SI Main, opex, change on the day, tonight's sweep) that the slicers never touch. **Positions** is the portfolio: allocation (cash / equities / notes presenting / Hakk's Orbital Air / property at cost), equities by issuer, property by owner, cash by entity, and a holdings table with % of issuer, % of class and % of all. Stocks and notes come from the packet's `cp-ref-si-portfolio.md` (§1 equity, §2 lines STILL PRESENTING, §9 Orbital Air); the tool checks the equity lines add to the register's EQUITY AT MARKET row and refuses to write if not. Rocklin's Class B is shown as indicative, outside every total, as the register carries it. Prices are marks, not cash.

**Keeping the property register current.** After a close that deeds, sells or prices a property (the day's bank debits and the place's row in `cp-ref-places-master-list.md` say so), edit the matching row in `data/property-register.md` — `Owned` with the recorded price; `Committed` for won or accepted but not deeded; `Verify` when the page is ambiguous (tell the owner); `—` when owned with no price on the page. Never invent a price. Then re-run the dry run above; the summary line prints the owned total.

How lines are built: each SI Main debit is one outflow line (category by keyword; `capex` in the memo → Capital flow); each nightly sweep is an Intra-group inflow to SI Main; each day-over-day change in an opex balance is one line on that company (the sheet has no detail behind it). Positions are the latest day's balances. New companies in a later sheet get an account automatically; add them to `KNOWN` in the tool for a nicer code.

### 4.5 Verify

- Browser: http://localhost:8087/ → Canon floor → search for a new title and one body phrase; open one entry and its PDF. `/finance` shows the new day in the rail (D-number) and `N checks · all reconcile` under the ledger table.
- Terminal: `clear; podman logs --since 10m ws-payload-web 2>&1 | grep -iE 'error|EACCES' | tail -5` → nothing.

### 4.6 Commit (code and ledger only; entries live in Postgres)

```bash
clear; cd ~/projects/payload && git status --short | head -20 && git add -A && git commit -q -m "Day X close: ledger + site changes" && git push 2>&1 | tail -3; cd ~
```

Skip if `git status` is empty. The GitHub key has no passphrase (owner's choice, 2026-11-17), so the push runs unattended; use `timeout 60 git -c core.sshCommand='ssh -o BatchMode=yes' push origin main` so it fails fast instead of hanging if that ever changes. Never leave a command waiting at a prompt: the next line typed goes into it.

### 4.7 Log the day and report

Append the packet's row to the filing log on hades and in the Project (§0):

```bash
clear; echo "| $X | $((X-1)) | $(date '+%F %H:%M') | <canon> | <npc> | <pc> | <sheets> | <sourcebooks> | <dlc> | <created/updated/same; finance Day N> | <backup file> |" >> ~/datafort-days/FILING-LOG.md; tail -3 ~/datafort-days/FILING-LOG.md
```

Then `project_read` → add the same row → `project_write` `claude/datafort-filing-log.md`. Tell the owner: items created/updated/same, the backup file, finance result, anything skipped and why. Keep the bundle zip; the owner files it with the day's packet in Drive.

## 5. Recover

- **Undo a sync:** `podman exec -i ws-payload-db pg_restore -U payload -d payload --clean --if-exists < ~/backups/payload-db-pre-sync-dayX-<ts>.dump` (owner's go first; it rolls back everything after that backup).
- **Undo a theme install:** `tar -xzf ~/backups/payload-pre-datafort-<ts>.tar.gz -C ~/projects/payload`, then §3.2 if canon was added, then restart.
- Uploaded files aren't in the dump; a restore can leave orphan files in `media/` (harmless).

## 6. Modifying the site

### 6.1 Ground rules

1. Backup first:
   ```bash
   clear; cd ~/projects/payload && TS=$(date +%Y%m%d-%H%M%S) && tar -czf ~/backups/payload-src-$TS.tar.gz src public next.config.ts tools && podman exec ws-payload-db pg_dump -U payload -Fc payload > ~/backups/payload-db-$TS.dump && chmod 600 ~/backups/*-$TS.*; ls -l ~/backups/*-$TS.*; cd ~
   ```
2. Edit in `~/projects/payload` only. Prefer a small, idempotent Python patch script (like `tools/add_canon_floor.py`: exact-anchor replace, assert the anchor occurs once, skip if already applied) over hand edits through the terminal. Build and test it in Claude's workspace against a copy of the same files first.
3. After writing files: `chcon -R --reference=. <changed paths>`.
4. What reloads by itself: `public/*` (refresh the browser) and most of `src/` (hot reload). What needs `systemctl --user restart webstack-payload.service`: `next.config.ts`, `payload.config.ts`, new or changed collections and access rules, `Users.ts`.
5. Schema: Payload dev mode **pushes** the schema to Postgres on start. Adding fields, collections or select options is safe. **Renaming or removing a field or option drops its column/data** — back up, and confirm with the owner. Datafort entry fields live inside the JSON `data` column, so page-only fields (§6.3) need no schema change at all.
6. Verify (§4.5), then commit (§4.6).

### 6.2 Where things live

| To change | Edit |
|---|---|
| A floor's fields, labels, search, list text | `public/index.html` → `const FLOORS = [...]` (one object per floor) |
| How an entry reads in the detail pane | `public/index.html` → `const READ = { <floor>(f, r) {...} }` — **every floor needs one** |
| Badge colours for status values | `public/index.html` → `const TONE` (`ok` / `warn` / `bad` / `dim`) |
| Search | `matches()` searches primary field, sub-line, `name`, badge, code, the floor's optional `search: r => [...]` list, plus `FT` (server-side `where[text][like]` on floors with full text; Payload's like = every word, any order, case-insensitive) |
| Full text (large) | `Entries.text` (≤ 5,000,000 chars) + `textLength`; page: `loadText()` / `markText()`; list loads use `select[text]=false` — never load text in lists |
| Data access (save, load, uploads) | `public/index.html` → `const API` (Payload REST, same origin, cookie) |
| Allowed `floor` values | `src/collections/Entries.ts` → `floor` options (must include every `FLOORS[].key` + `meta`) |
| Who can see/change what | `src/collections/datafortAccess.ts` (owner-only) |
| Upload types / folders | `src/collections/DatafortUploads.ts` (`mimeTypes`, `staticDir`) |
| Upload size limit | `src/payload.config.ts` `upload.limits.fileSize` **and** `public/config.js` `maxFileMB` (keep equal) |
| Port / cookie origins | `src/payload.config.ts` `csrf` (or env `SITE_ORIGINS`) |
| URLs, security headers | `next.config.ts` (`rewrites`, `headers`); keep `connect-src 'self'` |
| Sync tool floors / match keys | `tools/datafort-sync.py` → `FLOORS` dict |

### 6.3 Worked example: the searchable Canon floor

`tools/add_canon_floor.py` is the reference implementation. What it does, in order (all five are needed for any new floor):

1. **Payload** — `Entries.ts`, allow the new floor value:
   ```ts
   { label: 'Canon', value: 'canon' },
   ```
2. **Floor definition** — append to `FLOORS` in `index.html`:
   ```js
   { key: "canon", code: "CAN", title: "Canon", short: "Canon", noun: "canon entry", newLabel: "Add canon", ph: "Search canon (full text)",
     desc: "What is true in this campaign …", empty: ["No canon filed", "…"],
     primary: "title",
     sub: r => [r.kind, r.day && "Day " + r.day], badge: r => r.status,
     chips: r => [r.kind, r.day && "Day " + r.day, r.when, ...String(r.tags || "").split(",").map(t => t.trim()).filter(Boolean)],
     search: r => [r.summary, r.body, r.tags, r.when, r.source, r.day && "day " + r.day],   // full-text search
     fields: [ { k: "title", label: "Title", type: "text", req: true }, { k: "kind", type: "select", opts: [...] , label: "Kind" }, … ] }
   ```
   Field types available: `text`, `url`, `select` (+`opts`), `textarea` (+`rows`, `mono`), `image`, `file`, `meter` (stores `k` and `kMax`), `stats`.
3. **Search** — `matches()` adds the floor's `search(r)` values to what it searches:
   ```js
   const hay = [r[f.primary], ...(f.sub(r) || []), r.name, f.badge(r), code(f, r), ...((f.search && f.search(r)) || [])]…
   ```
4. **Detail renderer** — add `READ.canon(f, r)` built from the helpers `headHTML`, `readouts`, `blockHTML`, `fileHTML`. Without it, opening an entry throws and the pane stays empty.
5. **Badge tones** — `TONE`: `Canon: "ok", Rumor: "warn", Retconned: "bad"`.

Plus: `Users.ts` gets `useAPIKey: true` (for §3.3), the ticker's floor count follows `FLOORS.length`, and `tools/datafort-sync.py` already knows `canon` (match key `title`).

### 6.4 Other recipes

- **Add a field to an existing floor:** add `{ k, label, type }` to that floor's `fields`, show it in its `READ` renderer (`readouts([...])` or `blockHTML(...)`), and add it to `search` if it should be searchable. No restart, no schema change.
- **Make another floor full-text searchable:** add `search: r => [r.notes, r.body, …]` to that floor.
- **Add a select option** (e.g. a new NPC status): edit the `opts` list; add a `TONE` entry if it's a badge.
- **Allow another attachment type** (e.g. `.zip` packets): add the MIME type to `DatafortFiles.mimeTypes`, the extension to the `accept=` and the magic-byte check in `API.uploadFile` (index.html), restart.
- **Another whole floor:** copy §6.3 steps 1–5 with a new key; add the key to `datafort-sync.py` `FLOORS` with its match field.
- **Never:** add a CDN script/font, widen `connect-src`, turn off `csrf`, make a collection's `read` public, or bind a port beyond 127.0.0.1.

## 7. `bundle.json` reference

```json
{
  "day": 112,
  "entries": [
    { "floor": "canon",
      "data": { "title": "Hakk buys the SI TEAB stake", "kind": "Event", "status": "Canon", "day": "112",
                "when": "Mon Oct 16, 2045", "tags": "Slipstream, TEAB, Hakk",
                "summary": "…", "body": "…", "source": "cp-day-112-complete.md §3" },
      "files": { "file": "handouts/teab-term-sheet.pdf" } },
    { "floor": "npc", "data": { "handle": "Aster Vale", "disposition": "Wary" },
      "files": { "portrait": "portraits/aster.png" } },
    { "floor": "pc", "data": { "handle": "Rogue", "status": "Injured", "eddies": "12,400" } },
    { "floor": "sheets", "data": { "title": "Day 112 — The Rollover", "category": "Session log", "system": "RED", "body": "…" } },
    { "floor": "meta", "data": { "session": "112" } }
  ]
}
```

- `match` (optional): the field that identifies an existing entry; default `handle` for pc/npc, `title` otherwise; `meta` is a single entry.
- `mode` (optional): `merge` (default, only the given fields change) or `replace`.
- `text` (optional): path to a UTF-8 file stored as the entry's server-side full text (searchable, shown on demand); skipped when unchanged (`data.textSrc` = sha256).
- `files`: `portrait` / `image` / `cover` → images (PNG/JPEG/GIF/WebP ≤ 10 MB); `file` → PDF/EPUB (≤ 100 MB; Payload rejects files that aren't real PDFs/EPUBs).
- The tool adds `seq` and `createdAt` to new entries, `updatedAt` on changes, and `<field>Name`/`<field>Size`/`<field>Src` for files.

## 8. Field keys per floor

| Floor | Key fields (match key first) |
|---|---|
| `pc` | **handle**, name, role, player, system, status (Active/Injured/Flatlined/Retired/MIA), hp/hpMax, hum/humMax, eddies, rep, ip, stats, skills, cyberware, gear, lifepath, notes, portrait |
| `npc` | **handle**, name, affiliation, role, location, threat (Mook/Lieutenant/Mini-Boss/Boss), disposition (Hostile/Wary/Neutral/Friendly/Ally), status (Active/Flatlined/Missing/Unknown), system, stats, abilities, notes, secrets, portrait |
| `sheets` | **title**, category (Rules/Table/Map/Handout/House rule/Session log/Other), system, link, file, image, body |
| `sourcebooks` | **title**, system, publisher, year, pages, format, file, status (Owned/Wishlist/Borrowed), link, notes, cover |
| `dlc` | **title**, type, status (Active/Planned/Disabled), system, appliesTo, released, file, link, notes |
| `canon` | **title**, kind, status (Canon/Rumor/Retconned), day, when, tags, summary, body, source, file |
| `meta` | name, gm, session, system (single entry) |

`system` values: 2020, 2030, RED, 2077, Other. Select values must match exactly (the page shows unknown values as blank).

## 9. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Admin page blank | Opened via `127.0.0.1` without `allowedDevOrigins` → use `http://localhost:8087/admin` |
| `/` or `/finance` HTTP 500, log shows `EACCES` | SELinux label → `chcon -R --reference=$HOME/projects/payload <path>` |
| Clicking a list entry shows an empty detail pane | Theme v1.0 (numeric ids) → install v1.1 (§3.1); or a floor without a `READ` renderer |
| `datafort-sync`: "API key was not accepted" | Key not saved in admin, or file wrong → §3.3 |
| `datafort-sync`: floor 'canon' → HTTP 400 | §3.2 not applied or stack not restarted |
| `datafort-sync`: "matches N existing entries" | Duplicate titles/handles → merge or rename them in /admin first |
| Datafort "Couldn't reach the Payload server" | Stack down → `systemctl --user status webstack-payload.service`, then `start` |
| Cockpit shows Disconnected / login | Idle timeout → owner logs in again |
| Search feels slow (~1 s) | Normal: Postgres scans ~50 MB of text per query. A `pg_trgm` index is the fix if it grows a lot (§6.1 rules apply) |
| Opening an entry shows "Full text · loading…" forever | Stack down or entry deleted → reload; check `podman logs --tail 20 ws-payload-web` |
| `bank-to-ledger.py` `[FAIL] Day N: SI Main … ≠ …` | The close's bank sheet doesn't roll (a missing/duplicated debit or sweep) → report the day and the difference, stop |
| `bank-to-ledger.py` "no SI TOTAL / SI Main row" | The sheet's layout changed → show the owner the block, adapt `parse()` (§6.1 rules) |
| Positions shows no stocks | `cp-ref-si-portfolio.md` missing from the packet, or its §1 heading changed → check `grep -n '^## 1' …/cp-ref-si-portfolio.md` |
| `[FAIL] portfolio: equity lines add to …` | A line or the register's total changed shape → read §1 of the portfolio file, report, stop |
| `/finance` shows old numbers | Browser cache → reload; check `ls -Z public/data/ledger.json` label |

---

## §10 · Character sheets, sheet history and the F02 rule (v1.4, added Day 121 · Nov 18 2026)

**What the site does now**
- **F01 PCs / F02 NPCs open as the official RED character sheet** (`public/sheet.js` + `sheet.css`): tabs *1 · Stats & skills*, *2 · Lifepath & gear*, *3 · Cyberware*, *4 · More* (every sheet section the RED layout has no box for, in the sheet's order) and *Full text*. The sheet is read from the entry's full text (`pc-*.md` / `npc-*.md`). **Nothing is invented:** a box the sheet doesn't fill stays empty; book-block NPCs (Kade, Banerjee, Pulido…) and base-only sheets (Milo, Dov) show what they have.
- **F02 lists only NPCs that have their own `npc-<name>.md`.** Everyone else stays searchable in *Reference sheets → NPC master list*.
- **Sheet history:** the `sheet-history` collection keeps one version of a PC/NPC sheet each time it changes (the Entries `afterChange` hook; bookkeeping keys `updatedAt textSrc asOfDay seq createdAt` don't count). Each version is labelled with the play day it was filed for (`asOfDay`, from the bundle's last closed day); a second change on the same day is labelled "revised". **History starts at Day 120 (packet 121)** — nothing earlier was kept.
- On the sheet: **Version** shows an older filing; **Mark changes since** outlines every changed cell (hover: "was …") and lists the changes at the top. Default: against the version before the one shown.

**Every game day (replaces the sync line in §4)**
```bash
python3 tools/packet-to-bundle.py ~/datafort-days/<X>/packet ~/datafort-days/<X>/bundle
python3 tools/datafort-sync.py ~/datafort-days/<X>/bundle --prune npc            # dry run: NPC deletes show as DELETE
python3 tools/datafort-sync.py ~/datafort-days/<X>/bundle --prune npc --apply    # pg_dump first, then file
```
- `--prune npc` deletes NPC entries the bundle no longer lists (it refuses if the bundle has no NPCs at all). Expect **0 DELETE** on a normal day; a DELETE means an `npc-*.md` left the packet, so check with Shane before applying.
- Check after applying: `curl -s -H "Authorization: users API-Key $(cat ~/.config/datafort/api-key)" "http://localhost:8087/api/sheet-history?limit=0" | python3 -c 'import json,sys;print(json.load(sys.stdin)["totalDocs"])'`. The count goes up by the number of sheets that changed that day.
- In the filing-log row, add "sheets changed: N".

**Modifying the sheet view**
- Layout and styles: `public/sheet.js` (`page1`…`page4`) and `public/sheet.css`. Static files reload on refresh; bump `?v=` in `index.html` so browsers drop the cached copy.
- New sheet section → a sheet box: add a `find(/^HEADING/)` block in `parse()` and a box in the page renderer; anything not taken lands on page 4 automatically.
- A new value to track in history: add it to `flatten()` and tag the rendered cell with `K("<key>")`.
- Collection or hook changes (`src/collections/SheetHistory.ts`) need a stack restart.
- Installer: `tools/add_sheet_view.py PROJECT_DIR` (idempotent; re-labels for SELinux).
