import type { Metadata } from "next"
import { ChatsView } from "@/components/workspace/chats-view"
import { accountEnabled, getProjects, getSession, getThreads } from "@/lib/api"

export const metadata: Metadata = { title: "Chats" }

export default async function Chats() {
  if (!accountEnabled())
    return <ChatsView threads={[]} projects={[]} />
  const [projects, threads, session] = await Promise.all([
    getProjects(),
    getThreads(),
    getSession(),
  ])
  return (
    <ChatsView
      threads={threads.threads.map((thread) => ({
        ...thread,
        label: thread.archived ? "Archived" : "",
      }))}
      projects={projects.projects}
      csrfToken={session.csrf_token}
    />
  )
}
