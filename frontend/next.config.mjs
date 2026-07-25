/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: process.cwd(),
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "/api",
    NEXT_PUBLIC_ALLOW_REGISTRATION: process.env.NEXT_PUBLIC_ALLOW_REGISTRATION || "true",
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://api:8000/:path*",
      },
      {
        source: "/browser/:path*",
        destination: "http://browser-agent:6080/:path*",
      },
    ];
  },
};
export default nextConfig;
