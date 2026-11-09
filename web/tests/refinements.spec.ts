import { test, expect } from "@playwright/test"

test("search groups destinations and library opens a section chooser", async ({
  page,
}) => {
  await page.goto("/chat")
  await page.keyboard.press("Control+k")
  const search = page.getByRole("dialog", { name: "Search" })
  await expect(
    search.locator("[cmdk-group-heading]").filter({ hasText: "Threads" })
  ).toBeVisible()
  await expect(
    search.locator('[data-slot="command-separator"]').first()
  ).toBeVisible()
  await page.getByRole("combobox").fill("Library")
  await page.keyboard.press("Enter")
  await expect(page).toHaveURL(/\/library$/)
  await page.getByRole("link", { name: "Memory", exact: true }).click()
  await expect(page).toHaveURL(/\/library\/memory$/)
})

test("mobile text stays at least 16px and Details has a swipe handle", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/dev/states/ready")
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await expect(page.locator('[data-slot="drawer-swipe-handle"]')).toBeVisible()
  const undersized = await page.evaluate(() =>
    Array.from(document.querySelectorAll("body *"))
      .filter(
        (el) =>
          el.getClientRects().length &&
          Array.from(el.childNodes).some(
            (node) =>
              node.nodeType === Node.TEXT_NODE && node.textContent?.trim()
          )
      )
      .filter((el) => parseFloat(getComputedStyle(el).fontSize) < 16)
      .map((el) => ({
        text: el.textContent?.slice(0, 60),
        size: getComputedStyle(el).fontSize,
      }))
  )
  expect(undersized).toEqual([])
  await page.screenshot({ path: info.outputPath("mobile-details.png") })
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await page.getByRole("button", { name: "Toggle Sidebar" }).click()
  await expect(page.locator('[data-slot="drawer-swipe-handle"]')).toBeVisible()
  await page.screenshot({ path: info.outputPath("mobile-navigation.png") })
})

test("settings and projects expose real tab panels", async ({ page }) => {
  await page.goto("/settings/general")
  await page.getByRole("tab", { name: "Privacy" }).click()
  await expect(page).toHaveURL(/\/settings\/privacy$/)
  await expect(page.getByRole("tabpanel")).toContainText("History")
  await page.goto("/projects/skye-web")
  await page.getByRole("tab", { name: "Instructions" }).click()
  await expect(page.getByRole("tabpanel", { name: "Instructions" })).toBeVisible()
})
