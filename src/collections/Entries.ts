// Datafort entries: one row per PC, NPC, reference sheet, sourcebook or DLC,
// plus one "meta" row for the campaign. Same shape as the old Supabase table
// (floor + free-form JSON `data`), so the page and JSON backups are unchanged.
import type { CollectionConfig } from 'payload'
import { ownerField, ownerOnly, signedIn, stampOwner } from './datafortAccess'
import { snapshotSheet } from './SheetHistory'

export const Entries: CollectionConfig = {
  slug: 'entries',
  labels: { singular: 'Datafort entry', plural: 'Datafort entries' },
  admin: {
    group: 'Datafort',
    defaultColumns: ['floor', 'summary', 'owner', 'updatedAt'],
    useAsTitle: 'summary',
  },
  access: { read: ownerOnly, create: signedIn, update: ownerOnly, delete: ownerOnly },
  hooks: { beforeChange: [stampOwner], afterChange: [snapshotSheet] },
  fields: [
    {
      name: 'floor',
      type: 'select',
      required: true,
      index: true,
      options: [
        { label: 'PCs', value: 'pc' },
        { label: 'NPCs', value: 'npc' },
        { label: 'Reference sheets', value: 'sheets' },
        { label: 'Sourcebooks', value: 'sourcebooks' },
        { label: 'DLCs', value: 'dlc' },
        { label: 'Canon', value: 'canon' },
        { label: 'Campaign (meta)', value: 'meta' },
      ],
    },
    { name: 'data', type: 'json', required: true, defaultValue: {} },
    {
      // Read-only label for the admin list, derived from the JSON (name/title).
      name: 'summary',
      type: 'text',
      admin: { readOnly: true },
      hooks: {
        beforeChange: [
          ({ siblingData }) => {
            const d = (siblingData?.data ?? {}) as Record<string, unknown>
            const pick = [d.handle, d.name, d.title].find((x) => typeof x === 'string' && x.trim())
            return pick ? String(pick).slice(0, 120) : `(${siblingData?.floor ?? 'entry'})`
          },
        ],
      },
    },
    {
      // Long markdown (day files, full sheets). Kept out of list loads (select[text]=false),
      // fetched when an entry is opened, searched server-side with where[text][like].
      name: 'text',
      type: 'textarea',
      maxLength: 5_000_000, // Payload's default cap is 40,000; day files run to ~330,000
      admin: { description: 'Full text (large). Loaded on demand by the Datafort page.' },
    },
    {
      name: 'textLength',
      type: 'number',
      admin: { readOnly: true, position: 'sidebar' },
      hooks: {
        beforeChange: [
          // recompute when text is sent; otherwise keep the stored length (a data-only PATCH must not clear it)
          ({ siblingData, originalDoc }) =>
            typeof siblingData?.text === 'string' ? siblingData.text.length : (originalDoc?.textLength ?? null),
        ],
      },
    },
    ownerField,
  ],
  timestamps: true,
}
