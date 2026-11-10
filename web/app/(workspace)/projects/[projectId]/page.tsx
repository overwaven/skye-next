import { notFound } from "next/navigation"
import { ProjectView } from "@/components/workspace/resource-view"
import { accountEnabled, getProjects, getSession, getThreads } from "@/lib/api"
import { getTranslator } from "@/lib/i18n-server"

type Props = { params: Promise<{ projectId: string }> }

export async function generateMetadata({ params }: Props) {
  const { t } = await getTranslator()
  if (accountEnabled()) return { title: t("meta.project") }
  if (process.env.NODE_ENV !== "development")
    return { title: t("error.projectUnavailable") }
  const { projectId } = await params
  const { navigation } = await import("@/lib/preview-data")
  return {
    title:
      navigation.projects.find((project) => project.id === projectId)?.name ||
      t("meta.project"),
  }
}

export default async function Project({ params }: Props) {
  if (accountEnabled()) {
    const { projectId } = await params
    const [projects, threads, session] = await Promise.all([
      getProjects(),
      getThreads(),
      getSession(),
    ])
    const project = projects.projects.find((item) => item.id === projectId)
    if (!project) notFound()
    return (
      <ProjectView
        project={project}
        projects={projects.projects}
        csrfToken={session.csrf_token}
        threads={threads.threads
          .filter((thread) => thread.project_id === projectId)
          .map((thread) => ({ ...thread, label: "" }))}
      />
    )
  }
  if (process.env.NODE_ENV !== "development") notFound()
  const { projectId } = await params
  const { navigation } = await import("@/lib/preview-data")
  const project = navigation.projects.find(
    (project) => project.id === projectId
  )
  if (!project) notFound()
  return (
    <ProjectView
      project={project}
      projects={navigation.projects}
      threads={navigation.threads.filter(
        (thread) => thread.project_id === project.id
      )}
    />
  )
}
