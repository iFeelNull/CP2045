// NXROOT Datafort: settings.
//
// The Datafort now stores everything in the Payload CMS on this machine
// (PostgreSQL + files under the project's media/ folder). There are no keys here
// and nothing is sent anywhere else. Sign in with your Payload account.

window.DATAFORT_CONFIG = {
  // Largest attachment (PDF/EPUB) the page will try to upload, in MB.
  // Keep it equal to upload.limits.fileSize in src/payload.config.ts (100 MB).
  maxFileMB: 100
};
