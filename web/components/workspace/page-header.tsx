"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft01Icon } from "@hugeicons/core-free-icons"
import { buttonVariants } from "@/components/ui/button"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { useI18n } from "@/components/i18n-provider"

export function PageHeader({
  title,
  parent,
  children,
}: {
  title: string
  parent?: { name: string; href: string }
  children?: React.ReactNode
}) {
  const pathname = usePathname()
  const { t } = useI18n()
  const showBack = Boolean(parent && pathname !== parent.href)
  return (
    <header className="workspace-header">
      <div className="header-identity">
        <SidebarTrigger />
        {parent && showBack && (
          <Link
            href={parent.href}
            aria-label={t("ui.backTo", { name: parent.name })}
            className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
          >
            <HugeiconsIcon icon={ArrowLeft01Icon} />
          </Link>
        )}
        <div className="header-titles">
          {parent && (
            <Link href={parent.href} className="parent-link">
              {parent.name}
            </Link>
          )}
          <h1 id="page-title" tabIndex={-1}>
            {title}
          </h1>
        </div>
      </div>
      <div className="header-actions">{children}</div>
    </header>
  )
}
