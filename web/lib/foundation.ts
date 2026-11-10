export const librarySections = {
  memory: { nameKey: "library.memory", actionKey: "library.actionMemory" },
  connectors: {
    nameKey: "library.connectors",
    actionKey: "library.actionConnectors",
  },
  skills: { nameKey: "library.skills", actionKey: "library.actionSkills" },
  files: { nameKey: "library.files", actionKey: "library.actionFiles" },
  agents: { nameKey: "library.agents", actionKey: "library.actionAgents" },
  automations: {
    nameKey: "library.automations",
    actionKey: "library.actionAutomations",
  },
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
    pinned?: boolean
    preview?: string
  }[]
}
