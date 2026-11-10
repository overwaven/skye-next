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

  const list = page.locator("main [role=\"list\"]")
  await expect(list.getByRole("checkbox")).toHaveCount(0)
  const listTop = (await list.boundingBox())?.y

  await page.getByRole("button", { name: "Select", exact: true }).click()
  await expect(list.getByRole("checkbox")).not.toHaveCount(0)
  const selectedTop = (await list.boundingBox())?.y
  expect(Math.abs((selectedTop ?? 0) - (listTop ?? 0))).toBeLessThan(2)

  const checks = list.getByRole("checkbox")
  await checks.nth(0).check()
  await checks.nth(1).check()
  await expect(page.getByText("2 selected", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Pin", exact: true }).click()
  await expect(page.getByText("Chats pinned", { exact: true })).toBeVisible()
  await expect(page.getByText("Pinned", { exact: true })).toBeVisible()

  await page.getByRole("button", { name: "Select", exact: true }).click()
  const pinnedChecks = page.getByRole("list").getByRole("checkbox")
  await pinnedChecks.nth(0).check()
  await pinnedChecks.nth(1).check()
  await page.getByRole("button", { name: "Unpin", exact: true }).click()
  await expect(
    page.getByText("Chats unpinned", { exact: true })
  ).toBeVisible()

  const firstOpen = page.getByRole("button", { name: /^Open / }).first()
  const title = (await firstOpen.getAttribute("aria-label"))?.replace(
    /^Open /,
    ""
  )
  await firstOpen.click()
  await expect(page).toHaveURL(/\/chat\//)
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    title ?? ""
  )
  await page.goBack()
  await expect(
    page.getByRole("heading", { name: "Chats", exact: true })
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
