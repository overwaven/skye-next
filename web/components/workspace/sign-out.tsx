"use client"

import { useFormStatus } from "react-dom"
import { HugeiconsIcon } from "@hugeicons/react"
import { Logout01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useI18n } from "@/components/i18n-provider"

export function SignOutButton({
  allDevices = false,
}: {
  allDevices?: boolean
}) {
  const { pending } = useFormStatus()
  const { t } = useI18n()
  return (
    <Button type="submit" variant="ghost" disabled={pending}>
      {pending ? (
        <Spinner data-icon="inline-start" />
      ) : (
        <HugeiconsIcon icon={Logout01Icon} data-icon="inline-start" />
      )}
      {pending
        ? t("signout.pending")
        : allDevices
          ? t("signout.all")
          : t("signout.one")}
    </Button>
  )
}
