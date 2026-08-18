/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  headers: async () => [
    {
      // The artifacts change once a week when the refresh workflow commits.
      // Immutable would be wrong, but a day of browser cache plus a long CDN
      // stale-while-revalidate keeps repeat visits from re-downloading 1.4 MB.
      source: "/data/:file*",
      headers: [
        {
          key: "Cache-Control",
          value: "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
        },
      ],
    },
  ],
};

export default nextConfig;
