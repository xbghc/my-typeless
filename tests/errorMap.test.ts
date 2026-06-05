import { describe, expect, it } from 'vitest'
import OpenAI from 'openai'
import { mapProcessingError } from '@main/errorMap'

const headers = new Headers()

describe('mapProcessingError', () => {
  it('maps unknown errors to a generic chinese message', () => {
    const r = mapProcessingError(new Error('boom'))
    expect(r.message).toBe('发生未知错误：boom')
    expect(r.critical).toBe(false)
  })

  it('maps authentication errors as critical', () => {
    const e = new OpenAI.AuthenticationError(401, undefined, 'bad key', headers)
    const r = mapProcessingError(e)
    expect(r.message).toContain('API 密钥无效')
    expect(r.critical).toBe(true)
  })

  it('maps rate limit errors as non-critical', () => {
    const e = new OpenAI.RateLimitError(429, undefined, 'slow down', headers)
    const r = mapProcessingError(e)
    expect(r.message).toContain('过于频繁')
    expect(r.critical).toBe(false)
  })

  it('maps generic API status errors', () => {
    const e = new OpenAI.APIError(500, undefined, 'server error', headers)
    const r = mapProcessingError(e)
    expect(r.message).toContain('API 服务异常')
    expect(r.message).toContain('HTTP 500')
    expect(r.critical).toBe(false)
  })
})
