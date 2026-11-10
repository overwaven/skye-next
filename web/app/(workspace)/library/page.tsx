import type { Metadata } from "next"
import { LibraryHome } from "@/components/workspace/resource-view"
import { getTranslator } from "@/lib/i18n-server"

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getTranslator()
  return { title: t("meta.library") }
}

export default function Library() {
  return <LibraryHome />
}
