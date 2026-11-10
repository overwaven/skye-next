"use client"

import Link from "next/link"
import { useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowRight01Icon,
  BrainIcon,
  Folder01Icon,
  Message01Icon,
  PinIcon,
  Plug01Icon,
  Robot01Icon,
  SparklesIcon,
  WorkflowIcon,
} from "@hugeicons/core-free-icons"
import { PageHeader } from "@/components/workspace/page-header"
import { ThreadMenu } from "@/components/workspace/thread-menu"
import { ProjectMenu } from "@/components/workspace/project-menu"
import {
  Item,
  ItemGroup,
  ItemContent,
  ItemTitle,
  ItemMedia,
  ItemActions,
} from "@/components/ui/item"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  librarySections,
  type LibrarySection,
  type NavigationData,
} from "@/lib/foundation"
import { useI18n } from "@/components/i18n-provider"

const sectionIcons = {
  memory: BrainIcon,
  connectors: Plug01Icon,
  skills: SparklesIcon,
  files: Folder01Icon,
  agents: Robot01Icon,
  automations: WorkflowIcon,
} satisfies Record<LibrarySection, typeof Add01Icon>

export function LibraryHome() {
  const { t } = useI18n()
  return (
    <div className="detail-page">
      <PageHeader title={t("library.title")} />
      <main className="detail-content">
        <ItemGroup>
          {Object.entries(librarySections).map(([key, value]) => (
            <Item key={key} render={<Link href={`/library/${key}`} />}>
              <ItemMedia>
                <HugeiconsIcon icon={sectionIcons[key as LibrarySection]} />
              </ItemMedia>
              <ItemContent>
                <ItemTitle>{t(value.nameKey)}</ItemTitle>
              </ItemContent>
              <ItemActions>
                <HugeiconsIcon icon={ArrowRight01Icon} />
              </ItemActions>
            </Item>
          ))}
        </ItemGroup>
      </main>
    </div>
  )
}

export function ResourceView({ section }: { section: LibrarySection }) {
  const { t } = useI18n()
  const content = librarySections[section]
  const name = t(content.nameKey)
  const action = t(content.actionKey)
  const SectionIcon = sectionIcons[section]
  const [query, setQuery] = useState("")
  return (
    <div className="detail-page">
      <PageHeader
        title={name}
        parent={{ name: t("library.title"), href: "/library" }}
      />
      <main className="detail-content">
        <div className="resource-toolbar">
          <Field className="resource-search">
            <FieldLabel htmlFor="resource-search" className="sr-only">
              {t("library.search")}
            </FieldLabel>
            <Input
              id="resource-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("library.search")}
            />
          </Field>
          <Dialog>
            <DialogTrigger render={<Button variant="outline" />}>
              <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
              {action}
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{action}</DialogTitle>
                <DialogDescription>
                  {t("library.previewOnly")}
                </DialogDescription>
              </DialogHeader>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="resource-name">
                    {section === "memory"
                      ? t("library.memory")
                      : t("common.name")}
                  </FieldLabel>
                  <Input id="resource-name" autoComplete="off" />
                </Field>
                <Field>
                  <FieldLabel htmlFor="resource-notes">{t("common.notes")}</FieldLabel>
                  <Textarea id="resource-notes" rows={3} />
                </Field>
              </FieldGroup>
              <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>
                  {t("common.close")}
                </DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
        <Empty className="resource-empty">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <HugeiconsIcon icon={SectionIcon} />
            </EmptyMedia>
            <EmptyTitle>
              {query
                ? t("library.noMatches")
                : t("library.empty", { name })}
            </EmptyTitle>
          </EmptyHeader>
          {query && (
            <Button variant="outline" onClick={() => setQuery("")}>
              {t("library.clearSearch")}
            </Button>
          )}
        </Empty>
      </main>
    </div>
  )
}

export function ProjectView({
  project,
  threads,
  projects,
  csrfToken,
}: {
  project: NavigationData["projects"][number]
  threads: NavigationData["threads"]
  projects: NavigationData["projects"]
  csrfToken?: string
}) {
  const { t } = useI18n()
  return (
    <div className="detail-page">
      <PageHeader
        title={`${project.emoji ? `${project.emoji} ` : ""}${project.name}`}
        parent={{ name: t("project.parent"), href: "/chat" }}
      >
        {csrfToken && <ProjectMenu project={project} csrfToken={csrfToken} />}
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link href={`/chat?project=${project.id}`} />}
        >
          {t("project.newThread")}
          <HugeiconsIcon icon={Add01Icon} data-icon="inline-end" />
        </Button>
      </PageHeader>
      <main className="detail-content resource-page">
        {threads.length === 0 ? (
          <Empty className="border border-dashed bg-card/30 py-14">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HugeiconsIcon icon={Folder01Icon} />
              </EmptyMedia>
              <EmptyTitle>{t("project.noThreads")}</EmptyTitle>
              <EmptyDescription>
                {t("project.noThreadsDescription")}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button
                nativeButton={false}
                render={<Link href={`/chat?project=${project.id}`} />}
              >
                {t("project.createFirst")}
                <HugeiconsIcon icon={Add01Icon} data-icon="inline-end" />
              </Button>
            </EmptyContent>
          </Empty>
        ) : (
          <div className="overflow-hidden rounded-3xl border bg-card/40">
            <div
              role="list"
              className="flex w-full flex-col divide-y divide-border"
            >
              {threads.map((thread) => (
                <Item
                  key={thread.id}
                  role="listitem"
                  className="relative rounded-none border-0 px-4 py-3.5 transition-colors hover:bg-muted/25 sm:px-5"
                >
                  <Link
                    href={`/chat/${thread.id}`}
                    aria-label={t("project.open", { title: thread.title })}
                    className="absolute inset-0 z-0 rounded-none outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset"
                  />
                  <ItemMedia
                    variant="icon"
                    className="pointer-events-none relative z-10 size-10 rounded-xl bg-muted"
                  >
                    <HugeiconsIcon
                      icon={thread.pinned ? PinIcon : Message01Icon}
                    />
                  </ItemMedia>
                  <ItemContent className="pointer-events-none relative z-10">
                    <ItemTitle>{thread.title}</ItemTitle>
                    <p className="line-clamp-2 text-sm text-muted-foreground">
                      {thread.preview || t("chats.noMessages")}
                    </p>
                  </ItemContent>
                  <ItemActions className="relative z-10">
                    {thread.archived && (
                      <span className="text-sm text-muted-foreground">
                        {t("project.archived")}
                      </span>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      nativeButton={false}
                      render={<Link href={`/chat/${thread.id}`} />}
                      aria-label={t("project.open", { title: thread.title })}
                    >
                      <HugeiconsIcon icon={ArrowRight01Icon} />
                    </Button>
                    {csrfToken && (
                      <ThreadMenu
                        thread={thread}
                        projects={projects}
                        csrfToken={csrfToken}
                      />
                    )}
                  </ItemActions>
                </Item>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
