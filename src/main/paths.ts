import { homedir } from 'node:os'
import { join } from 'node:path'

// 复用旧版数据目录，老用户无缝迁移。
export const CONFIG_DIR = join(homedir(), '.my-typeless')
export const CONFIG_FILE = join(CONFIG_DIR, 'config.json')
export const HISTORY_DB = join(CONFIG_DIR, 'history.db')
export const HISTORY_JSON = join(CONFIG_DIR, 'history.json')
export const LOG_FILE = join(CONFIG_DIR, 'app.log')
