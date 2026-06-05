// 自动 glossary 候选：从精修结果提取英文缩写，反复出现的提示加入术语表。对应旧版 candidates.py。
import type { DB } from './db'
import type { Candidate } from '@shared/types'

// 抓全大写至少 2 字符的 token，允许后缀数字：CSS / DOM / API / S3 / HTTP2。
export const ACRONYM_RE = /\b[A-Z][A-Z0-9]+\b/g

// 太常见、几乎不是用户特有术语，跳过避免噪声。
const STOPWORDS = new Set(['OK', 'TV', 'PC', 'USA', 'UK', 'EU', 'AM', 'PM'])

export function extractAcronyms(text: string): Set<string> {
  const out = new Set<string>()
  for (const m of text.matchAll(ACRONYM_RE)) {
    if (STOPWORDS.has(m[0])) continue
    out.add(m[0])
  }
  return out
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function nowDateTime(d = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

interface CandRow {
  term: string
  count: number
  last_seen: string
  ignored: number
}

export class CandidateStore {
  constructor(private db: DB) {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS glossary_candidates (
        term TEXT PRIMARY KEY,
        count INTEGER NOT NULL DEFAULT 0,
        last_seen TEXT NOT NULL,
        ignored INTEGER NOT NULL DEFAULT 0
      )
    `)
  }

  recordFromRefined(refinedText: string, existingGlossary: Iterable<string>): void {
    const existing = new Set([...existingGlossary].map((g) => g.toUpperCase()))
    const terms = [...extractAcronyms(refinedText)].filter((t) => !existing.has(t))
    if (terms.length === 0) return

    const now = nowDateTime()
    const stmt = this.db.prepare(
      `INSERT INTO glossary_candidates (term, count, last_seen) VALUES (?, 1, ?)
       ON CONFLICT(term) DO UPDATE SET count = count + 1, last_seen = excluded.last_seen`,
    )
    const tx = this.db.transaction((items: string[]) => {
      for (const t of items) stmt.run(t, now)
    })
    tx(terms)
  }

  get(minCount = 3, includeIgnored = false): Candidate[] {
    let query = 'SELECT term, count, last_seen, ignored FROM glossary_candidates WHERE count >= ?'
    if (!includeIgnored) query += ' AND ignored = 0'
    query += ' ORDER BY count DESC, last_seen DESC'
    const rows = this.db.prepare(query).all(minCount) as CandRow[]
    return rows.map((r) => ({
      term: r.term,
      count: r.count,
      last_seen: r.last_seen,
      ignored: !!r.ignored,
    }))
  }

  accept(term: string): void {
    this.db.prepare('DELETE FROM glossary_candidates WHERE term = ?').run(term)
  }

  dismiss(term: string): void {
    this.db.prepare('UPDATE glossary_candidates SET ignored = 1 WHERE term = ?').run(term)
  }

  clear(): void {
    this.db.exec('DELETE FROM glossary_candidates')
  }
}
