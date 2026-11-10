"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowDown01Icon,
  Archive01Icon,
  ArchiveRestoreIcon,
  CheckListIcon,
  Delete02Icon,
  FilterIcon,
  Folder01Icon,
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
import { Item, ItemContent } from "@/components/ui/item"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import { useI18n } from "@/components/i18n-provider"
import type { NavigationData } from "@/lib/foundation"
import { cn } from "@/lib/utils"
import type { MessageKey, MessageValues } from "@/lib/i18n"

type Thread = NavigationData["threads"][number]
type Project = NavigationData["projects"][number]
type Translate = (key: MessageKey, values?: MessageValues) => string

function projectOf(thread: Thread, projects: Project[]) {
  return projects.find((project) => project.id === thread.project_id)
}

function projectLabel(
  filter: string,
  projects: Project[],
  t: Translate
): string {
  if (filter === "all") return t("chats.allProjects")
  if (filter === "none") return t("chats.noProject")
  return projects.find((project) => project.id === filter)?.name ??
    t("chats.allProjects")
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
  const { t, tn } = useI18n()
  const [query, setQuery] = useState("")
  const [projectFilter, setProjectFilter] = useState("all")
  const [filterOpen, setFilterOpen] = useState(false)
  const [selectMode, setSelectMode] = useState(false)
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

  function enterSelectMode() {
    setSelected(new Set())
    setSelectMode(true)
  }

  function exitSelectMode() {
    setSelectMode(false)
    setSelected(new Set())
  }

  function toggle(id: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
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
        throw new Error(t("chats.someFailed"))
      setSelected(new Set())
      setSelectMode(false)
      setRemoveOpen(false)
      router.refresh()
      toast.add({ title: success, type: "success" })
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : t("chats.actionNotCompleted")
      setError(message)
      toast.add({
        title: t("chats.actionFailed"),
        description: message,
        type: "error",
      })
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
      <PageHeader
        title={t("chats.title")}
        parent={{ name: "Skye", href: "/chat" }}
      >
        {threads.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={selectMode ? exitSelectMode : enterSelectMode}
          >
            <HugeiconsIcon icon={CheckListIcon} data-icon="inline-start" />
            {selectMode ? t("chats.done") : t("chats.select")}
          </Button>
        )}
        {!selectMode && (
          <Button
            nativeButton={false}
            render={<Link href="/chat" />}
            aria-label={t("chats.newThread")}
          >
            <span className="hidden sm:inline">{t("chats.newThread")}</span>
            <HugeiconsIcon icon={Add01Icon} data-icon="inline-end" />
          </Button>
        )}
      </PageHeader>
      <main className="detail-content resource-page">
        {threads.length > 0 && (
          <div className="flex min-h-10 flex-col gap-3 sm:flex-row sm:items-center">
            {selectMode ? (
              <>
                <span className="flex min-h-10 shrink-0 items-center text-sm text-muted-foreground">
                  {tn("chats.selected", selected.size)}
                </span>
                <div className="flex min-h-10 min-w-0 flex-1 items-center overflow-x-auto">
                  <ButtonGroup aria-label={tn("chats.selected", selected.size)}>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy || selected.size === 0}
                      aria-label={allPinned ? t("chats.unpin") : t("chats.pin")}
                      onClick={() =>
                        void updateSelected(
                          { pinned: !allPinned },
                          allPinned
                            ? t("chats.unpinnedToast")
                            : t("chats.pinnedToast")
                        )
                      }
                    >
                      <HugeiconsIcon icon={allPinned ? PinOffIcon : PinIcon} />
                      <span className="hidden sm:inline">
                        {allPinned ? t("chats.unpin") : t("chats.pin")}
                      </span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy || selected.size === 0}
                      aria-label={
                        allArchived ? t("chats.unarchive") : t("chats.archive")
                      }
                      onClick={() =>
                        void updateSelected(
                          { archived: !allArchived },
                          allArchived
                            ? t("chats.unarchivedToast")
                            : t("chats.archivedToast")
                        )
                      }
                    >
                      <HugeiconsIcon
                        icon={allArchived ? ArchiveRestoreIcon : Archive01Icon}
                      />
                      <span className="hidden sm:inline">
                        {allArchived
                          ? t("chats.unarchive")
                          : t("chats.archive")}
                      </span>
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy || selected.size === 0}
                            aria-label={t("chats.moveTo")}
                          />
                        }
                      >
                        <HugeiconsIcon icon={Folder01Icon} />
                        <span className="hidden sm:inline">
                          {t("chats.moveTo")}
                        </span>
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
                                t("chats.movedToast")
                              )
                            }
                          >
                            {t("chats.noProject")}
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
                                  t("chats.movedToast")
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
                      disabled={busy || selected.size === 0}
                      aria-label={t("chats.delete")}
                      onClick={() => setRemoveOpen(true)}
                    >
                      <HugeiconsIcon icon={Delete02Icon} />
                      <span className="hidden sm:inline">
                        {t("chats.delete")}
                      </span>
                    </Button>
                  </ButtonGroup>
                </div>
                {busy && <Spinner />}
              </>
            ) : (
              <>
                <ResourceSearch
                  id="chats-search"
                  value={query}
                  onChange={setQuery}
                  placeholder={t("chats.search")}
                  className="sm:max-w-sm"
                />
                <DropdownMenu open={filterOpen} onOpenChange={setFilterOpen}>
                  <DropdownMenuTrigger
                    render={
                      <Button
                        variant="outline"
                        className="h-10 w-full justify-between gap-2 sm:w-auto"
                      />
                    }
                  >
                    <span className="flex items-center gap-2">
                      <HugeiconsIcon icon={FilterIcon} />
                      {projectLabel(projectFilter, projects, t)}
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
                          {t("chats.allProjects")}
                        </DropdownMenuRadioItem>
                        <DropdownMenuRadioItem value="none">
                          {t("chats.noProject")}
                        </DropdownMenuRadioItem>
                        {projects.map((project) => (
                          <DropdownMenuRadioItem
                            key={project.id}
                            value={project.id}
                          >
                            <span aria-hidden="true">
                              {project.emoji || "📁"}
                            </span>
                            {project.name}
                          </DropdownMenuRadioItem>
                        ))}
                      </DropdownMenuRadioGroup>
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {threads.length === 0 ? (
          <Empty className="border border-dashed bg-card/30 py-14">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HugeiconsIcon icon={Message01Icon} />
              </EmptyMedia>
              <EmptyTitle>{t("chats.noChats")}</EmptyTitle>
              <EmptyDescription>
                {t("chats.noChatsDescription")}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button nativeButton={false} render={<Link href="/chat" />}>
                {t("chats.startChat")}
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
              <EmptyTitle>{t("chats.noFound")}</EmptyTitle>
              <EmptyDescription>
                {t("chats.tryDifferent")}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" onClick={clearFilters}>
                {t("chats.clearFilters")}
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
                const picked = selected.has(thread.id)
                return (
                  <Item
                    key={thread.id}
                    role="listitem"
                    className="relative flex-nowrap items-start rounded-none border-0 px-4 py-4 transition-colors hover:bg-muted/25 sm:px-5"
                  >
                    <button
                      type="button"
                      aria-label={
                        selectMode
                          ? t("chats.selectAria", { title: thread.title })
                          : t("chats.open", { title: thread.title })
                      }
                      aria-pressed={selectMode ? picked : undefined}
                      className="absolute inset-0 z-0 rounded-none outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset"
                      onClick={() =>
                        selectMode
                          ? toggle(thread.id, !picked)
                          : router.push(`/chat/${thread.id}`)
                      }
                    />
                    <div
                      className={cn(
                        "relative z-10 mt-1 shrink-0 overflow-hidden transition-[width,margin,opacity,transform] duration-200 ease-out",
                        selectMode
                          ? "w-4 translate-x-0 opacity-100"
                          : "-me-3.5 w-0 -translate-x-1 opacity-0"
                      )}
                      aria-hidden={!selectMode}
                    >
                      <Checkbox
                        checked={picked}
                        disabled={!selectMode}
                        tabIndex={selectMode ? 0 : -1}
                        onCheckedChange={(checked) =>
                          toggle(thread.id, Boolean(checked))
                        }
                        aria-label={t("chats.selectAria", {
                          title: thread.title,
                        })}
                      />
                    </div>
                    <ItemContent className="pointer-events-none relative z-10 gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-sm font-medium">
                          {thread.title}
                        </span>
                        {thread.pinned && (
                          <HugeiconsIcon
                            icon={PinIcon}
                            className="size-3.5 shrink-0 text-muted-foreground"
                            aria-label={t("chats.pinned")}
                          />
                        )}
                        {thread.archived && (
                          <Badge variant="outline">
                            {t("common.archived")}
                          </Badge>
                        )}
                      </div>
                      <p className="line-clamp-2 text-sm text-muted-foreground">
                        {thread.preview || t("chats.noMessages")}
                      </p>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary" className="font-normal">
                          <span aria-hidden="true">
                            {project?.emoji || "📁"}
                          </span>
                          {project?.name ?? t("chats.noProject")}
                        </Badge>
                      </div>
                    </ItemContent>
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
              {tn("chats.deleteTitle", selected.size)}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("chats.deleteDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>
              {t("common.cancel")}
            </AlertDialogCancel>
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
                  t("chats.deletedToast")
                )
              }
            >
              {busy && <Spinner data-icon="inline-start" />}
              {t("chats.deleteConfirm")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
