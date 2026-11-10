"use client"

import type { FormEvent, ReactNode } from "react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  AlertCircleIcon,
  AppStoreIcon,
  CheckmarkCircle02Icon,
  Clock01Icon,
  Delete02Icon,
  Link01Icon,
  MoreHorizontalIcon,
  PencilEdit01Icon,
  Plug01Icon,
  Refresh01Icon,
  Search01Icon,
  ServerStack01Icon,
} from "@hugeicons/core-free-icons"
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
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type {
  ConnectorRecord,
  ResourceSnapshot,
} from "@/lib/contracts.generated"
import {
  resourceRequest,
  useResourceActions,
  useResourceSnapshot,
} from "@/components/workspace/resources/resource-api"
import { ConnectorLogo } from "@/components/workspace/resources/connector-logo"
import {
  ResourceEmpty,
  ResourceError,
  ResourceList,
  ResourcePage,
  ResourceSearch,
  ResourceStatus,
  SectionLabel,
} from "@/components/workspace/resources/resource-ui"
import { useI18n } from "@/components/i18n-provider"
import type { MessageKey, MessageValues } from "@/lib/i18n"

type Translate = (key: MessageKey, values?: MessageValues) => string
type ConnectorStatusTone = "secondary" | "outline" | "destructive"

function connectorStatus(
  connector: ConnectorRecord,
  t: Translate
): {
  label: string
  icon: typeof Add01Icon
  tone: ConnectorStatusTone
} {
  if (connector.kind === "custom") {
    return connector.status === "disabled"
      ? {
          label: t("connectors.disabled"),
          icon: AlertCircleIcon,
          tone: "destructive",
        }
      : {
          label: t("connectors.ready"),
          icon: ServerStack01Icon,
          tone: "secondary",
        }
  }
  if (connector.status === "connected")
    return {
      label: t("connectors.connected"),
      icon: CheckmarkCircle02Icon,
      tone: "secondary",
    }
  if (connector.status === "pending")
    return { label: t("connectors.pending"), icon: Clock01Icon, tone: "outline" }
  return {
    label: t("connectors.attention"),
    icon: AlertCircleIcon,
    tone: "destructive",
  }
}

function ConnectorStatusBadge({ connector }: { connector: ConnectorRecord }) {
  const { t } = useI18n()
  const meta = connectorStatus(connector, t)
  return (
    <Badge variant={meta.tone} className="gap-1.5 font-normal">
      <HugeiconsIcon icon={meta.icon} />
      {meta.label}
    </Badge>
  )
}

function ActionRow({
  icon,
  children,
  onClick,
  destructive = false,
  disabled = false,
}: {
  icon: typeof Add01Icon
  children: ReactNode
  onClick: () => void
  destructive?: boolean
  disabled?: boolean
}) {
  return (
    <Button
      variant="ghost"
      className={
        destructive
          ? "w-full justify-start text-destructive hover:bg-destructive/10 hover:text-destructive"
          : "w-full justify-start"
      }
      onClick={onClick}
      disabled={disabled}
    >
      <HugeiconsIcon icon={icon} data-icon="inline-start" />
      {children}
    </Button>
  )
}

