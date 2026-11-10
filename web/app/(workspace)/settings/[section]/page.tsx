import { notFound } from "next/navigation"
import { SettingsView } from "@/components/workspace/settings-view"
import { settingsSections } from "@/lib/foundation"
import { accountEnabled } from "@/lib/api"
import { getTranslator } from "@/lib/i18n-server"

type Props = { params: Promise<{ section: string }> }

const sectionNames = {
  general: "settings.general",
  account: "settings.account",
  privacy: "settings.privacy",
  sessions: "settings.sessions",
} as const

export async function generateMetadata({ params }: Props) {
  const { section } = await params
  const { t } = await getTranslator()
  const name = sectionNames[section as keyof typeof sectionNames]
  return {
    title: t("meta.settings", {
      name: name ? t(name) : section,
    }),
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
