import "server-only"

import type { NavigationData } from "@/lib/foundation"
import type { VisibleMessage } from "@/lib/contracts.generated"

// Synthetic design fixtures. Only imported by a development-only server branch.
export const navigation: NavigationData = {
  preview: true,
  projects: [
    {
      id: "skye-web",
      name: "Skye, on the web",
      emoji: "🌐",
      instructions:
        "Keep the interface quiet. Explain what is happening. Make room for the work, not the controls.",
    },
    {
      id: "everyday",
      name: "A quieter week",
      emoji: "🌿",
      instructions: "Prefer small, practical steps. Leave evenings free.",
    },
  ],
  threads: [
    {
      id: "a-place-to-think",
      title: "A place to think",
      project_id: "skye-web",
      label: "Today",
    },
    {
      id: "the-context-edge",
      title: "What stays with a thread",
      project_id: "skye-web",
      label: "Today",
    },
    {
      id: "weekend",
      title: "A little room for the weekend",
      project_id: "everyday",
      label: "Yesterday",
    },
    {
      id: "loose-thoughts",
      title: "A thought for later",
      project_id: null,
      label: "Yesterday",
    },
  ],
}

const text = (
  id: string,
  role: "user" | "assistant",
  value: string,
  sequence: number
): VisibleMessage => ({
  id,
  role,
  sequence,
  thread_id: "a-place-to-think",
  origin: "web",
  run_id: null,
  parts: [{ type: "text", text: value }],
})

export const messages: VisibleMessage[] = [
  text(
    "preview-1",
    "user",
    "I’d like the web chat to feel like a place to think. Everything I need, but not everything at once.",
    1
  ),
  text(
    "preview-2",
    "assistant",
    "Then the conversation gets the room. Projects on one side; the context you need, just a little further in.",
    2
  ),
  text(
    "preview-3",
    "assistant",
    "A thread can belong to a project, or simply be a thought of its own. Your memories, skills, and connected apps stay with you.",
    3
  ),
  text("preview-4", "user", "And when something is taking a while?", 4),
  text(
    "preview-5",
    "assistant",
    "You’ll know what I’m working on, and you can stop me. If something goes wrong, the next step should be right there—not hidden in a notification.",
    5
  ),
]

export const longMessages = [
  ...messages,
  text(
    "preview-long",
    "assistant",
    "A deliberately long reference: https://example.org/skye/" +
      "context-and-conversation-".repeat(15) +
      "\n\nA project is an instruction boundary, not a private vault. Moving a thread changes the instructions for future replies; it does not remove earlier context.\n\nملاحظة صغيرة: تبقى ذكرياتك شخصية عبر المحادثات.\n\n“Keep it simple” is easy to say. The real work is making the unusual states as considered as the ordinary ones.",
    6
  ),
]
