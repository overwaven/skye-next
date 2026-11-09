"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { PageHeader } from "@/components/workspace/page-header"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { resourceRequest } from "@/components/workspace/personal-resources"

export function ConnectorVerification({ csrf }: { csrf: string }) {
  const [status, setStatus] = useState("Verifying your connection…")
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
    ) : Promise.reject(new Error("Missing authorization"))
    void verification
      .then(() =>
        setStatus("Connection verified. You can return to Connectors.")
      )
      .catch(() => {
        setError(true)
        setStatus(
          "Could not verify this connection. Return to Connectors and start again."
        )
      })
  }, [csrf])
  return (
    <div className="detail-page">
      <PageHeader
        title="Verify connection"
        parent={{ name: "Connectors", href: "/library/connectors" }}
      />
      <main className="detail-content resource-manager">
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
          Return to connectors
        </Button>
      </main>
    </div>
  )
}
