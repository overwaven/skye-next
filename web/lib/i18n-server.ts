import "server-only"

import { cookies, headers } from "next/headers"
import {
  defaultLocale,
  isLocale,
  localeCookie,
  translate,
  type Locale,
  type MessageKey,
  type MessageValues,
} from "@/lib/i18n"

export async function getLocale(): Promise<Locale> {
  const requestHeaders = await headers()
  const fromHeader = requestHeaders.get("x-skye-locale")
  if (isLocale(fromHeader)) return fromHeader
  const store = await cookies()
  const fromCookie = store.get(localeCookie)?.value
  if (isLocale(fromCookie)) return fromCookie
  return defaultLocale
}

export async function getTranslator() {
  const locale = await getLocale()
  return {
    locale,
    t: (key: MessageKey, values?: MessageValues) =>
      translate(locale, key, values),
  }
}
