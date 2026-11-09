import { test, expect } from "@playwright/test"

test.use({ reducedMotion: "reduce" })

const fakeRecorder = () => {
  class FakeMediaRecorder {
    static isTypeSupported() {
      return true
    }
    mimeType = "audio/webm"
    ondataavailable: ((event: { data: Blob }) => void) | null = null
    onstop: (() => void) | null = null
    state = "inactive"
    constructor() {}
    start() {
      this.state = "recording"
      window.setTimeout(() => {
        this.ondataavailable?.({
          data: new Blob(["dictation"], { type: "audio/webm" }),
        })
      }, 10)
    }
    stop() {
      this.state = "inactive"
      this.onstop?.()
    }
  }
  Object.defineProperty(window, "MediaRecorder", {
    configurable: true,
    value: FakeMediaRecorder,
  })
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: async () => ({
        getTracks: () => [{ stop() {} }],
      }),
    },
  })
}

async function record(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Record a voice message" }).click()
  await page.getByRole("button", { name: "Stop recording" }).click()
}

test("dictation transcribes into the composer without an attachment", async ({
  page,
}) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated Next → Python preview"
  )
  await page.addInitScript(fakeRecorder)
  await page.route("**/api/v1/audio/transcribe", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        text: "Hello from dictation",
        media: { id: "unused" },
      }),
    })
  )
  await page.goto("/chat")
  await page.locator('[data-hydrated="true"]').waitFor()
  await record(page)
  const input = page.getByRole("textbox", { name: "Message Skye" })
  await expect(input).toHaveValue("Hello from dictation")
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.locator('[data-slot="attachment"]')).toHaveCount(0)
})

test("empty dictation reports that nothing was recorded", async ({ page }) => {
  test.skip(
    !process.env.SKYE_TEST_BASE_URL,
    "Uses the isolated Next → Python preview"
  )
  await page.addInitScript(fakeRecorder)
  await page.route("**/api/v1/audio/transcribe", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ text: "  ", media: { id: "unused" } }),
    })
  )
  await page.goto("/chat")
  await page.locator('[data-hydrated="true"]').waitFor()
  await record(page)
  await expect(page.getByText("Nothing recorded", { exact: true })).toBeVisible()
  await expect(
    page.getByRole("textbox", { name: "Message Skye" })
  ).toHaveValue("")
})
