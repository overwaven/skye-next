import { test, expect } from "@playwright/test"

test.use({ reducedMotion: "reduce" })

test("a new project starts empty and can be deleted", async ({ page }, info) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated Next → Python preview"
  )
  const name = `Empty ${Date.now()}`
  await page.goto("/chat")
  await page.locator('[data-hydrated="true"]').waitFor()
  await page.getByRole("button", { name: "New project", exact: true }).click()
  await page.getByRole("textbox", { name: "Name", exact: true }).fill(name)
  await page.getByRole("button", { name: "Create", exact: true }).click()
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("link", { name, exact: true })
    .click()
  await expect(page.getByText("No threads yet", { exact: true })).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Create the first thread", exact: true })
  ).toBeVisible()
  await page.screenshot({ path: info.outputPath("project-empty.png") })

  await page
    .locator("header")
    .getByRole("button", { name: `Actions for ${name}`, exact: true })
    .click()
  await page.getByRole("menuitem", { name: "Delete project", exact: true }).click()
  await expect(
    page.getByRole("alertdialog").getByText(`Delete ${name}?`, { exact: true })
  ).toBeVisible()
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Delete project", exact: true })
    .click()
  await expect(page.getByText("Project deleted", { exact: true })).toBeVisible()
  await expect(page).toHaveURL(/\/chat$/)
  await expect(
    page
      .getByRole("navigation", { name: "Workspace navigation" })
      .getByRole("link", { name, exact: true })
  ).toHaveCount(0)
})
