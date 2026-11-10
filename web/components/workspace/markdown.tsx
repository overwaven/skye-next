"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  CodeBlock,
  CodeBlockActions,
  CodeBlockContent,
  CodeBlockCopyButton,
  CodeBlockHeader,
  CodeBlockTitle,
} from "@/components/ui/code-block"
import { useI18n } from "@/components/i18n-provider"

/** Safe Markdown: raw HTML is never rendered and images never load remotely. */
export function Markdown({ text }: { text: string }) {
  const { t } = useI18n()
  return (
    <div className="message-text">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
          img: () => null,
          pre: ({ children }) => {
            const child = React.Children.toArray(children)[0]
            const props = React.isValidElement<{
              children?: React.ReactNode
              className?: string
            }>(child)
              ? child.props
              : undefined
            const value = String(props?.children ?? "").replace(/\n$/, "")
            const language = /language-([\w-]+)/.exec(
              props?.className ?? ""
            )?.[1]
            if (!value) return null
            return (
              <CodeBlock>
                <CodeBlockHeader>
                  <CodeBlockTitle>{language ?? t("common.code")}</CodeBlockTitle>
                  <CodeBlockActions>
                    <CodeBlockCopyButton value={value} />
                  </CodeBlockActions>
                </CodeBlockHeader>
                <CodeBlockContent>{value}</CodeBlockContent>
              </CodeBlock>
            )
          },
          code: ({ children }) => (
            <code className="inline-code">{children}</code>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
