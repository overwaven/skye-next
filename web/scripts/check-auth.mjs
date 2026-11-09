import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { chromium, firefox, webkit } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"

const accounts = JSON.parse(await readFile(process.argv[2], "utf8"))
const origin = "http://localhost:3004"
const cookie = (account) => `__Host-skye_session=${account.token}`

const unsigned = await fetch(`${origin}/chat`, { redirect: "manual" })
assert.equal(unsigned.status, 307)
assert.equal(unsigned.headers.get("location"), "/login")

let engineIndex = 0
for (const [engineName, engine] of Object.entries({
  chromium,
  firefox,
  webkit,
})) {
  const browser = await engine.launch()
  try {
    for (const owner of ["101", "202"]) {
      const other = owner === "101" ? "202" : "101"
      // Synthetic HTTP transport only: deliberately supply a test cookie header.
      // This does not claim to verify HTTPS/Secure-cookie or real OIDC behavior.
      const context = await browser.newContext({
        extraHTTPHeaders: { Cookie: cookie(accounts[owner]) },
      })
      const page = await context.newPage()
      const errors = []
      page.on("pageerror", (error) => errors.push(error.message))
      await page.goto(`${origin}/chat/${accounts[owner].thread_id}`)
      await page
        .getByText(`Private message for account ${owner}`, { exact: true })
        .waitFor()
      assert.deepEqual(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
            .analyze()
        ).violations,
        []
      )
      // This finite read-only fixture has no polling/streams. Let prefetch settle
      // before another full navigation instead of auditing harness-aborted fetches.
      await page.waitForLoadState("networkidle")
      assert(
        !(await page.locator("body").innerText()).includes(
          `Private project ${other}`
        )
      )
      await page.goto(`${origin}/projects/${accounts[owner].project_id}`)
      await page
        .getByRole("heading", { name: `Private project ${owner}`, exact: true, level: 1 })
        .waitFor()
      await page.waitForLoadState("networkidle")
      await page.goto(`${origin}/projects/${accounts[other].project_id}`)
      await page.waitForLoadState("networkidle")
      assert(
        !(await page.locator("body").innerText()).includes(
          `Private project ${other}`
        )
      )
      await page.goto(`${origin}/chat/${accounts[other].thread_id}`)
      await page.waitForLoadState("networkidle")
      assert(
        !(await page.locator("body").innerText()).includes(
          `Private message for account ${other}`
        )
      )
      assert.deepEqual(errors, [])
      await context.close()
    }
    const logoutAccount = {
      ...accounts["101"],
      token: accounts["101"].logout_tokens[engineIndex],
    }
    const context = await browser.newContext({
      extraHTTPHeaders: { Cookie: cookie(logoutAccount) },
    })
    const page = await context.newPage()
    await page.goto(`${origin}/chat/${logoutAccount.thread_id}`)
    await page.getByRole("button", { name: "Sign out", exact: true }).click()
    await page.waitForURL("**/login")
    await page.goto(`${origin}/chat/${logoutAccount.thread_id}`)
    assert(page.url().includes("/login"))
    assert(
      !(await page.locator("body").innerText()).includes(
        "Private message for account 101"
      )
    )
    await context.close()
  } finally {
    await browser.close()
  }
  console.log(
    `${engineName}: own account rendered; foreign transcript and navigation absent.`
  )
  engineIndex += 1
}
console.log(
  "Synthetic two-account Next.js → Python isolation checks passed; real OIDC remains unverified."
)
