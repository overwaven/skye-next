"use client"

import { signOutAllDevices } from "@/app/account-actions"
import { SignOutButton } from "@/components/workspace/sign-out"
import Link from "next/link"
import { useTheme } from "next-themes"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ComputerIcon,
  LanguagesIcon,
  Moon02Icon,
  Sun03Icon,
  Tick02Icon,
} from "@hugeicons/core-free-icons"
import { PageHeader } from "@/components/workspace/page-header"
import { buttonVariants } from "@/components/ui/button"
import { settingsSections } from "@/lib/foundation"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useRouter } from "next/navigation"
import { useI18n } from "@/components/i18n-provider"
import type { Locale } from "@/lib/i18n"

const themeOptions = [
  { value: "system", labelKey: "nav.themeSystem", icon: ComputerIcon },
  { value: "light", labelKey: "nav.themeLight", icon: Sun03Icon },
  { value: "dark", labelKey: "nav.themeDark", icon: Moon02Icon },
] as const

const languageOptions: {
  value: Locale
  labelKey: "common.english" | "common.russian"
  icon: typeof LanguagesIcon
}[] = [
  { value: "en", labelKey: "common.english", icon: LanguagesIcon },
  { value: "ru", labelKey: "common.russian", icon: LanguagesIcon },
]

export function SettingsView({
  section,
  accountConnected = false,
}: {
  section: (typeof settingsSections)[number]
  accountConnected?: boolean
}) {
  const { theme, setTheme } = useTheme()
  const router = useRouter()
  const { t, locale, setLocale } = useI18n()
  const activeTheme = theme ?? "system"
  const title = {
    general: t("settings.general"),
    account: t("settings.account"),
    privacy: t("settings.privacy"),
    sessions: t("settings.sessions"),
  }[section]
  return (
    <div className="detail-page">
      <PageHeader
        title={title}
        parent={{ name: t("settings.title"), href: "/settings/general" }}
      />
      <main className="detail-content">
        <Tabs
          value={section}
          onValueChange={(value) => router.push(`/settings/${value}`)}
        >
          <TabsList aria-label={t("settings.sections")} className="mb-8 justify-start">
            {settingsSections.map((name) => (
              <TabsTrigger key={name} value={name}>
                {t(`settings.${name}`)}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value={section}>
            {section === "general" ? (
              <div className="flex flex-col gap-8">
                <fieldset className="theme-fieldset">
                  <legend>{t("settings.appearance")}</legend>
                  <div className="theme-options">
                    {themeOptions.map((option) => (
                      <label key={option.value} className="theme-option">
                        <input
                          type="radio"
                          name="appearance"
                          value={option.value}
                          checked={activeTheme === option.value}
                          onChange={() => setTheme(option.value)}
                          className="sr-only"
                        />
                        <HugeiconsIcon icon={option.icon} />
                        <span>{t(option.labelKey)}</span>
                        <HugeiconsIcon
                          icon={Tick02Icon}
                          className="theme-option-check"
                          aria-hidden="true"
                        />
                      </label>
                    ))}
                  </div>
                </fieldset>
                <fieldset className="theme-fieldset">
                  <legend>{t("settings.language")}</legend>
                  <div className="theme-options">
                    {languageOptions.map((option) => (
                      <label key={option.value} className="theme-option">
                        <input
                          type="radio"
                          name="language"
                          value={option.value}
                          checked={locale === option.value}
                          onChange={() => setLocale(option.value)}
                          className="sr-only"
                        />
                        <HugeiconsIcon icon={option.icon} />
                        <span>{t(option.labelKey)}</span>
                        <HugeiconsIcon
                          icon={Tick02Icon}
                          className="theme-option-check"
                          aria-hidden="true"
                        />
                      </label>
                    ))}
                  </div>
                </fieldset>
              </div>
            ) : (
              <div className="settings-row">
                <p>
                  {section === "account"
                    ? t("settings.balancesUnavailable")
                    : section === "privacy"
                      ? t("settings.history")
                      : t("settings.sessionsExpire")}
                </p>
                {accountConnected && section === "sessions" ? (
                  <form action={signOutAllDevices}>
                    <SignOutButton allDevices />
                  </form>
                ) : !accountConnected ? (
                  <Link
                    href="/login"
                    className={buttonVariants({ variant: "outline" })}
                  >
                    {t("settings.signIn")}
                  </Link>
                ) : null}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
