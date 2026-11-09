"use client"

import { signOutAllDevices } from "@/app/account-actions"
import { SignOutButton } from "@/components/workspace/sign-out"
import Link from "next/link"
import { useTheme } from "next-themes"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ComputerIcon,
  Moon02Icon,
  Sun03Icon,
  Tick02Icon,
} from "@hugeicons/core-free-icons"
import { PageHeader } from "@/components/workspace/page-header"
import { buttonVariants } from "@/components/ui/button"
import { settingsSections } from "@/lib/foundation"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useRouter } from "next/navigation"

const themeOptions = [
  { value: "system", label: "System", icon: ComputerIcon },
  { value: "light", label: "Light", icon: Sun03Icon },
  { value: "dark", label: "Dark", icon: Moon02Icon },
] as const

export function SettingsView({
  section,
  accountConnected = false,
}: {
  section: (typeof settingsSections)[number]
  accountConnected?: boolean
}) {
  const { theme, setTheme } = useTheme()
  const router = useRouter()
  const activeTheme = theme ?? "system"
  const title = {
    general: "General",
    account: "Account",
    privacy: "Privacy",
    sessions: "Sessions",
  }[section]
  return (
    <div className="detail-page">
      <PageHeader
        title={title}
        parent={{ name: "Settings", href: "/settings/general" }}
      />
      <main className="detail-content">
        <Tabs
          value={section}
          onValueChange={(value) => router.push(`/settings/${value}`)}
        >
          <TabsList aria-label="Settings sections" className="mb-8">
            {settingsSections.map((name) => (
              <TabsTrigger key={name} value={name}>
                {name.charAt(0).toUpperCase() + name.slice(1)}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value={section}>
            {section === "general" ? (
              <fieldset className="theme-fieldset">
                <legend>Appearance</legend>
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
                      <span>{option.label}</span>
                      <HugeiconsIcon
                        icon={Tick02Icon}
                        className="theme-option-check"
                        aria-hidden="true"
                      />
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : (
              <div className="settings-row">
                <p>
                  {section === "account"
                    ? "Balances are not available here."
                    : section === "privacy"
                      ? "History is kept until you clear it. Logs contain metadata only."
                      : "Sessions expire after 7 idle days or 30 days total."}
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
                    Sign in
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
