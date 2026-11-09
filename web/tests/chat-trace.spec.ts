import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"

test.use({ reducedMotion: "reduce" })

test("tool steps show names and expandable input and result", async ({
  page,
}, info) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated Next → Python preview"
  )
  await page.goto("/chat")
  await page.locator('[data-hydrated="true"]').waitFor()
  await page
    .getByRole("textbox", { name: "Message Skye" })
    .fill("Calculate this for me")
  await page.getByRole("button", { name: "Send message" }).click()
  await expect(
    page.getByText("Local demo reply", { exact: false })
  ).toBeVisible({ timeout: 20000 })
  await page.getByRole("button", { name: "2 tools", exact: true }).click()
  const web = page.getByRole("button", { name: /web search/ })
  const code = page.getByRole("button", { name: /execute code/ })
  await expect(web).toBeVisible()
  await expect(code).toBeVisible()
  await web.click()
  await expect(
    page.getByText("Found 4 short references.", { exact: true })
  ).toBeVisible()
  await code.click()
  const codeStep = page
    .locator('[data-slot="trace-collapsible"]')
    .filter({ hasText: "execute code" })
  await expect(
    codeStep.getByText('{"code":"print(2 + 2)"}', { exact: true })
  ).toBeVisible()
  await expect(codeStep.getByText("4", { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath("tool-trace.png"), fullPage: true })
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations
  ).toEqual([])
})
