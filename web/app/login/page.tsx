import type { Metadata } from "next"
import Link from "next/link"
import { SkyeMark } from "@/components/skye-mark"
import { Button, buttonVariants } from "@/components/ui/button"
import { accountEnabled } from "@/lib/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { devPreviewEnabled } from "@/lib/dev-preview"
import { enterPreview } from "@/app/account-actions"

export const metadata: Metadata = { title: "Sign in" }
export const dynamic = "force-dynamic"

export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>
}) {
  const enabled = accountEnabled()
  const { error } = await searchParams
  return (
    <main className="login-page">
      <Link href="/chat" className="brand-lockup">
        <SkyeMark />
        <span>skye</span>
      </Link>
      <div className="login-content">
        <h1 className="sr-only">Sign in to Skye</h1>
        {(error === "verification" || error === "session") && (
          <Alert>
            <AlertTitle>
              {error === "session"
                ? "Sign in again"
                : "Login could not be verified"}
            </AlertTitle>
            <AlertDescription>
              {error === "session"
                ? "Your session expired or was signed out."
                : "Start again with your existing Telegram account."}
            </AlertDescription>
          </Alert>
        )}
        {devPreviewEnabled() ? (
          <form action={enterPreview}>
            <Button>Open local preview</Button>
          </form>
        ) : enabled ? (
          // OIDC must start as a full navigation, never a prefetched client transition.
          // eslint-disable-next-line @next/next/no-html-link-for-pages
          <a className={buttonVariants()} href="/api/v1/auth/start">
            Continue with Telegram
          </a>
        ) : (
          <Button disabled>Continue with Telegram</Button>
        )}
        {!enabled && (
          <Link className={buttonVariants({ variant: "outline" })} href="/chat">
            Explore the interface
          </Link>
        )}
      </div>
    </main>
  )
}
