// FLOOR-SEARCH v1 -- GET /api/entries/search?floor=<floor>&q=<text>&mode=all|phrase
// Owner-only full-text search over Entries.text for one floor. Returns, per matching entry,
// the number of hits and up to 3 snippets, each with the heading or scene stamp it sits under.
import type { PayloadHandler, Where } from 'payload'

const MAX_SNIPS = 3
const PAD = 90
const reEsc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** The nearest markdown heading or `Day N | … | ~hh:mm` scene stamp above a hit. */
function context(text: string, at: number): string {
  const lines = text.slice(Math.max(0, at - 30000), at).split('\n')
  for (let i = lines.length - 1; i >= 0; i--) {
    const l = lines[i].trim()
    const stamp = l.match(/^`(Day \d+[^`]*)`$/)
    if (stamp) {
      const f = stamp[1].split('|').map((x) => x.trim()).filter(Boolean)
      const time = f.find((x) => /^~?\d{1,2}:\d{2}/.test(x)) || f[f.length - 1] || ''
      const place = f.slice(1).find((x) => !/^~?\d{1,2}:\d{2}/.test(x) && !/\d{4}\s*$/.test(x) && !/°[FC]/.test(x) && !/^(Sec|Util)\b/i.test(x)) || ''
      return [time, place].filter(Boolean).join(' · ').slice(0, 90)
    }
    const h = l.match(/^#{1,6}\s+(.+)$/)
    if (h) return h[1].replace(/[*_`]/g, '').trim().slice(0, 90)
  }
  return ''
}

export const entriesSearch: PayloadHandler = async (req) => {
  if (!req.user) {
    return Response.json({ errors: [{ message: 'You are not allowed to perform this action.' }] }, { status: 403 })
  }
  const u = new URL(req.url || '/', 'http://localhost')
  const floor = String(u.searchParams.get('floor') || '')
  const q = String(u.searchParams.get('q') || '').trim().toLowerCase().slice(0, 200)
  const phrase = u.searchParams.get('mode') === 'phrase'
  const terms = phrase ? [q] : q.split(/\s+/).filter((w) => w.length > 1).slice(0, 8)
  if (!floor || q.length < 2 || !terms.length) return Response.json({ docs: [], terms })

  const where: Where = { and: [{ floor: { equals: floor } }, ...terms.map((t) => ({ text: { contains: t } }))] }
  const found = await req.payload.find({
    collection: 'entries', where, pagination: false, limit: 1000, depth: 0,
    select: { text: true }, overrideAccess: false, user: req.user, req,
  })

  const re = new RegExp(terms.map(reEsc).join('|'), 'gi')
  const docs = []
  for (const d of found.docs as Array<{ id: number | string; text?: string | null }>) {
    const t = d.text || ''
    let hits = 0
    const at: number[] = []
    re.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = re.exec(t))) {
      if (!m[0]) { re.lastIndex++; continue }
      hits++
      if (at.length < MAX_SNIPS && (!at.length || m.index - at[at.length - 1] > PAD * 2)) at.push(m.index)
    }
    if (!hits) continue
    const snips = at.map((i) => {
      let a = Math.max(0, i - PAD), b = Math.min(t.length, i + PAD)
      const sa = t.lastIndexOf(' ', i - PAD + 15); if (sa > a) a = sa + 1
      const sb = t.indexOf(' ', i + PAD - 15); if (sb > 0 && sb < b) b = sb
      return { at: i, s: t.slice(a, b).replace(/\s+/g, ' ').trim(), ctx: context(t, i) }
    })
    docs.push({ id: d.id, hits, snips })
  }
  return Response.json({ docs, terms })
}
