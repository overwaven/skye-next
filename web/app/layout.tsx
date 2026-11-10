import { Geist, Geist_Mono } from "next/font/google"

import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { I18nProvider } from "@/components/i18n-provider"
import { ServiceWorkerReset } from "@/components/service-worker-reset"
import { Toaster } from "@/components/ui/toast"
import { getLocale } from "@/lib/i18n-server"
import { translate } from "@/lib/i18n"
import { cn } from "@/lib/utils"
import type { Metadata, Viewport } from "next"

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale()
  return {
    title: { default: "Skye", template: "%s · Skye" },
    description: translate(locale, "meta.description"),
    robots: { index: false, follow: false },
  }
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
}

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" })

const fontMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const locale = await getLocale()
  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={cn(
        "antialiased",
        fontMono.variable,
        "font-sans",
        geist.variable
      )}
    >
      <body>
        <ServiceWorkerReset />
        <ThemeProvider>
          <I18nProvider initialLocale={locale}>
            <Toaster>{children}</Toaster>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
