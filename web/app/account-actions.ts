"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { revokeSession } from "@/lib/api"
import { devPreviewEnabled } from "@/lib/dev-preview"

export async function enterPreview() {
  if (!devPreviewEnabled()) redirect("/login")
  const store = await cookies()
  store.delete("skye_dev_signed_out")
  redirect("/chat")
}

export async function signOut() {
  if (devPreviewEnabled()) {
    const store = await cookies()
    store.set("skye_dev_signed_out", "true", {
      httpOnly: true,
      sameSite: "strict",
      path: "/",
    })
    redirect("/login")
  }
  await revokeSession()
  const store = await cookies()
  store.set("__Host-skye_session", "", {
    secure: true,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  })
  redirect("/login")
}

export async function signOutAllDevices() {
  if (devPreviewEnabled()) return signOut()
  await revokeSession(true)
  const store = await cookies()
  store.set("__Host-skye_session", "", {
    secure: true,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  })
  redirect("/login")
}
