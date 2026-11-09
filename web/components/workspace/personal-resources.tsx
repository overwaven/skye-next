"use client"

import type { ResourceSnapshot, SkillRecord } from "@/lib/contracts.generated"
import { ConnectorsResource } from "@/components/workspace/resources/connectors-resource"
import { MemoryResource } from "@/components/workspace/resources/memory-resource"
import { SkillsResource } from "@/components/workspace/resources/skills-resource"

export { resourceRequest } from "@/components/workspace/resources/resource-api"

export function PersonalResources({
  section,
  initial,
  csrf,
  detailId,
  skillDetail,
}: {
  section: "memory" | "connectors" | "skills"
  initial: ResourceSnapshot
  csrf: string
  detailId?: string
  skillDetail?: SkillRecord
}) {
  if (section === "memory")
    return <MemoryResource initial={initial} csrf={csrf} />
  if (section === "skills")
    return (
      <SkillsResource
        initial={initial}
        csrf={csrf}
        detailId={detailId}
        skillDetail={skillDetail}
      />
    )
  return (
    <ConnectorsResource initial={initial} csrf={csrf} detailId={detailId} />
  )
}
