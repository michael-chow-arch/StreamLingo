import { build } from "esbuild";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve, relative, isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const extension = resolve(root, "extension");
const store = process.argv.includes("--store");
const dist = resolve(root, "dist");
const out = resolve(dist, store ? "store-extension" : "extension");
const bounded = relative(dist, out);
if (!bounded || bounded.startsWith("..") || isAbsolute(bounded)) throw new Error("Unsafe output directory");
// Clean only this bounded build directory so stale development files cannot leak.
await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });

const entries = [
  ["src/background/index.ts", "background.js", "esm"],
  ["src/popup/index.ts", "popup.js", "esm"],
  ["src/offscreen/index.ts", "offscreen.js", "esm"],
  ["src/offscreen/pcm-worklet.ts", "pcm-worklet.js", "iife"],
  ["src/content/index.ts", "content.js", "iife"],
];
await Promise.all(entries.map(([entry, name, format]) => build({
  absWorkingDir: root,
  entryPoints: [resolve(extension, entry)],
  outfile: resolve(out, name),
  bundle: true,
  format,
  platform: "browser",
  target: "chrome116",
  sourcemap: !store,
  legalComments: "eof",
})));
const manifest = JSON.parse(await readFile(resolve(extension, "manifest.json"), "utf8"));
delete manifest.key;
if (!store) manifest.key = JSON.parse(await readFile(resolve(extension, "dev-key.json"), "utf8")).key;
const pkg = JSON.parse(await readFile(resolve(extension, "package.json"), "utf8"));
if (manifest.version !== pkg.version) throw new Error("Manifest and package versions differ");
await writeFile(resolve(out, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
for (const file of ["popup.html", "offscreen.html", "_locales/en/messages.json", "_locales/zh_CN/messages.json",
  ...[16, 32, 48, 128].map(size => `icons/icon${size}.png`)]) {
  await mkdir(resolve(out, file, ".."), { recursive: true });
  await copyFile(resolve(extension, file), resolve(out, file));
}
await copyFile(resolve(extension, "src/popup/popup.css"), resolve(out, "popup.css"));
await copyFile(resolve(root, "THIRD_PARTY_NOTICES.md"), resolve(out, "THIRD_PARTY_NOTICES.md"));
await copyFile(resolve(root, "LICENSE"), resolve(out, "LICENSE"));
await copyFile(resolve(extension, "src/offscreen/LICENSE.apache-2.0.txt"), resolve(out, "LICENSE.apache-2.0.txt"));
await copyFile(resolve(root, "node_modules/zod/LICENSE"), resolve(out, "LICENSE.zod.txt"));
await copyFile(resolve(extension, "src/offscreen/README.md"), resolve(out, "AUDIO_SOURCE_NOTICES.md"));
for (const file of [manifest.background.service_worker, manifest.action.default_popup, "content.js", "pcm-worklet.js"]) {
  await readFile(resolve(out, file));
}
console.log(`${store ? "Store" : "Development"} extension built: ${out}`);
