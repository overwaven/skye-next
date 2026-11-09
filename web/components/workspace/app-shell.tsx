"use client"

import { signOut } from "@/app/account-actions"
import { SignOutButton } from "@/components/workspace/sign-out"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  Search01Icon,
  Message01Icon,
  LibraryIcon,
  Settings01Icon,
  ArrowRight01Icon,
  Cancel01Icon,
  Folder01Icon,
  BrainIcon,
  Plug01Icon,
  SparklesIcon,
  WorkflowIcon,
  Robot01Icon,
} from "@hugeicons/core-free-icons"
import { useTheme } from "next-themes"

import { CreateProjectDialog } from "@/components/workspace/create-project-dialog"
import { ThreadMenu } from "@/components/workspace/thread-menu"
import { ProjectMenu } from "@/components/workspace/project-menu"
import { SkyeMark } from "@/components/skye-mark"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  useSidebar,
} from "@/components/ui/sidebar"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandDialog,
  CommandSeparator,
} from "@/components/ui/command"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Kbd } from "@/components/ui/kbd"
import { librarySections, type NavigationData } from "@/lib/foundation"

function Navigation({ data }: { data: NavigationData }) {
  const pathname = usePathname()
  const { setOpenMobile } = useSidebar()
  const { setTheme } = useTheme()
  const [searchOpen, setSearchOpen] = useState(false)
  const [projectDialog, setProjectDialog] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault()
        setSearchOpen((open) => !open)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  function go(href: string) {
    setSearchOpen(false)
    setOpenMobile(false)
    router.push(href)
  }

  const libraryIcons = {
    memory: BrainIcon,
    connectors: Plug01Icon,
    skills: SparklesIcon,
    files: Folder01Icon,
    agents: Robot01Icon,
    automations: WorkflowIcon,
  }

  return (
    <Sidebar role="navigation" aria-label="Workspace navigation">
      <SidebarHeader className="px-5 pt-6 pb-5">
        <div className="flex items-center justify-between gap-3">
          <Link
            href="/chat"
            className="brand-lockup"
            onClick={() => setOpenMobile(false)}
            aria-label="Skye home"
          >
            <SkyeMark />
            <span>skye</span>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Close navigation"
            onClick={() => setOpenMobile(false)}
          >
            <HugeiconsIcon icon={Cancel01Icon} />
          </Button>
        </div>
      </SidebarHeader>
      <SidebarContent className="px-3">
        <SidebarGroup>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                render={<Link href="/chat" />}
                onClick={() => setOpenMobile(false)}
                isActive={pathname === "/chat"}
              >
                <HugeiconsIcon icon={Add01Icon} />
                <span>New thread</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => setSearchOpen(true)}>
                <HugeiconsIcon icon={Search01Icon} />
                <span>Search</span>
                <Kbd className="ms-auto">⌘ K</Kbd>
              </SidebarMenuButton>
              <CommandDialog
                open={searchOpen}
                onOpenChange={setSearchOpen}
                title="Search"
                description="Search threads, projects and destinations."
              >
                <Command>
                  <CommandInput
                    aria-label="Search threads and destinations"
                    placeholder="Search"
                  />
                  <CommandList>
                    <CommandEmpty>No matches. Try another name.</CommandEmpty>
                    <CommandGroup heading="Threads">
                      <CommandItem
                        value="New thread"
                        onSelect={() => go("/chat")}
                      >
                        <HugeiconsIcon icon={Add01Icon} />
                        New thread
                      </CommandItem>
                      {data.threads.map((item) => (
                        <CommandItem
                          key={item.id}
                          value={`thread ${item.title} ${item.id}`}
                          onSelect={() => go(`/chat/${item.id}`)}
                        >
                          <HugeiconsIcon icon={Message01Icon} />
                          <span className="truncate">{item.title}</span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                    <CommandSeparator />
                    <CommandGroup heading="Projects">
                      {data.projects.map((item) => (
                        <CommandItem
                          key={item.id}
                          value={`project ${item.name} ${item.id}`}
                          onSelect={() => go(`/projects/${item.id}`)}
                        >
                          <span aria-hidden="true">{item.emoji || "📁"}</span>
                          <span className="truncate">{item.name}</span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                    <CommandSeparator />
                    <CommandGroup heading="Library">
                      <CommandItem
                        value="Library"
                        onSelect={() => go("/library")}
                      >
                        <HugeiconsIcon icon={LibraryIcon} />
                        Library
                      </CommandItem>
                      {Object.entries(librarySections).map(([key, value]) => (
                        <CommandItem
                          key={key}
                          value={value.name}
                          onSelect={() => go(`/library/${key}`)}
                        >
                          <HugeiconsIcon
                            icon={
                              libraryIcons[key as keyof typeof libraryIcons]
                            }
                          />
                          {value.name}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                    <CommandSeparator />
                    <CommandGroup heading="Settings">
                      <CommandItem onSelect={() => go("/settings/general")}>
                        <HugeiconsIcon icon={Settings01Icon} />
                        Settings
                      </CommandItem>
                    </CommandGroup>
                  </CommandList>
                </Command>
              </CommandDialog>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <div className="flex items-center justify-between pe-1">
            <SidebarGroupLabel>Projects</SidebarGroupLabel>
            {data.accountConnected && data.csrfToken && (
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="New project"
                onClick={() => setProjectDialog(true)}
              >
                <HugeiconsIcon icon={Add01Icon} />
              </Button>
            )}
          </div>
          <SidebarMenu>
            {data.projects.map((project) => (
              <SidebarMenuItem key={project.id} className="relative">
                <SidebarMenuButton
                  render={<Link href={`/projects/${project.id}`} />}
                  onClick={() => setOpenMobile(false)}
                  isActive={pathname === `/projects/${project.id}`}
                  className="pe-12"
                >
                  <span aria-hidden="true">{project.emoji || "📁"}</span>
                  <span>{project.name}</span>
                </SidebarMenuButton>
                {data.csrfToken && (
                  <div className="absolute end-1 top-1/2 -translate-y-1/2">
                    <ProjectMenu project={project} csrfToken={data.csrfToken} />
                  </div>
                )}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Recent threads</SidebarGroupLabel>
          <SidebarMenu>
            {data.threads.map((thread) => (
              <SidebarMenuItem key={thread.id} className="relative">
                <SidebarMenuButton
                  render={<Link href={`/chat/${thread.id}`} />}
                  onClick={() => setOpenMobile(false)}
                  isActive={pathname === `/chat/${thread.id}`}
                  className="pe-10"
                >
                  <HugeiconsIcon icon={Message01Icon} />
                  <span>{thread.title}</span>
                </SidebarMenuButton>
                {data.accountConnected && data.csrfToken && (
                  <div className="absolute end-1 top-1/2 -translate-y-1/2">
                    <ThreadMenu
                      thread={thread}
                      projects={data.projects}
                      csrfToken={data.csrfToken}
                      onDeleted={() => {
                        if (pathname === `/chat/${thread.id}`)
                          router.push("/chat")
                      }}
                    />
                  </div>
                )}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-3 p-4">
        {data.localPreview && (
          <span className="px-3 text-muted-foreground">Local preview</span>
        )}
        <Link
          className={buttonVariants({
            variant: "ghost",
            className: "w-full justify-start",
          })}
          href="/library"
          onClick={() => setOpenMobile(false)}
        >
          <HugeiconsIcon icon={LibraryIcon} data-icon="inline-start" />
          Library
        </Link>
        {data.preview && (
          <Link
            href="/dev/states/ready"
            className="preview-link"
            onClick={() => setOpenMobile(false)}
          >
            Preview <HugeiconsIcon icon={ArrowRight01Icon} />
            <span className="sr-only"> — synthetic data, not connected</span>
          </Link>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" className="w-full justify-start" />}
          >
            <HugeiconsIcon icon={Settings01Icon} data-icon="inline-start" />
            Settings
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top">
            <DropdownMenuGroup>
              <DropdownMenuLabel>Appearance</DropdownMenuLabel>
              {["Light", "Dark", "System"].map((name) => (
                <DropdownMenuItem
                  key={name}
                  onClick={() => setTheme(name.toLowerCase())}
                >
                  {name}
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
            <DropdownMenuGroup>
              <DropdownMenuLabel>Account</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => go("/settings/general")}>
                Open settings
              </DropdownMenuItem>
              {!data.accountConnected && (
                <DropdownMenuItem onClick={() => go("/login")}>
                  Sign in with Telegram
                </DropdownMenuItem>
              )}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        {data.accountConnected && (
          <form action={signOut}>
            <SignOutButton />
          </form>
        )}
      </SidebarFooter>
      {data.accountConnected && data.csrfToken && (
        <CreateProjectDialog
          open={projectDialog}
          onOpenChange={setProjectDialog}
          csrfToken={data.csrfToken}
          onCreated={() => router.refresh()}
        />
      )}
    </Sidebar>
  )
}

export function AppShell({
  data,
  children,
}: {
  data: NavigationData
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const shell = useRef<HTMLDivElement>(null)
  const previousPath = useRef(pathname)
  useEffect(() => {
    if (shell.current) shell.current.dataset.hydrated = "true"
  }, [])
  useEffect(() => {
    // Telegram can change projects, threads, memory and connected apps while
    // the web tab is in the background. Revalidate when the person returns.
    const refresh = () => {
      if (document.visibilityState === "visible") router.refresh()
    }
    window.addEventListener("focus", refresh)
    document.addEventListener("visibilitychange", refresh)
    return () => {
      window.removeEventListener("focus", refresh)
      document.removeEventListener("visibilitychange", refresh)
    }
  }, [router])
  useEffect(() => {
    if (previousPath.current === pathname) return
    previousPath.current = pathname
    document
      .querySelector<HTMLElement>("#page-title")
      ?.focus({ preventScroll: true })
  }, [pathname])
  return (
    <SidebarProvider className="workspace-shell" ref={shell}>
      <a href="#page-title" className="skip-link">
        Skip to content
      </a>
      <Navigation data={data} />
      <div className="workspace-canvas">{children}</div>
    </SidebarProvider>
  )
}
