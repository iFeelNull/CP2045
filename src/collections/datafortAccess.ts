// Shared owner-only rules for the Datafort collections.
// Same model as the Supabase row-level security it replaces: a signed-in user
// sees, changes and deletes only the rows and files they own; nobody else
// (and no signed-out request) sees anything.
import type { Access, CollectionBeforeChangeHook, Field } from 'payload'

/** Signed in? Then only rows whose owner is you. Signed out? Nothing. */
export const ownerOnly: Access = ({ req: { user } }) =>
  user ? { owner: { equals: user.id } } : false

/** Any signed-in user may create; the hook below stamps them as owner. */
export const signedIn: Access = ({ req: { user } }) => Boolean(user)

/** On create, the owner is always the signed-in user, whatever the request body says. */
export const stampOwner: CollectionBeforeChangeHook = ({ data, operation, req }) => {
  if (operation === 'create' && req.user) data.owner = req.user.id
  return data
}

/** Owner relationship: set by stampOwner, never editable afterwards. */
export const ownerField: Field = {
  name: 'owner',
  type: 'relationship',
  relationTo: 'users',
  required: true,
  index: true,
  access: { update: () => false },              // cannot be reassigned after creation
  admin: { readOnly: true, position: 'sidebar' },
}
