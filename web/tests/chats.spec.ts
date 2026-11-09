import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"

test.use({ reducedMotion: "reduce" })

test("recent threads opens chats with filters and multi-select", async ({
  page,
}, info) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated Next → Python preview"
  )
  await page.goto("/chat")
  await page.locator('[data-hydrated="true"]').waitFor()
  await page.getByRole("link", { name: "Recent threads", exact: true }).click()
  await expect(page).toHaveURL(/\/chats$/)
  await expect(
    page.getByRole("heading", { name: "Chats", exact: true })
  ).toBeVisible()
  await expect(
    page.getByRole("textbox", { name: "Search chats" })
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "All projects", exact: true })
  ).toBeVisible()
  await page.getByRole("button", { name: "All projects", exact: true }).click()
  await page.getByRole("menuitemradio", { name: "No project" }).click()
  await expect(
    page.getByRole("button", { name: "No project", exact: true })
  ).toBeVisible()
  await page.getByRole("button", { name: "No project", exact: true }).click()
  await page.getByRole("menuitemradio", { name: "All projects" }).click()

  const checks = page.getByRole("list").getByRole("checkbox")
  expect(await checks.count()).toBeGreaterThan(1)
  await checks.nth(0).check()
  await checks.nth(1).check()
  await expect(page.getByText("2 selected", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Pin", exact: true }).click()
  await expect(page.getByText("Chats pinned", { exact: true })).toBeVisible()
  await expect(page.getByText("Pinned", { exact: true })).toBeVisible()

  const pinnedChecks = page.getByRole("list").getByRole("checkbox")
  await pinnedChecks.nth(0).check()
  await pinnedChecks.nth(1).check()
  await page.getByRole("button", { name: "Unpin", exact: true }).click()
  await expect(
    page.getByText("Chats unpinned", { exact: true })
  ).toBeVisible()

  await page.screenshot({ path: info.outputPath("chats.png"), fullPage: true })
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations
  ).toEqual([])
})
