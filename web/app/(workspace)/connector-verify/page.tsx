import { getSession } from "@/lib/api"
import type { Metadata } from "next"
import { ConnectorVerification } from "@/components/workspace/connector-verification"
import { getTranslator } from "@/lib/i18n-server"

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getTranslator()
  return { title: t("meta.verify") }
}

export default async function VerifyConnector() {
  const session = await getSession()
  return <ConnectorVerification csrf={session.csrf_token} />
}
