"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  localeCookie,
  translate,
  translateCount,
  type CountMessageBase,
  type Locale,
  type MessageKey,
  type MessageValues,
} from "@/lib/i18n"

type I18nValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey, values?: MessageValues) => string
  tn: (
    base: CountMessageBase,
    count: number,
    values?: MessageValues
  ) => string
}

const I18nContext = React.createContext<I18nValue | null>(null)

export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale
  children: React.ReactNode
}) {
  const router = useRouter()
  const [locale, setLocaleState] = React.useState<Locale>(initialLocale)

  const setLocale = React.useCallback(
    (next: Locale) => {
      setLocaleState(next)
      document.documentElement.lang = next
      document.cookie = `${localeCookie}=${next}; path=/; max-age=31536000; samesite=lax`
      try {
        localStorage.setItem(localeCookie, next)
      } catch {
        // Storage can be unavailable in private or embedded contexts.
      }
      router.refresh()
    },
    [router]
  )

  React.useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const value = React.useMemo<I18nValue>(
    () => ({
      locale,
      setLocale,
      t: (key, values) => translate(locale, key, values),
      tn: (base, count, values) => translateCount(locale, base, count, values),
    }),
    [locale, setLocale]
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const value = React.useContext(I18nContext)
  if (!value) throw new Error("useI18n must be used inside I18nProvider")
  return value
}
