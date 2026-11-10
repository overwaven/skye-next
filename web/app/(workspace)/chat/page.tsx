import type { Metadata } from "next"
import { Conversation } from "@/components/workspace/conversation"
import { accountEnabled, getProjects, getSession } from "@/lib/api"
import { getTranslator } from "@/lib/i18n-server"

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getTranslator()
  return { title: t("meta.newThread") }
}

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
