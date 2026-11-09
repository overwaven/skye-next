import Image from "next/image"

export function SkyeMark({ size = 28 }: { size?: number }) {
  return (
    <Image
      src="/skye-sign.svg"
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      priority
    />
  )
}
