import type { CollectionConfig } from 'payload'

export const Users: CollectionConfig = {
  slug: 'users',
  admin: {
    useAsTitle: 'email',
  },
  auth: {
    // The Datafort signs in with the same account as /admin. Stay signed in for
    // 7 days instead of Payload's default 2 hours (local-only site).
    tokenExpiration: 60 * 60 * 24 * 7,
    // Lets tools/datafort-sync.py sign in with an API key (header: users API-Key <key>).
    useAPIKey: true,
  },
  fields: [
    // Email added by default
  ],
}
