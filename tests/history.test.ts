import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createDatabase, type DB } from '@main/db'
import { HistoryStore, type HistoryStoreOptions } from '@main/history'

let dir: string
let db: DB

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'mt-history-'))
  db = createDatabase(':memory:')
})
afterEach(() => {
  db.close()
  rmSync(dir, { recursive: true, force: true })
})

function newStore(opts: HistoryStoreOptions = {}): HistoryStore {
  return new HistoryStore(db, opts)
}

describe('history', () => {
  it('adds and queries a single entry', () => {
    const store = newStore()
    store.add('raw text', 'refined text')
    const page = store.getPage(0, 10)
    expect(page.has_more).toBe(false)
    expect(page.next_offset).toBeNull()
    expect(page.entries.length).toBe(1)
    expect(page.entries[0].raw_input).toBe('raw text')
    expect(page.entries[0].refined_output).toBe('refined text')
    expect(page.entries[0].timestamp).toBeTruthy()
  })

  it('paginates newest first with has_more', () => {
    const store = newStore()
    for (let i = 0; i < 15; i++) store.add(`raw${i}`, `refined${i}`)

    const page = store.getPage(0, 10)
    expect(page.entries.length).toBe(10)
    expect(page.has_more).toBe(true)
    expect(page.next_offset).toBe(10)
    expect(page.entries[0].raw_input).toBe('raw14')
    expect(page.entries[9].raw_input).toBe('raw5')

    const page2 = store.getPage(10, 10)
    expect(page2.entries.length).toBe(5)
    expect(page2.has_more).toBe(false)
    expect(page2.next_offset).toBeNull()
    expect(page2.entries[0].raw_input).toBe('raw4')
  })

  it('prunes to max entries keeping newest', () => {
    const store = newStore({ maxEntries: 5 })
    for (let i = 0; i < 8; i++) store.add(`raw${i}`, `refined${i}`)
    const page = store.getPage(0, 20)
    expect(page.entries.length).toBe(5)
    expect(page.entries.map((e) => e.raw_input)).toEqual(['raw7', 'raw6', 'raw5', 'raw4', 'raw3'])
  })

  it('clears history', () => {
    const store = newStore()
    store.add('a', 'A')
    store.add('b', 'B')
    store.clear()
    const page = store.getPage()
    expect(page.entries).toEqual([])
    expect(page.has_more).toBe(false)
  })

  it('persists timing columns', () => {
    const store = newStore()
    store.add('raw', 'refined', {
      keyPressAt: '12:00:00.000000',
      keyReleaseAt: '12:00:05.000000',
      sttDoneAt: '12:00:06.500000',
      llmDoneAt: '12:00:08.200000',
    })
    const e = store.getPage().entries[0]
    expect(e.key_press_at).toBe('12:00:00.000000')
    expect(e.key_release_at).toBe('12:00:05.000000')
    expect(e.stt_done_at).toBe('12:00:06.500000')
    expect(e.llm_done_at).toBe('12:00:08.200000')
  })

  it('migrates legacy json then deletes it', () => {
    const jsonPath = join(dir, 'history.json')
    writeFileSync(
      jsonPath,
      JSON.stringify([
        {
          timestamp: '2026-01-01 12:00',
          raw_input: 'old raw',
          refined_output: 'old refined',
          key_press_at: '12:00:00.000',
        },
        { timestamp: '2026-01-02 09:00', raw_input: 'old raw 2', refined_output: 'old refined 2' },
      ]),
    )
    const store = new HistoryStore(db, { legacyJsonPath: jsonPath })
    const page = store.getPage(0, 10)
    expect(page.entries.length).toBe(2)
    expect(new Set(page.entries.map((e) => e.raw_input))).toEqual(new Set(['old raw', 'old raw 2']))
    expect(existsSync(jsonPath)).toBe(false)
  })

  it('skips migration when legacy file absent', () => {
    const store = new HistoryStore(db, { legacyJsonPath: join(dir, 'history.json') })
    store.add('raw', 'refined')
    expect(store.getPage().entries.length).toBe(1)
  })
})
