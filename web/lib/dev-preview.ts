import "server-only"

// Never activates in `next build` / `next start`, even with a leaked dev flag.
export function devPreviewEnabled() {
  return (
    process.env.NODE_ENV === "development" &&
    process.env.SKYE_DEV_PREVIEW === "true"
  )
}
