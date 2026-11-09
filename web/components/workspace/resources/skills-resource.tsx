"use client"

import type { FormEvent } from "react"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Download01Icon,
  EyeIcon,
  File01Icon,
  MoreHorizontalIcon,
  SparklesIcon,
  Upload01Icon,
} from "@hugeicons/core-free-icons"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  CodeBlock,
  CodeBlockActions,
  CodeBlockContent,
  CodeBlockCopyButton,
  CodeBlockHeader,
  CodeBlockTitle,
} from "@/components/ui/code-block"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Item, ItemContent, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type {
  ResourceSnapshot,
  SkillRecord,
  SkillUpload,
} from "@/lib/contracts.generated"
import {
  resourceRequest,
  useResourceActions,
  useResourceSnapshot,
} from "@/components/workspace/resources/resource-api"
import {
  ResourceEmpty,
  ResourceError,
  ResourceList,
  ResourcePage,
  ResourceSearch,
  ResourceStatus,
} from "@/components/workspace/resources/resource-ui"

function downloadUrl(skill: SkillRecord) {
  return `/api/v1/skills/${encodeURIComponent(skill.id ?? "")}/download`
}

export function SkillsResource({
  initial,
  csrf,
  detailId,
  skillDetail,
}: {
  initial: ResourceSnapshot
  csrf: string
  detailId?: string
  skillDetail?: SkillRecord
}) {
  const router = useRouter()
  const { data, error: loadError, refresh } = useResourceSnapshot(
    initial,
    "skills"
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
  const [selected, setSelected] = useState<SkillRecord | null>(() =>
    detailId
      ? ((initial.skills ?? []).find((skill) => skill.id === detailId) ?? null)
      : null
  )
  const [details, setDetails] = useState<Record<string, SkillRecord>>(() =>
    skillDetail?.id ? { [skillDetail.id]: skillDetail } : {}
  )
  const [detailLoading, setDetailLoading] = useState(false)
  const detailRequest = useRef<string | null>(null)
  const [removeConfirm, setRemoveConfirm] = useState(false)

  const [uploadOpen, setUploadOpen] = useState(false)
  const [upload, setUpload] = useState<SkillUpload | null>(null)
  const [preview, setPreview] = useState<SkillRecord | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const skills = data.skills ?? []
  const needle = query.trim().toLowerCase()
  const filtered = skills.filter((skill) =>
    `${skill.name} ${skill.description}`.toLowerCase().includes(needle)
  )
  const selectedDetail = selected?.id ? details[selected.id] : undefined

  useEffect(() => {
    if (!selected?.id) return
    const id = selected.id
    if (details[id] || detailRequest.current === id) return
    detailRequest.current = id
    setDetailLoading(true)
    setError("")
    void resourceRequest<SkillRecord>(
      `/resources/skills/${encodeURIComponent(id)}`,
      csrf
    )
      .then((record) =>
        setDetails((current) => ({ ...current, [id]: record }))
      )
      .catch((requestError) => {
        setError((requestError as Error).message)
        detailRequest.current = null
      })
      .finally(() => setDetailLoading(false))
  }, [selected, details, csrf, setError])

  function openSkill(skill: SkillRecord) {
    setSelected(skill)
    setRemoveConfirm(false)
    setError("")
  }

  function closeSkill() {
    if (busy) return
    setSelected(null)
    setRemoveConfirm(false)
    setError("")
    if (detailId) router.replace("/library/skills")
  }

  function closeUpload() {
    if (busy) return
    setUploadOpen(false)
    setUpload(null)
    setPreview(null)
    setError("")
  }

  async function pickSkill(file: File | undefined) {
    setPreview(null)
    setUpload(null)
    setError("")
    if (!file) return
    if (file.size > 25 * 1024 * 1024) {
      setError("Use a skill smaller than 25 MB.")
      return
    }
    setPreviewLoading(true)
    try {
      const bytes = new Uint8Array(await file.arrayBuffer())
      let binary = ""
      for (let index = 0; index < bytes.length; index += 8192)
        binary += String.fromCharCode(
          ...bytes.subarray(index, index + 8192)
        )
      const payload = { filename: file.name, base64: btoa(binary) }
      const result = await resourceRequest<SkillRecord>(
        "/skills/preview",
        csrf,
        "POST",
        payload
      )
      setUpload(payload)
      setPreview(result)
    } catch (requestError) {
      setError((requestError as Error).message)
    } finally {
      setPreviewLoading(false)
    }
  }

  function installSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!upload) return
    void perform(async () => {
      await resourceRequest("/skills", csrf, "POST", upload)
      setUploadOpen(false)
      setUpload(null)
      setPreview(null)
      setStatus("Skill installed.")
    })
  }

  function deleteSkill() {
    if (!selected?.id) return
    const id = selected.id
    void perform(async () => {
      await resourceRequest(
        `/skills/${encodeURIComponent(id)}`,
        csrf,
        "DELETE"
      )
      setDetails((current) => {
        const next = { ...current }
        delete next[id]
        return next
      })
      setSelected(null)
      setRemoveConfirm(false)
      setStatus("Skill removed.")
      if (detailId) router.replace("/library/skills")
    })
  }

  return (
    <ResourcePage
      title="Skills"
      action={
        <Button
          aria-label="Upload skill"
          disabled={busy}
          onClick={() => {
            setError("")
            setUploadOpen(true)
          }}
        >
          <HugeiconsIcon icon={Upload01Icon} data-icon="inline-start" />
          <span className="hidden min-[380px]:inline">Upload skill</span>
        </Button>
      }
    >
      <ResourceSearch
        value={query}
        onChange={setQuery}
        placeholder="Search skills"
        className="sm:max-w-sm"
      />
      <ResourceStatus>{status}</ResourceStatus>

      {(error || loadError) && !selected && !uploadOpen && (
        <ResourceError
          message={error || loadError}
          errorRef={errorRef}
          onRetry={loadError && !error ? () => void refresh() : undefined}
        />
      )}

      {skills.length === 0 ? (
        <ResourceEmpty
          icon={<HugeiconsIcon icon={SparklesIcon} />}
          title="No skills yet"
          description="Teach Skye a repeated workflow."
          action={
            <Button onClick={() => setUploadOpen(true)}>
              <HugeiconsIcon icon={Upload01Icon} data-icon="inline-start" />
              Upload a skill
            </Button>
          }
        />
      ) : filtered.length === 0 ? (
        <ResourceEmpty
          icon={<HugeiconsIcon icon={SparklesIcon} />}
          title="No skills found"
          description="Try a different search."
          action={
            <Button variant="outline" onClick={() => setQuery("")}>
              Clear search
            </Button>
          }
        />
      ) : (
        <ResourceList>
          <div
            role="list"
            className="flex w-full flex-col divide-y divide-border"
          >
            {filtered.map((skill) => (
              <Item
                key={skill.id}
                role="listitem"
                className="relative rounded-none border-0 px-4 py-3.5 hover:bg-muted/25 sm:px-5"
              >
                <button
                  type="button"
                  aria-label={`Open ${skill.name}`}
                  className="absolute inset-0 z-0 rounded-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                  onClick={() => openSkill(skill)}
                />
                <ItemMedia
                  variant="icon"
                  className="pointer-events-none size-10 rounded-xl bg-muted"
                >
                  <HugeiconsIcon icon={SparklesIcon} />
                </ItemMedia>
                <ItemContent className="pointer-events-none">
                  <ItemTitle>{skill.name}</ItemTitle>
                  <p className="line-clamp-2 text-sm text-muted-foreground">
                    {skill.description}
                  </p>
                </ItemContent>
                <div className="relative z-10 flex shrink-0 items-center gap-1">
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      render={
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Actions for ${skill.name}`}
                        />
                      }
                    >
                      <HugeiconsIcon icon={MoreHorizontalIcon} />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuGroup>
                        <DropdownMenuItem onClick={() => openSkill(skill)}>
                          <HugeiconsIcon icon={EyeIcon} />
                          View details
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          render={
                            <a href={downloadUrl(skill)} download />
                          }
                        >
                          <HugeiconsIcon icon={Download01Icon} />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          variant="destructive"
                          onClick={() => {
                            setSelected(skill)
                            setRemoveConfirm(true)
                          }}
                        >
                          <HugeiconsIcon icon={Delete02Icon} />
                          Remove
                        </DropdownMenuItem>
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </Item>
            ))}
          </div>
        </ResourceList>
      )}

      <Sheet
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) closeSkill()
        }}
      >
        <SheetContent className="gap-0 p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-xl">
          {selected && (
            <>
              <SheetHeader className="border-b p-6 pr-14">
                <div className="flex items-start gap-3">
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-muted">
                    <HugeiconsIcon icon={SparklesIcon} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <SheetTitle className="truncate text-lg">
                      {selected.name}
                    </SheetTitle>
                    <SheetDescription className="line-clamp-2">
                      {selected.description}
                    </SheetDescription>
                  </div>
                </div>
              </SheetHeader>
              <Tabs
                defaultValue="instructions"
                className="flex min-h-0 flex-1 flex-col gap-0"
              >
                <div className="border-b px-6 py-3">
                  <TabsList aria-label={`${selected.name} details`}>
                    <TabsTrigger value="instructions">
                      Instructions
                    </TabsTrigger>
                    <TabsTrigger value="files">Files</TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent
                  value="instructions"
                  className="flex min-h-0 flex-1 flex-col p-6"
                >
                  {detailLoading && !selectedDetail ? (
                    <div className="flex flex-col gap-3">
                      <Skeleton className="h-5 w-32" />
                      <Skeleton className="h-48 w-full" />
                    </div>
                  ) : selectedDetail?.instructions ? (
                    <CodeBlock>
                      <CodeBlockHeader>
                        <CodeBlockTitle>
                          <HugeiconsIcon icon={File01Icon} />
                          SKILL.md
                        </CodeBlockTitle>
                        <CodeBlockActions>
                          <CodeBlockCopyButton
                            value={selectedDetail.instructions}
                          />
                        </CodeBlockActions>
                      </CodeBlockHeader>
                      <CodeBlockContent wrap className="max-h-[55dvh]">
                        {selectedDetail.instructions}
                      </CodeBlockContent>
                    </CodeBlock>
                  ) : (
                    <Empty>
                      <EmptyHeader>
                        <EmptyTitle>No instructions</EmptyTitle>
                      </EmptyHeader>
                    </Empty>
                  )}
                </TabsContent>
                <TabsContent
                  value="files"
                  className="min-h-0 flex-1 overflow-y-auto p-6"
                >
                  {selectedDetail?.files?.length ? (
                    <ItemGroup className="gap-2">
                      {selectedDetail.files.map((file) => (
                        <Item key={file} variant="muted" size="sm">
                          <ItemMedia variant="icon">
                            <HugeiconsIcon icon={File01Icon} />
                          </ItemMedia>
                          <ItemContent>
                            <ItemTitle className="font-normal">
                              {file}
                            </ItemTitle>
                          </ItemContent>
                        </Item>
                      ))}
                    </ItemGroup>
                  ) : (
                    <Empty>
                      <EmptyHeader>
                        <EmptyTitle>No files</EmptyTitle>
                      </EmptyHeader>
                    </Empty>
                  )}
                </TabsContent>
              </Tabs>
              {error && (
                <p className="border-t px-6 py-3 text-sm text-destructive">
                  {error}
                </p>
              )}
              <SheetFooter className="border-t p-4">
                {removeConfirm ? (
                  <div className="flex w-full flex-col gap-3">
                    <p className="text-sm text-muted-foreground">
                      Remove this skill? New runs will not use it.
                    </p>
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() => setRemoveConfirm(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="destructive"
                        disabled={busy}
                        onClick={deleteSkill}
                      >
                        {busy && <Spinner data-icon="inline-start" />}
                        Remove
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex w-full items-center justify-between gap-2">
                    <Button
                      variant="ghost"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => setRemoveConfirm(true)}
                    >
                      <HugeiconsIcon
                        icon={Delete02Icon}
                        data-icon="inline-start"
                      />
                      Remove skill
                    </Button>
                    <Button
                      variant="outline"
                      nativeButton={false}
                      render={
                        <a href={downloadUrl(selected)} download />
                      }
                    >
                      <HugeiconsIcon
                        icon={Download01Icon}
                        data-icon="inline-start"
                      />
                      Download
                    </Button>
                  </div>
                )}
              </SheetFooter>
            </>
          )}
        </SheetContent>
      </Sheet>

      <Sheet
        open={uploadOpen}
        onOpenChange={(open) => {
          if (!open) closeUpload()
        }}
      >
        <SheetContent className="gap-0 p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-md">
          <form
            onSubmit={installSkill}
            className="flex min-h-0 flex-1 flex-col"
          >
            <SheetHeader className="border-b p-6 pr-14">
              <SheetTitle>Upload skill</SheetTitle>
              <SheetDescription>
                Install a SKILL.md file or a zip bundle.
              </SheetDescription>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              {error && (
                <Alert variant="destructive" className="mb-5">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <label
                htmlFor="skill-upload"
                className="flex cursor-pointer flex-col items-center gap-2 rounded-3xl border border-dashed p-8 text-center transition-colors hover:bg-muted/30"
              >
                <div className="flex size-11 items-center justify-center rounded-2xl bg-muted">
                  <HugeiconsIcon icon={Upload01Icon} />
                </div>
                <span className="font-medium">
                  {preview ? preview.name : "Choose a skill file"}
                </span>
                <span className="text-sm text-muted-foreground">
                  SKILL.md or .zip
                </span>
                <Input
                  id="skill-upload"
                  type="file"
                  name="skill"
                  accept=".md,.zip"
                  aria-label="SKILL.md or zip bundle"
                  disabled={busy || previewLoading}
                  onChange={(event) =>
                    void pickSkill(event.target.files?.[0])
                  }
                  className="sr-only"
                />
              </label>
              {previewLoading && (
                <div className="mt-5 flex flex-col gap-3">
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="h-36 w-full" />
                </div>
              )}
              {preview && (
                <div className="mt-5 flex flex-col gap-3">
                  <div>
                    <h3 className="text-base font-medium">{preview.name}</h3>
                    <p className="text-sm text-muted-foreground">
                      {preview.description}
                    </p>
                  </div>
                  {preview.instructions && (
                    <CodeBlock size="sm">
                      <CodeBlockHeader>
                        <CodeBlockTitle>
                          <HugeiconsIcon icon={File01Icon} />
                          SKILL.md
                        </CodeBlockTitle>
                      </CodeBlockHeader>
                      <CodeBlockContent
                        wrap
                        className="max-h-48 text-xs"
                      >
                        {preview.instructions}
                      </CodeBlockContent>
                    </CodeBlock>
                  )}
                </div>
              )}
            </div>
            <SheetFooter className="flex-row justify-end border-t p-4">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={closeUpload}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={busy || !preview}>
                {busy && <Spinner data-icon="inline-start" />}
                Install skill
              </Button>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>
    </ResourcePage>
  )
}
