"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { PageHeader } from "@/components/workspace/page-header"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { resourceRequest } from "@/components/workspace/resources/resource-api"
import { useI18n } from "@/components/i18n-provider"

export function ConnectorVerification({ csrf }: { csrf: string }) {
  const { t } = useI18n()
  const [status, setStatus] = useState(t("verify.verifying"))
  const [error, setError] = useState(false)
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    const token = new URL(window.location.href).searchParams.get("session_uri")
    window.history.replaceState(null, "", "/connector-verify")
    const verification = token ? resourceRequest<{ status: string }>(
      "/connectors/verify",
      csrf,
      "POST",
      { session_uri: token }
    ) : Promise.reject(new Error(t("verify.missing")))
    void verification
      .then(() =>
        setStatus(t("verify.verified"))
      )
      .catch(() => {
        setError(true)
        setStatus(t("verify.failed"))
      })
  }, [csrf, t])
  return (
    <div className="detail-page">
      <PageHeader
        title={t("verify.title")}
        parent={{ name: t("library.connectors"), href: "/library/connectors" }}
      />
      <main className="detail-content resource-page">
        {error ? (
          <Alert>
            <AlertDescription>{status}</AlertDescription>
          </Alert>
        ) : (
          <p role="status">{status}</p>
        )}
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link href="/library/connectors" />}
        >
          {t("verify.return")}
        </Button>
      </main>
    </div>
  )
}
