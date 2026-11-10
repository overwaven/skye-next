"use client"

import type { FormEvent } from "react"
import { useEffect, useMemo, useRef, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowDown01Icon,
  BrainIcon,
  Delete02Icon,
  FilterIcon,
  Folder01Icon,
  MoreHorizontalIcon,
  PencilEdit01Icon,
  Search01Icon,
  Settings02Icon,
  StarIcon,
  Tag01Icon,
  Task01Icon,
  UserIcon,
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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Field, FieldLabel } from "@/components/ui/field"
import { Item, ItemActions, ItemContent } from "@/components/ui/item"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type {
  MemoryRecord,
  MemoryWrite,
  ResourceSnapshot,
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
import { useI18n } from "@/components/i18n-provider"
import type { MessageKey, MessageValues } from "@/lib/i18n"

type MemoryCategory = NonNullable<MemoryWrite["category"]>
type Translate = (key: MessageKey, values?: MessageValues) => string

const categoryOptions = [
  { value: "personal", labelKey: "memory.personal", icon: UserIcon },
  { value: "preference", labelKey: "memory.preference", icon: StarIcon },
  { value: "project", labelKey: "memory.project", icon: Folder01Icon },
  { value: "instruction", labelKey: "memory.instruction", icon: Task01Icon },
  { value: "other", labelKey: "memory.other", icon: Tag01Icon },
] satisfies {
  value: MemoryCategory
  labelKey: MessageKey
  icon: typeof Add01Icon
}[]

function categoryOption(value: MemoryCategory | undefined, t: Translate) {
  const option =
    categoryOptions.find((option) => option.value === value) ?? {
      value: "other" as const,
      labelKey: "memory.other" as const,
      icon: Tag01Icon,
    }
  return { ...option, label: t(option.labelKey) }
}

function CategoryBadge({ category }: { category?: MemoryCategory }) {
  const { t } = useI18n()
  const option = categoryOption(category, t)
  return (
    <Badge variant="secondary" className="gap-1.5 font-normal">
      <HugeiconsIcon icon={option.icon} />
      {option.label}
    </Badge>
  )
}

function MemoryForm({
  memory,
  csrf,
  onSaved,
  onCancel,
}: {
  memory: MemoryRecord | null
  csrf: string
  onSaved: () => void
  onCancel: () => void
}) {
  const { t } = useI18n()
  const [content, setContent] = useState(memory?.content ?? "")
  const [kind, setKind] = useState<MemoryCategory>(
    memory?.category ?? "other"
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    textareaRef.current?.focus()
    if (memory) textareaRef.current?.select()
  }, [memory])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!content.trim()) return
    setSaving(true)
    setError("")
    try {
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
      onSaved()
    } catch (requestError) {
      setError((requestError as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      <PopoverTitle className="text-base font-medium">
        {memory ? t("memory.edit") : t("memory.new")}
      </PopoverTitle>
      <Textarea
        ref={textareaRef}
        aria-label={t("memory.title")}
        name="content"
        required
        maxLength={500}
        rows={3}
        value={content}
        onChange={(event) => {
          setContent(event.target.value)
          setError("")
        }}
        placeholder={t("memory.placeholder")}
        className="min-h-24 resize-none bg-background"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup
          aria-label={t("memory.categoryAria")}
          value={[kind]}
          onValueChange={(value) => {
            const next = value[0] as MemoryCategory | undefined
            if (next) setKind(next)
          }}
          variant="outline"
          size="sm"
          className="flex-wrap"
        >
          {categoryOptions.map((option) => (
            <ToggleGroupItem
              key={option.value}
              value={option.value}
              aria-label={t(option.labelKey)}
            >
              <HugeiconsIcon icon={option.icon} data-icon="inline-start" />
              {t(option.labelKey)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <span className="text-sm text-muted-foreground tabular-nums">
          {content.length}/500
        </span>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={saving}
        >
          {t("common.cancel")}
        </Button>
        <Button type="submit" disabled={saving || !content.trim()}>
          {saving && <Spinner data-icon="inline-start" />}
          {t("common.save")}
        </Button>
      </div>
    </form>
  )
}

function MemoryRow({
  memory,
  csrf,
  onSaved,
  onDelete,
}: {
  memory: MemoryRecord
  csrf: string
  onSaved: () => void
  onDelete: (memory: MemoryRecord) => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<"actions" | "edit">("actions")

  function changeOpen(next: boolean) {
    setOpen(next)
    if (!next) setMode("actions")
  }

  return (
    <Popover open={open} onOpenChange={changeOpen}>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            className="shrink-0"
            aria-label={t("memory.actionsFor", { content: memory.content.slice(0, 40) })}
          />
        }
      >
        <HugeiconsIcon icon={MoreHorizontalIcon} />
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={6}
        className={
          mode === "edit"
            ? "w-[min(calc(100vw-2rem),22rem)] p-4"
            : "w-48 gap-0.5 p-1.5"
        }
      >
        {mode === "edit" ? (
          <MemoryForm
            memory={memory}
            csrf={csrf}
            onCancel={() => setOpen(false)}
            onSaved={() => {
              setOpen(false)
              setMode("actions")
              onSaved()
            }}
          />
        ) : (
          <>
            <PopoverTitle className="sr-only">{t("memory.title")}</PopoverTitle>
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={() => setMode("edit")}
            >
              <HugeiconsIcon icon={PencilEdit01Icon} data-icon="inline-start" />
              {t("common.edit")}
            </Button>
            <Button
              variant="ghost"
              className="w-full justify-start text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => {
                setOpen(false)
                onDelete(memory)
              }}
            >
              <HugeiconsIcon icon={Delete02Icon} data-icon="inline-start" />
              {t("common.delete")}
            </Button>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}

export function MemoryResource({
  initial,
  csrf,
}: {
  initial: ResourceSnapshot
  csrf: string
}) {
  const { t } = useI18n()
  const { data, error: loadError, refresh } = useResourceSnapshot(
    initial,
    "memory"
  )
  const {
    busy,
    error,
    status,
    setStatus,
    perform,
    errorRef,
  } = useResourceActions(refresh)
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState<MemoryCategory | "all">("all")
  const [categoryOpen, setCategoryOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [remove, setRemove] = useState<MemoryRecord | null>(null)

  const memories = data.memories ?? []
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return memories.filter(
      (memory) =>
        (category === "all" || memory.category === category) &&
        (!needle || memory.content.toLowerCase().includes(needle))
    )
  }, [memories, query, category])

  function deleteMemory() {
    if (!remove) return
    void perform(async () => {
      await resourceRequest(`/memories/${remove.id}`, csrf, "DELETE")
      setRemove(null)
      setStatus(t("memory.deleted"))
    })
  }

  function clearFilters() {
    setQuery("")
    setCategory("all")
  }

  return (
    <ResourcePage
      title={t("memory.title")}
      action={
        <>
          <Popover>
            <PopoverTrigger
              render={
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={t("memory.settings")}
                />
              }
            >
              <HugeiconsIcon icon={Settings02Icon} />
            </PopoverTrigger>
            <PopoverContent align="end" className="w-72">
              <PopoverHeader>
                <PopoverTitle>{t("memory.title")}</PopoverTitle>
                <PopoverDescription>
                  {t("memory.description")}
                </PopoverDescription>
              </PopoverHeader>
              <Field orientation="horizontal">
                <FieldLabel htmlFor="memory-enabled">{t("memory.remember")}</FieldLabel>
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
                      setStatus(checked ? t("memory.on") : t("memory.off"))
                    })
                  }
                />
              </Field>
            </PopoverContent>
          </Popover>
          <Popover open={addOpen} onOpenChange={setAddOpen}>
            <PopoverTrigger
              render={<Button aria-label={t("memory.add")} />}
            >
              <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
              <span className="hidden min-[380px]:inline">
                {t("memory.add")}
              </span>
            </PopoverTrigger>
            <PopoverContent
              align="end"
              sideOffset={8}
              className="w-[min(calc(100vw-2rem),22rem)] p-4"
            >
              <MemoryForm
                memory={null}
                csrf={csrf}
                onCancel={() => setAddOpen(false)}
                onSaved={() => {
                  setAddOpen(false)
                  void refresh()
                  setStatus(t("memory.added"))
                }}
              />
            </PopoverContent>
          </Popover>
        </>
      }
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <ResourceSearch
          id="resource-search"
          value={query}
          onChange={setQuery}
          placeholder={t("memory.search")}
          className="sm:max-w-sm"
        />
        <DropdownMenu open={categoryOpen} onOpenChange={setCategoryOpen}>
          <DropdownMenuTrigger
            render={
              <Button
                variant="outline"
                className="w-full justify-between gap-2 sm:w-auto"
              />
            }
          >
            <span className="flex items-center gap-2">
              <HugeiconsIcon icon={FilterIcon} />
              {category === "all"
                ? t("memory.allCategories")
                : categoryOption(category, t).label}
            </span>
            <HugeiconsIcon
              icon={ArrowDown01Icon}
              className="text-muted-foreground"
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuGroup>
              <DropdownMenuRadioGroup
                value={category}
                onValueChange={(value) => {
                  setCategory(value as MemoryCategory | "all")
                  setCategoryOpen(false)
                }}
              >
                <DropdownMenuRadioItem value="all">
                  {t("memory.allCategories")}
                </DropdownMenuRadioItem>
                {categoryOptions.map((option) => (
                  <DropdownMenuRadioItem
                    key={option.value}
                    value={option.value}
                  >
                    <HugeiconsIcon icon={option.icon} />
                    {t(option.labelKey)}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <ResourceStatus>{status}</ResourceStatus>

      {(error || loadError) && (
        <ResourceError
          message={error || loadError}
          errorRef={errorRef}
          onRetry={loadError && !error ? () => void refresh() : undefined}
        />
      )}

      {memories.length === 0 ? (
        <ResourceEmpty
          icon={<HugeiconsIcon icon={BrainIcon} />}
          title={t("memory.empty")}
          description={t("memory.emptyDescription")}
          action={
            <Button onClick={() => setAddOpen(true)}>
              <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
              {t("memory.addFirst")}
            </Button>
          }
        />
      ) : filtered.length === 0 ? (
        <ResourceEmpty
          icon={<HugeiconsIcon icon={Search01Icon} />}
          title={t("memory.notFound")}
          description={t("memory.tryDifferent")}
          action={
            <Button variant="outline" onClick={clearFilters}>
              {t("memory.clearFilters")}
            </Button>
          }
        />
      ) : (
        <ResourceList>
          <div
            role="list"
            className="flex w-full flex-col divide-y divide-border"
          >
            {filtered.map((memory) => (
              <Item
                key={memory.id}
                role="listitem"
                className="flex-nowrap items-start rounded-none border-0 px-4 py-4 hover:bg-muted/25 sm:px-5"
              >
                <ItemContent className="gap-2">
                  <p
                    dir="auto"
                    className="max-w-[72ch] whitespace-pre-wrap text-sm leading-relaxed"
                  >
                    {memory.content}
                  </p>
                  <CategoryBadge category={memory.category} />
                </ItemContent>
                <ItemActions className="self-start">
                  <MemoryRow
                    memory={memory}
                    csrf={csrf}
                    onSaved={() => {
                      void refresh()
                      setStatus(t("memory.updated"))
                    }}
                    onDelete={setRemove}
                  />
                </ItemActions>
              </Item>
            ))}
          </div>
        </ResourceList>
      )}

      <AlertDialog
        open={!!remove}
        onOpenChange={(open) => {
          if (!open && !busy) setRemove(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("memory.deleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("memory.deleteDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>{t("common.cancel")}</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={deleteMemory}
            >
              {busy && <Spinner data-icon="inline-start" />}
              {t("common.delete")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ResourcePage>
  )
}
