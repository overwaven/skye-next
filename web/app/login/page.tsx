import type { Metadata } from "next"
import Link from "next/link"
import { SkyeMark } from "@/components/skye-mark"
import { Button, buttonVariants } from "@/components/ui/button"
import { accountEnabled } from "@/lib/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { devPreviewEnabled } from "@/lib/dev-preview"
import { enterPreview } from "@/app/account-actions"
import { getTranslator } from "@/lib/i18n-server"

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getTranslator()
  return { title: t("login.title") }
}

export const dynamic = "force-dynamic"

export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>
}) {
  const enabled = accountEnabled()
  const { t } = await getTranslator()
  const { error } = await searchParams
  return (
    <main className="login-page">
      <Link href="/chat" className="brand-lockup">
        <SkyeMark />
        <span>skye</span>
      </Link>
      <div className="login-content">
        <h1 className="sr-only">{t("login.signInAria")}</h1>
        {(error === "verification" || error === "session") && (
          <Alert>
            <AlertTitle>
              {error === "session"
                ? t("login.session")
                : t("login.verification")}
            </AlertTitle>
            <AlertDescription>
              {error === "session"
                ? t("login.sessionDescription")
                : t("login.verificationDescription")}
            </AlertDescription>
          </Alert>
        )}
        {devPreviewEnabled() ? (
          <form action={enterPreview}>
            <Button>{t("login.preview")}</Button>
          </form>
        ) : enabled ? (
          // OIDC must start as a full navigation, never a prefetched client transition.
          // eslint-disable-next-line @next/next/no-html-link-for-pages
          <a className={buttonVariants()} href="/api/v1/auth/start">
            {t("login.continue")}
          </a>
        ) : (
          <Button disabled>{t("login.continue")}</Button>
        )}
        {!enabled && (
          <Link className={buttonVariants({ variant: "outline" })} href="/chat">
            {t("login.explore")}
          </Link>
        )}
      </div>
    </main>
  )
}
