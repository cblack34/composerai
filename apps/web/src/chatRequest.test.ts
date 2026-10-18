import { describe, expect, it } from 'vitest'
import { buildChatRequest } from './chatRequest.ts'

describe('buildChatRequest', () => {
  it('sends the prompt separately from prior turns', () => {
    const prior = [
      { role: 'user' as const, content: 'start a verse' },
      { role: 'assistant' as const, content: 'saved verse-1/sketch.mid' },
    ]

    const body = buildChatRequest('add a chorus', prior)

    expect(body).toEqual({
      prompt: 'add a chorus',
      messages: [
        { role: 'user', content: 'start a verse' },
        { role: 'assistant', content: 'saved verse-1/sketch.mid' },
      ],
    })
    expect(prior).toEqual([
      { role: 'user', content: 'start a verse' },
      { role: 'assistant', content: 'saved verse-1/sketch.mid' },
    ])
  })

  it('sends an empty message list when nothing came before', () => {
    expect(buildChatRequest('hello', [])).toEqual({
      prompt: 'hello',
      messages: [],
    })
  })
})
