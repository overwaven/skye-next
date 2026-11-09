import { spawn } from "node:child_process"
import { createInterface } from "node:readline"
import { fileURLToPath } from "node:url"
import { randomBytes } from "node:crypto"

const webRoot = fileURLToPath(new URL("../", import.meta.url))
const root = fileURLToPath(new URL("../../", import.meta.url))
const internalToken = randomBytes(32).toString("hex")
const backend = spawn("uv", ["run", "python", "scripts/dev_web.py"], {
  cwd: root,
  env: { ...process.env, SKYE_DEV_INTERNAL_TOKEN: internalToken },
  stdio: ["ignore", "pipe", "inherit"],
})
let next
let closing = false
const stop = () => {
  if (closing) return
  closing = true
  next?.kill("SIGTERM")
  backend.kill("SIGTERM")
}
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, stop)
backend.on("error", (error) => {
  console.error("Cannot start local preview:", error.message)
  process.exitCode = 1
  stop()
})
backend.on("exit", (code) => {
  if (!closing) {
    process.exitCode = code || 1
    stop()
  }
})
createInterface({ input: backend.stdout }).on("line", (line) => {
  if (!line.startsWith("SKYE_DEV_READY ")) return
  const ready = JSON.parse(line.slice("SKYE_DEV_READY ".length))
  console.log(
    "\nSkye local preview · isolated demo database · simulated replies · no paid calls"
  )
  console.log(
    "Demo data persists in web/.dev-data. Ctrl+C stops both servers.\n"
  )
  next = spawn(
    process.execPath,
    [
      fileURLToPath(
        new URL("../node_modules/next/dist/bin/next", import.meta.url)
      ),
      "dev",
      ...process.argv.slice(2),
      "--hostname",
      "localhost",
    ],
    {
      cwd: webRoot,
      stdio: "inherit",
      env: {
        ...process.env,
        SKYE_DEV_PREVIEW: "true",
        SKYE_DEV_SESSION: ready.session,
        SKYE_WEB_ENABLED: "true",
        SKYE_WEB_API_ORIGIN: ready.origin,
        SKYE_WEB_ORIGIN: "https://skye-preview.invalid",
        SKYE_WEB_INTERNAL_TOKEN: internalToken,
      },
    }
  )
  next.on("exit", (code) => {
    process.exitCode = code || 0
    stop()
  })
  next.on("error", (error) => {
    console.error(error.message)
    process.exitCode = 1
    stop()
  })
})
