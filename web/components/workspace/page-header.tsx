"use client"

import Link from "next/link"
import { SidebarTrigger } from "@/components/ui/sidebar"

export function PageHeader({
  title,
  parent,
  children,
}: {
  title: string
  parent?: { name: string; href: string }
  children?: React.ReactNode
}) {
  return (
    <header className="workspace-header">
      <div className="header-identity">
        <SidebarTrigger />
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
