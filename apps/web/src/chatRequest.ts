export type ChatRole = 'user' | 'assistant'

export type ChatMessage = {
  role: ChatRole
  content: string
}

export type ChatRequestBody = {
  prompt: string
  messages: ChatMessage[]
}

export function buildChatRequest(
  prompt: string,
  messages: readonly ChatMessage[],
): ChatRequestBody {
  return {
    prompt,
    messages: messages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
  }
}
