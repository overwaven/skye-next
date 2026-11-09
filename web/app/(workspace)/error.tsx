"use client"

import Link from "next/link"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"

export default function AccountError({ reset }: { reset: () => void }) {
  return (
    <main className="detail-content">
      <Alert>
        <AlertTitle>Account view unavailable</AlertTitle>
        <AlertDescription>
          Skye could not load this view. Try loading it again, or sign in with
          Telegram.
        </AlertDescription>
      </Alert>
      <Button onClick={reset}>Try again</Button>
      <Link href="/login" className={buttonVariants({ variant: "outline" })}>
        Sign in
      </Link>
    </main>
  )
}
