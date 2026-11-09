"use client"

import { useMediaQuery } from "@/hooks/use-media-query"

export function useIsMobile() {
  return useMediaQuery("(max-width: 1023px)")
}
