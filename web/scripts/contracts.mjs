import { spawnSync } from "node:child_process"
import { readFile, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { compile } from "json-schema-to-typescript"

const root = fileURLToPath(new URL("../../", import.meta.url))
const output = new URL("../lib/contracts.generated.ts", import.meta.url)
const schemaOutput = new URL("../lib/contracts.schema.json", import.meta.url)
const exported = spawnSync("uv", ["run", "python", "scripts/export_web_contracts.py"], { cwd: root, encoding: "utf8" })
if (exported.status !== 0) throw new Error(exported.stderr || "Python contract export failed")
const types = await compile(JSON.parse(exported.stdout), "WebContract", {
  bannerComment: "/* Generated from src/skye/web_contracts.py. Run npm run contracts; do not edit. */",
  additionalProperties: false,
  ignoreMinAndMaxItems: true,
  style: { semi: false, singleQuote: false },
})
const schema = JSON.stringify(JSON.parse(exported.stdout), null, 2) + "\n"
if (process.argv.includes("--check")) {
  if (await readFile(output, "utf8") !== types) throw new Error("Contract drift: run npm run contracts")
  if (await readFile(schemaOutput, "utf8") !== schema) throw new Error("Schema drift: run npm run contracts")
  console.log("Python/TypeScript contracts match")
} else {
  await writeFile(output, types)
  await writeFile(schemaOutput, schema)
}
