import { readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = fileURLToPath(new URL("../", import.meta.url));
async function collect(path) {
  const files = [];
  for (const item of await readdir(path, { withFileTypes: true })) {
    const absolute = resolve(path, item.name);
    if (item.isDirectory()) files.push(...await collect(absolute));
    else if (item.name.endsWith(".test.ts")) files.push(absolute);
  }
  return files;
}
const files = [...await collect(resolve(root, "extension/src")), ...await collect(resolve(root, "packages/protocol/src"))];
if (!files.length) throw new Error("No tests found");
const result = spawnSync(process.execPath, ["--import", "tsx", "--test", ...files], { cwd: root, stdio: "inherit" });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
