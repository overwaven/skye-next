import { notFound } from "next/navigation"
import { ResourceView } from "@/components/workspace/resource-view"
import { librarySections, type LibrarySection } from "@/lib/foundation"
import { accountEnabled, getResources, getSession } from "@/lib/api"
import { PersonalResources } from "@/components/workspace/personal-resources"

type Props = { params: Promise<{ section: string }> }

export async function generateMetadata({ params }: Props) {
  const { section } = await params
  return {
    title: librarySections[section as LibrarySection]?.name || "Library",
  }
}

export default async function Library({ params }: Props) {
  const { section } = await params
  if (!Object.hasOwn(librarySections, section)) notFound()
  if (
    accountEnabled() &&
    ["memory", "connectors", "skills"].includes(section)
  ) {
    const [initial, session] = await Promise.all([
      getResources(section),
      getSession(),
    ])
    return (
      <PersonalResources
        section={section as "memory" | "connectors" | "skills"}
        initial={initial}
        csrf={session.csrf_token}
      />
    )
  }
  return <ResourceView section={section as LibrarySection} />
}
