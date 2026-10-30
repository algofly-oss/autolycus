const defaultCache = require("next-pwa/cache");
const withPWA = require("next-pwa")({
  dest: "public",
  skipWaiting: true,
  clientsClaim: true,
  runtimeCaching: [
    {
      urlPattern: ({ url }) => url.pathname === "/api" || url.pathname.startsWith("/api/"),
      handler: "NetworkOnly",
    },
    ...defaultCache,
  ],
});

module.exports = withPWA({
  images: { unoptimized: process.env.AUTOLYCUS_STATIC_EXPORT === "1" },
  reactStrictMode: true,
});
