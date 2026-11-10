import { notFound } from "next/navigation"
import { Conversation } from "@/components/workspace/conversation"
import {
  accountEnabled,
  getProjects,
  getSession,
  getThreadState,
} from "@/lib/api"
import { getTranslator } from "@/lib/i18n-server"

type Props = { params: Promise<{ threadId: string }> }

export async function generateMetadata({ params }: Props) {
  const { t } = await getTranslator()
  if (accountEnabled()) return { title: t("meta.thread") }
  if (process.env.NODE_ENV !== "development")
    return { title: t("error.threadUnavailable") }
  const { threadId } = await params
  const { navigation } = await import("@/lib/preview-data")
  return {
    title:
      navigation.threads.find((thread) => thread.id === threadId)?.title ||
      t("chat.previewThread"),
  }
}

export default async function Thread({ params }: Props) {
  if (accountEnabled()) {
    const { threadId } = await params
    const [snapshot, projects, session] = await Promise.all([
      getThreadState(threadId),
      getProjects(),
      getSession(),
    ])
    return (
      <Conversation
        title={snapshot.thread.title}
        thread={snapshot.thread}
        csrfToken={session.csrf_token}
        messages={snapshot.messages}
        olderThan={snapshot.older_than}
        initialRun={snapshot.run}
        initialActivities={snapshot.activities}
        projects={projects.projects}
        project={projects.projects.find(
          (project) => project.id === snapshot.thread.project_id
        )}
      />
    )
  }
  if (process.env.NODE_ENV !== "development") notFound()
  const { threadId } = await params
  const { navigation, messages } = await import("@/lib/preview-data")
  const thread = navigation.threads.find((thread) => thread.id === threadId)
  if (!thread) notFound()
  return (
    <Conversation
      title={thread.title}
      project={navigation.projects.find(
        (project) => project.id === thread.project_id
      )}
      messages={messages}
      state="ready"
      preview
    />
  )
}
