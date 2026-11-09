import Link from "next/link"
import { notFound } from "next/navigation"
import { Conversation } from "@/components/workspace/conversation"
import { previewStates, type PreviewState } from "@/lib/foundation"

export const metadata = { title: "Interface state preview" }

export default async function StatePreview({
  params,
}: {
  params: Promise<{ state: string }>
}) {
  if (process.env.NODE_ENV !== "development") notFound()
  const { state } = await params
  if (!previewStates.includes(state as PreviewState)) notFound()
  const { messages, longMessages, navigation } =
    await import("@/lib/preview-data")
  return (
    <div className="state-preview">
      <nav aria-label="Design states" className="state-toolbar">
        {previewStates.map((name) => (
          <Link
            key={name}
            href={`/dev/states/${name}`}
            aria-current={name === state ? "page" : undefined}
          >
            {name.replace("-", " ")}
          </Link>
        ))}
      </nav>
      <Conversation
        preview
        title={state === "empty" ? "New thread" : "A place to think"}
        project={navigation.projects[0]}
        messages={state === "long" ? longMessages : messages}
        state={state as PreviewState}
      />
    </div>
  )
}
