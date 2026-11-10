// Versioned, same-origin assets; no runtime CDN or server decoder dependency.
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const dest = path.join(root, "public/media-codecs/hevc-1.6.0");
fs.mkdirSync(dest, { recursive: true });
for (const [pkg, file] of [
  ["@hevcjs/mediabunny-plugin", "dist/decode-worker.js"],
  ["@hevcjs/core", "dist/wasm/hevc-decode.js"],
  ["@hevcjs/core", "dist/wasm/hevc-decode.wasm"],
]) fs.copyFileSync(path.join(root, "node_modules", pkg, file), path.join(dest, path.basename(file)));
for (const pkg of ["@hevcjs/core", "@hevcjs/mediabunny-plugin", "mediabunny", "@mediabunny/ac3", "@mediabunny/dts", "@mediabunny/aac-encoder", "@videojs/react"]) {
  const source = path.join(root, "node_modules", pkg);
  const licenseDest = path.join(root, "public/media-codecs/licenses", pkg.replaceAll("/", "-"));
  fs.mkdirSync(licenseDest, { recursive: true });
  if (fs.existsSync(path.join(source, "LICENSE"))) fs.copyFileSync(path.join(source, "LICENSE"), path.join(licenseDest, "LICENSE.txt"));
  if (fs.existsSync(path.join(source, "licenses"))) fs.cpSync(path.join(source, "licenses"), path.join(licenseDest, "third-party"), { recursive: true });
}
