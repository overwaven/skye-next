import { cn } from "cn"
import { HugeiconsIcon } from "@hugeicons/react"
import { Loading03Icon } from "@hugeicons/core-free-icons"
import { useI18n } from "@/components/i18n-provider"

function Spinner({ className, ...props }: Omit<React.ComponentProps<typeof HugeiconsIcon>, "icon">) {
  const { t } = useI18n()
  return (
    <HugeiconsIcon icon={Loading03Icon} strokeWidth={2} data-slot="spinner" role="status" aria-label={t("ui.loading")} className={cn("size-4 animate-spin", className)} {...props} />
  )
}

export { Spinner }
