"use client"

import Link from "next/link"
import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { PageHeader } from "@/components/workspace/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
  FieldError,
} from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import {
  Item,
  ItemGroup,
  ItemContent,
  ItemTitle,
  ItemDescription,
  ItemActions,
} from "@/components/ui/item"
import { Spinner } from "@/components/ui/spinner"
import type {
  ResourceSnapshot,
  MemoryRecord,
  MemoryWrite,
  ConnectorRecord,
  SkillRecord,
  SkillUpload,
} from "@/lib/contracts.generated"

export async function resourceRequest<T>(
  path: string,
  csrf: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
      headers: {
        "X-CSRF-Token": csrf,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch {
    throw new Error(
      "Could not reach Skye. Check your connection and try again."
    )
  }
  if (!response.ok) {
    if (response.status === 401)
      throw new Error("Your session expired. Sign in with Telegram again.")
    if (response.status === 409)
      throw new Error(
        "This resource changed. Your draft is kept; close and reopen to review the latest version."
      )
    const error = await response.json().catch(() => null)
    throw new Error(
      error?.message || "Could not save this change. Review it and try again."
    )
  }
  return response.json()
}

export function useResourceSnapshot(
  initial: ResourceSnapshot,
  section: string
) {
  const [data, setData] = useState(initial)
  const [error, setError] = useState("")
  const refresh = useCallback(async () => {
    try {
      setData(
        await resourceRequest<ResourceSnapshot>(`/resources/${section}`, "")
      )
      setError("")
    } catch (error) {
      setError((error as Error).message)
    }
  }, [section])
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") void refresh()
    }
    window.addEventListener("focus", tick)
    const source = new EventSource("/api/v1/resources/events")
    source.addEventListener("ready", tick)
    source.addEventListener("resource.changed", tick)
    const timer = window.setInterval(tick, 15000)
    return () => {
      window.removeEventListener("focus", tick)
      window.clearInterval(timer)
      source.close()
    }
  }, [refresh])
  return { data, error, refresh }
}

const categories = [
  "personal",
  "preference",
  "project",
  "instruction",
  "other",
] as const
type Section = "memory" | "connectors" | "skills"

