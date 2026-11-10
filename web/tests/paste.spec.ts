import { test, expect } from "@playwright/test"

test("pasting files from the clipboard attaches any file type", async ({
  page,
}, info) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated Next → Python preview"
  )
  const uploads: { id: string; name: string }[] = []
  page.on("response", (response) => {
    if (
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/media" &&
      response.status() === 201
    ) {
      void response.json().then((body: { id: string; name: string }) => {
        uploads.push({ id: body.id, name: body.name })
      })
    }
  })

  await page.goto("/chat")
  await page.locator('[data-hydrated="true"]').waitFor()
  const textbox = page.getByRole("textbox", { name: "Message Skye" })
  await textbox.click()
  await page.evaluate(() => {
    const transfer = new DataTransfer()
    transfer.items.add(
      new File(["<!doctype html><title>pasted</title>"], "page.html", {
        type: "text/html",
      })
    )
    const event = new Event("paste", { bubbles: true, cancelable: true })
    Object.defineProperty(event, "clipboardData", { value: transfer })
    document
      .querySelector<HTMLTextAreaElement>('textarea[name="message"]')
      ?.dispatchEvent(event)
  })

  await expect(page.getByText("page.html", { exact: true })).toBeVisible()
  await expect.poll(() => uploads.length).toBe(1)
  await expect(page.getByText("Attaching files…", { exact: true })).toHaveCount(
    0
  )

  const html = uploads.find((upload) => upload.name === "page.html")
  expect(html).toBeTruthy()
  const response = await page.request.get(`/api/v1/media/${html!.id}`)
  expect(response.status()).toBe(200)
  expect(response.headers()["content-disposition"]).toContain("attachment")
  expect(response.headers()["content-type"]).toContain("text/html")

  await page.screenshot({ path: info.outputPath("paste.png"), fullPage: true })
})
