"use client"
import * as React from "react"
import { useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowDown01Icon,
  ArrowUp02Icon,
  Attachment01Icon,
  BrainIcon,
  CodeIcon,
  Folder01Icon,
  Image01Icon,
  Mic01Icon,
  Plug01Icon,
  Search01Icon,
  ToolsIcon,
  WorkflowIcon,
  Square01Icon,
} from "@hugeicons/core-free-icons"
import { SkyeMark } from "@/components/skye-mark"
import { PageHeader } from "@/components/workspace/page-header"
import { ContextPanel } from "@/components/workspace/context-panel"
import { Markdown } from "@/components/workspace/markdown"
import { MediaPicker } from "@/components/workspace/media-picker"
import { PreviewableAttachment } from "@/components/workspace/attachment-preview"
import { CreateProjectDialog } from "@/components/workspace/create-project-dialog"
import { VoiceRecorder } from "@/components/workspace/voice-recorder"
import { Button } from "@/components/ui/button"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Message, MessageContent, MessageHeader } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AttachmentGroup } from "@/components/ui/attachment"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace"
import { Spinner } from "@/components/ui/spinner"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type {
  APIError,
  ActivityRecord,
  FilePart,
  MediaRecord,
  MessageEvent as StreamMessageEvent,
  ProjectRecord,
  RunDetails,
  RunStatus,
  Snapshot,
  ThreadRecord,
  VisibleMessage,
} from "@/lib/contracts.generated"
import type { PreviewState } from "@/lib/foundation"

type Connection = "connecting" | "live" | "reconnecting"

type PendingSend = {
  requestId: string
  text: string
  files: MediaRecord[]
  transcripts: Record<string, string>
}

type Step = {
  key: string
  label: string
  status: "running" | "completed" | "failed"
  category: string
}

const ACTIVE = new Set(["accepted", "running", "cancelling"])

function steps(activities: ActivityRecord[]): Step[] {
  const found = new Map<string, ActivityRecord>()
  for (const activity of activities) {
    const key =
      activity.tool_id ||
      `${activity.category}:${activity.label}:${activity.sequence}`
    const current = found.get(key)
    if (!current || activity.sequence > current.sequence)
      found.set(key, activity)
  }
  return [...found.entries()].map(([key, activity]) => ({
    key,
    label:
      activity.label ||
      ({
        web: "Searched the web",
        image: "Worked on an image",
        voice: "Recorded a voice reply",
        code: "Ran a command",
        memory: "Used memory",
        connector: "Used a connected app",
        automation: "Managed an automation",
        tool: "Used a tool",
      }[activity.category] ??
        "Used a tool"),
    status: activity.status,
    category: activity.category,
  }))
}

function failureCopy(failure: RunStatus["failure"]): string {
  return (
    {
      quota: "Your allowance is used and your Sparks balance is empty.",
      provider: "The provider stopped the request. Nothing else was sent.",
      moderation: "The request was blocked before it ran.",
      context:
        "This conversation is too long for the model. Try a shorter message.",
      interrupted: "The request stopped before it finished.",
      unknown: "The request did not finish. Review it before retrying.",
    }[failure ?? "unknown"] ?? "The request did not finish."
  )
}

function mergeMessages(current: VisibleMessage[], incoming: VisibleMessage[]) {
  const byId = new Map(current.map((message) => [message.id, message]))
  for (const message of incoming) byId.set(message.id, message)
  return [...byId.values()].sort(
    (left, right) => left.sequence - right.sequence
  )
}

function optimistic(
  text: string,
  files: MediaRecord[],
  threadId: string
): VisibleMessage {
  return {
    id: "local-pending",
    thread_id: threadId,
    sequence: 2 ** 50,
    role: "user",
    origin: "web",
    run_id: null,
    parts: [
      { type: "text", text },
      ...files.map((file): FilePart => ({
        type: "file",
        file_id: file.id,
        name: file.name,
        media_type: file.media_type,
        availability: "available",
      })),
    ],
  }
}

function FileView({ part }: { part: FilePart }) {
  return (
    <PreviewableAttachment
      name={part.name}
      mediaType={part.media_type}
      availability={part.availability}
      src={
        part.availability === "available"
          ? `/api/v1/media/${encodeURIComponent(part.file_id)}`
          : undefined
      }
    />
  )
}

