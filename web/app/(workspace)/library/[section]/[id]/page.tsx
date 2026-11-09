import { notFound } from "next/navigation"
import { getResources, getSession, getSkill, accountEnabled } from "@/lib/api"
import { PersonalResources } from "@/components/workspace/personal-resources"

type Props = { params: Promise<{ section: string; id: string }> }
export async function generateMetadata({ params }: Props) {
  const { section } = await params
  return { title: section === "skills" ? "Skill" : "Connector" }
}
export default async function ResourceDetail({ params }: Props) {
  const { section, id } = await params
  if (!accountEnabled() || (section !== "skills" && section !== "connectors"))
    notFound()
  const [initial, session, skill] = await Promise.all([
    getResources(section),
    getSession(),
    section === "skills" ? getSkill(id) : undefined,
  ])
  if (
    !(
      section === "skills" ? (initial.skills ?? []) : (initial.connectors ?? [])
    ).some((item) => item.id === id)
  )
    notFound()
  return (
    <PersonalResources
      section={section}
      initial={initial}
      csrf={session.csrf_token}
      detailId={id}
      skillDetail={skill}
    />
  )
}
