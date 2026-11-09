import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"

test("personal memory and skills persist through real API; MCP errors keep drafts", async ({
  page,
}, info) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses isolated Next → Python preview"
  )
  const suffix = `${info.project.name}-${Date.now()}`
  const memory = `Stage six prefers tea ${suffix}`
  await page.goto("/library/memory")
  await page.getByRole("button", { name: "Add memory", exact: true }).click()
  await page.getByRole("textbox", { name: "Memory", exact: true }).fill(memory)
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await page.reload()
  await expect(page.getByText(memory, { exact: true })).toBeVisible()
  const row = page.locator('[data-slot="item"]').filter({ hasText: memory })
  await row.getByRole("button", { name: "Edit", exact: true }).click()
  await page
    .getByRole("textbox", { name: "Memory", exact: true })
    .fill(memory + " edited")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(
    page.getByText(memory + " edited", { exact: true })
  ).toBeVisible()
  await page.getByRole("textbox", { name: "Search memory" }).fill(suffix)
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth
      )
    ).toBe(true)
    await page.screenshot({ path: info.outputPath(`memory-${width}.png`) })
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.setViewportSize({ width: 1440, height: 900 })
  await row.getByRole("button", { name: "Delete", exact: true }).click()
  await page.getByRole("button", { name: "Remove", exact: true }).click()
  await expect(page.getByText(memory + " edited", { exact: true })).toHaveCount(
    0
  )

  await page.goto("/library/skills")
  await page.getByRole("button", { name: "Upload skill", exact: true }).click()
  const name = `tea-${suffix}`
  await page.getByLabel("SKILL.md or zip bundle").setInputFiles({
    name: "SKILL.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      `---\nname: ${name}\ndescription: A calm tea ritual\n---\nBoil the water. Leave the tea for three minutes.`
    ),
  })
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Install skill", exact: true }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await page.getByRole("link", { name: new RegExp(name) }).click()
  await expect(
    page.getByText("Boil the water.", { exact: false })
  ).toBeVisible()
  await page.screenshot({ path: info.outputPath("skill-detail.png") })
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.getByRole("button", { name: "Remove skill", exact: true }).click()
  await page.getByRole("button", { name: "Remove", exact: true }).click()
  await expect(page).toHaveURL(/\/library\/skills$/)

  await page.goto("/library/connectors")
  await page
    .getByRole("button", { name: "Add MCP server", exact: true })
    .click()
  await page
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Private server")
  await page
    .getByRole("textbox", { name: "HTTPS URL", exact: true })
    .fill("https://127.0.0.1/mcp")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(
    page.getByText("That host is not allowed.", { exact: true })
  ).toBeVisible()
  await expect(
    page.getByRole("textbox", { name: "HTTPS URL", exact: true })
  ).toHaveValue("https://127.0.0.1/mcp")
  await page.screenshot({ path: info.outputPath("mcp-error.png") })
  await page.getByRole("button", { name: "Cancel", exact: true }).click()
})
