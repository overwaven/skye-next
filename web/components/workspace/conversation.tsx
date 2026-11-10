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
  StopIcon,
} from "@hugeicons/core-free-icons"
import { SkyeMark } from "@/components/skye-mark"
import { PageHeader } from "@/components/workspace/page-header"
import { Markdown } from "@/components/workspace/markdown"
import { MediaPicker } from "@/components/workspace/media-picker"
import { PreviewableAttachment } from "@/components/workspace/attachment-preview"
import { CreateProjectDialog } from "@/components/workspace/create-project-dialog"
import { VoiceRecorder } from "@/components/workspace/voice-recorder"
import { uploadMediaFile } from "@/components/workspace/media-upload"
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
  CodeBlock,
  CodeBlockContent,
} from "@/components/ui/code-block"
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceDescription,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
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
import { useI18n } from "@/components/i18n-provider"
import {
  translateServerMessage,
  type MessageKey,
  type MessageValues,
} from "@/lib/i18n"

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
  tool_name: string
  tool_args: string
  tool_output: string
}

const ACTIVE = new Set(["accepted", "running", "cancelling"])

type Translate = (key: MessageKey, values?: MessageValues) => string

const activityKeys: Record<string, MessageKey> = {
  "Searched the web": "chat.labelSearched",
  "Searching the web": "chat.labelSearching",
  "Generating image": "chat.labelGeneratingImage",
  "Editing image": "chat.labelEditingImage",
  "Ran a command": "chat.labelRanCommand",
  "Ran code": "chat.labelRanCode",
  "Saved a memory": "chat.labelSavedMemory",
  "Looked up a memory": "chat.labelLookedUpMemory",
  "Forgot a memory": "chat.labelForgotMemory",
  "Used a connected app": "chat.labelUsedApp",
  "Listed automations": "chat.labelListedAutomations",
  "Created a scheduled automation": "chat.labelCreatedScheduled",
  "Created a webhook automation": "chat.labelCreatedWebhook",
  "Updated an automation": "chat.labelUpdatedAutomation",
  "Showed webhook details": "chat.labelShowedWebhook",
  "Deleted an automation": "chat.labelDeletedAutomation",
  "Recorded a voice reply": "chat.labelRecordedVoice",
  "Recording a voice reply": "chat.labelRecordingVoice",
}

function categoryLabel(category: string, t: Translate) {
  return (
    ({
      web: t("chat.activityWeb"),
      image: t("chat.activityImage"),
      voice: t("chat.activityVoice"),
      code: t("chat.activityCode"),
      memory: t("chat.activityMemory"),
      connector: t("chat.activityConnector"),
      automation: t("chat.activityAutomation"),
      tool: t("chat.activityTool"),
    } as Record<string, string>)[category] ?? t("chat.activityTool")
  )
}

function activityLabel(
  label: string,
  category: string,
  locale: string,
  t: Translate
) {
  const key = activityKeys[label]
  if (key) return t(key)
  if (label && locale === "en") return label
  return categoryLabel(category, t)
}

function runLabel(state: RunStatus["state"], t: Translate) {
  return (
    ({
      accepted: t("run.queued"),
      running: t("run.working"),
      completed: t("run.finished"),
      failed: t("run.failed"),
      cancelling: t("run.stopping"),
      cancelled: t("run.stopped"),
      interrupted: t("run.interrupted"),
    } as Record<string, string>)[state] ?? t("run.working")
  )
}

function steps(
  activities: ActivityRecord[],
  locale: string,
  t: Translate
): Step[] {
  const found = new Map<string, ActivityRecord>()
  for (const activity of activities) {
    const key =
      activity.tool_id ||
      `${activity.category}:${activity.label}:${activity.sequence}`
    const current = found.get(key)
    if (!current) {
      found.set(key, activity)
      continue
    }
    const latest =
      activity.sequence >= current.sequence ? activity : current
    const earlier = latest === activity ? current : activity
    found.set(key, {
      ...latest,
      label: latest.label || earlier.label,
      tool_name: latest.tool_name || earlier.tool_name,
      tool_args: latest.tool_args || earlier.tool_args,
      tool_output: latest.tool_output || earlier.tool_output,
    })
  }
  return [...found.entries()].map(([key, activity]) => ({
    key,
    label: activityLabel(
      activity.label ?? "",
      activity.category,
      locale,
      t
    ),
    status: activity.status,
    category: activity.category,
    tool_name: activity.tool_name || "",
    tool_args: activity.tool_args || "",
    tool_output: activity.tool_output || "",
  }))
}

