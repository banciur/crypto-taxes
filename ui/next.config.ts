import type { NextConfig } from "next";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const API_BASE_URL = process.env.CRYPTO_TAXES_API_URL ?? DEFAULT_API_BASE_URL;
const NORMALIZED_API_BASE_URL = API_BASE_URL.endsWith("/")
  ? API_BASE_URL.slice(0, -1)
  : API_BASE_URL;

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/crypto-taxes/:path*",
        destination: `${NORMALIZED_API_BASE_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
