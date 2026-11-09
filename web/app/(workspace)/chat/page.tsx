import type { Metadata } from "next"
import { Conversation } from "@/components/workspace/conversation"
import { accountEnabled, getProjects, getSession } from "@/lib/api"

export const metadata: Metadata = { title: "New thread" }

type Props = { searchParams: Promise<{ project?: string }> }

export default async function NewThread({ searchParams }: Props) {
  if (accountEnabled()) {
    const [session, projects] = await Promise.all([getSession(), getProjects()])
    const { project } = await searchParams
    return (
      <Conversation
        csrfToken={session.csrf_token}
        projects={projects.projects}
        defaultProjectId={
          projects.projects.some((item) => item.id === project)
            ? (project ?? null)
            : null
        }
      />
    )
  }
  return <Conversation />
}
