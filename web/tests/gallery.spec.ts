import { test, expect } from "@playwright/test"

test("file tiles contain size and menu in grid and list at every width", async ({
  page,
}, info) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated connected preview"
  )
  await page.route("**/api/v1/media/gallery-*", (route) =>
    route.fulfill({
      contentType: "image/png",
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGP0blrAgA0wYRUdtBIAIRABfYoYwmMAAAAASUVORK5CYII=",
        "base64"
      ),
    })
  )
  await page.route("**/api/v1/media", (route) =>
    route.fulfill({
      json: {
        media: Array.from({ length: 9 }, (_, i) => ({
          id: `gallery-${i}`,
          name:
            i === 0
              ? "A very long document title that must not widen a tile.txt"
              : `Landscape ${i}.png`,
          media_type: i === 0 ? "text/plain" : "image/png",
          size: 4096,
          created_at: 10 - i,
          is_image: i !== 0,
          availability: "available",
        })),
      },
    })
  )
  await page.goto("/chat")
  await page
    .getByRole("button", { name: "Add files", exact: true })
    .first()
    .click()
  const dialog = page.getByRole("dialog", { name: "Files", exact: true })
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    for (const layout of ["Grid view", "List view"]) {
      await dialog.getByRole("button", { name: layout, exact: true }).click()
      const tiles = dialog.locator(".library-attachment")
      await expect(tiles).toHaveCount(9)
      for (let i = 0; i < 9; i++) {
        const tile = tiles.nth(i)
        const box = await tile.boundingBox()
        expect(box).not.toBeNull()
        for (const selector of [
          ".media-size",
          "[data-slot=attachment-actions]",
        ]) {
          const child = await tile.locator(selector).boundingBox()
          expect(child).not.toBeNull()
          expect(child!.x).toBeGreaterThanOrEqual(box!.x - 1)
          expect(child!.x + child!.width).toBeLessThanOrEqual(
            box!.x + box!.width + 1
          )
          expect(child!.y).toBeGreaterThanOrEqual(box!.y - 1)
          expect(child!.y + child!.height).toBeLessThanOrEqual(
            box!.y + box!.height + 1
          )
        }
      }
      expect(
        await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)
      ).toBe(true)
      await dialog
        .getByRole("button", { name: /Actions for/ })
        .first()
        .click()
      await expect(
        page.getByRole("menuitem", { name: "Preview", exact: true })
      ).toBeVisible()
      await page.keyboard.press("Escape")
      await page.screenshot({
        path: info.outputPath(`gallery-${width}-${layout}.png`),
      })
    }
  }
})
