import { getSession } from "@/lib/api"
import { ConnectorVerification } from "@/components/workspace/connector-verification"

export const metadata = { title: "Verify connection" }

export default async function VerifyConnector() {
  const session = await getSession()
  return <ConnectorVerification csrf={session.csrf_token} />
}
