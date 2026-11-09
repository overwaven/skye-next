"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Cancel01Icon,
  InformationCircleIcon,
  ArrowUpRight01Icon,
} from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  DrawerClose,
} from "@/components/ui/drawer"
import { useIsMobile } from "@/hooks/use-mobile"
import { useMediaQuery } from "@/hooks/use-media-query"
import type {
  ResourceSnapshot,
  ActivityRecord,
} from "@/lib/contracts.generated"
import { Trace, TraceLine, TraceTitle } from "@/components/ui/trace"

function ContextDetails({
  instructions,
  connected,
  open,
  activities,
}: {
  instructions?: string
  connected: boolean
  open: boolean
  activities: ActivityRecord[]
}) {
  const [resources, setResources] = useState<ResourceSnapshot | null>(null)
  const [error, setError] = useState("")
  useEffect(() => {
    if (!connected || !open) return
    const controller = new AbortController()
    const refresh = () =>
      fetch("/api/v1/resources/context", {
        cache: "no-store",
        signal: controller.signal,
      })
        .then(async (r) => {
          if (!r.ok) throw new Error()
          setResources(await r.json())
          setError("")
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError(
              "Resources could not be refreshed. Reopen Details to retry."
            )
        })
    void refresh()
    const timer = window.setInterval(refresh, 15000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [connected, open])
  return (
    <div className="context-details">
      <section>
        <h3>Project instructions</h3>
        <p>{instructions || "No project instructions."}</p>
      </section>
      <section>
        <h3>Personal context</h3>
        <p>Shared across your threads.</p>
        {connected && resources && (
          <>
            <p>
              Memory {resources.memory_enabled ? "on" : "off"} ·{" "}
              {resources.memories?.length ?? 0} saved
            </p>
            <p>{resources.skills?.length ?? 0} skills available</p>
            <p>
              {resources.connectors?.length ?? 0} connectors listed
              {resources.apps_configured && !resources.provider_verified
                ? " · app status unverified"
                : ""}
            </p>
            <p>
              Available does not mean used in this run. Project instructions do
              not isolate personal resources.
            </p>
          </>
        )}
        {error && <p role="status">{error}</p>}
        <Link className="text-link" href="/library/memory">
          Review memory <HugeiconsIcon icon={ArrowUpRight01Icon} />
        </Link>
        <Link className="text-link" href="/library/connectors">
          Review connectors
        </Link>
        <Link className="text-link" href="/library/skills">
          Review skills
        </Link>
      </section>
      {connected && (
        <section>
          <h3>Run evidence</h3>
          {activities.length ? (
            <Trace>
              {activities
                .filter((a) => a.label)
                .map((a) => (
                  <TraceLine
                    key={a.sequence}
                    status={
                      a.status === "running"
                        ? "running"
                        : a.status === "failed"
                          ? "error"
                          : undefined
                    }
                  >
                    <TraceTitle>
                      {a.label} · {a.status}
                    </TraceTitle>
                  </TraceLine>
                ))}
            </Trace>
          ) : (
            <p>
              No recorded tool activity. Memory injection and individual
              connector use are not proven by this list.
            </p>
          )}
        </section>
      )}
    </div>
  )
}

export function ContextPanel({
  instructions,
  connected = false,
  activities = [],
}: {
  instructions?: string
  connected?: boolean
  activities?: ActivityRecord[]
}) {
  const [open, setOpen] = useState(false)
  const wide = useMediaQuery("(min-width: 1200px)")
  const mobile = useIsMobile()
  const trigger = useRef<HTMLButtonElement>(null)
  const details = (
    <ContextDetails
      instructions={instructions}
      connected={connected}
      open={open}
      activities={activities}
    />
  )
  if (!wide)
    return (
      <Drawer
        open={open}
        onOpenChange={setOpen}
        swipeDirection={mobile ? "down" : "right"}
        showSwipeHandle
      >
        <DrawerTrigger render={<Button variant="ghost" aria-label="Details" />}>
          <HugeiconsIcon
            icon={InformationCircleIcon}
            data-icon="inline-start"
          />
          <span className="hidden sm:inline">Details</span>
        </DrawerTrigger>
        <DrawerContent className="details-drawer">
          <DrawerHeader>
            <div className="flex items-center justify-between gap-3">
              <DrawerTitle>Details</DrawerTitle>
              <DrawerClose
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Close details"
                  />
                }
              >
                <HugeiconsIcon icon={Cancel01Icon} />
              </DrawerClose>
            </div>
            <DrawerDescription className="sr-only">
              Project instructions and personal context.
            </DrawerDescription>
          </DrawerHeader>
          <div className="min-h-0 flex-1 overflow-y-auto">{details}</div>
        </DrawerContent>
      </Drawer>
    )
  return (
    <>
      <Button
        variant="ghost"
        ref={trigger}
        aria-label="Details"
        aria-expanded={open}
        aria-controls="thread-context"
        onClick={() => setOpen(!open)}
      >
        <HugeiconsIcon icon={InformationCircleIcon} data-icon="inline-start" />
        <span className="hidden sm:inline">Details</span>
      </Button>
      <aside
        id="thread-context"
        className="context-pane"
        data-state={open ? "open" : "closed"}
        aria-labelledby="context-title"
        inert={!open}
      >
        <div className="context-heading">
          <h2 id="context-title">Details</h2>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Close details"
            onClick={() => {
              setOpen(false)
              trigger.current?.focus()
            }}
          >
            <HugeiconsIcon icon={Cancel01Icon} />
          </Button>
        </div>
        {details}
      </aside>
    </>
  )
}
