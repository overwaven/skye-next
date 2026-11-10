import { NextResponse, type NextRequest } from "next/server"
import { isLocale, localeCookie, negotiateLocale } from "./lib/i18n"

export function proxy(request: NextRequest) {
  const current = request.cookies.get(localeCookie)?.value
  const locale = isLocale(current)
    ? current
    : negotiateLocale(request.headers.get("accept-language"))

  const requestHeaders = new Headers(request.headers)
  requestHeaders.set("x-skye-locale", locale)
  const response = NextResponse.next({ request: { headers: requestHeaders } })

  if (!isLocale(current)) {
    response.cookies.set(localeCookie, locale, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    })
  }

  return response
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|sw.js|.*\\..*).*)",
  ],
}
