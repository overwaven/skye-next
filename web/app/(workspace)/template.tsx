"use client"

import { usePathname } from "next/navigation"

export default function WorkspaceTemplate({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  return (
    <div key={pathname} className="page-transition">
      {children}
    </div>
  )
}
