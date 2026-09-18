const backendApiUrl = (process.env.BACKEND_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const isVercel = process.env.VERCEL === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    if (isVercel) {
      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${backendApiUrl}/api/:path*`,
      },
      {
        source: "/backend/:path*",
        destination: `${backendApiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
