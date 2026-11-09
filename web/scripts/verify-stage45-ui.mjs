import { chromium, expect } from "@playwright/test"
import { mkdir, readFile, writeFile } from "node:fs/promises"

const token = (await readFile("/tmp/stage45-token", "utf8")).trim()
const out = new URL("../.taste-skill/inspect/stage45/", import.meta.url)
await mkdir(out, { recursive: true })
const browser = await chromium.launch()
const context = await browser.newContext({
  ignoreHTTPSErrors: true,
  viewport: { width: 1440, height: 900 },
  permissions: [],
})
await context.addCookies([
  {
    name: "__Host-skye_session",
    value: token,
    url: "https://localhost:3443",
    secure: true,
    sameSite: "Lax",
  },
])
const page = await context.newPage()
const errors = []
page.on("pageerror", (error) => errors.push(error.message))
page.on("console", (message) => {
  if (["error", "warning"].includes(message.type())) errors.push(message.text())
})
const results = []
const uploadName = `tiny-${Date.now()}.png`
const shot = async (name) => {
  await page.screenshot({
    path: new URL(`${name}.png`, out).pathname,
  })
}

await page.goto("https://localhost:3443/chat")
await page.locator('[data-hydrated="true"]').waitFor()
await expect(page.getByRole("heading", { level: 1 })).toHaveText("New thread")
await shot("new-thread")

await page.getByRole("button", { name: "No project", exact: true }).click()
await page.getByRole("menuitem", { name: "New project" }).click()
await page.getByLabel("Name", { exact: true }).fill("Test project")
await page.getByRole("button", { name: "Choose project icon" }).click()
await page.getByRole("button", { name: "Code", exact: true }).click()
await page.getByRole("button", { name: "Create", exact: true }).click()
await expect(
  page.getByRole("button", { name: /💻 Test project/ })
).toBeVisible()
results.push({ step: "project.created", ok: true })

const composer = page.getByRole("textbox", { name: "Message Skye" })
await composer.fill("What changed today?")
await page.getByRole("button", { name: "Send message", exact: true }).click()
await expect(page).toHaveURL(/\/chat\/[0-9a-f]{32}/)
await expect(page.getByText("Searched the web", { exact: true })).toBeVisible()
await expect(page.getByText("Here is the short answer.", { exact: false })).toBeVisible()
await expect(
  page.getByText("A second committed message.", { exact: false })
).toBeVisible()
await expect(page.getByText("Skye", { exact: true })).toHaveCount(1)
await shot("first-reply")
results.push({ step: "send.text", ok: true, url: page.url() })

await expect(page.getByText("1 tool", { exact: true })).toBeVisible()
await page.getByText("1 tool", { exact: true }).click()
await expect(page.getByText("Searched the web", { exact: true })).toBeVisible()
results.push({ step: "tools.visible", ok: true })

await page.getByRole("button", { name: "Add files", exact: true }).click()
await expect(page.getByRole("textbox", { name: "Search files" })).toBeVisible()
await page.getByRole("button", { name: "List view" }).click()
await page.getByRole("button", { name: "Grid view" }).click()
await shot("media-picker")
await page.locator('input[type="file"]').setInputFiles({
  name: uploadName,
  mimeType: "image/png",
  buffer: Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lK3Q6wAAAABJRU5ErkJggg==",
    "base64"
  ),
})
await expect(
  page.getByRole("dialog").getByText(uploadName, { exact: true })
).toBeVisible()
await expect(
  page
    .getByRole("main", { name: "Conversation" })
    .getByRole("button", { name: `Remove ${uploadName}` })
).toBeVisible()
await page.keyboard.press("Escape")
await expect(page.getByRole("dialog")).toHaveCount(0)
await composer.fill("Keep this picture")
await page.getByRole("button", { name: "Send message", exact: true }).click()
await expect(
  page
    .getByRole("main", { name: "Conversation" })
    .getByText(uploadName, { exact: true })
    .first()
).toBeVisible()
await page
  .getByRole("main", { name: "Conversation" })
  .getByRole("button", { name: `Preview ${uploadName}` })
  .first()
  .click()
await expect(page.getByRole("dialog")).toContainText(uploadName)
await page.keyboard.press("Escape")
await shot("image-reply")
results.push({ step: "send.image", ok: true })

const threadRow = page
  .getByRole("listitem")
  .filter({ hasText: "What changed today?" })
  .first()
await threadRow.hover()
await threadRow.getByRole("button", { name: "Thread actions" }).click()
await page.getByRole("menuitem", { name: "Rename" }).click()
await page.getByLabel("Title").fill("Renamed on the web")
await page.getByRole("button", { name: "Save", exact: true }).click()
await expect(page.getByRole("heading", { level: 1 })).toHaveText("Renamed on the web")
results.push({ step: "thread.rename", ok: true })

await composer.fill("Draft survives a reload")
await page.reload()
await expect(page.getByRole("textbox", { name: "Message Skye" })).toHaveValue(
  "Draft survives a reload"
)
await shot("reloaded-draft")
results.push({ step: "draft.reload", ok: true })


const report = {
  version: 1,
  status: errors.length ? "failed" : "passed",
  steps: results,
  errors,
}
await writeFile(
  new URL("../test-results/stage45-connected.json", import.meta.url),
  JSON.stringify(report, null, 2)
)
console.log(JSON.stringify(report, null, 2))
await browser.close()
if (errors.length) process.exit(1)
