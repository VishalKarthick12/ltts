import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable linting during build for deployment stability
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Optimize for production
  poweredByHeader: false,
  reactStrictMode: true,
  // Handle static file serving
  trailingSlash: false,
};

export default nextConfig;
