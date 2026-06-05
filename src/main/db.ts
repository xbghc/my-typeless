import Database from 'better-sqlite3'

export type DB = Database.Database

// history 与 candidates 共用同一个 db 文件（表独立），与旧版一致。
export function createDatabase(path: string): DB {
  const db = new Database(path)
  db.pragma('journal_mode = WAL')
  return db
}
