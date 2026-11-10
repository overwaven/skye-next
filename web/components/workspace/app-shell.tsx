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
  PinIcon,
  BrainIcon,
  Plug01Icon,
  SparklesIcon,
  WorkflowIcon,
  Robot01Icon,
} from "@hugeicons/core-free-icons"
import { useTheme } from "next-themes"

import { useI18n } from "@/components/i18n-provider"
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
  const { t } = useI18n()
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

  const pinnedThreads = data.threads.filter((thread) => thread.pinned)
  const recentThreads = data.threads
    .filter((thread) => !thread.pinned)
    .slice(0, 8)

  function threadItem(thread: NavigationData["threads"][number]) {
    return (
      <SidebarMenuItem key={thread.id} className="relative">
        <SidebarMenuButton
          render={<Link href={`/chat/${thread.id}`} />}
          onClick={() => setOpenMobile(false)}
          isActive={pathname === `/chat/${thread.id}`}
          className="pe-10"
        >
          <HugeiconsIcon icon={thread.pinned ? PinIcon : Message01Icon} />
          <span>{thread.title}</span>
        </SidebarMenuButton>
        {data.accountConnected && data.csrfToken && (
          <div className="absolute end-1 top-1/2 -translate-y-1/2">
            <ThreadMenu
              thread={thread}
              projects={data.projects}
              csrfToken={data.csrfToken}
              onDeleted={() => {
                if (pathname === `/chat/${thread.id}`) router.push("/chat")
              }}
            />
          </div>
        )}
      </SidebarMenuItem>
    )
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
    <Sidebar role="navigation" aria-label={t("nav.workspace")}>
      <SidebarHeader className="px-5 pt-6 pb-5">
        <div className="flex items-center justify-between gap-3">
          <Link
            href="/chat"
            className="brand-lockup"
            onClick={() => setOpenMobile(false)}
            aria-label={t("nav.skyeHome")}
          >
            <SkyeMark />
            <span>skye</span>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label={t("nav.close")}
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
                <span>{t("nav.newThread")}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => setSearchOpen(true)}>
                <HugeiconsIcon icon={Search01Icon} />
                <span>{t("nav.search")}</span>
                <Kbd className="ms-auto">⌘ K</Kbd>
              </SidebarMenuButton>
              <CommandDialog
                open={searchOpen}
                onOpenChange={setSearchOpen}
                title={t("nav.searchTitle")}
                description={t("nav.searchDescription")}
              >
                <Command>
                  <CommandInput
                    aria-label={t("nav.searchAria")}
                    placeholder={t("nav.search")}
                  />
                  <CommandList>
                    <CommandEmpty>{t("nav.noMatches")}</CommandEmpty>
                    <CommandGroup heading={t("nav.threads")}>
                      <CommandItem
                        value={t("nav.newThread")}
                        onSelect={() => go("/chat")}
                      >
                        <HugeiconsIcon icon={Add01Icon} />
                        {t("nav.newThread")}
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
                    <CommandGroup heading={t("nav.projects")}>
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
                    <CommandGroup heading={t("nav.library")}>
                      <CommandItem
                        value={t("nav.library")}
                        onSelect={() => go("/library")}
                      >
                        <HugeiconsIcon icon={LibraryIcon} />
                        {t("nav.library")}
                      </CommandItem>
                      {Object.entries(librarySections).map(([key, value]) => (
                        <CommandItem
                          key={key}
                          value={t(value.nameKey)}
                          onSelect={() => go(`/library/${key}`)}
                        >
                          <HugeiconsIcon
                            icon={
                              libraryIcons[key as keyof typeof libraryIcons]
                            }
                          />
                          {t(value.nameKey)}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                    <CommandSeparator />
                    <CommandGroup heading={t("nav.settings")}>
                      <CommandItem onSelect={() => go("/settings/general")}>
                        <HugeiconsIcon icon={Settings01Icon} />
                        {t("nav.settings")}
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
            <SidebarGroupLabel>{t("nav.projects")}</SidebarGroupLabel>
            {data.accountConnected && data.csrfToken && (
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label={t("nav.newProject")}
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
        {pinnedThreads.length > 0 && (
          <SidebarGroup>
            <SidebarGroupLabel>{t("nav.pinned")}</SidebarGroupLabel>
            <SidebarMenu>{pinnedThreads.map(threadItem)}</SidebarMenu>
          </SidebarGroup>
        )}
        <SidebarGroup>
          <SidebarGroupLabel
            render={<Link href="/chats" />}
            onClick={() => setOpenMobile(false)}
            className="group/recent justify-between hover:text-sidebar-foreground"
          >
            {t("nav.recentThreads")}
            <HugeiconsIcon
              icon={ArrowRight01Icon}
              className="opacity-60 transition-opacity group-hover/recent:opacity-100"
            />
          </SidebarGroupLabel>
          <SidebarMenu>{recentThreads.map(threadItem)}</SidebarMenu>
        </SidebarGroup>
        {recentThreads.length === 0 && pinnedThreads.length === 0 && (
          <p className="px-3 pb-2 text-sm text-muted-foreground">
            {t("nav.noThreads")}
          </p>
        )}
      </SidebarContent>
      <SidebarFooter className="gap-3 p-4">
        {data.localPreview && (
          <span className="px-3 text-muted-foreground">{t("nav.localPreview")}</span>
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
          {t("nav.library")}
        </Link>
        {data.preview && (
          <Link
            href="/dev/states/ready"
            className="preview-link"
            onClick={() => setOpenMobile(false)}
          >
            {t("nav.preview")} <HugeiconsIcon icon={ArrowRight01Icon} />
            <span className="sr-only">{t("nav.syntheticData")}</span>
          </Link>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" className="w-full justify-start" />}
          >
            <HugeiconsIcon icon={Settings01Icon} data-icon="inline-start" />
            {t("nav.settings")}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top">
            <DropdownMenuGroup>
              <DropdownMenuLabel>{t("nav.appearance")}</DropdownMenuLabel>
              {[
                { value: "light", label: t("nav.themeLight") },
                { value: "dark", label: t("nav.themeDark") },
                { value: "system", label: t("nav.themeSystem") },
              ].map((theme) => (
                <DropdownMenuItem
                  key={theme.value}
                  onClick={() => setTheme(theme.value)}
                >
                  {theme.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
            <DropdownMenuGroup>
              <DropdownMenuLabel>{t("nav.account")}</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => go("/settings/general")}>
                {t("nav.openSettings")}
              </DropdownMenuItem>
              {!data.accountConnected && (
                <DropdownMenuItem onClick={() => go("/login")}>
                  {t("nav.signInTelegram")}
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
  const { t } = useI18n()
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
        {t("nav.skipToContent")}
      </a>
      <Navigation data={data} />
      <div className="workspace-canvas">{children}</div>
    </SidebarProvider>
  )
}
