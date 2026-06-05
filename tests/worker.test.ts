import { describe, expect, it } from 'vitest'
import { Worker, buildSttPromptWithTail, updateTranscriptionTail } from '@main/worker'
import { defaultConfig } from '@main/config'
import type { AppState } from '@shared/types'

const seg = (s: string): Buffer => Buffer.from(s)

describe('worker pure helpers', () => {
  it('keeps only recent chars in transcription tail', () => {
    let tail = ''
    tail = updateTranscriptionTail(tail, 'hello', 4)
    tail = updateTranscriptionTail(tail, 'world', 4)
    expect(tail).toBe('orld')
  })

  it('appends glossary after tail', () => {
    expect(buildSttPromptWithTail('最近上下文', '术语A、术语B')).toBe('最近上下文 术语A、术语B')
  })

  it('uses tail only without glossary', () => {
    expect(buildSttPromptWithTail('only tail', '')).toBe('only tail')
  })
})

describe('worker incrementalProcess', () => {
  it('runs full pipeline with injected dependencies', async () => {
    const sttPrompts: string[] = []
    const injectCalls: string[] = []
    const historyCalls: { raw: string; ref: string }[] = []

    const cfg = defaultConfig()
    cfg.glossary = ['MyTypeless']

    const w = new Worker(cfg, {
      sttClientFactory: () => ({
        transcribe: (_a, p = '') => {
          sttPrompts.push(p)
          return '测试文本'
        },
      }),
      llmClientFactory: () => ({ refine: (t) => `[${t}]` }),
      textInjector: (t) => {
        injectCalls.push(t)
      },
      historyAdder: (raw, ref) => {
        historyCalls.push({ raw, ref })
      },
      candidatesRecorder: () => {},
    })

    await w.incrementalProcess('09:00:00.000000', [seg('segment-1')], '10:00:00.000000')

    expect(sttPrompts[0]).toContain('MyTypeless')
    expect(injectCalls).toEqual(['[测试文本]'])
    expect(historyCalls.length).toBe(1)
    expect(historyCalls[0].raw).toBe('测试文本')
    expect(historyCalls[0].ref).toBe('[测试文本]')
  })

  it('calls LLM once with full concatenated text and no context', async () => {
    const refineCalls: { t: string; ctx: string }[] = []
    const injectCalls: string[] = []
    const historyCalls: { raw: string; ref: string; ti: Record<string, unknown> }[] = []

    const segs = ['第一段。', '第二段。', '第三段。']
    let i = 0

    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => segs[i++] }),
      llmClientFactory: () => ({
        refine: (t, _sp = '', ctx = '') => {
          refineCalls.push({ t, ctx })
          return '整段精修后的文本。'
        },
      }),
      textInjector: (t) => {
        injectCalls.push(t)
      },
      historyAdder: (raw, ref, ti) => {
        historyCalls.push({ raw, ref, ti: ti as Record<string, unknown> })
      },
      candidatesRecorder: () => {},
    })

    await w.incrementalProcess('09:00:00.000000', [seg('a1'), seg('a2'), seg('a3')], 'r')

    expect(refineCalls.length).toBe(1)
    expect(refineCalls[0].t).toBe('第一段。第二段。第三段。')
    expect(refineCalls[0].ctx).toBe('')
    expect(injectCalls).toEqual(['整段精修后的文本。'])
    expect(historyCalls.length).toBe(1)
    expect(historyCalls[0].raw).toBe('第一段。第二段。第三段。')
    expect(historyCalls[0].ref).toBe('整段精修后的文本。')
    expect(historyCalls[0].ti.sttDoneAt).toBeTruthy()
    expect(historyCalls[0].ti.llmDoneAt).toBeTruthy()
  })

  it('skips empty/blank segments', async () => {
    const segs = ['有效内容', '', '   ', '更多内容']
    let i = 0
    const refineArgs: string[] = []
    const injectCalls: string[] = []

    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => segs[i++] }),
      llmClientFactory: () => ({
        refine: (t) => {
          refineArgs.push(t)
          return '精修结果'
        },
      }),
      textInjector: (t) => {
        injectCalls.push(t)
      },
    })

    await w.incrementalProcess('t0', [seg('a'), seg('b'), seg('c'), seg('d')])
    expect(refineArgs).toEqual(['有效内容更多内容'])
    expect(injectCalls).toEqual(['精修结果'])
  })

  it('skips LLM/inject/history when all segments empty', async () => {
    const refineCalls: string[] = []
    const injectCalls: string[] = []
    const historyCalls: number[] = []

    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => '' }),
      llmClientFactory: () => ({
        refine: (t) => {
          refineCalls.push(t)
          return 'x'
        },
      }),
      textInjector: (t) => {
        injectCalls.push(t)
      },
      historyAdder: () => {
        historyCalls.push(1)
      },
    })

    await w.incrementalProcess('t0', [seg('a'), seg('b')])
    expect(refineCalls).toEqual([])
    expect(injectCalls).toEqual([])
    expect(historyCalls).toEqual([])
  })

  it('converts traditional chinese to simplified before LLM', async () => {
    const segs = ['組件之間的衝突。', '解決方案。']
    let i = 0
    const refineArgs: string[] = []

    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => segs[i++] }),
      llmClientFactory: () => ({
        refine: (t) => {
          refineArgs.push(t)
          return 'out'
        },
      }),
    })

    await w.incrementalProcess('t0', [seg('s1'), seg('s2')])
    expect(refineArgs.length).toBe(1)
    const raw = refineArgs[0]
    expect(raw).toContain('组件')
    expect(raw).toContain('之间')
    expect(raw).toContain('冲突')
    expect(raw).toContain('解决方案')
    expect(raw).not.toContain('組件')
    expect(raw).not.toContain('衝突')
  })

  it('records candidates with refined text and glossary', async () => {
    const recordCalls: [string, string[]][] = []
    const cfg = defaultConfig()
    cfg.glossary = ['CSS']

    const w = new Worker(cfg, {
      sttClientFactory: () => ({ transcribe: () => '内容。' }),
      llmClientFactory: () => ({ refine: () => '整段精修使用 DOM 和 API。' }),
      candidatesRecorder: (text, gl) => {
        recordCalls.push([text, [...gl]])
      },
    })

    await w.incrementalProcess('t0', [seg('s1')])
    expect(recordCalls).toEqual([['整段精修使用 DOM 和 API。', ['CSS']]])
  })

  it('does not break pipeline when candidates recorder throws', async () => {
    const injectCalls: string[] = []
    const historyCalls: number[] = []

    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => '内容。' }),
      llmClientFactory: () => ({ refine: () => '精修。' }),
      textInjector: (t) => {
        injectCalls.push(t)
      },
      historyAdder: () => {
        historyCalls.push(1)
      },
      candidatesRecorder: () => {
        throw new Error('simulated candidates failure')
      },
    })

    await w.incrementalProcess('t0', [seg('s1')])
    expect(injectCalls).toEqual(['精修。'])
    expect(historyCalls.length).toBe(1)
  })
})

describe('worker recording lifecycle', () => {
  it('isRunning is false initially and stopRecording is a no-op when idle', () => {
    const states: AppState[] = []
    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => '内容' }),
      llmClientFactory: () => ({ refine: () => '精修' }),
      onStateChange: (s) => states.push(s),
    })

    expect(w.isRunning()).toBe(false)
    // 未运行时松键不得把状态切到 processing（崩溃/错误提前收尾后的松键路径）。
    w.stopRecording()
    expect(states).toEqual([])
    expect(w.isRunning()).toBe(false)
  })

  it('isRunning becomes true after startRecording and emits recording state', () => {
    const states: AppState[] = []
    const w = new Worker(defaultConfig(), {
      sttClientFactory: () => ({ transcribe: () => '内容' }),
      llmClientFactory: () => ({ refine: () => '精修' }),
      onStateChange: (s) => states.push(s),
    })

    w.startRecording()
    expect(w.isRunning()).toBe(true)
    expect(states).toContain('recording')
    // 收尾，避免悬挂的段流 for-await。
    w.finishSegments()
  })
})
