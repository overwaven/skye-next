import { AppShell } from "@/components/workspace/app-shell"
import { getNavigation } from "@/lib/workspace-data"

// The opt-in flag is runtime configuration. Never prerender a shared account shell.
export const dynamic = "force-dynamic"

export default async function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <AppShell data={await getNavigation()}>{children}</AppShell>
}
