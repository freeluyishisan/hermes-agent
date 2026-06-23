import { describe, expect, it } from 'vitest'

import { chatMessageText, type ChatMessagePart } from '@/lib/chat-messages'

import { settleAssistantPartsOnCompletion } from './use-message-stream'

describe('settleAssistantPartsOnCompletion', () => {
  it('keeps streamed assistant text when message.complete has no final text', () => {
    const parts: ChatMessagePart[] = [{ text: 'Visible before completion.', type: 'text' }]

    const settled = settleAssistantPartsOnCompletion(parts, '')

    expect(chatMessageText({ id: 'assistant-stream', parts: settled, role: 'assistant' })).toBe(
      'Visible before completion.'
    )
  })

  it('replaces streamed text with final completion text when provided', () => {
    const parts: ChatMessagePart[] = [{ text: 'Partial', type: 'text' }]

    const settled = settleAssistantPartsOnCompletion(parts, 'Final answer')

    expect(chatMessageText({ id: 'assistant-stream', parts: settled, role: 'assistant' })).toBe('Final answer')
  })
})
