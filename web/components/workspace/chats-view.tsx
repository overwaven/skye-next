"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowDown01Icon,
  ArrowRight01Icon,
  Archive01Icon,
  ArchiveRestoreIcon,
  Delete02Icon,
  FilterIcon,
  Message01Icon,
  PinIcon,
  PinOffIcon,
  Search01Icon,
} from "@hugeicons/core-free-icons"
import { PageHeader } from "@/components/workspace/page-header"
import { ResourceSearch } from "@/components/workspace/resources/resource-ui"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ButtonGroup } from "@/components/ui/button-group"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Item, ItemActions, ItemContent } from "@/components/ui/item"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import type { NavigationData } from "@/lib/foundation"

type Thread = NavigationData["threads"][number]
type Project = NavigationData["projects"][number]

function projectOf(thread: Thread, projects: Project[]) {
  return projects.find((project) => project.id === thread.project_id)
}

function projectLabel(
  filter: string,
  projects: Project[]
): string {
  if (filter === "all") return "All projects"
  if (filter === "none") return "No project"
  return projects.find((project) => project.id === filter)?.name ?? "All projects"
}

export function ChatsView({
  threads,
  projects,
  csrfToken,
}: {
  threads: Thread[]
  projects: Project[]
  csrfToken?: string
}) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [projectFilter, setProjectFilter] = useState("all")
  const [filterOpen, setFilterOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [removeOpen, setRemoveOpen] = useState(false)

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return threads.filter((thread) => {
      if (projectFilter === "none" && thread.project_id !== null) return false
      if (
        projectFilter !== "all" &&
        projectFilter !== "none" &&
        thread.project_id !== projectFilter
      )
        return false
      return (
        !needle ||
        `${thread.title} ${thread.preview ?? ""}`
          .toLowerCase()
          .includes(needle)
      )
    })
  }, [threads, query, projectFilter])

  const selectedThreads = threads.filter((thread) => selected.has(thread.id))
  const allPinned =
    selectedThreads.length > 0 &&
    selectedThreads.every((thread) => thread.pinned)
  const allArchived =
    selectedThreads.length > 0 &&
    selectedThreads.every((thread) => thread.archived)
  const allSelected =
    filtered.length > 0 && filtered.every((thread) => selected.has(thread.id))

  function toggle(id: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function toggleAll() {
    setSelected(
      allSelected ? new Set() : new Set(filtered.map((thread) => thread.id))
    )
  }

  async function runBatch(
    work: (id: string) => Promise<Response>,
    success: string
  ) {
    if (!csrfToken || selected.size === 0) return
    setBusy(true)
    setError("")
    try {
      const responses = await Promise.all([...selected].map(work))
      if (responses.some((response) => !response.ok))
        throw new Error("Some chats could not be updated.")
      setSelected(new Set())
      setRemoveOpen(false)
      router.refresh()
      toast.add({ title: success, type: "success" })
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "The action could not be completed."
      setError(message)
      toast.add({ title: "Action failed", description: message, type: "error" })
    } finally {
      setBusy(false)
    }
  }

  function updateSelected(body: Record<string, unknown>, success: string) {
    return runBatch(
      (id) =>
        fetch(`/api/v1/threads/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken ?? "",
          },
          body: JSON.stringify(body),
        }),
      success
    )
  }

  function clearFilters() {
    setQuery("")
    setProjectFilter("all")
  }

  return (
    <div className="detail-page">
      <PageHeader title="Chats" parent={{ name: "Skye", href: "/chat" }}>
        <Button
          nativeButton={false}
          render={<Link href="/chat" />}
        >
          New thread
          <HugeiconsIcon icon={Add01Icon} data-icon="inline-end" />
        </Button>
      </PageHeader>
      <main className="detail-content resource-page">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <ResourceSearch
            id="chats-search"
            value={query}
            onChange={setQuery}
            placeholder="Search chats"
            className="sm:max-w-sm"
          />
          <DropdownMenu open={filterOpen} onOpenChange={setFilterOpen}>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="outline"
                  className="w-full justify-between gap-2 sm:w-auto"
                />
              }
            >
              <span className="flex items-center gap-2">
                <HugeiconsIcon icon={FilterIcon} />
                {projectLabel(projectFilter, projects)}
              </span>
              <HugeiconsIcon
                icon={ArrowDown01Icon}
                className="text-muted-foreground"
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuGroup>
                <DropdownMenuRadioGroup
                  value={projectFilter}
                  onValueChange={(value) => {
                    setProjectFilter(value)
                    setFilterOpen(false)
                  }}
                >
                  <DropdownMenuRadioItem value="all">
                    All projects
                  </DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="none">
                    No project
                  </DropdownMenuRadioItem>
                  {projects.map((project) => (
                    <DropdownMenuRadioItem
                      key={project.id}
                      value={project.id}
                    >
                      <span aria-hidden="true">{project.emoji || "📁"}</span>
                      {project.name}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {filtered.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleAll}
                aria-label="Select all visible chats"
              />
              {selected.size > 0
                ? `${selected.size} selected`
                : `${filtered.length} ${filtered.length === 1 ? "chat" : "chats"}`}
            </label>
            {selected.size > 0 && (
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <div className="max-w-full overflow-x-auto">
                  <ButtonGroup>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        void updateSelected(
                          { pinned: !allPinned },
                          allPinned ? "Chats unpinned" : "Chats pinned"
                        )
                      }
                    >
                      <HugeiconsIcon
                        icon={allPinned ? PinOffIcon : PinIcon}
                        data-icon="inline-start"
                      />
                      {allPinned ? "Unpin" : "Pin"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        void updateSelected(
                          { archived: !allArchived },
                          allArchived ? "Chats unarchived" : "Chats archived"
                        )
                      }
                    >
                      <HugeiconsIcon
                        icon={allArchived ? ArchiveRestoreIcon : Archive01Icon}
                        data-icon="inline-start"
                      />
                      {allArchived ? "Unarchive" : "Archive"}
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                          />
                        }
                      >
                        Move to
                        <HugeiconsIcon
                          icon={ArrowDown01Icon}
                          data-icon="inline-end"
                        />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuGroup>
                          <DropdownMenuItem
                            onClick={() =>
                              void updateSelected(
                                { project_id: null },
                                "Chats moved"
                              )
                            }
                          >
                            No project
                          </DropdownMenuItem>
                        </DropdownMenuGroup>
                        <DropdownMenuSeparator />
                        <DropdownMenuGroup>
                          {projects.map((project) => (
                            <DropdownMenuItem
                              key={project.id}
                              onClick={() =>
                                void updateSelected(
                                  { project_id: project.id },
                                  "Chats moved"
                                )
                              }
                            >
                              <span aria-hidden="true">
                                {project.emoji || "📁"}
                              </span>
                              {project.name}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuGroup>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={busy}
                      onClick={() => setRemoveOpen(true)}
                    >
                      <HugeiconsIcon
                        icon={Delete02Icon}
                        data-icon="inline-start"
                      />
                      Delete
                    </Button>
                  </ButtonGroup>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() => setSelected(new Set())}
                >
                  Clear
                </Button>
                {busy && <Spinner />}
              </div>
            )}
          </div>
        )}

        {threads.length === 0 ? (
          <Empty className="border border-dashed bg-card/30 py-14">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HugeiconsIcon icon={Message01Icon} />
              </EmptyMedia>
              <EmptyTitle>No chats yet</EmptyTitle>
              <EmptyDescription>
                Start a conversation and it will appear here.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button nativeButton={false} render={<Link href="/chat" />}>
                Start a chat
                <HugeiconsIcon icon={Add01Icon} data-icon="inline-end" />
              </Button>
            </EmptyContent>
          </Empty>
        ) : filtered.length === 0 ? (
          <Empty className="border border-dashed bg-card/30 py-14">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HugeiconsIcon icon={Search01Icon} />
              </EmptyMedia>
              <EmptyTitle>No chats found</EmptyTitle>
              <EmptyDescription>
                Try a different search or project.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" onClick={clearFilters}>
                Clear filters
              </Button>
            </EmptyContent>
          </Empty>
        ) : (
          <div className="overflow-hidden rounded-3xl border bg-card/40">
            <div
              role="list"
              className="flex w-full flex-col divide-y divide-border"
            >
              {filtered.map((thread) => {
                const project = projectOf(thread, projects)
                return (
                  <Item
                    key={thread.id}
                    role="listitem"
                    className="flex-nowrap items-start rounded-none border-0 px-4 py-4 sm:px-5"
                  >
                    <Checkbox
                      className="mt-1"
                      checked={selected.has(thread.id)}
                      onCheckedChange={(checked) =>
                        toggle(thread.id, Boolean(checked))
                      }
                      aria-label={`Select ${thread.title}`}
                    />
                    <ItemContent className="gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <Link
                          href={`/chat/${thread.id}`}
                          className="truncate text-sm font-medium underline-offset-4 hover:underline"
                        >
                          {thread.title}
                        </Link>
                        {thread.pinned && (
                          <HugeiconsIcon
                            icon={PinIcon}
                            className="size-3.5 shrink-0 text-muted-foreground"
                            aria-label="Pinned"
                          />
                        )}
                        {thread.archived && (
                          <Badge variant="outline">Archived</Badge>
                        )}
                      </div>
                      <p className="line-clamp-2 text-sm text-muted-foreground">
                        {thread.preview || "No messages yet."}
                      </p>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary" className="font-normal">
                          <span aria-hidden="true">
                            {project?.emoji || "📁"}
                          </span>
                          {project?.name ?? "No project"}
                        </Badge>
                      </div>
                    </ItemContent>
                    <ItemActions className="self-start">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        nativeButton={false}
                        render={<Link href={`/chat/${thread.id}`} />}
                        aria-label={`Open ${thread.title}`}
                      >
                        <HugeiconsIcon icon={ArrowRight01Icon} />
                      </Button>
                    </ItemActions>
                  </Item>
                )
              })}
            </div>
          </div>
        )}
      </main>

      <AlertDialog
        open={removeOpen}
        onOpenChange={(open) => {
          if (!open && !busy) setRemoveOpen(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selected.size} {selected.size === 1 ? "chat" : "chats"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Their messages, runs and activity are removed. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() =>
                void runBatch(
                  (id) =>
                    fetch(`/api/v1/threads/${encodeURIComponent(id)}`, {
                      method: "DELETE",
                      headers: { "X-CSRF-Token": csrfToken ?? "" },
                    }),
                  "Chats deleted"
                )
              }
            >
              {busy && <Spinner data-icon="inline-start" />}
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
