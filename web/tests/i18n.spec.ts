import { test, expect } from "@playwright/test"

test("an English device can choose Russian and the choice survives reload", async ({
  page,
}) => {
  await page.goto("/settings/general")
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("General")
  await page.getByText("Русский", { exact: true }).click()
  await expect(page.getByRole("radio", { name: "Русский" })).toBeChecked()
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Основные")
  await expect(page.getByRole("tab", { name: "Аккаунт" })).toBeVisible()

  await page.reload()
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Основные")
  await expect(page.locator("html")).toHaveAttribute("lang", "ru")

  await page.getByText("English", { exact: true }).click()
  await expect(page.getByRole("radio", { name: "English" })).toBeChecked()
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("General")
})

test.describe("Russian device", () => {
  test.use({ locale: "ru-RU" })

  test("starts in Russian and can switch to English", async ({ page }) => {
    await page.goto("/chats")
    await expect(
      page.getByRole("heading", { name: "Чаты", exact: true })
    ).toBeVisible()
    await expect(page.getByRole("checkbox")).toHaveCount(0)
    await page.getByRole("button", { name: "Выбрать", exact: true }).click()
    await expect(page.getByRole("checkbox").first()).toBeVisible()

    await page.goto("/settings/general")
    await page.getByText("English", { exact: true }).click()
  await expect(page.getByRole("radio", { name: "English" })).toBeChecked()
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("General")
    await page.reload()
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("General")
    await expect(page.locator("html")).toHaveAttribute("lang", "en")
  })
})
