// Datafort uploads, replacing the two private Supabase buckets.
// Files are stored on hades under <project>/media/ (git-ignored) and served at
// /api/<slug>/file/<filename> only to their owner (Payload checks read access
// on every file request).
import type { CollectionConfig } from 'payload'
import { ownerField, ownerOnly, signedIn, stampOwner } from './datafortAccess'

const base = (slug: string, label: string): Omit<CollectionConfig, 'upload'> => ({
  slug,
  labels: { singular: label, plural: label + 's' },
  admin: { group: 'Datafort', defaultColumns: ['filename', 'filesize', 'owner', 'createdAt'] },
  access: { read: ownerOnly, create: signedIn, update: ownerOnly, delete: ownerOnly },
  hooks: { beforeChange: [stampOwner] },
  fields: [ownerField],
})

/** Portraits, maps and covers (was bucket "datafort", 10 MB limit enforced by the page). */
export const DatafortImages: CollectionConfig = {
  ...base('datafort-images', 'Datafort image'),
  upload: {
    staticDir: 'media/datafort-images',
    mimeTypes: ['image/png', 'image/jpeg', 'image/gif', 'image/webp'],
  },
}

/** Sourcebook PDFs and adventure EPUBs (was bucket "datafort-files"). */
export const DatafortFiles: CollectionConfig = {
  ...base('datafort-files', 'Datafort file'),
  upload: {
    staticDir: 'media/datafort-files',
    mimeTypes: ['application/pdf', 'application/epub+zip'],
  },
}
