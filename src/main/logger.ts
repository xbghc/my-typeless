import log from 'electron-log/main'
import { LOG_FILE } from './paths'

export function initLogger(): typeof log {
  log.transports.file.resolvePathFn = () => LOG_FILE
  log.transports.file.level = 'debug'
  log.transports.console.level = 'info'
  log.transports.console.format = '{h}:{i}:{s} [{level}] {text}'
  log.initialize()
  return log
}

export default log
