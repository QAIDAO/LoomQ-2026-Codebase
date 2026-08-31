import {build} from "esbuild";

await build({
  entryPoints: ["src/quantum-story.js"],
  outfile: "../web/quantum-story.iife.js",
  bundle: true,
  format: "iife",
  platform: "browser",
  target: ["es2020"],
  legalComments: "none",
  sourcemap: false,
  minify: false,
  banner: {js: "/* LoomQ quantum story · generated from starter_kit/webgl/src */"},
});