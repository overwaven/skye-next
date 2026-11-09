import { Geist, Geist_Mono } from "next/font/google"

import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { ServiceWorkerReset } from "@/components/service-worker-reset"
import { cn } from "@/lib/utils"
import type { Metadata, Viewport } from "next"

export const metadata: Metadata = {
  title: { default: "Skye", template: "%s · Skye" },
  description: "A little more room for your conversation with Skye.",
  robots: { index: false, follow: false },
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
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
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  )
}
