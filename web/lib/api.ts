import "server-only"

import Ajv from "ajv/dist/2020"
import { cookies } from "next/headers"
import { notFound, redirect } from "next/navigation"
import schema from "@/lib/contracts.schema.json"
import { devPreviewEnabled } from "@/lib/dev-preview"
import type {
  SessionRecord,
  ProjectList,
  ThreadList,
  ThreadRecord,
  MessagePage,
  Snapshot,
  ResourceSnapshot,
  SkillRecord,
} from "@/lib/contracts.generated"

export function accountEnabled() {
  return process.env.SKYE_WEB_ENABLED === "true"
}

const validator = new Ajv({ strict: false, allErrors: false })
validator.addSchema(schema, "skye")

// All paths are application constants/encoded opaque IDs, never a caller-supplied URL.
async function get<T>(
  path: string,
  contract: string | null,
  csrf?: string
): Promise<T> {
  if (!accountEnabled()) throw new Error("Account access is disabled.")
  const store = await cookies()
  if (devPreviewEnabled() && store.get("skye_dev_signed_out")?.value === "true")
    redirect("/login")
  const token = devPreviewEnabled()
    ? process.env.SKYE_DEV_SESSION
    : store.get("__Host-skye_session")?.value
  if (!token) redirect("/login")
  const internal = new URL(
    process.env.SKYE_WEB_API_ORIGIN || "http://127.0.0.1:8090"
  )
  const publicOrigin = new URL(process.env.SKYE_WEB_ORIGIN || "")
  const internalToken = process.env.SKYE_WEB_INTERNAL_TOKEN
  if (
    internal.pathname !== "/" ||
    internal.search ||
    internal.hash ||
    internal.username ||
    internal.password ||
    publicOrigin.protocol !== "https:"
  ) {
    throw new Error("Account server configuration is unavailable.")
  }
  if (
    internal.origin !== publicOrigin.origin &&
    (!internalToken || internalToken.length < 32)
  ) {
    throw new Error("Internal account access is not configured.")
  }
  let response: Response
  try {
    response = await fetch(new URL(path, internal), {
      method: csrf ? "POST" : "GET",
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(8000),
      // Forward only the opaque session, not the browser's other cookies or headers.
      headers: {
        Cookie: `__Host-skye_session=${token}`,
        ...(internalToken ? { "X-Skye-Internal-Token": internalToken } : {}),
        ...(csrf ? { Origin: publicOrigin.origin, "X-CSRF-Token": csrf } : {}),
      },
    })
  } catch {
    throw new Error("The account server is unavailable. Try again later.")
  }
  if (response.status === 401) redirect("/login?error=session")
  if (response.status === 404) notFound()
  if (!response.ok)
    throw new Error("This account view is unavailable. Try again later.")
  if (contract === null) return undefined as T
  const value: unknown = await response.json()
  const validate = validator.getSchema(`skye#/$defs/${contract}`)
  if (!validate || !validate(value))
    throw new Error("The account response could not be verified.")
  return value as T
}

export const getSession = () =>
  get<SessionRecord>("/api/v1/session", "SessionRecord")
export const getResources = (section: string) =>
  get<ResourceSnapshot>(
    `/api/v1/resources/${encodeURIComponent(section)}`,
    "ResourceSnapshot"
  )
export const getSkill = (id: string) =>
  get<SkillRecord>(
    `/api/v1/resources/skills/${encodeURIComponent(id)}`,
    "SkillRecord"
  )
export const getProjects = () =>
  get<ProjectList>("/api/v1/projects", "ProjectList")
export const getThreads = () => get<ThreadList>("/api/v1/threads", "ThreadList")
export const getThread = (id: string) =>
  get<ThreadRecord>(`/api/v1/threads/${encodeURIComponent(id)}`, "ThreadRecord")
export const getHistory = (id: string) =>
  get<MessagePage>(
    `/api/v1/threads/${encodeURIComponent(id)}/messages`,
    "MessagePage"
  )
export const getThreadState = (id: string) =>
  get<Snapshot>(`/api/v1/threads/${encodeURIComponent(id)}/state`, "Snapshot")

export async function revokeSession(allDevices = false) {
  const session = await getSession()
  await get<void>(
    `/api/v1/auth/logout${allDevices ? "/all" : ""}`,
    null,
    session.csrf_token
  )
}
