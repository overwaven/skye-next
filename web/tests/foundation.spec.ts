import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"

test("draft is never sent and survives the feature dialog", async ({
  page,
}) => {
  await page.goto("/chat")
  const input = page.getByRole("textbox", { name: "Message Skye" })
  await input.fill("A private thought")
  await page.getByRole("button", { name: "Add files", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await expect(page.getByRole("dialog")).toHaveCSS("opacity", "1")
  await expect(page.locator('[data-slot="dialog-overlay"]')).toHaveCSS(
    "opacity",
    "1"
  )
  await page.keyboard.press("Escape")
  await expect(
    page.getByRole("button", { name: "Add files", exact: true })
  ).toBeFocused()
  await page.getByRole("button", { name: "Send message", exact: true }).click()
  await expect(page.getByRole("status")).toContainText("Not sent")
  await expect(input).toHaveValue("A private thought")
})

test("search is keyboard reachable and routes to memory", async ({ page }) => {
  await page.goto("/chat")
  await page.keyboard.press("Control+k")
  await expect(page.getByRole("dialog", { name: "Search" })).toBeVisible()
  await page.getByRole("combobox").fill("Memory")
  await page.keyboard.press("Enter")
  await expect(page).toHaveURL(/\/library\/memory/)
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Memory")
})

for (const width of [1440, 768, 390, 320]) {
  test(`chat and context at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto("/dev/states/ready")
    await expect(
      page.getByText("Preview · Sample conversation.", { exact: false })
    ).toBeVisible()
    await page.getByRole("button", { name: "Details", exact: true }).click()
    await expect(
      page.getByRole("heading", { name: "Details", exact: true })
    ).toBeVisible()
    if (width < 1200) {
      await page.keyboard.press("Escape")
      // Audit the settled page, not fading-out text that is being unmounted.
      await expect(page.getByRole("dialog")).toHaveCount(0)
    } else {
      await page.getByRole("button", { name: "Close details" }).click()
      await expect(page.locator("#thread-context")).toBeHidden()
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth
      )
    ).toBe(true)
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze()
    expect(results.violations).toEqual([])
  })
}

test("all states and library routes have a title and accessible controls", async ({
  page,
}) => {
  for (const state of [
    "empty",
    "loading",
    "failed",
    "running",
    "long",
    "low-funds",
  ]) {
    await page.goto(`/dev/states/${state}`)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
          .analyze()
      ).violations
    ).toEqual([])
  }
  for (const section of [
    "memory",
    "connectors",
    "skills",
    "files",
    "agents",
    "automations",
  ]) {
    await page.goto(`/library/${section}`)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  }
})

test("mobile navigation closes on destination and has a visible close path", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/chat")
  await page.getByRole("button", { name: "Toggle Sidebar" }).click()
  await expect(
    page.getByRole("button", { name: "Close navigation" })
  ).toBeVisible()
  await page.getByRole("link", { name: "Library", exact: true }).click()
  await page.getByRole("link", { name: "Memory", exact: true }).click()
  await expect(page).toHaveURL(/\/library\/memory/)
  await expect(page.getByRole("dialog")).toHaveCount(0)
})

test("library action sits beside search and empty states name themselves", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto("/library/skills")
  const search = await page
    .getByRole("textbox", { name: "Search skills" })
    .boundingBox()
  const action = await page
    .getByRole("button", { name: "Upload a skill" })
    .boundingBox()
  expect(search).not.toBeNull()
  expect(action).not.toBeNull()
  expect(action!.x).toBeGreaterThan(search!.x + search!.width)
  expect(
    Math.abs(action!.y + action!.height / 2 - (search!.y + search!.height / 2))
  ).toBeLessThan(2)
  await expect(page.getByText("No skills yet", { exact: true })).toBeVisible()
  await expect(page.locator('[data-slot="empty-icon"] svg')).toBeVisible()
})

test("appearance cards switch theme and page-title focus stays quiet", async ({
  page,
}) => {
  await page.goto("/settings/general")
  await page.locator('[data-hydrated="true"]').waitFor()
  await page.getByText("Dark", { exact: true }).click()
  await expect(page.locator("html")).toHaveClass(/dark/)
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked()
  await page.getByText("Light", { exact: true }).click()
  await expect(page.locator("html")).not.toHaveClass(/dark/)
  await page.getByRole("tab", { name: "Account", exact: true }).click()
  const title = page.locator("#page-title")
  await expect(title).toBeFocused()
  await expect(title).toHaveCSS("outline-style", "none")
})

test("dark appearance and reduced motion", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" })
  await page.goto("/dev/states/running")
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations
  ).toEqual([])
  expect(
    await page
      .locator('[data-slot="spinner"]')
      .evaluate((el) => getComputedStyle(el).animationName)
  ).toBe("none")
})

test("200% text resize keeps the composer and recovery actions reachable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 450 })
  await page.goto("/dev/states/failed")
  await page.locator('[data-hydrated="true"]').waitFor()
  await page.addStyleTag({ content: "html { font-size: 200%; }" })
  const send = page.getByRole("button", { name: "Send message", exact: true })
  await page.getByRole("textbox", { name: "Message Skye" }).fill("Resize check")
  await send.scrollIntoViewIfNeeded()
  await expect(send).toBeInViewport()
  await send.click()
  await expect(page.getByRole("status")).toContainText("Not sent")
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth
    )
  ).toBe(true)
})

test("resource editor and context have no console errors and pass axe while open", async ({
  page,
}) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type()))
      errors.push(message.text())
  })
  await page.goto("/library/memory")
  await page.locator('[data-hydrated="true"]').waitFor()
  await page.getByRole("button", { name: "Add memory", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await expect(page.getByRole("dialog")).toHaveCSS("opacity", "1")
  await expect(page.locator('[data-slot="dialog-overlay"]')).toHaveCSS(
    "opacity",
    "1"
  )
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations
  ).toEqual([])
  await page.keyboard.press("Escape")
  await expect(
    page.getByRole("button", { name: "Add memory", exact: true })
  ).toBeFocused()
  await page.goto("/chat/a-place-to-think")
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await expect(page.locator("#thread-context")).toBeVisible()
  await page.getByRole("button", { name: "Close details" }).click()
  await expect(page.locator("#thread-context")).toBeHidden()
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations
  ).toEqual([])
  // Firefox's axe injection can emit this engine scheduling diagnostic. Do not
  // suppress application/framework warnings or any uncaught exceptions.
  expect(
    errors.filter(
      (message) =>
        !message.startsWith(
          '[JavaScript Warning: "The execution of microtasks on this page was reordered'
        )
    )
  ).toEqual([])
})
