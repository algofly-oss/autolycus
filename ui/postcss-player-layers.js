// Keep the player's native cascade layers separate from Tailwind 3's directives.
module.exports = () => ({
  postcssPlugin: "autolycus-player-layers",
  Once(root) {
    if (!root.source?.input.file?.includes("@videojs")) return;
    root.walkAtRules("layer", rule => {
      rule.params = rule.params.replace(/\b(base|components|utilities)\b/g, "videojs-$1");
    });
  },
});
module.exports.postcss = true;