function toolIcon(category: string) {
  return (
    {
      web: Search01Icon,
      code: CodeIcon,
      image: Image01Icon,
      memory: BrainIcon,
      connector: Plug01Icon,
      automation: WorkflowIcon,
      voice: Mic01Icon,
      tool: ToolsIcon,
    }[category] ?? ToolsIcon
  )
}

function RunTools({
  run,
  activities,
}: {
  run: RunStatus
  activities: ActivityRecord[]
}) {
  const list = steps(activities)
  const stopped = run.state === "failed" || run.state === "interrupted"
  if (list.length === 0 && !ACTIVE.has(run.state)) return null
  return (
    <MessageScrollerItem messageId={`run-tools-${run.id}`}>
      <Trace>
        {list.length === 0 ? (
          <TraceLine status={stopped ? "error" : "running"}>
            <TraceIcon>
              <Spinner />
            </TraceIcon>
            <TraceTitle>{run.label}</TraceTitle>
          </TraceLine>
        ) : (
          <TraceCollapsible defaultOpen={ACTIVE.has(run.state) || stopped}>
            <TraceCollapsibleTrigger>
              <TraceLine status={stopped ? "error" : undefined}>
                <TraceIcon>
                  <HugeiconsIcon icon={ToolsIcon} />
                </TraceIcon>
                <TraceTitle>
                  {list.length} {list.length === 1 ? "tool" : "tools"}
                </TraceTitle>
              </TraceLine>
            </TraceCollapsibleTrigger>
            <TraceCollapsibleContent>
              <div className="flex flex-col gap-2">
                {list.map((step) => (
                  <TraceLine
                    key={step.key}
                    status={
                      step.status === "running"
                        ? "running"
                        : step.status === "failed"
                          ? "error"
                          : undefined
                    }
                  >
                    <TraceIcon>
                      <HugeiconsIcon icon={toolIcon(step.category)} />
                    </TraceIcon>
                    <TraceTitle>{step.label}</TraceTitle>
                    {step.status === "running" && (
                      <Spinner className="size-3" />
                    )}
                  </TraceLine>
                ))}
              </div>
            </TraceCollapsibleContent>
          </TraceCollapsible>
        )}
      </Trace>
    </MessageScrollerItem>
  )
}

