import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { stripReasoning } from '@main/llmClient'
import { resolveSecret } from '@main/config'

describe('stripReasoning', () => {
  it('removes an inline <think> block', () => {
    expect(stripReasoning('<think>reasoning here</think>结果文本')).toBe('结果文本')
    expect(stripReasoning('前缀<think>x</think>后缀')).toBe('前缀后缀')
  })

  it('handles multiline content and multiple blocks', () => {
    expect(stripReasoning('<think>\nline1\nline2\n</think>\n  最终')).toBe('最终')
    expect(stripReasoning('<think>a</think>x<think>b</think>y')).toBe('xy')
  })

  it('leaves clean text untouched', () => {
    expect(stripReasoning('普通文本')).toBe('普通文本')
  })

  it('strips an unclosed/truncated <think> (no closing tag) to empty', () => {
    expect(stripReasoning('<think>reasoning got cut off')).toBe('')
    expect(stripReasoning('<think>done</think>结果<think>截断了')).toBe('结果')
  })

  it('removes a stray closing tag left by a nested block', () => {
    expect(stripReasoning('<think><think>x</think></think>最终')).toBe('最终')
  })
})

describe('resolveSecret', () => {
  const KEY = 'MT_TEST_SECRET_VAR'
  beforeEach(() => {
    process.env[KEY] = 'resolved-value'
  })
  afterEach(() => {
    delete process.env[KEY]
  })

  it('resolves a ${ENV_VAR} placeholder from process.env', () => {
    expect(resolveSecret('${MT_TEST_SECRET_VAR}')).toBe('resolved-value')
  })

  it('returns empty string when the referenced env var is missing', () => {
    expect(resolveSecret('${MT_DEFINITELY_MISSING_VAR}')).toBe('')
  })

  it('passes plain api keys through unchanged', () => {
    expect(resolveSecret('sk-plain-key-123')).toBe('sk-plain-key-123')
    expect(resolveSecret('')).toBe('')
  })

  it('trims surrounding whitespace before matching the placeholder', () => {
    expect(resolveSecret('  ${MT_TEST_SECRET_VAR}  ')).toBe('resolved-value')
  })
})
