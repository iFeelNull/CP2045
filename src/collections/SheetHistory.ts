// Sheet history: one row per version of a PC or NPC entry (F01/F02).
// A version is saved by the Entries afterChange hook whenever the sheet text or
// its data changes (bookkeeping keys ignored), so each filed day that changes a
// sheet adds one. History starts the day this was installed (Day 120, packet 121).
// Rows are written only by the hook; nobody can edit one. The owner may delete.
import type { CollectionAfterChangeHook, CollectionConfig } from 'payload'
import { ownerField, ownerOnly } from './datafortAccess'

export const SheetHistory: CollectionConfig = {
  slug: 'sheet-history',
  labels: { singular: 'Sheet version', plural: 'Sheet history' },
  admin: {
    group: 'Datafort',
    useAsTitle: 'label',
    defaultColumns: ['handle', 'label', 'floor', 'createdAt'],
    description: 'Versions of PC and NPC sheets, saved automatically when a sheet changes.',
  },
  access: { read: ownerOnly, create: () => false, update: () => false, delete: ownerOnly },
  fields: [
    { name: 'entry', type: 'number', required: true, index: true, admin: { description: 'Datafort entry id' } },
    { name: 'floor', type: 'text', index: true },
    { name: 'handle', type: 'text' },
    { name: 'day', type: 'number', index: true, admin: { description: 'Play day the sheet was filed for' } },
    { name: 'label', type: 'text' },
    { name: 'data', type: 'json' },
    { name: 'text', type: 'textarea', maxLength: 5_000_000 },
    ownerField,
  ],
  timestamps: true,
}

// keys the filing tools touch on every run; a change in only these is not a new version
const IGNORE = new Set(['updatedAt', 'textSrc', 'asOfDay', 'seq', 'createdAt'])
const sig = (data: unknown, text: unknown) => {
  const d = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
  const o: Record<string, unknown> = {}
  for (const k of Object.keys(d).sort()) if (!IGNORE.has(k)) o[k] = d[k]
  return JSON.stringify(o) + '\u0000' + (typeof text === 'string' ? text : '')
}

export const snapshotSheet: CollectionAfterChangeHook = async ({ doc, req }) => {
  if (doc?.floor !== 'pc' && doc?.floor !== 'npc') return doc
  try {
    const p = req.payload as any
    // the full row (the triggering request may have asked for the text to be left out of its response)
    const full = await p.findByID({ collection: 'entries', id: doc.id, depth: 0, overrideAccess: true, req })
    const text = typeof full.text === 'string' ? full.text : ''
    const last = (await p.find({ collection: 'sheet-history', where: { entry: { equals: Number(doc.id) } }, sort: '-createdAt', limit: 1, depth: 0, overrideAccess: true, req })).docs[0]
    if (last && sig(last.data, last.text) === sig(full.data, text)) return doc
    const data = (full.data || {}) as Record<string, unknown>
    const n = Number(data.asOfDay)
    const day = data.asOfDay != null && data.asOfDay !== '' && Number.isFinite(n) ? n : null
    let label = day != null ? `Day ${day}` : 'Hand edit'
    if (last && day != null && last.day === day) label += ` · revised ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`
    const owner = full.owner && typeof full.owner === 'object' ? full.owner.id : full.owner
    await p.create({
      collection: 'sheet-history', overrideAccess: true, req, depth: 0,
      data: { entry: Number(doc.id), floor: doc.floor, handle: String(data.handle || data.name || ''), day, label, data, text, owner },
    })
  } catch (e) {
    // a failed snapshot must never block filing; it shows in the container log
    req.payload.logger.error({ err: e, msg: `sheet-history: snapshot of entry ${doc?.id} failed` })
  }
  return doc
}