export function Conversation({
  title = "New thread",
  project,
  messages = [],
  state = "empty",
  preview = false,
  thread,
  csrfToken,
  projects = [],
  olderThan: initialOlderThan = null,
  initialRun = null,
  initialActivities = [],
  defaultProjectId = null,
}: {
  title?: string
  project?: { id: string; name: string; instructions: string }
  messages?: VisibleMessage[]
  state?: PreviewState
  preview?: boolean
  thread?: ThreadRecord
  csrfToken?: string
  projects?: ProjectRecord[]
  olderThan?: number | null
  initialRun?: RunStatus | null
  initialActivities?: ActivityRecord[]
  defaultProjectId?: string | null
}) {
  const router = useRouter()
  const connected = Boolean(csrfToken)
  const id = React.useId()
  const [draft, setDraft] = React.useState("")
  const [notice, setNotice] = React.useState("")
  const [detail, setDetail] = React.useState<string | null>(null)
  const [current, setCurrent] = React.useState<ThreadRecord | null>(
    thread ?? null
  )
  const [history, setHistory] = React.useState<VisibleMessage[]>(messages)
  const [olderThan, setOlderThan] = React.useState<number | null>(
    initialOlderThan
  )
  const [loadingOlder, setLoadingOlder] = React.useState(false)
  const [run, setRun] = React.useState<RunStatus | null>(initialRun)
  const [activities, setActivities] =
    React.useState<ActivityRecord[]>(initialActivities)
  const [runDetails, setRunDetails] = React.useState<
    Record<string, RunDetails>
  >({})
  const fetchedRuns = React.useRef(new Set<string>())
  const [connection, setConnection] = React.useState<Connection>("connecting")
  const [pending, setPending] = React.useState<VisibleMessage | null>(null)
  const [sending, setSending] = React.useState(false)
  const [failure, setFailure] = React.useState<APIError | null>(null)
  const [lastSend, setLastSend] = React.useState<PendingSend | null>(null)
  const [selected, setSelected] = React.useState<MediaRecord[]>([])
  const [transcripts, setTranscripts] = React.useState<Record<string, string>>(
    {}
  )
  const [picker, setPicker] = React.useState(false)
  const [projectCreator, setProjectCreator] = React.useState(false)
  const [createdProjects, setCreatedProjects] = React.useState<ProjectRecord[]>(
    []
  )
  const [newProject, setNewProject] = React.useState<string | null>(
    defaultProjectId
  )
  const draftLoaded = React.useRef(false)

  const draftKey = `skye:draft:${current?.id ?? "new"}`
  React.useEffect(() => {
    draftLoaded.current = false
    // Restoring a client-only draft is external-store synchronisation.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft(localStorage.getItem(draftKey) ?? "")
    draftLoaded.current = true
  }, [draftKey])
  React.useEffect(() => {
    if (!draftLoaded.current) return
    if (draft) localStorage.setItem(draftKey, draft)
    else localStorage.removeItem(draftKey)
  }, [draft, draftKey])

  const applySnapshot = React.useCallback((snapshot: Snapshot) => {
    setCurrent(snapshot.thread)
    setHistory(snapshot.messages)
    setOlderThan(snapshot.older_than ?? null)
    setRun(snapshot.run ?? null)
    setActivities(snapshot.activities ?? [])
    setPending((value) => {
      const text = value?.parts.find((part) => "text" in part)?.text
      if (!value || !text) return value
      return snapshot.messages.some(
        (message) =>
          message.role === "user" &&
          message.parts.some((part) => "text" in part && part.text === text)
      )
        ? null
        : value
    })
  }, [])

  React.useEffect(() => {
    if (!connected) return
    const ids = [
      ...new Set(
        history
          .map((message) => message.run_id)
          .filter((value): value is string => Boolean(value))
      ),
    ].slice(-10)
    for (const id of ids) {
      if (id === run?.id || fetchedRuns.current.has(id)) continue
      fetchedRuns.current.add(id)
      fetch(`/api/v1/runs/${encodeURIComponent(id)}`, { cache: "no-store" })
        .then(async (response) =>
          response.ok ? ((await response.json()) as RunDetails) : null
        )
        .then((details) => {
          if (!details) return
          setRunDetails((current) =>
            current[id] ? current : { ...current, [id]: details }
          )
        })
        .catch(() => undefined)
    }
  }, [connected, history, run?.id])

  React.useEffect(() => {
    if (!thread || !csrfToken) return
    const source = new EventSource(
      `/api/v1/threads/${encodeURIComponent(thread.id)}/events`
    )
    const snapshot = (event: Event) => {
      try {
        applySnapshot(JSON.parse((event as MessageEvent).data) as Snapshot)
        setConnection("live")
      } catch {
        setConnection("reconnecting")
      }
    }
    const created = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as {
          data: StreamMessageEvent
        }
        const message = payload.data.message
        setHistory((current) => mergeMessages(current, [message]))
        setPending((value) => {
          const text = value?.parts.find((part) => "text" in part)?.text
          if (!value || !text || message.role !== "user") return value
          return message.parts.some(
            (part) => "text" in part && part.text === text
          )
            ? null
            : value
        })
      } catch {
        setConnection("reconnecting")
      }
    }
    const changed = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as {
          data: { run: RunStatus }
        }
        setRun(payload.data.run)
      } catch {
        setConnection("reconnecting")
      }
    }
    const activityEvent = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as {
          data: { activity: ActivityRecord }
        }
        setActivities((current) => [...current, payload.data.activity])
      } catch {
        setConnection("reconnecting")
      }
    }
    const resource = () => {
      router.refresh()
    }
    source.addEventListener("snapshot", snapshot)
    source.addEventListener("message.created", created)
    source.addEventListener("run.changed", changed)
    source.addEventListener("run.activity", activityEvent)
    source.addEventListener("resource.changed", resource)
    source.onopen = () => setConnection("live")
    source.onerror = () => setConnection("reconnecting")
    return () => source.close()
  }, [thread, csrfToken, applySnapshot, router])

  async function call<T>(
    path: string,
    method: string,
    body?: unknown
  ): Promise<T> {
    const response = await fetch(path, {
      method,
      cache: "no-store",
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      let parsed: APIError | null = null
      try {
        parsed = (await response.json()) as APIError
      } catch {
        parsed = null
      }
      throw Object.assign(new Error(parsed?.message ?? "The request failed."), {
        api: parsed,
      })
    }
    return (await response.json()) as T
  }

  function toggleMedia(media: MediaRecord) {
    const present = selected.some((item) => item.id === media.id)
    setSelected(
      present
        ? selected.filter((item) => item.id !== media.id)
        : [...selected, media]
    )
    if (present) {
      setTranscripts((current) => {
        const next = { ...current }
        delete next[media.id]
        return next
      })
    }
  }

  async function send(
    text: string,
    files: MediaRecord[],
    reviewed: Record<string, string>
  ) {
    if (!csrfToken) return
    setSending(true)
    setFailure(null)
    setNotice("")
    const allowed = new Set(files.map((file) => file.id))
    const transcriptsForSend = Object.fromEntries(
      Object.entries(reviewed).filter(([id]) => allowed.has(id))
    )
    const request: PendingSend = {
      requestId: crypto.randomUUID(),
      text,
      files,
      transcripts: transcriptsForSend,
    }
    try {
      let target = current
      if (!target) {
        target = await call<ThreadRecord>("/api/v1/threads", "POST", {
          title: text.replace(/\s+/g, " ").trim().slice(0, 80),
          project_id: newProject,
        })
        setCurrent(target)
      }
      setPending(optimistic(text, files, target.id))
      await call(
        `/api/v1/threads/${encodeURIComponent(target.id)}/messages`,
        "POST",
        {
          request_id: request.requestId,
          text,
          file_ids: files.map((file) => file.id),
          transcripts: reviewed,
        }
      )
      setLastSend(request)
      setDraft("")
      setSelected([])
      setTranscripts({})
      if (!thread) {
        router.replace(`/chat/${target.id}`)
        router.refresh()
      }
    } catch (error) {
      setPending(null)
      const api = (error as { api?: APIError }).api
      setFailure(
        api ?? {
          code: "unavailable",
          message: "The message was not sent.",
          recovery: "Your draft is still here. Try again.",
          request_id: "",
          retriable: true,
          field_errors: {},
        }
      )
    } finally {
      setSending(false)
    }
  }

  async function submit() {
    const text = draft.trim()
    if (!text || sending || (run && ACTIVE.has(run.state))) return
    if (!connected) {
      setNotice("Not sent. Your draft stays here.")
      return
    }
    await send(text, selected, transcripts)
  }

  async function stop() {
    if (!current) return
    try {
      await call(
        `/api/v1/threads/${encodeURIComponent(current.id)}/stop`,
        "POST",
        {}
      )
    } catch {
      setFailure({
        code: "unavailable",
        message: "Stop did not reach Skye.",
        recovery: "Try again in a moment.",
        request_id: "",
        retriable: true,
        field_errors: {},
      })
    }
  }

  async function loadOlder() {
    if (!current || olderThan === null) return
    setLoadingOlder(true)
    try {
      const page = await call<{
        messages: VisibleMessage[]
        older_than: number | null
      }>(
        `/api/v1/threads/${encodeURIComponent(current.id)}/messages?before=${olderThan}&limit=50`,
        "GET"
      )
      setHistory((existing) => mergeMessages(existing, page.messages))
      setOlderThan(page.older_than)
    } catch {
      setNotice("Earlier messages could not be loaded.")
    } finally {
      setLoadingOlder(false)
    }
  }

  const lastUser = [...history]
    .reverse()
    .find((message) => message.role === "user")
  const retryText =
    lastSend?.text ?? lastUser?.parts.find((part) => "text" in part)?.text
  const retryFiles = lastSend?.files ?? []
  const retryTranscripts = lastSend?.transcripts ?? {}

  function retry() {
    if (!retryText) return
    void send(retryText, retryFiles, retryTranscripts)
  }

  const projectList = [
    ...projects,
    ...createdProjects.filter(
      (item) => !projects.some((project) => project.id === item.id)
    ),
  ]
  const currentProject = current?.project_id
    ? projectList.find((item) => item.id === current.project_id)
    : undefined
  const instructions = currentProject?.instructions ?? project?.instructions
  const chosenProject = newProject
    ? projectList.find((item) => item.id === newProject)
    : undefined
  const active = Boolean(run && ACTIVE.has(run.state))
  const list = pending ? [...history, pending] : history
  const showEmpty =
    list.length === 0 && !active && (!preview || state === "empty")
  const lastRunIndex = new Map<string, number>()
  list.forEach((message, index) => {
    if (message.run_id) lastRunIndex.set(message.run_id, index)
  })
  const hasRunMessage = Boolean(
    run && list.some((message) => message.run_id === run.id)
  )

  return (
    <div className="conversation-page">
      <PageHeader
        title={current?.title ?? title}
        parent={
          currentProject
            ? {
                name: currentProject.name,
                href: `/projects/${currentProject.id}`,
              }
            : project
              ? { name: project.name, href: `/projects/${project.id}` }
              : undefined
        }
      >
        {!current && connected && (
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="ghost" size="sm" />}>
              <HugeiconsIcon icon={Folder01Icon} data-icon="inline-start" />
              {chosenProject
                ? `${chosenProject.emoji || "📁"} ${chosenProject.name}`
                : "No project"}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => setNewProject(null)}>
                  No project
                </DropdownMenuItem>
                {projectList.map((item) => (
                  <DropdownMenuItem
                    key={item.id}
                    onClick={() => setNewProject(item.id)}
                  >
                    <span aria-hidden="true">{item.emoji || "📁"}</span>
                    {item.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => setProjectCreator(true)}>
                  <HugeiconsIcon icon={Add01Icon} />
                  New project
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        {connected && active && (
          <Button
            variant="outline"
            size="sm"
            aria-label="Stop"
            onClick={() => void stop()}
          >
            <HugeiconsIcon icon={Square01Icon} data-icon="inline-start" />
            <span className="hidden sm:inline">Stop</span>
          </Button>
        )}
        <ContextPanel instructions={instructions} connected={connected} activities={activities} />
      </PageHeader>
      <main className="conversation-main" aria-label="Conversation">
        {preview && (
          <p className="preview-notice">Preview · Sample conversation.</p>
        )}
        {connected && connection === "reconnecting" && (
          <p className="preview-notice" role="status">
            Reconnecting…
          </p>
        )}
        {failure && (
          <div className="px-6 pb-2">
            <Alert variant="destructive">
              <AlertTitle>{failure.message}</AlertTitle>
              <AlertDescription>
                <p>{failure.recovery}</p>
                {retryText && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 w-fit"
                    disabled={sending || active}
                    onClick={retry}
                  >
                    Retry
                  </Button>
                )}
              </AlertDescription>
            </Alert>
          </div>
        )}
        <div className="transcript-area">
          {preview && state === "loading" ? (
            <div
              className="transcript-loading"
              role="status"
              aria-label="Loading sample conversation"
              aria-busy="true"
            >
              <Skeleton className="ms-auto h-18 w-3/5" />
              <Skeleton className="h-5 w-4/5" />
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="mt-4 h-5 w-3/4" />
            </div>
          ) : showEmpty ? (
            <Empty className="conversation-empty">
              <EmptyHeader>
                <EmptyMedia>
                  <SkyeMark size={42} />
                </EmptyMedia>
                <EmptyTitle>Start a conversation.</EmptyTitle>
              </EmptyHeader>
            </Empty>
          ) : (
            <MessageScrollerProvider
              defaultScrollPosition="last-anchor"
              autoScroll
            >
              <MessageScroller>
                <MessageScrollerViewport
                  tabIndex={0}
                  aria-label="Message history"
                >
                  <MessageScrollerContent
                    className="transcript-content"
                    aria-live="off"
                  >
                    {olderThan !== null && (
                      <div className="flex justify-center pb-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={loadingOlder}
                          onClick={() => void loadOlder()}
                        >
                          {loadingOlder ? <Spinner /> : null}
                          Earlier messages
                        </Button>
                      </div>
                    )}
                    {list.map((message, index) => (
                      <React.Fragment key={message.id}>
                        <MessageScrollerItem
                          messageId={message.id}
                          scrollAnchor={message.role === "user"}
                        >
                          <Message
                            align={message.role === "user" ? "end" : "start"}
                          >
                            <MessageContent>
                              {message.role === "assistant" &&
                                (index === 0 ||
                                  list[index - 1]?.role !== "assistant") && (
                                  <MessageHeader>Skye</MessageHeader>
                                )}
                              <Bubble
                                variant={
                                  message.role === "user"
                                    ? "secondary"
                                    : "ghost"
                                }
                              >
                                <BubbleContent>
                                  {message.parts.map((part, index) =>
                                    "file_id" in part ? (
                                      <FileView key={index} part={part} />
                                    ) : "text" in part ? (
                                      <Markdown key={index} text={part.text} />
                                    ) : null
                                  )}
                                </BubbleContent>
                              </Bubble>
                            </MessageContent>
                          </Message>
                        </MessageScrollerItem>
                        {message.run_id &&
                          lastRunIndex.get(message.run_id) === index &&
                          (() => {
                            const details =
                              message.run_id === run?.id
                                ? run
                                  ? { run, activities }
                                  : null
                                : runDetails[message.run_id]
                            return details ? (
                              <RunTools
                                run={details.run}
                                activities={details.activities}
                              />
                            ) : null
                          })()}
                      </React.Fragment>
                    ))}
                    {run && !hasRunMessage && (
                      <RunTools run={run} activities={activities} />
                    )}
                    {preview && state === "running" && (
                      <MessageScrollerItem messageId="preview-activity">
                        <Trace>
                          <TraceCollapsible>
                            <TraceCollapsibleTrigger>
                              <TraceLine status="running">
                                <TraceIcon>
                                  <Spinner />
                                </TraceIcon>
                                <TraceTitle>Searching the web</TraceTitle>
                              </TraceLine>
                            </TraceCollapsibleTrigger>
                            <TraceCollapsibleContent>
                              Preview activity.
                            </TraceCollapsibleContent>
                          </TraceCollapsible>
                        </Trace>
                      </MessageScrollerItem>
                    )}
                  </MessageScrollerContent>
                </MessageScrollerViewport>
                <MessageScrollerButton direction="start" />
                <MessageScrollerButton />
              </MessageScroller>
            </MessageScrollerProvider>
          )}
        </div>
        <div className="composer-region">
          {preview && (state === "failed" || state === "low-funds") && (
            <Alert>
              <AlertTitle>
                {state === "failed"
                  ? "The response was interrupted"
                  : "Your free allowance has been used"}
              </AlertTitle>
              <AlertDescription>
                <p>
                  {state === "failed"
                    ? "Sample error. Completed work may have taken effect."
                    : "Sample limit state."}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 w-fit"
                  onClick={() =>
                    setDetail(
                      state === "failed"
                        ? "Retry is not connected in this preview."
                        : "Balances are not connected in this preview."
                    )
                  }
                >
                  {state === "failed" ? "Retry" : "Account"}
                </Button>
              </AlertDescription>
            </Alert>
          )}
          {connected &&
            run &&
            (run.state === "failed" || run.state === "interrupted") && (
              <Alert variant="destructive">
                <AlertTitle>
                  {run.state === "interrupted"
                    ? "Request interrupted"
                    : "Skye stopped"}
                </AlertTitle>
                <AlertDescription>
                  <p>{failureCopy(run.failure)}</p>
                  {retryText && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3 w-fit"
                      disabled={sending || active}
                      onClick={retry}
                    >
                      Retry
                    </Button>
                  )}
                </AlertDescription>
              </Alert>
            )}
          {selected.length > 0 && (
            <AttachmentGroup>
              {selected.map((file) => (
                <PreviewableAttachment
                  key={file.id}
                  name={file.name}
                  mediaType={file.media_type}
                  size={file.size}
                  availability={file.availability ?? "available"}
                  src={`/api/v1/media/${encodeURIComponent(file.id)}`}
                  onRemove={() => toggleMedia(file)}
                />
              ))}
            </AttachmentGroup>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void submit()
            }}
          >
            <Field>
              <FieldLabel htmlFor={id} className="sr-only">
                Message Skye
              </FieldLabel>
              <InputGroup>
                <InputGroupTextarea
                  id={id}
                  name="message"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Message Skye…"
                  aria-describedby={notice ? `${id}-hint` : undefined}
                  rows={2}
                  dir="auto"
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing &&
                      !event.repeat
                    ) {
                      event.preventDefault()
                      void submit()
                    }
                  }}
                />
                <InputGroupAddon align="block-end">
                  <InputGroupButton
                    size="icon-sm"
                    aria-label="Add files"
                    onClick={() =>
                      connected
                        ? setPicker(true)
                        : setDetail(
                            "File uploads are not available in this preview."
                          )
                    }
                  >
                    <HugeiconsIcon icon={Attachment01Icon} />
                  </InputGroupButton>
                  {connected && csrfToken ? (
                    <VoiceRecorder
                      csrfToken={csrfToken}
                      disabled={active}
                      onReady={(text, media) => {
                        setSelected((current) =>
                          current.some((item) => item.id === media.id)
                            ? current
                            : [...current, media]
                        )
                        setTranscripts((current) => ({
                          ...current,
                          [media.id]: text,
                        }))
                        setDraft((current) =>
                          current.trim() ? `${current}\n${text}` : text
                        )
                      }}
                    />
                  ) : (
                    <InputGroupButton
                      size="icon-sm"
                      aria-label="Record a voice message"
                      onClick={() =>
                        setDetail(
                          "Voice recording is not available in this preview."
                        )
                      }
                    >
                      <HugeiconsIcon icon={Mic01Icon} />
                    </InputGroupButton>
                  )}
                  <InputGroupButton
                    size="sm"
                    onClick={() =>
                      setDetail("Model settings are not available yet.")
                    }
                  >
                    Sun Engine
                    <HugeiconsIcon
                      icon={ArrowDown01Icon}
                      data-icon="inline-end"
                    />
                  </InputGroupButton>
                  {connected && active ? (
                    <InputGroupButton
                      size="icon-sm"
                      variant="destructive"
                      className="ms-auto"
                      aria-label="Stop"
                      onClick={() => void stop()}
                    >
                      <HugeiconsIcon icon={Square01Icon} />
                    </InputGroupButton>
                  ) : (
                    <InputGroupButton
                      size="icon-sm"
                      variant="default"
                      type="submit"
                      className="ms-auto"
                      aria-label="Send message"
                      disabled={sending || !draft.trim()}
                    >
                      {sending ? (
                        <Spinner />
                      ) : (
                        <HugeiconsIcon icon={ArrowUp02Icon} />
                      )}
                    </InputGroupButton>
                  )}
                </InputGroupAddon>
              </InputGroup>
              {notice && (
                <FieldDescription id={`${id}-hint`}>{notice}</FieldDescription>
              )}
            </Field>
          </form>
          <p role="status" aria-live="polite" className="sr-only">
            {notice || (run && active ? run.label : "")}
          </p>
        </div>
      </main>
      <MediaPicker
        open={picker}
        onOpenChange={setPicker}
        csrfToken={csrfToken ?? ""}
        selected={selected}
        onToggle={toggleMedia}
      />
      {csrfToken && (
        <CreateProjectDialog
          open={projectCreator}
          onOpenChange={setProjectCreator}
          csrfToken={csrfToken}
          onCreated={(created) => {
            setCreatedProjects((current) => [created, ...current])
            setNewProject(created.id)
            router.refresh()
          }}
        />
      )}
      <Dialog
        open={detail !== null}
        onOpenChange={(open) => {
          if (!open) setDetail(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Not available</DialogTitle>
            <DialogDescription>{detail}</DialogDescription>
          </DialogHeader>
          <Button variant="outline" onClick={() => setDetail(null)}>
            Close
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}
