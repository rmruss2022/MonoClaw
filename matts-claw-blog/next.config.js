/** @type {import('next').NextConfig} */
const nextConfig = {
  // Let Vercel handle deployment natively - no static export needed
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
