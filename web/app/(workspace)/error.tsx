"use client"

import Link from "next/link"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { useI18n } from "@/components/i18n-provider"

export default function AccountError({ reset }: { reset: () => void }) {
  const { t } = useI18n()
  return (
    <main className="detail-content">
      <Alert>
        <AlertTitle>{t("error.accountTitle")}</AlertTitle>
        <AlertDescription>
          {t("error.accountDescription")}
        </AlertDescription>
      </Alert>
      <Button onClick={reset}>{t("error.tryAgain")}</Button>
      <Link href="/login" className={buttonVariants({ variant: "outline" })}>
        {t("error.signIn")}
      </Link>
    </main>
  )
}
