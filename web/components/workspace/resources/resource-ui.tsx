"use client"

import type { ReactNode, RefObject } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  AlertCircleIcon,
  Cancel01Icon,
  Search01Icon,
} from "@hugeicons/core-free-icons"
import { PageHeader } from "@/components/workspace/page-header"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "cn"
import { useI18n } from "@/components/i18n-provider"

export function ResourcePage({
  title,
  action,
  children,
}: {
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  const { t } = useI18n()
  return (
    <div className="detail-page">
      <PageHeader
        title={title}
        parent={{ name: t("library.title"), href: "/library" }}
      >
        {action}
      </PageHeader>
      <main className="detail-content resource-page">{children}</main>
    </div>
  )
}

export function ResourceSearch({
  value,
  onChange,
  placeholder,
  loading = false,
  className,
  id,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  loading?: boolean
  className?: string
  id?: string
}) {
  const { t } = useI18n()
  return (
    <InputGroup className={cn("h-10 bg-background", className)}>
      <InputGroupAddon>
        <HugeiconsIcon icon={Search01Icon} />
      </InputGroupAddon>
      <InputGroupInput
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        autoCorrect="off"
        autoCapitalize="none"
        spellCheck={false}
      />
      {loading ? (
        <InputGroupAddon align="inline-end">
          <Spinner />
        </InputGroupAddon>
      ) : value ? (
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            size="icon-xs"
            aria-label={t("library.clearSearch")}
            onClick={() => onChange("")}
          >
            <HugeiconsIcon icon={Cancel01Icon} />
          </InputGroupButton>
        </InputGroupAddon>
      ) : null}
    </InputGroup>
  )
}

export function ResourceStatus({ children }: { children: ReactNode }) {
  return (
    <p
      role="status"
      className="text-sm text-muted-foreground empty:hidden"
    >
      {children}
    </p>
  )
}

export function ResourceError({
  message,
  errorRef,
  onRetry,
}: {
  message: string
  errorRef?: RefObject<HTMLDivElement | null>
  onRetry?: () => void
}) {
  const { t } = useI18n()
  return (
    <Alert variant="destructive">
      <HugeiconsIcon icon={AlertCircleIcon} />
      <AlertDescription ref={errorRef} tabIndex={-1}>
        {message}
        {onRetry && (
          <Button variant="link" size="sm" onClick={onRetry}>
            {t("library.retry")}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

export function SectionLabel({
  children,
  count,
}: {
  children: ReactNode
  count?: number
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="text-sm font-medium">{children}</h2>
      {count !== undefined && (
        <span className="text-sm text-muted-foreground tabular-nums">
          {count}
        </span>
      )}
    </div>
  )
}

export function ResourceList({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-3xl border bg-card/40">
      {children}
    </div>
  )
}

export function ResourceEmpty({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <Empty className="border border-dashed bg-card/30 py-14">
      <EmptyHeader>
        <EmptyMedia variant="icon">{icon}</EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  )
}
