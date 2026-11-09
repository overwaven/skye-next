"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import { Edit02Icon, MoreHorizontalIcon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu"
import { CreateProjectDialog } from "@/components/workspace/create-project-dialog"
import type { NavigationData } from "@/lib/foundation"

export function ProjectMenu({
  project,
  csrfToken,
}: {
  project: NavigationData["projects"][number]
  csrfToken: string
}) {
  const [editing, setEditing] = useState(false)
  const router = useRouter()
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              className="row-overflow"
              aria-label={`Actions for ${project.name}`}
            />
          }
        >
          <HugeiconsIcon icon={MoreHorizontalIcon} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => setEditing(true)}>
              <HugeiconsIcon icon={Edit02Icon} />
              Edit project
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {editing && (
        <CreateProjectDialog
          key={`${project.id}:${project.revision}`}
          project={project}
          open={editing}
          onOpenChange={setEditing}
          csrfToken={csrfToken}
          onCreated={() => router.refresh()}
        />
      )}
    </>
  )
}
