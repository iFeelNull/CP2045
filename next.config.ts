import { withPayload } from '@payloadcms/next/withPayload'
import type { NextConfig } from 'next'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(__filename)

// Security headers for the Datafort pages (moved here from the old
// _headers / .htaccess / nginx files). connect-src is 'self' only: the pages talk
// to this Payload server and nothing else. Not applied to /admin or /api.
const datafortHeaders = [
  {
    key: 'Content-Security-Policy',
    value:
      "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
      "font-src 'self' data:; img-src 'self' data: blob: https:; connect-src 'self'; " +
      "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
  },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'no-referrer' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
  { key: 'X-Robots-Tag', value: 'noindex, nofollow' },
]

const nextConfig: NextConfig = {
  // Next 16 dev blocks its HMR connection for origins other than localhost; the
  // Payload admin renders blank without it. Allow the loopback IP too.
  allowedDevOrigins: ['127.0.0.1'],
  images: {
    localPatterns: [
      {
        pathname: '/api/media/file/**',
      },
    ],
  },
  // The Datafort is plain HTML in public/. Serve it at / and /finance.
  async rewrites() {
    return {
      beforeFiles: [
        { source: '/', destination: '/index.html' },
        { source: '/finance', destination: '/finance.html' },
      ],
      afterFiles: [],
      fallback: [],
    }
  },
  async headers() {
    const pages = ['/', '/index.html', '/finance', '/finance.html', '/config.js', '/data/:path*', '/assets/:path*']
    return [
      ...pages.map((source) => ({ source, headers: datafortHeaders })),
      { source: '/data/:path*', headers: [{ key: 'Cache-Control', value: 'no-cache' }] },
      { source: '/assets/:path*', headers: [{ key: 'Cache-Control', value: 'public, max-age=604800' }] },
    ]
  },
  webpack: (webpackConfig) => {
    webpackConfig.resolve.extensionAlias = {
      '.cjs': ['.cts', '.cjs'],
      '.js': ['.ts', '.tsx', '.js', '.jsx'],
      '.mjs': ['.mts', '.mjs'],
    }

    return webpackConfig
  },
  turbopack: {
    root: path.resolve(dirname),
  },
}

export default withPayload(nextConfig, { devBundleServerPackages: false })
