import { notFound } from "next/navigation"
import { SettingsView } from "@/components/workspace/settings-view"
import { settingsSections } from "@/lib/foundation"
import { accountEnabled } from "@/lib/api"

type Props = { params: Promise<{ section: string }> }

export async function generateMetadata({ params }: Props) {
  const { section } = await params
  return {
    title: `${section.charAt(0).toUpperCase()}${section.slice(1)} settings`,
  }
}

export default async function Settings({ params }: Props) {
  const { section } = await params
  if (!settingsSections.includes(section as (typeof settingsSections)[number]))
    notFound()
  return (
    <SettingsView
      section={section as (typeof settingsSections)[number]}
      accountConnected={accountEnabled()}
    />
  )
}
