import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createDatabase, type DB } from '@main/db'
import { CandidateStore, extractAcronyms } from '@main/candidates'

describe('extractAcronyms', () => {
  it('extracts uppercase acronyms', () => {
    const text = '我们用 CSS 和 DOM 实现 BEM 命名，调用 API 走 HTTP 协议。'
    expect(extractAcronyms(text)).toEqual(new Set(['CSS', 'DOM', 'BEM', 'API', 'HTTP']))
  })

  it('filters single letters and lowercase', () => {
    expect(extractAcronyms('A simple test with css and dom should not match.')).toEqual(new Set())
  })

  it('skips common stopwords', () => {
    const extracted = extractAcronyms('OK 我们在 USA 测试，结果 PM 出问题。')
    expect(extracted.has('OK')).toBe(false)
    expect(extracted.has('USA')).toBe(false)
    expect(extracted.has('PM')).toBe(false)
  })

  it('allows trailing digits', () => {
    expect(extractAcronyms('用 S3 存储，IPv4 走 HTTP2 协议。').has('S3')).toBe(true)
  })
})

describe('CandidateStore', () => {
  let db: DB
  let store: CandidateStore
  beforeEach(() => {
    db = createDatabase(':memory:')
    store = new CandidateStore(db)
  })
  afterEach(() => {
    db.close()
  })

  it('records and gets candidates', () => {
    store.recordFromRefined('讨论 CSS 和 DOM。', [])
    expect(store.get(3)).toEqual([])
    const cands = store.get(1)
    expect(new Set(cands.map((c) => c.term))).toEqual(new Set(['CSS', 'DOM']))
    expect(cands.every((c) => c.count === 1)).toBe(true)
  })

  it('accumulates count across calls', () => {
    for (let i = 0; i < 3; i++) store.recordFromRefined('使用 CSS 处理样式', [])
    store.recordFromRefined('DOM 出现一次', [])
    const cands = store.get(3)
    expect(cands.length).toBe(1)
    expect(cands[0].term).toBe('CSS')
    expect(cands[0].count).toBe(3)
  })

  it('excludes glossary terms (case-insensitive)', () => {
    store.recordFromRefined('CSS DOM API', ['css'])
    const terms = new Set(store.get(1).map((c) => c.term))
    expect(terms.has('CSS')).toBe(false)
    expect(terms.has('DOM')).toBe(true)
    expect(terms.has('API')).toBe(true)
  })

  it('accept removes from table', () => {
    store.recordFromRefined('API', [])
    store.recordFromRefined('API', [])
    expect(new Set(store.get(1).map((c) => c.term))).toEqual(new Set(['API']))
    store.accept('API')
    expect(store.get(1)).toEqual([])
  })

  it('dismiss hides by default but keeps record', () => {
    store.recordFromRefined('API CSS', [])
    store.dismiss('API')
    expect(new Set(store.get(1).map((c) => c.term))).toEqual(new Set(['CSS']))
    expect(new Set(store.get(1, true).map((c) => c.term)).has('API')).toBe(true)
  })

  it('orders by count descending', () => {
    for (let i = 0; i < 5; i++) store.recordFromRefined('CSS', [])
    for (let i = 0; i < 3; i++) store.recordFromRefined('DOM', [])
    store.recordFromRefined('API', [])
    expect(store.get(1).map((c) => c.term)).toEqual(['CSS', 'DOM', 'API'])
  })

  it('clears candidates', () => {
    store.recordFromRefined('CSS DOM API', [])
    store.clear()
    expect(store.get(1)).toEqual([])
  })

  it('empty text is a noop', () => {
    store.recordFromRefined('', [])
    store.recordFromRefined('纯中文没有缩写', [])
    expect(store.get(1)).toEqual([])
  })
})
