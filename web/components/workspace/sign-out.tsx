"use client"

import { useFormStatus } from "react-dom"
import { HugeiconsIcon } from "@hugeicons/react"
import { Logout01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

export function SignOutButton({
  allDevices = false,
}: {
  allDevices?: boolean
}) {
  const { pending } = useFormStatus()
  return (
    <Button type="submit" variant="ghost" disabled={pending}>
      {pending ? (
        <Spinner data-icon="inline-start" />
      ) : (
        <HugeiconsIcon icon={Logout01Icon} data-icon="inline-start" />
      )}
      {pending
        ? "Signing out…"
        : allDevices
          ? "Sign out all devices"
          : "Sign out"}
    </Button>
  )
}