function failureCopy(failure: RunStatus["failure"], t: Translate): string {
  return (
    {
      quota: t("chat.failureQuota"),
      provider: t("chat.failureProvider"),
      moderation: t("chat.failureModeration"),
      context: t("chat.failureContext"),
      interrupted: t("chat.failureInterrupted"),
      unknown: t("chat.failureUnknown"),
    }[failure ?? "unknown"] ?? t("chat.failureFallback")
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
  const { t, tn, locale } = useI18n()
  const list = steps(activities, locale, t)
  const stopped = run.state === "failed" || run.state === "interrupted"
  const [expanded, setExpanded] = React.useState<boolean | undefined>(undefined)
  if (list.length === 0 && !ACTIVE.has(run.state)) return null
  return (
    <MessageScrollerItem messageId={`run-tools-${run.id}`}>
      <Trace>
        {list.length === 0 ? (
          <TraceLine status={stopped ? "error" : "running"}>
            <TraceIcon>
              <Spinner />
            </TraceIcon>
            <TraceTitle>{runLabel(run.state, t)}</TraceTitle>
          </TraceLine>
        ) : (
          <TraceCollapsible
            open={expanded ?? (ACTIVE.has(run.state) || stopped)}
            onOpenChange={setExpanded}
          >
            <TraceCollapsibleTrigger>
              <TraceLine status={stopped ? "error" : undefined}>
                <TraceIcon>
                  <HugeiconsIcon icon={ToolsIcon} />
                </TraceIcon>
                <TraceTitle>{tn("chat.tools", list.length)}</TraceTitle>
              </TraceLine>
            </TraceCollapsibleTrigger>
            <TraceCollapsibleContent>
              <div className="flex flex-col gap-2">
                {list.map((step) => (
                  <TraceCollapsible key={step.key}>
                    <TraceCollapsibleTrigger>
                      <TraceLine
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
                        <TraceTitle>{step.tool_name || step.label}</TraceTitle>
                        {step.tool_name && step.label !== step.tool_name && (
                          <TraceDescription>{step.label}</TraceDescription>
                        )}
                        {step.status === "running" && (
                          <Spinner className="size-3" />
                        )}
                      </TraceLine>
                    </TraceCollapsibleTrigger>
                    <TraceCollapsibleContent>
                      <div className="flex flex-col gap-3 text-foreground">
                        {step.tool_args && (
                          <div className="flex flex-col gap-1.5">
                            <span className="text-xs font-medium text-muted-foreground">
                              {t("chat.input")}
                            </span>
                            <CodeBlock size="sm">
                              <CodeBlockContent wrap>
                                {step.tool_args}
                              </CodeBlockContent>
                            </CodeBlock>
                          </div>
                        )}
                        {step.tool_output && (
                          <div className="flex flex-col gap-1.5">
                            <span className="text-xs font-medium text-muted-foreground">
                              {t("chat.result")}
                            </span>
                            <CodeBlock size="sm">
                              <CodeBlockContent wrap>
                                {step.tool_output}
                              </CodeBlockContent>
                            </CodeBlock>
                          </div>
                        )}
                        {!step.tool_args && !step.tool_output && (
                          <p className="text-sm text-muted-foreground">
                            {t("chat.noDetails")}
                          </p>
                        )}
                      </div>
                    </TraceCollapsibleContent>
                  </TraceCollapsible>
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
  title,
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
  const { t, locale } = useI18n()
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
  const [attaching, setAttaching] = React.useState(0)
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
  const composerRef = React.useRef<HTMLTextAreaElement>(null)

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
      throw Object.assign(
        new Error(parsed?.message ?? t("chat.failureFallback")),
        {
          api: parsed,
        }
      )
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

  async function attachFiles(files: File[]) {
    if (files.length === 0) return
    if (!csrfToken) {
      setDetail(t("chat.previewFileUpload"))
      return
    }
    setAttaching((current) => current + 1)
    try {
      const uploaded: MediaRecord[] = []
      let failure = ""
      for (const file of files) {
        try {
          uploaded.push(await uploadMediaFile(file, csrfToken))
        } catch (error) {
          if ((error as Error).name !== "AbortError" && !failure)
            failure = (error as Error).message
        }
      }
      if (uploaded.length > 0) {
        setSelected((current) => {
          const known = new Set(current.map((item) => item.id))
          return [...current, ...uploaded.filter((item) => !known.has(item.id))]
        })
        setNotice("")
      }
      if (failure)
        toast.add({
          title: t("chat.pasteFailed"),
          description: failure,
          type: "error",
        })
    } finally {
      setAttaching((current) => Math.max(0, current - 1))
    }
  }

  function pasteFiles(event: React.ClipboardEvent<HTMLFormElement>) {
    const clipboard = event.clipboardData
    if (!clipboard) return
    const direct = Array.from(clipboard.files ?? [])
    const files =
      direct.length > 0
        ? direct
        : Array.from(clipboard.items ?? [])
            .filter((item) => item.kind === "file")
            .map((item) => item.getAsFile())
            .filter((file): file is File => Boolean(file))
    if (files.length === 0) return
    event.preventDefault()
    void attachFiles(files)
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
        api
          ? {
              ...api,
              message: translateServerMessage(locale, api.message),
              recovery: translateServerMessage(locale, api.recovery),
            }
          : {
              code: "unavailable",
              message: t("chat.sendFailed"),
              recovery: t("chat.draftStays"),
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
    if (!text || sending || attaching > 0 || (run && ACTIVE.has(run.state)))
      return
    if (!connected) {
      setNotice(t("chat.notSent"))
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
        message: t("chat.stopFailed"),
        recovery: t("chat.stopFailedRecovery"),
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
      setNotice(t("chat.earlierFailed"))
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
        title={current?.title ?? title ?? t("chat.newThreadTitle")}
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
              {chosenProject ? (
                <span aria-hidden="true">{chosenProject.emoji || "📁"}</span>
              ) : (
                <HugeiconsIcon icon={Folder01Icon} data-icon="inline-start" />
              )}
              {chosenProject ? chosenProject.name : t("chat.noProject")}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => setNewProject(null)}>
                  {t("chat.noProject")}
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
                  {t("chat.newProject")}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        {connected && active && (
          <Button
            variant="outline"
            size="sm"
            aria-label={t("chat.stop")}
            onClick={() => void stop()}
          >
            <HugeiconsIcon icon={StopIcon} data-icon="inline-start" />
            <span className="hidden sm:inline">{t("chat.stop")}</span>
          </Button>
        )}
      </PageHeader>
      <main className="conversation-main" aria-label={t("chat.conversation")}>
        {preview && (
          <p className="preview-notice">{t("chat.previewNotice")}</p>
        )}
        {connected && connection === "reconnecting" && (
          <p className="preview-notice" role="status">
            {t("chat.reconnecting")}
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
              aria-label={t("chat.loadingSample")}
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
                <EmptyTitle>{t("chat.start")}</EmptyTitle>
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
                  aria-label={t("chat.history")}
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
                          {t("chat.earlierMessages")}
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
                                <TraceTitle>{t("chat.activityWeb")}</TraceTitle>
                              </TraceLine>
                            </TraceCollapsibleTrigger>
                            <TraceCollapsibleContent>
                              {t("chat.previewActivity")}
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
                  ? t("chat.responseInterrupted")
                  : t("chat.freeAllowance")}
              </AlertTitle>
              <AlertDescription>
                <p>
                  {state === "failed"
                    ? t("chat.sampleError")
                    : t("chat.sampleLimit")}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 w-fit"
                  onClick={() =>
                    setDetail(
                      state === "failed"
                        ? t("chat.previewRetry")
                        : t("chat.previewBalances")
                    )
                  }
                >
                  {state === "failed" ? t("chat.retry") : t("chat.account")}
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
                    ? t("chat.requestInterrupted")
                    : t("chat.stopped")}
                </AlertTitle>
                <AlertDescription>
                  <p>{failureCopy(run.failure, t)}</p>
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
          {attaching > 0 && (
            <p
              role="status"
              className="flex items-center gap-2 px-1 text-sm text-muted-foreground"
            >
              <Spinner />
              {t("chat.attaching")}
            </p>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void submit()
            }}
            onPaste={pasteFiles}
          >
            <Field>
              <FieldLabel htmlFor={id} className="sr-only">
                {t("chat.messageAria")}
              </FieldLabel>
              <InputGroup>
                <InputGroupTextarea
                  ref={composerRef}
                  id={id}
                  name="message"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={t("chat.placeholder")}
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
                    aria-label={t("chat.addFiles")}
                    onClick={() =>
                      connected
                        ? setPicker(true)
                        : setDetail(
                            t("chat.previewFileUpload")
                          )
                    }
                  >
                    <HugeiconsIcon icon={Attachment01Icon} />
                  </InputGroupButton>
                  {connected && csrfToken ? (
                    <VoiceRecorder
                      csrfToken={csrfToken}
                      disabled={active}
                      onReady={(text) => {
                        setDraft((current) =>
                          current.trim() ? `${current.trimEnd()}\n${text}` : text
                        )
                        requestAnimationFrame(() =>
                          composerRef.current?.focus()
                        )
                      }}
                    />
                  ) : (
                    <InputGroupButton
                      size="icon-sm"
                      aria-label={t("chat.recordVoice")}
                      onClick={() => setDetail(t("chat.previewVoice"))}
                    >
                      <HugeiconsIcon icon={Mic01Icon} />
                    </InputGroupButton>
                  )}
                  <InputGroupButton
                    size="sm"
                    onClick={() =>
                      setDetail(t("chat.previewModel"))
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
                      aria-label={t("chat.stop")}
                      onClick={() => void stop()}
                    >
                      <HugeiconsIcon icon={StopIcon} />
                    </InputGroupButton>
                  ) : (
                    <InputGroupButton
                      size="icon-sm"
                      variant="default"
                      type="submit"
                      className="ms-auto"
                      aria-label={t("chat.send")}
                      disabled={sending || attaching > 0 || !draft.trim()}
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
            {notice || (run && active ? runLabel(run.state, t) : "")}
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
            <DialogTitle>{t("chat.notAvailable")}</DialogTitle>
            <DialogDescription>{detail}</DialogDescription>
          </DialogHeader>
          <Button variant="outline" onClick={() => setDetail(null)}>
            {t("common.close")}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}
