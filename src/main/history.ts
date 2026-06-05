// 历史记录 - SQLite。对应旧版 history.py（WAL / prune 200 / 分页最新在前 / legacy json 迁移）。
import { existsSync, readFileSync, unlinkSync } from 'node:fs'
import type { DB } from './db'
import type { HistoryEntry, HistoryPage, TimingInfo } from '@shared/types'

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function nowTimestamp(d = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

interface HistoryRow {
  id: number
  timestamp: string
  raw_input: string
  refined_output: string
  key_press_at: string | null
  key_release_at: string | null
  stt_done_at: string | null
  llm_done_at: string | null
}

interface LegacyEntry {
  timestamp?: string
  raw_input?: string
  refined_output?: string
  key_press_at?: string | null
  key_release_at?: string | null
  stt_done_at?: string | null
  llm_done_at?: string | null
}

export interface HistoryStoreOptions {
  maxEntries?: number
  legacyJsonPath?: string
}

export class HistoryStore {
  private maxEntries: number

  constructor(
    private db: DB,
    opts: HistoryStoreOptions = {},
  ) {
    this.maxEntries = opts.maxEntries ?? 200
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        raw_input TEXT NOT NULL,
        refined_output TEXT NOT NULL,
        key_press_at TEXT,
        key_release_at TEXT,
        stt_done_at TEXT,
        llm_done_at TEXT
      )
    `)
    if (opts.legacyJsonPath) this.maybeMigrate(opts.legacyJsonPath)
  }

  add(rawInput: string, refinedOutput: string, timing: TimingInfo = {}): void {
    this.db
      .prepare(
        `INSERT INTO history (timestamp, raw_input, refined_output, key_press_at, key_release_at, stt_done_at, llm_done_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        nowTimestamp(),
        rawInput,
        refinedOutput,
        timing.keyPressAt ?? null,
        timing.keyReleaseAt ?? null,
        timing.sttDoneAt ?? null,
        timing.llmDoneAt ?? null,
      )
    this.prune()
  }

  getPage(offset = 0, limit = 20): HistoryPage {
    const rows = this.db
      .prepare(
        `SELECT id, timestamp, raw_input, refined_output, key_press_at, key_release_at, stt_done_at, llm_done_at
         FROM history ORDER BY id DESC LIMIT ? OFFSET ?`,
      )
      .all(limit + 1, offset) as HistoryRow[]

    const hasMore = rows.length > limit
    const entries: HistoryEntry[] = rows.slice(0, limit).map((r) => ({
      id: r.id,
      timestamp: r.timestamp,
      raw_input: r.raw_input,
      refined_output: r.refined_output,
      key_press_at: r.key_press_at,
      key_release_at: r.key_release_at,
      stt_done_at: r.stt_done_at,
      llm_done_at: r.llm_done_at,
    }))

    return { entries, has_more: hasMore, next_offset: hasMore ? offset + limit : null }
  }

  clear(): void {
    this.db.exec('DELETE FROM history')
  }

  private prune(): void {
    this.db
      .prepare(`DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT ?)`)
      .run(this.maxEntries)
  }

  private maybeMigrate(jsonPath: string): void {
    if (!existsSync(jsonPath)) return
    try {
      const data = JSON.parse(readFileSync(jsonPath, 'utf-8')) as LegacyEntry[]
      if (!Array.isArray(data) || data.length === 0) {
        unlinkSync(jsonPath)
        return
      }
      const insert = this.db.prepare(
        `INSERT INTO history (timestamp, raw_input, refined_output, key_press_at, key_release_at, stt_done_at, llm_done_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      )
      const tx = this.db.transaction((items: LegacyEntry[]) => {
        for (const e of items) {
          insert.run(
            e.timestamp ?? '',
            e.raw_input ?? '',
            e.refined_output ?? '',
            e.key_press_at ?? null,
            e.key_release_at ?? null,
            e.stt_done_at ?? null,
            e.llm_done_at ?? null,
          )
        }
      })
      tx(data)
      this.prune()
      unlinkSync(jsonPath)
    } catch {
      // 迁移失败不阻断启动；保留 json 供后续重试。
    }
  }
}
