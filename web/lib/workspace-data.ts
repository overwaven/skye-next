import "server-only"

import type { NavigationData } from "@/lib/foundation"
import { accountEnabled, getProjects, getSession, getThreads } from "@/lib/api"
import { devPreviewEnabled } from "@/lib/dev-preview"

export async function getNavigation(): Promise<NavigationData> {
  if (accountEnabled()) {
    const session = await getSession()
    const [projects, threads] = await Promise.all([getProjects(), getThreads()])
    return {
      preview: false,
      localPreview: devPreviewEnabled(),
      accountConnected: true,
      csrfToken: session.csrf_token,
      projects: projects.projects,
      threads: threads.threads.map((thread) => ({
        ...thread,
        label: thread.archived ? "Archived" : "",
      })),
    }
  }
  if (process.env.NODE_ENV === "development") {
    return (await import("@/lib/preview-data")).navigation
  }
  return { preview: false, projects: [], threads: [] }
}
