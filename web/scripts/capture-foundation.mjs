import { chromium, expect } from "@playwright/test"
import { mkdir, writeFile } from "node:fs/promises"

const out = new URL("../.taste-skill/inspect/foundation/", import.meta.url)
await mkdir(out, { recursive: true })
const browser = await chromium.launch()
const evidence = []
const cases = [
  { name: "empty-desktop", path: "/chat", width: 1440 },
  { name: "context-desktop", path: "/chat/a-place-to-think", width: 1440, action: "context" },
  { name: "context-mobile", path: "/chat/a-place-to-think", width: 390, action: "context" },
  { name: "project-desktop", path: "/projects/skye-web", width: 1440 },
  { name: "memory-desktop", path: "/library/memory", width: 1440 },
  { name: "memory-mobile", path: "/library/memory", width: 390 },
  { name: "skills-mobile", path: "/library/skills", width: 390 },
  { name: "error-320", path: "/dev/states/failed", width: 320 },
  { name: "chat-dark", path: "/chat/a-place-to-think", width: 1440, dark: true },
  { name: "settings-desktop", path: "/settings/general", width: 1440 },
  { name: "settings-mobile", path: "/settings/general", width: 390 },
  { name: "search-focus", path: "/chat", width: 1440, action: "search" },
  { name: "composer-focus", path: "/chat", width: 1440, focus: "textarea" },
  { name: "resource-search-focus", path: "/library/memory", width: 1440, focus: "#resource-search" },
]
for (const item of cases) {
  const { name, path, width, dark = false, action, focus } = item
  const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: dark ? "dark" : "light", reducedMotion: "reduce" })
  const errors = []
  page.on("pageerror", (error) => errors.push(error.message))
  page.on("console", (msg) => { if (["error", "warning"].includes(msg.type())) errors.push(msg.text()) })
  await page.goto(`http://localhost:3000${path}`)
  await page.locator('[data-hydrated="true"]').waitFor()
  await page.getByRole("heading", { level: 1 }).waitFor()
  await page.evaluate(() => document.fonts.ready)
  if (action === "context") {
    await page.getByRole("button", { name: "Context", exact: true }).click()
    await page.getByRole("heading", { name: "Thread context" }).waitFor()
    if (width < 1200) {
      await page.locator('[data-slot="sheet-content"]:not([data-starting-style])').waitFor()
      await expect(page.getByRole("dialog")).toHaveCSS("opacity", "1")
    }
  }
  if (action === "search") {
    await page.keyboard.press("Control+k")
    await expect(page.getByRole("dialog", { name: "Search" })).toBeVisible()
    await expect(page.getByRole("dialog")).toHaveCSS("opacity", "1")
  }
  if (focus) await page.locator(focus).focus()
  await page.screenshot({ path: new URL(`${name}.png`, out).pathname, fullPage: true, caret: "initial" })
  evidence.push({ name, path, width, dark: Boolean(dark), errors, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) })
  await page.close()
}
await browser.close()
await writeFile(new URL("evidence.json", out), JSON.stringify(evidence, null, 2))
console.log(JSON.stringify(evidence, null, 2))
