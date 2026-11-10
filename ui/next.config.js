const defaultCache = require("next-pwa/cache");
const withPWA = require("next-pwa")({
  dest: "public",
  skipWaiting: true,
  clientsClaim: true,
  cacheStartUrl: false,
  runtimeCaching: [
    {
      urlPattern: ({ url }) => url.pathname === "/api" || url.pathname.startsWith("/api/"),
      handler: "NetworkOnly",
    },
    {
      urlPattern: ({ request }) => request.mode === "navigate",
      handler: "NetworkFirst",
      options: { cacheName: "autolycus-pages-v2", networkTimeoutSeconds: 3 },
    },
    ...defaultCache,
  ],
});

module.exports = withPWA({
  webpack(config) {
    // Next 13's resolver predates overlapping CSS export patterns in Video.js 10.
    config.resolve.alias["@videojs/react/video/neutral-skin.css$"] = require.resolve("@videojs/react/video/neutral-skin.css");
    return config;
  },
  images: { unoptimized: process.env.AUTOLYCUS_STATIC_EXPORT === "1" },
  reactStrictMode: true,
});
