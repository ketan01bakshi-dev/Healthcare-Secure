import type { NextConfig } from "next";

/**
 * Static export for Capacitor native shells.
 * Note: `headers` / rewrites are not supported with `output: "export"`.
 * Microphone permissions are declared in native Capacitor platform config.
 */
const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  reactStrictMode: true,
  poweredByHeader: false,
  trailingSlash: true,
};

export default nextConfig;
