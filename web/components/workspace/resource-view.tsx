"use client"

import Link from "next/link"
import { useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowRight01Icon,
  BrainIcon,
  Folder01Icon,
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
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  librarySections,
  type LibrarySection,
  type NavigationData,
} from "@/lib/foundation"

const sectionIcons = {
  memory: BrainIcon,
  connectors: Plug01Icon,
  skills: SparklesIcon,
  files: Folder01Icon,
  agents: Robot01Icon,
  automations: WorkflowIcon,
} satisfies Record<LibrarySection, typeof Add01Icon>

export function LibraryHome() {
  return (
    <div className="detail-page">
      <PageHeader title="Library" />
      <main className="detail-content">
        <ItemGroup>
          {Object.entries(librarySections).map(([key, value]) => (
            <Item key={key} render={<Link href={`/library/${key}`} />}>
              <ItemMedia>
                <HugeiconsIcon icon={sectionIcons[key as LibrarySection]} />
              </ItemMedia>
              <ItemContent>
                <ItemTitle>{value.name}</ItemTitle>
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
  const content = librarySections[section]
  const SectionIcon = sectionIcons[section]
  const [query, setQuery] = useState("")
  return (
    <div className="detail-page">
      <PageHeader
        title={content.name}
        parent={{ name: "Library", href: "/library" }}
      />
      <main className="detail-content">
        <div className="resource-toolbar">
          <Field className="resource-search">
            <FieldLabel htmlFor="resource-search" className="sr-only">
              Search {content.name.toLowerCase()}
            </FieldLabel>
            <Input
              id="resource-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search"
            />
          </Field>
          <Dialog>
            <DialogTrigger render={<Button variant="outline" />}>
              <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
              {content.action}
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{content.action}</DialogTitle>
                <DialogDescription>
                  Preview only. Nothing is saved.
                </DialogDescription>
              </DialogHeader>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="resource-name">
                    {section === "memory" ? "Memory" : "Name"}
                  </FieldLabel>
                  <Input id="resource-name" autoComplete="off" />
                </Field>
                <Field>
                  <FieldLabel htmlFor="resource-notes">Notes</FieldLabel>
                  <Textarea id="resource-notes" rows={3} />
                </Field>
              </FieldGroup>
              <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>
                  Close
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
              {query ? "No matches" : `No ${content.name.toLowerCase()} yet`}
            </EmptyTitle>
          </EmptyHeader>
          {query && (
            <Button variant="outline" onClick={() => setQuery("")}>
              Clear search
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
  return (
    <div className="detail-page">
      <PageHeader
        title={`${project.emoji ? `${project.emoji} ` : ""}${project.name}`}
        parent={{ name: "Projects", href: "/chat" }}
      >
        {csrfToken && <ProjectMenu project={project} csrfToken={csrfToken} />}
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link href={`/chat?project=${project.id}`} />}
        >
          New thread
          <HugeiconsIcon icon={Add01Icon} data-icon="inline-end" />
        </Button>
      </PageHeader>
      <main className="detail-content">
        <Tabs defaultValue="threads">
          <TabsList aria-label="Project sections">
            <TabsTrigger value="threads">Threads</TabsTrigger>
            <TabsTrigger value="instructions">Instructions</TabsTrigger>
          </TabsList>
          <TabsContent value="threads">
            <ul className="thread-list">
              {threads.map((thread) => (
                <li key={thread.id}>
                  <div className="flex items-center gap-2">
                    <Link href={`/chat/${thread.id}`} className="flex-1">
                      <h3>{thread.title}</h3>
                      <HugeiconsIcon icon={ArrowRight01Icon} />
                    </Link>
                    {csrfToken && (
                      <ThreadMenu
                        thread={thread}
                        projects={projects}
                        csrfToken={csrfToken}
                      />
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </TabsContent>
          <TabsContent value="instructions">
            <FieldGroup className="instructions-editor">
              <Field>
                <FieldLabel htmlFor="project-instructions">
                  Project instructions
                </FieldLabel>
                <Textarea
                  id="project-instructions"
                  value={project.instructions}
                  maxLength={12000}
                  rows={6}
                  disabled
                />
                <FieldDescription>
                  {csrfToken
                    ? "Use Edit project to change instructions."
                    : "Project instructions are shared with Telegram."}
                </FieldDescription>
              </Field>
            </FieldGroup>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