function ConnectorPopover({
  connector,
  csrf,
  consentEnabled,
  busy,
  defaultOpen,
  trigger,
  onConnect,
  onEdit,
  onRemove,
  onRefresh,
}: {
  connector: ConnectorRecord
  csrf: string
  consentEnabled: boolean
  busy: boolean
  defaultOpen?: boolean
  trigger: ReactNode
  onConnect: (connector: ConnectorRecord) => void
  onEdit: (connector: ConnectorRecord) => void
  onRemove: (connector: ConnectorRecord) => void
  onRefresh: () => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(Boolean(defaultOpen))
  const [testing, setTesting] = useState(false)
  const [testStatus, setTestStatus] = useState("")

  async function testConnection() {
    setTesting(true)
    setTestStatus("")
    try {
      const result = await resourceRequest<{ tools: number }>(
        `/connectors/custom/${connector.id}/test`,
        csrf,
        "POST",
        {}
      )
      setTestStatus(t("connectors.reachable", { count: result.tools }))
    } catch (error) {
      setTestStatus((error as Error).message)
    } finally {
      setTesting(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger className="block w-full rounded-2xl text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
        {trigger}
      </PopoverTrigger>
      <PopoverContent align="end" sideOffset={8} className="w-80 gap-0 p-0">
        <div className="flex items-start gap-3 border-b p-4">
          <div className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-muted p-1.5">
            <ConnectorLogo
              id={connector.id}
              name={connector.name}
              kind={connector.kind}
            />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{connector.name}</p>
            <ConnectorStatusBadge connector={connector} />
          </div>
        </div>
        <div className="flex flex-col gap-1 p-2">
          {connector.kind === "custom" && connector.url && (
            <p
              className="truncate px-3 pb-2 text-sm text-muted-foreground"
              title={connector.url}
            >
              {connector.url}
            </p>
          )}
          {connector.kind === "custom" ? (
            <>
              <ActionRow
                icon={PencilEdit01Icon}
                onClick={() => {
                  setOpen(false)
                  onEdit(connector)
                }}
                disabled={busy}
              >
                {t("connectors.editServer")}
              </ActionRow>
              <ActionRow
                icon={Refresh01Icon}
                onClick={() => void testConnection()}
                disabled={testing}
              >
                {testing ? t("connectors.testing") : t("connectors.test")}
              </ActionRow>
              <ActionRow
                icon={Delete02Icon}
                destructive
                onClick={() => {
                  setOpen(false)
                  onRemove(connector)
                }}
                disabled={busy}
              >
                {t("connectors.removeServer")}
              </ActionRow>
            </>
          ) : (
            <>
              <ActionRow
                icon={Link01Icon}
                onClick={() => {
                  setOpen(false)
                  onConnect(connector)
                }}
                disabled={busy || !consentEnabled}
              >
                {connector.status === "connected"
                  ? t("connectors.reconnect")
                  : t("connectors.connect")}
              </ActionRow>
              <ActionRow
                icon={Refresh01Icon}
                onClick={() => {
                  setOpen(false)
                  onRefresh()
                }}
                disabled={busy}
              >
                {t("connectors.checkStatus")}
              </ActionRow>
              <ActionRow
                icon={Delete02Icon}
                destructive
                onClick={() => {
                  setOpen(false)
                  onRemove(connector)
                }}
                disabled={busy}
              >
                {t("connectors.disconnect")}
              </ActionRow>
            </>
          )}
        </div>
        {testStatus && (
          <p className="border-t px-4 py-3 text-sm text-muted-foreground">
            {testStatus}
          </p>
        )}
      </PopoverContent>
    </Popover>
  )
}

function ConnectorTile({
  connector,
  csrf,
  consentEnabled,
  busy,
  defaultOpen,
  onConnect,
  onEdit,
  onRemove,
  onRefresh,
}: {
  connector: ConnectorRecord
  csrf: string
  consentEnabled: boolean
  busy: boolean
  defaultOpen?: boolean
  onConnect: (connector: ConnectorRecord) => void
  onEdit: (connector: ConnectorRecord) => void
  onRemove: (connector: ConnectorRecord) => void
  onRefresh: () => void
}) {
  return (
    <ConnectorPopover
      connector={connector}
      csrf={csrf}
      consentEnabled={consentEnabled}
      busy={busy}
      defaultOpen={defaultOpen}
      onConnect={onConnect}
      onEdit={onEdit}
      onRemove={onRemove}
      onRefresh={onRefresh}
      trigger={
        <Item
          variant="outline"
          className="cursor-pointer flex-nowrap bg-card/40 text-left transition-colors hover:bg-muted/30"
        >
          <ItemMedia
            variant="image"
            className="rounded-xl bg-muted p-1.5"
          >
            <ConnectorLogo
              id={connector.id}
              name={connector.name}
              kind={connector.kind}
            />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>{connector.name}</ItemTitle>
            <ConnectorStatusBadge connector={connector} />
          </ItemContent>
          <ItemActions>
            <HugeiconsIcon
              icon={MoreHorizontalIcon}
              className="text-muted-foreground"
            />
          </ItemActions>
        </Item>
      }
    />
  )
}

function ServerRow({
  connector,
  csrf,
  consentEnabled,
  busy,
  defaultOpen,
  onConnect,
  onEdit,
  onRemove,
  onRefresh,
}: {
  connector: ConnectorRecord
  csrf: string
  consentEnabled: boolean
  busy: boolean
  defaultOpen?: boolean
  onConnect: (connector: ConnectorRecord) => void
  onEdit: (connector: ConnectorRecord) => void
  onRemove: (connector: ConnectorRecord) => void
  onRefresh: () => void
}) {
  return (
    <ConnectorPopover
      connector={connector}
      csrf={csrf}
      consentEnabled={consentEnabled}
      busy={busy}
      defaultOpen={defaultOpen}
      onConnect={onConnect}
      onEdit={onEdit}
      onRemove={onRemove}
      onRefresh={onRefresh}
      trigger={
        <Item className="cursor-pointer rounded-none border-0 px-4 py-3.5 text-left hover:bg-muted/25 sm:px-5">
          <ItemMedia
            variant="image"
            className="rounded-xl bg-muted p-1.5"
          >
            <ConnectorLogo
              id={connector.id}
              name={connector.name}
              kind={connector.kind}
            />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>{connector.name}</ItemTitle>
            {connector.url && (
              <ItemDescription className="truncate">
                {connector.url}
              </ItemDescription>
            )}
          </ItemContent>
          <ItemActions>
            <ConnectorStatusBadge connector={connector} />
            <HugeiconsIcon
              icon={MoreHorizontalIcon}
              className="text-muted-foreground"
            />
          </ItemActions>
        </Item>
      }
    />
  )
}

export function ConnectorsResource({
  initial,
  csrf,
  detailId,
}: {
  initial: ResourceSnapshot
  csrf: string
  detailId?: string
}) {
  const { t } = useI18n()
  const { data, error: loadError, refresh } = useResourceSnapshot(
    initial,
    "connectors"
  )
  const {
    busy,
    error,
    status,
    setError,
    setStatus,
    perform,
    errorRef,
  } = useResourceActions(refresh)
  const [query, setQuery] = useState("")
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [catalog, setCatalog] = useState<ConnectorRecord[] | null>(null)
  const [catalogQuery, setCatalogQuery] = useState("")
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState("")
  const catalogRequestId = useRef(0)

  const [serverOpen, setServerOpen] = useState(false)
  const [server, setServer] = useState<ConnectorRecord | null>(null)
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [headers, setHeaders] = useState("")
  const [replaceCredentials, setReplaceCredentials] = useState(false)

  const [remove, setRemove] = useState<ConnectorRecord | null>(null)

  const connectors = data.connectors ?? []
  const apps = useMemo(
    () => connectors.filter((connector) => connector.kind === "app"),
    [connectors]
  )
  const servers = useMemo(
    () => connectors.filter((connector) => connector.kind === "custom"),
    [connectors]
  )
  const needle = query.trim().toLowerCase()
  const filteredApps = apps.filter((connector) =>
    connector.name.toLowerCase().includes(needle)
  )
  const filteredServers = servers.filter((connector) =>
    connector.name.toLowerCase().includes(needle)
  )
  const loadCatalog = useCallback(
    async (value: string) => {
      const requestId = ++catalogRequestId.current
      setCatalogLoading(true)
      setCatalogError("")
      try {
        const result = await resourceRequest<{
          connectors: ConnectorRecord[]
        }>(`/connectors/catalog?q=${encodeURIComponent(value)}`, csrf)
        if (requestId === catalogRequestId.current)
          setCatalog(result.connectors)
      } catch (error) {
        if (requestId === catalogRequestId.current)
          setCatalogError((error as Error).message)
      } finally {
        if (requestId === catalogRequestId.current) setCatalogLoading(false)
      }
    },
    [csrf]
  )

  useEffect(() => {
    if (!catalogOpen) return
    const timer = window.setTimeout(
      () => void loadCatalog(catalogQuery.trim()),
      catalogQuery ? 250 : 0
    )
    return () => window.clearTimeout(timer)
  }, [catalogOpen, catalogQuery, loadCatalog])

  function openCatalog() {
    setError("")
    setCatalog(null)
    setCatalogQuery("")
    setCatalogOpen(true)
  }

  function connect(connector: ConnectorRecord) {
    void perform(async () => {
      const result = await resourceRequest<{ url: string | null }>(
        `/connectors/apps/${encodeURIComponent(connector.id)}/connect`,
        csrf,
        "POST",
        {}
      )
      if (result.url) {
        const parsed = new URL(result.url)
        if (parsed.protocol !== "https:")
          throw new Error(t("connectors.consentUnavailable"))
        window.location.assign(parsed.href)
        return
      }
      setStatus(t("connectors.connectedToast", { name: connector.name }))
    })
  }

  function openServer(connector: ConnectorRecord | null) {
    setServer(connector)
    setName(connector?.name ?? "")
    setUrl(connector?.url ?? "")
    setHeaders("")
    setReplaceCredentials(!connector)
    setError("")
    setServerOpen(true)
  }

  function saveServer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || !url.trim()) return
    void perform(async () => {
      const includeHeaders =
        Boolean(replaceCredentials) && data.credentials_configured
      await resourceRequest(
        server
          ? `/connectors/custom/${server.id}`
          : "/connectors/custom",
        csrf,
        server ? "PATCH" : "POST",
        { name, url, ...(includeHeaders ? { headers } : {}) }
      )
      setServerOpen(false)
      setStatus(server ? t("connectors.updated") : t("connectors.added"))
    })
  }

  function removeConnector() {
    if (!remove) return
    void perform(async () => {
      await resourceRequest(
        remove.kind === "custom"
          ? `/connectors/custom/${remove.id}`
          : `/connectors/apps/${remove.id}`,
        csrf,
        "DELETE"
      )
      setRemove(null)
      setStatus(
        remove.kind === "custom"
          ? t("connectors.removed")
          : t("connectors.disconnected")
      )
    })
  }

  const hasAny = apps.length + servers.length > 0
  const hasMatches = filteredApps.length + filteredServers.length > 0
  const appStatus = !data.apps_configured
    ? {
        text: t("connectors.noAppsConfigured"),
        retry: false,
      }
    : !data.app_consent_enabled
      ? {
          text: t("connectors.consentPending"),
          retry: false,
        }
      : !data.provider_verified
        ? { text: t("connectors.statusUnverified"), retry: true }
        : null

  return (
    <ResourcePage
      title={t("connectors.title")}
      action={
        <>
          <Button
            aria-label={t("connectors.browse")}
            disabled={!data.apps_configured || busy}
            onClick={openCatalog}
          >
            <HugeiconsIcon icon={AppStoreIcon} data-icon="inline-start" />
            <span className="hidden min-[380px]:inline">{t("connectors.browse")}</span>
          </Button>
          <Button
            variant="outline"
            aria-label={t("connectors.addMcp")}
            disabled={busy}
            onClick={() => openServer(null)}
          >
            <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
            <span className="hidden sm:inline">{t("connectors.addServer")}</span>
          </Button>
        </>
      }
    >
      <ResourceSearch
        value={query}
        onChange={setQuery}
        placeholder={t("connectors.search")}
        className="sm:max-w-sm"
      />
      <ResourceStatus>{status}</ResourceStatus>

      {appStatus && (
        <Alert>
          <HugeiconsIcon icon={AlertCircleIcon} />
          <AlertDescription>
            {appStatus.text}
            {appStatus.retry && (
              <Button variant="link" size="sm" onClick={() => void refresh()}>
                {t("common.retry")}
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {(error || loadError) && !serverOpen && !catalogOpen && !remove && (
        <ResourceError
          message={error || loadError}
          errorRef={errorRef}
          onRetry={loadError && !error ? () => void refresh() : undefined}
        />
      )}

      {!hasAny ? (
        <ResourceEmpty
          icon={<HugeiconsIcon icon={Plug01Icon} />}
          title={t("connectors.empty")}
          description={t("connectors.emptyDescription")}
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              {data.apps_configured && (
                <Button onClick={openCatalog}>
                  <HugeiconsIcon
                    icon={AppStoreIcon}
                    data-icon="inline-start"
                  />
                  {t("connectors.browse")}
                </Button>
              )}
              <Button variant="outline" onClick={() => openServer(null)}>
                <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
                {t("connectors.addMcp")}
              </Button>
            </div>
          }
        />
      ) : !hasMatches ? (
        <ResourceEmpty
          icon={<HugeiconsIcon icon={Search01Icon} />}
          title={t("connectors.notFound")}
          description={t("skills.tryDifferent")}
          action={
            <Button variant="outline" onClick={() => setQuery("")}>
              {t("connectors.clearSearch")}
            </Button>
          }
        />
      ) : (
        <>
          {filteredApps.length > 0 && (
            <section className="flex flex-col gap-3">
              <SectionLabel count={filteredApps.length}>{t("connectors.apps")}</SectionLabel>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {filteredApps.map((connector) => (
                  <ConnectorTile
                    key={connector.id}
                    connector={connector}
                    csrf={csrf}
                    consentEnabled={Boolean(data.app_consent_enabled)}
                    busy={busy}
                    defaultOpen={detailId === connector.id}
                    onConnect={connect}
                    onEdit={openServer}
                    onRemove={setRemove}
                    onRefresh={() => void refresh()}
                  />
                ))}
              </div>
            </section>
          )}
          {filteredServers.length > 0 && (
            <section className="flex flex-col gap-3">
              <SectionLabel count={filteredServers.length}>
                {t("connectors.servers")}
              </SectionLabel>
              <ResourceList>
                <div className="flex flex-col divide-y divide-border">
                  {filteredServers.map((connector) => (
                    <ServerRow
                      key={connector.id}
                      connector={connector}
                      csrf={csrf}
                      consentEnabled={Boolean(data.app_consent_enabled)}
                      busy={busy}
                      defaultOpen={detailId === connector.id}
                      onConnect={connect}
                      onEdit={openServer}
                      onRemove={setRemove}
                      onRefresh={() => void refresh()}
                    />
                  ))}
                </div>
              </ResourceList>
            </section>
          )}
        </>
      )}

      <Sheet
        open={catalogOpen}
        onOpenChange={(open) => {
          if (!open && !busy) setCatalogOpen(false)
        }}
      >
        <SheetContent className="gap-0 p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-md">
          <SheetHeader className="border-b p-6 pr-14">
            <SheetTitle>{t("connectors.browseTitle")}</SheetTitle>
            <SheetDescription>
              {t("connectors.browseDescription")}
            </SheetDescription>
          </SheetHeader>
          <div className="border-b p-4">
            <ResourceSearch
              value={catalogQuery}
              onChange={setCatalogQuery}
              placeholder={t("connectors.searchApps")}
              loading={catalogLoading}
            />
          </div>
          {!data.app_consent_enabled && (
            <div className="border-b p-4">
              <Alert>
                <HugeiconsIcon icon={AlertCircleIcon} />
                <AlertDescription>
                  {t("connectors.appsDisabled")}
                </AlertDescription>
              </Alert>
            </div>
          )}
          {error && catalogOpen && (
            <div className="border-b p-4">
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            </div>
          )}
          <ScrollArea className="min-h-0 flex-1">
            <div className="p-2">
              {catalogError ? (
                <ResourceError
                  message={catalogError}
                  onRetry={() => void loadCatalog(catalogQuery.trim())}
                />
              ) : catalog === null ? (
                <div className="flex flex-col gap-2 p-2">
                  {[0, 1, 2, 3].map((index) => (
                    <Skeleton key={index} className="h-14" />
                  ))}
                </div>
              ) : catalog.length === 0 ? (
                <ResourceEmpty
                  icon={<HugeiconsIcon icon={Search01Icon} />}
                  title={t("connectors.noApps")}
                  description={t("skills.tryDifferent")}
                  action={
                    <Button
                      variant="outline"
                      onClick={() => setCatalogQuery("")}
                    >
                      {t("connectors.clearSearch")}
                    </Button>
                  }
                />
              ) : (
                <div className="flex flex-col gap-1">
                  {catalog.map((app) => {
                    const existing = connectors.find(
                      (connector) =>
                        connector.kind === "app" && connector.id === app.id
                    )
                    return (
                      <div
                        key={app.id}
                        className="flex items-center gap-3 rounded-2xl px-3 py-2.5 transition-colors hover:bg-muted/30"
                      >
                        <div className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-muted p-1.5">
                          <ConnectorLogo
                            id={app.id}
                            name={app.name}
                            kind="app"
                          />
                        </div>
                        <p className="min-w-0 flex-1 truncate text-sm font-medium">
                          {app.name}
                        </p>
                        {existing ? (
                          <ConnectorStatusBadge connector={existing} />
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy || !data.app_consent_enabled}
                            onClick={() => connect(app)}
                          >
                            {t("connectors.connect")}
                          </Button>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </ScrollArea>
        </SheetContent>
      </Sheet>

      <Sheet
        open={serverOpen}
        onOpenChange={(open) => {
          if (!open && !busy) setServerOpen(false)
        }}
      >
        <SheetContent className="gap-0 p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-md">
          <form
            onSubmit={saveServer}
            className="flex min-h-0 flex-1 flex-col"
          >
            <SheetHeader className="border-b p-6 pr-14">
              <SheetTitle>
                {server ? t("connectors.editTitle") : t("connectors.addTitle")}
              </SheetTitle>
              <SheetDescription>{t("connectors.httpsOnly")}</SheetDescription>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              {error && (
                <Alert variant="destructive" className="mb-5">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="mcp-name">{t("connectors.name")}</FieldLabel>
                  <Input
                    id="mcp-name"
                    name="name"
                    required
                    maxLength={64}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="mcp-url">{t("connectors.url")}</FieldLabel>
                  <Input
                    id="mcp-url"
                    name="url"
                    type="url"
                    required
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder="https://example.com/mcp"
                    autoCorrect="off"
                    autoCapitalize="none"
                    spellCheck={false}
                  />
                </Field>
                {server && data.credentials_configured && (
                  <Field orientation="horizontal">
                    <FieldLabel htmlFor="replace-credentials">
                      {t("connectors.replaceCredentials")}
                    </FieldLabel>
                    <Switch
                      id="replace-credentials"
                      checked={replaceCredentials}
                      onCheckedChange={setReplaceCredentials}
                    />
                  </Field>
                )}
                {(replaceCredentials || (!server && data.credentials_configured)) &&
                  data.credentials_configured && (
                    <Field>
                      <FieldLabel htmlFor="mcp-headers">{t("connectors.headers")}</FieldLabel>
                      <Textarea
                        id="mcp-headers"
                        name="headers"
                        autoComplete="off"
                        spellCheck={false}
                        value={headers}
                        onChange={(event) => setHeaders(event.target.value)}
                        rows={3}
                      />
                      <FieldDescription>
                        {t("connectors.headersHint")}
                      </FieldDescription>
                    </Field>
                  )}
              </FieldGroup>
            </div>
            <SheetFooter className="flex-row justify-end border-t p-4">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => setServerOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="submit"
                disabled={busy || !name.trim() || !url.trim()}
              >
                {busy && <Spinner data-icon="inline-start" />}
                {t("connectors.save")}
              </Button>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>

      <AlertDialog
        open={!!remove}
        onOpenChange={(open) => {
          if (!open && !busy) setRemove(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {remove?.kind === "custom"
                ? t("connectors.removeTitle", { name: remove.name })
                : t("connectors.disconnectTitle", {
                    name: remove?.name ?? t("connectors.thisApp"),
                  })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {remove?.kind === "custom"
                ? t("connectors.removeDescription")
                : t("connectors.disconnectDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>{t("common.cancel")}</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={removeConnector}
            >
              {busy && <Spinner data-icon="inline-start" />}
              {remove?.kind === "custom"
                ? t("connectors.removeConfirm")
                : t("connectors.disconnectConfirm")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ResourcePage>
  )
}
