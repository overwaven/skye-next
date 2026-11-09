export const librarySections = {
  memory: { name: "Memory", action: "Add memory" },
  connectors: { name: "Connectors", action: "Connect an app" },
  skills: { name: "Skills", action: "Upload a skill" },
  files: { name: "Files", action: "Upload a file" },
  agents: { name: "Agents", action: "Create an agent" },
  automations: { name: "Automations", action: "Create an automation" },
} as const

export type LibrarySection = keyof typeof librarySections
export const settingsSections = [
  "general",
  "account",
  "privacy",
  "sessions",
] as const
export type PreviewState =
  "empty" | "ready" | "loading" | "failed" | "running" | "long" | "low-funds"

export const previewStates: PreviewState[] = [
  "empty",
  "ready",
  "loading",
  "failed",
  "running",
  "long",
  "low-funds",
]

export type NavigationData = {
  localPreview?: boolean
  accountConnected?: boolean
  csrfToken?: string
  preview: boolean
  projects: {
    id: string
    name: string
    emoji?: string
    instructions: string
    revision?: number
  }[]
  threads: {
    id: string
    title: string
    project_id: string | null
    label: string
    archived?: boolean
  }[]
}