export function PersonalResources({
  section,
  initial,
  csrf,
  detailId,
  skillDetail,
}: {
  section: Section
  initial: ResourceSnapshot
  csrf: string
  detailId?: string
  skillDetail?: SkillRecord
}) {
  const router = useRouter()
  const {
    data: snapshot,
    error: loadError,
    refresh,
  } = useResourceSnapshot(initial, section)
  const data = {
    ...snapshot,
    memories: snapshot.memories ?? [],
    connectors: snapshot.connectors ?? [],
    skills: snapshot.skills ?? [],
  }
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [editor, setEditor] = useState<"memory" | "custom" | "skill" | null>(
    null
  )
  const [memory, setMemory] = useState<MemoryRecord | null>(null)
  const [connector, setConnector] = useState<ConnectorRecord | null>(null)
  const [content, setContent] = useState("")
  const [kind, setKind] = useState<MemoryWrite["category"]>("other")
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [headers, setHeaders] = useState("")
  const [replaceCredentials, setReplaceCredentials] = useState(false)
  const [upload, setUpload] = useState<SkillUpload | null>(null)
  const [preview, setPreview] = useState<SkillRecord | null>(null)
  const [catalog, setCatalog] = useState<ConnectorRecord[] | null>(null)
  const [remove, setRemove] = useState<{ title: string; path: string } | null>(
    null
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [status, setStatus] = useState("")
  const errorRef = useRef<HTMLDivElement>(null)
  const title =
    section === "memory"
      ? "Memory"
      : section === "skills"
        ? "Skills"
        : "Connectors"
  const action =
    section === "memory"
      ? "Add memory"
      : section === "skills"
        ? "Upload skill"
        : "Browse apps"
  const currentConnector = data.connectors.find((c) => c.id === detailId)
  const currentSkill = data.skills.find((s) => s.id === detailId)

  async function perform(work: () => Promise<void>) {
    setBusy(true)
    setError("")
    setStatus("")
    try {
      await work()
      await refresh()
    } catch (error) {
      setError((error as Error).message)
      requestAnimationFrame(() => errorRef.current?.focus())
    } finally {
      setBusy(false)
    }
  }

  function openMemory(value: MemoryRecord | null) {
    setMemory(value)
    setContent(value?.content || "")
    setKind(value?.category || "other")
    setError("")
    setEditor("memory")
  }
  function openCustom(value: ConnectorRecord | null) {
    setConnector(value)
    setName(value?.name || "")
    setUrl(value?.url || "")
    setHeaders("")
    setReplaceCredentials(!value)
    setError("")
    setEditor("custom")
  }
  async function pickSkill(file: File | undefined) {
    setPreview(null)
    setUpload(null)
    if (!file) return
    if (file.size > 25 * 1024 * 1024) {
      setError("Use a skill smaller than 25 MB.")
      return
    }
    await perform(async () => {
      const bytes = new Uint8Array(await file.arrayBuffer())
      let binary = ""
      for (let i = 0; i < bytes.length; i += 8192)
        binary += String.fromCharCode(...bytes.subarray(i, i + 8192))
      const payload = { filename: file.name, base64: btoa(binary) }
      const result = await resourceRequest<SkillRecord>(
        "/skills/preview",
        csrf,
        "POST",
        payload
      )
      setUpload(payload)
      setPreview(result)
    })
  }
  async function connect(c: ConnectorRecord) {
    await perform(async () => {
      const result = await resourceRequest<{ url: string | null }>(
        `/connectors/apps/${encodeURIComponent(c.id)}/connect`,
        csrf,
        "POST",
        {}
      )
      setStatus(
        result.url
          ? "Consent pending. Complete authorization, then return here and check the connection."
          : "App connected."
      )
      if (result.url) {
        const parsed = new URL(result.url)
        if (parsed.protocol !== "https:")
          throw new Error("The consent link is unavailable. Try again.")
        window.location.assign(parsed.href)
      }
    })
  }
  function requestRemove(title: string, path: string) {
    setRemove({ title, path })
    setError("")
  }

  return (
    <div className="detail-page">
      <PageHeader
        title={
          detailId
            ? currentConnector?.name || currentSkill?.name || title
            : title
        }
        parent={{
          name: detailId ? title : "Library",
          href: detailId ? `/library/${section}` : "/library",
        }}
      >
        {!detailId && (
          <Button
            variant="outline"
            disabled={
              busy || (section === "connectors" && !data.apps_configured)
            }
            onClick={() => {
              setError("")
              if (section === "memory") openMemory(null)
              else if (section === "skills") {
                setPreview(null)
                setUpload(null)
                setEditor("skill")
              } else
                void perform(async () =>
                  setCatalog(
                    (
                      await resourceRequest<{ connectors: ConnectorRecord[] }>(
                        "/connectors/catalog",
                        csrf
                      )
                    ).connectors
                  )
                )
            }}
          >
            {action}
          </Button>
        )}
      </PageHeader>
      <main className="detail-content resource-manager">
        <p className="resource-scope">
          Personal · Shared across your threads and Telegram. Projects do not
          isolate these resources.
        </p>
        {(error || loadError) && !editor && !remove && (
          <Alert>
            <AlertDescription ref={errorRef} tabIndex={-1}>
              {error || loadError}{" "}
              <Button variant="link" onClick={() => void refresh()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}
        <p role="status" className="resource-status">
          {busy ? "Working…" : status}
        </p>
        {!detailId && (
          <>
            {section === "memory" && (
              <FieldGroup>
                <Field orientation="horizontal">
                  <FieldLabel htmlFor="memory-enabled">Use memory</FieldLabel>
                  <Switch
                    id="memory-enabled"
                    checked={data.memory_enabled}
                    disabled={busy}
                    onCheckedChange={(checked) =>
                      void perform(async () => {
                        await resourceRequest(
                          "/resources/preferences",
                          csrf,
                          "PATCH",
                          { memory_enabled: checked }
                        )
                        setStatus("Memory preference saved.")
                      })
                    }
                  />
                </Field>
                <FieldDescription>
                  Turning memory off keeps saved facts. Deleting a memory does
                  not remove it from past messages.
                </FieldDescription>
              </FieldGroup>
            )}
            <FieldGroup className="resource-filters">
              <Field>
                <FieldLabel htmlFor="personal-resource-search">
                  Search {title.toLowerCase()}
                </FieldLabel>
                <Input
                  id="personal-resource-search"
                  name="query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  autoCorrect="off"
                  autoCapitalize="none"
                  spellCheck={false}
                />
              </Field>
              {section === "memory" && (
                <Field>
                  <FieldLabel htmlFor="memory-filter">Category</FieldLabel>
                  <Select
                    value={category}
                    items={["all", ...categories].map((value) => ({
                      value,
                      label: value === "all" ? "All categories" : value,
                    }))}
                    onValueChange={(v) => setCategory(v || "all")}
                  >
                    <SelectTrigger id="memory-filter">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {["all", ...categories].map((c) => (
                          <SelectItem key={c} value={c}>
                            {c === "all" ? "All categories" : c}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              )}
            </FieldGroup>
          </>
        )}
        {section === "memory" && (
          <ItemGroup>
            {data.memories
              .filter(
                (m) =>
                  (category === "all" || m.category === category) &&
                  m.content.toLowerCase().includes(query.toLowerCase())
              )
              .map((m) => (
                <Item key={m.id} role="listitem">
                  <ItemContent>
                    <ItemTitle dir="auto">{m.content}</ItemTitle>
                    <ItemDescription>
                      {m.category === "project"
                        ? "Project category · still personal, not project-isolated"
                        : m.category}
                    </ItemDescription>
                  </ItemContent>
                  <ItemActions>
                    <Button variant="ghost" onClick={() => openMemory(m)}>
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() =>
                        requestRemove("this memory", `/memories/${m.id}`)
                      }
                    >
                      Delete
                    </Button>
                  </ItemActions>
                </Item>
              ))}
          </ItemGroup>
        )}
        {section === "skills" &&
          (detailId && currentSkill ? (
            <section className="resource-detail">
              <p>{currentSkill.description}</p>
              <h2>Instructions</h2>
              <pre className="skill-instructions">
                {skillDetail?.instructions}
              </pre>
              <h2>Files</h2>
              <ul>
                {skillDetail?.files?.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <div className="resource-actions">
                <Button
                  variant="outline"
                  nativeButton={false}
                  render={
                    <a
                      href={`/api/v1/skills/${encodeURIComponent(detailId)}/download`}
                      download
                    />
                  }
                >
                  Download
                </Button>
                <Button
                  variant="outline"
                  onClick={() =>
                    requestRemove(currentSkill.name, `/skills/${detailId}`)
                  }
                >
                  Remove skill
                </Button>
              </div>
            </section>
          ) : (
            <ItemGroup>
              {data.skills
                .filter((s) =>
                  `${s.name} ${s.description}`
                    .toLowerCase()
                    .includes(query.toLowerCase())
                )
                .map((s) => (
                  <div key={s.id} role="listitem">
                    <Item render={<Link href={`/library/skills/${s.id}`} />}>
                      <ItemContent>
                        <ItemTitle>{s.name}</ItemTitle>
                        <ItemDescription>{s.description}</ItemDescription>
                      </ItemContent>
                    </Item>
                  </div>
                ))}
            </ItemGroup>
          ))}
        {section === "connectors" && (
          <>
            {!data.apps_configured && (
              <p>
                App connections are not configured on this deployment. You can
                add a public HTTPS MCP server.
              </p>
            )}
            {data.apps_configured && !data.app_consent_enabled && (
              <p>
                Connecting apps is unavailable until the deployment configures
                callback identity verification. Existing connections remain
                available.
              </p>
            )}
            {data.apps_configured && !data.provider_verified && (
              <Alert>
                <AlertDescription>
                  App status could not be verified. Check again before relying
                  on a connection.
                </AlertDescription>
              </Alert>
            )}
            {!detailId && (
              <Button variant="outline" onClick={() => openCustom(null)}>
                Add MCP server
              </Button>
            )}
            {currentConnector ? (
              <section className="resource-detail">
                <p>
                  {currentConnector.kind === "custom"
                    ? "Available to Skye; a connection test does not call tools."
                    : currentConnector.status === "connected"
                      ? "Connection verified with the provider."
                      : "Reconnect this app to restore access."}
                </p>
                {currentConnector.kind === "custom" && (
                  <>
                    <p className="break-all">{currentConnector.url}</p>
                    <p>
                      Credentials:{" "}
                      {currentConnector.credential_names?.length
                        ? currentConnector.credential_names
                            .map((h) => `${h}: ••••••••`)
                            .join(", ")
                        : "None"}
                    </p>
                  </>
                )}
                <div className="resource-actions">
                  {currentConnector.kind === "custom" ? (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => openCustom(currentConnector)}
                      >
                        Edit server
                      </Button>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() =>
                          void perform(async () => {
                            const r = await resourceRequest<{ tools: number }>(
                              `/connectors/custom/${detailId}/test`,
                              csrf,
                              "POST",
                              {}
                            )
                            setStatus(
                              `Connection reached. ${r.tools} tools available; none called.`
                            )
                          })
                        }
                      >
                        Test connection
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="outline"
                      disabled={busy || !data.app_consent_enabled}
                      onClick={() => void connect(currentConnector)}
                    >
                      {currentConnector.status === "connected"
                        ? "Authorize again"
                        : "Reconnect app"}
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    onClick={() =>
                      requestRemove(
                        currentConnector.name,
                        `/connectors/${currentConnector.kind === "custom" ? "custom" : "apps"}/${detailId}`
                      )
                    }
                  >
                    Disconnect
                  </Button>
                </div>
              </section>
            ) : (
              !detailId && (
                <ItemGroup>
                  {data.connectors
                    .filter((c) =>
                      c.name.toLowerCase().includes(query.toLowerCase())
                    )
                    .map((c) => (
                      <div key={`${c.kind}-${c.id}`} role="listitem">
                        <Item
                          render={<Link href={`/library/connectors/${c.id}`} />}
                        >
                          <ItemContent>
                            <ItemTitle>{c.name}</ItemTitle>
                            <ItemDescription>
                              {c.kind === "custom"
                                ? "MCP server · available, not tested"
                                : c.status === "connected"
                                  ? "Connected"
                                  : c.status === "pending"
                                    ? "Authorization pending"
                                    : "Needs attention · reconnect"}
                            </ItemDescription>
                          </ItemContent>
                        </Item>
                      </div>
                    ))}
                </ItemGroup>
              )
            )}
            {catalog && (
              <section className="resource-detail">
                <h2>App catalog</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    void perform(async () =>
                      setCatalog(
                        (
                          await resourceRequest<{
                            connectors: ConnectorRecord[]
                          }>(
                            `/connectors/catalog?q=${encodeURIComponent(query)}`,
                            csrf
                          )
                        ).connectors
                      )
                    )
                  }}
                >
                  <Button variant="outline" disabled={busy}>
                    Search catalog
                  </Button>
                </form>
                <ItemGroup>
                  {catalog.map((c) => (
                    <Item key={c.id} role="listitem">
                      <ItemContent>
                        <ItemTitle>{c.name}</ItemTitle>
                      </ItemContent>
                      <ItemActions>
                        <Button
                          variant="outline"
                          disabled={busy || !data.app_consent_enabled}
                          onClick={() => void connect(c)}
                        >
                          Connect
                        </Button>
                      </ItemActions>
                    </Item>
                  ))}
                </ItemGroup>
                <Button variant="ghost" onClick={() => setCatalog(null)}>
                  Close catalog
                </Button>
              </section>
            )}
          </>
        )}
        {!detailId &&
          !(
            section === "memory"
              ? data.memories
              : section === "skills"
                ? data.skills
                : data.connectors
          ).length && (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No {title.toLowerCase()} yet</EmptyTitle>
              </EmptyHeader>
            </Empty>
          )}
        {detailId && !currentConnector && !currentSkill && (
          <Alert>
            <AlertDescription>
              This resource was removed.{" "}
              <Link href={`/library/${section}`}>
                Return to {title.toLowerCase()}
              </Link>
            </AlertDescription>
          </Alert>
        )}
      </main>
      <Dialog
        open={editor !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setEditor(null)
        }}
      >
        <DialogContent className="resource-editor">
          <DialogHeader>
            <DialogTitle>
              {editor === "memory"
                ? memory
                  ? "Edit memory"
                  : "Add memory"
                : editor === "custom"
                  ? connector
                    ? "Edit MCP server"
                    : "Add MCP server"
                  : "Upload skill"}
            </DialogTitle>
            <DialogDescription>
              Personal resources are shared with Telegram and across your
              threads.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void perform(async () => {
                if (editor === "memory")
                  await resourceRequest(
                    memory ? `/memories/${memory.id}` : "/memories",
                    csrf,
                    memory ? "PATCH" : "POST",
                    {
                      content,
                      category: kind,
                      ...(memory ? { revision: memory.revision } : {}),
                    }
                  )
                if (editor === "custom")
                  await resourceRequest(
                    connector
                      ? `/connectors/custom/${connector.id}`
                      : "/connectors/custom",
                    csrf,
                    connector ? "PATCH" : "POST",
                    { name, url, ...(replaceCredentials ? { headers } : {}) }
                  )
                if (editor === "skill") {
                  if (!upload || !preview) return
                  await resourceRequest("/skills", csrf, "POST", upload)
                }
                setEditor(null)
                setHeaders("")
                setUpload(null)
                setStatus("Saved.")
              })
            }}
          >
            <FieldGroup>
              {editor === "memory" && (
                <>
                  <Field data-invalid={!!error}>
                    <FieldLabel htmlFor="memory-content">Memory</FieldLabel>
                    <Textarea
                      id="memory-content"
                      name="content"
                      required
                      maxLength={500}
                      rows={4}
                      value={content}
                      onChange={(e) => {
                        setContent(e.target.value)
                        setError("")
                      }}
                      aria-invalid={!!error}
                      aria-describedby={
                        error ? "resource-form-error" : undefined
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="memory-category">Category</FieldLabel>
                    <Select
                      value={kind}
                      onValueChange={(v) =>
                        setKind(v as MemoryWrite["category"])
                      }
                    >
                      <SelectTrigger id="memory-category">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {categories.map((c) => (
                            <SelectItem value={c} key={c}>
                              {c}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                </>
              )}
              {editor === "custom" && (
                <>
                  <Field>
                    <FieldLabel htmlFor="mcp-name">Name</FieldLabel>
                    <Input
                      id="mcp-name"
                      name="name"
                      required
                      maxLength={64}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="mcp-url">HTTPS URL</FieldLabel>
                    <Input
                      id="mcp-url"
                      name="url"
                      type="url"
                      required
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      autoCorrect="off"
                      autoCapitalize="none"
                      spellCheck={false}
                    />
                    <FieldDescription>
                      Public HTTPS endpoints only. No URL credentials, queries
                      or redirects.
                    </FieldDescription>
                  </Field>
                  {connector && (
                    <Field orientation="horizontal">
                      <FieldLabel htmlFor="replace-credentials">
                        Replace credentials
                      </FieldLabel>
                      <Switch
                        id="replace-credentials"
                        checked={replaceCredentials}
                        onCheckedChange={setReplaceCredentials}
                        disabled={!data.credentials_configured}
                      />
                    </Field>
                  )}
                  {replaceCredentials && (
                    <Field>
                      <FieldLabel htmlFor="mcp-headers">Headers</FieldLabel>
                      <Textarea
                        id="mcp-headers"
                        name="headers"
                        autoComplete="off"
                        spellCheck={false}
                        value={headers}
                        onChange={(e) => setHeaders(e.target.value)}
                        disabled={!data.credentials_configured}
                        rows={3}
                      />
                      <FieldDescription>
                        {data.credentials_configured
                          ? "Header: value, one per line. Values are never returned. Empty replacement removes credentials."
                          : "Credential editing needs deployment encryption. You can add a server without headers."}
                      </FieldDescription>
                    </Field>
                  )}
                </>
              )}
              {editor === "skill" && (
                <>
                  <Field>
                    <FieldLabel htmlFor="skill-upload">
                      SKILL.md or zip bundle
                    </FieldLabel>
                    <Input
                      id="skill-upload"
                      type="file"
                      name="skill"
                      accept=".md,.zip"
                      disabled={busy}
                      onChange={(e) => void pickSkill(e.target.files?.[0])}
                    />
                  </Field>
                  {preview && (
                    <section className="resource-detail">
                      <h2>{preview.name}</h2>
                      <p>{preview.description}</p>
                      <h3>Instructions</h3>
                      <pre className="skill-instructions">
                        {preview.instructions}
                      </pre>
                      <h3>Files</h3>
                      <ul>
                        {preview.files?.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    </section>
                  )}
                </>
              )}
              {error && (
                <FieldError
                  id="resource-form-error"
                  ref={errorRef}
                  tabIndex={-1}
                >
                  {error}
                </FieldError>
              )}
            </FieldGroup>
            <DialogFooter className="mt-6">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => setEditor(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={busy || (editor === "skill" && !preview)}
              >
                {busy && <Spinner data-icon="inline-start" />}
                {editor === "skill" ? "Install skill" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <AlertDialog
        open={!!remove}
        onOpenChange={(open) => {
          if (!open && !busy) setRemove(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {remove?.title}?</AlertDialogTitle>
            <AlertDialogDescription>
              {section === "memory"
                ? "Skye will no longer recall this saved memory. Past messages are unchanged."
                : section === "skills"
                  ? "This skill will no longer be available in new runs, including Telegram."
                  : "Future runs lose access. Existing group shares are also revoked. External actions already started cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && (
            <Alert>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  if (remove) await resourceRequest(remove.path, csrf, "DELETE")
                  setRemove(null)
                  if (detailId) router.push(`/library/${section}`)
                })
              }
            >
              {busy ? "Removing…" : "Remove"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
