import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import path from 'path'
import { buildConfig } from 'payload'
import { fileURLToPath } from 'url'
import sharp from 'sharp'

import { Users } from './collections/Users'
import { Media } from './collections/Media'
import { Entries } from './collections/Entries'
import { DatafortFiles, DatafortImages } from './collections/DatafortUploads'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)

// Origins allowed to use the sign-in cookie. Without this list Payload accepts
// the cookie from ANY origin, and the other local sites on hades (8081-8085)
// count as the same site to the browser. Override with SITE_ORIGINS (comma list).
const origins = (process.env.SITE_ORIGINS || 'http://localhost:8087,http://127.0.0.1:8087')
  .split(',')
  .map((o) => o.trim())
  .filter(Boolean)

export default buildConfig({
  admin: {
    user: Users.slug,
    importMap: {
      baseDir: path.resolve(dirname),
    },
  },
  collections: [Users, Media, Entries, DatafortImages, DatafortFiles],
  csrf: origins,
  // Largest single upload (PDF/EPUB attachments). Keep public/config.js maxFileMB equal.
  upload: { limits: { fileSize: 100 * 1024 * 1024 } },
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  typescript: {
    outputFile: path.resolve(dirname, 'payload-types.ts'),
  },
  db: postgresAdapter({
    pool: {
      connectionString: process.env.DATABASE_URL || '',
    },
  }),
  sharp,
  telemetry: false,
  plugins: [],
})
