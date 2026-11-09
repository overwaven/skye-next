"use client"

import { useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Globe02Icon } from "@hugeicons/core-free-icons"
import { cn } from "cn"

export function ConnectorLogo({
  id,
  name,
  kind,
  className,
}: {
  id: string
  name: string
  kind: "app" | "custom"
  className?: string
}) {
  const [failedId, setFailedId] = useState("")
  const failed = failedId === `${kind}:${id}`

  const source =
    kind === "app" && id
      ? `https://logos.composio.dev/api/${encodeURIComponent(id)}`
      : null

  if (!source || failed) {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "flex size-full items-center justify-center overflow-hidden rounded-[inherit] bg-muted text-muted-foreground",
          className
        )}
      >
        {kind === "custom" ? (
          <HugeiconsIcon icon={Globe02Icon} className="size-5" />
        ) : (
          <span className="text-sm font-medium uppercase">
            {name.slice(0, 1)}
          </span>
        )}
      </div>
    )
  }

  return (
    // The provider logo service is the only stable source for app marks.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={source}
      alt=""
      loading="lazy"
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() => setFailedId(`${kind}:${id}`)}
      className={cn("size-full object-contain", className)}
    />
  )
}
