# AGENTS.md

本文件为 AI 编码 agent 提供本仓库的工作指南。

## Project Overview

My Typeless 是 Windows 平台的 AI 语音听写工具（Electron + React + TypeScript）。用户按住热键说话，松开后语音经 STT 转录、LLM 润色，自动粘贴到光标位置。

## Development Commands

```bash
npm install            # 安装依赖
npm run dev            # 开发模式（electron-vite，热更新）
npm test               # 单元测试 (vitest)
npm run lint           # ESLint（typescript-eslint + react-hooks，flat config）
npm run typecheck      # TypeScript 类型检查（node + web 两套 tsconfig）
npm run build          # 构建（copy:ort + electron-vite build）
npm run dist           # 打包 x64 + arm64 安装器（electron-builder）
npm run dist:arm64     # 仅 arm64（本地 ARM 开发机可直接验证）
```

测试位于 `tests/`（vitest），覆盖 `worker` 流水线（依赖注入 + mock STT/LLM/inject/history/candidates）、
`config` 默认值与旧版迁移、`history` SQLite 读写与迁移、`candidates` 缩写提取、`errorMap` 异常映射。

## Architecture

### 数据流

```
按住热键 → 录音(16kHz/mono) → Silero VAD 分段(600ms 停顿)
        → STT 转录(OpenAI 兼容 API)
        → opencc 繁→简 后处理
        → 拼接 → 整段 LLM 精修(含术语表)
        → 剪贴板注入(Ctrl+V)
        → 写历史 + 提取英文缩写到 glossary 候选
```

STT 在录音过程中分段进行（边录边转），松开热键后对完整转录做一次 LLM 精修——
分段 STT 降低端到端延迟，整段 LLM 让模型看到全文做跨段去重、统一列表序号等全局整理。

### 进程模型

- **main 进程** (`src/main/`)：应用生命周期、单实例、托盘、全局热键(uiohook-napi)、worker 流水线编排、
  STT/LLM SDK 调用、文本注入(ffi-rs)、配置、better-sqlite3、自动更新、日志。
- **设置窗口 renderer** (`src/renderer/`)：React + Tailwind 设置界面（5 页 + Provider 弹窗 + 术语候选区），
  通过 preload 暴露的 `window.api` 调用 main。
- **隐藏音频 worker renderer** (`src/audio/`)：常驻隐藏窗口，getUserMedia + AudioWorklet 重采样到 16kHz/512 帧
  + onnxruntime-web 跑 Silero VAD 分段，WAV 段经 IPC 上行 main。

进程间通信走 `src/preload/index.ts`（contextBridge）+ `src/shared/ipc-channels.ts`（通道常量单一真源）。

### 核心模块（src/main/）

- `index.ts`：控制器，组装所有组件、窗口、事件接线、单实例、日志、AppUserModelID。
- `worker.ts`：录音→分段STT→整段LLM→注入 流水线（纯函数 + 可注入依赖，便于单测；运行时由 IPC 段流驱动）。
- `hotkey.ts`：uiohook-napi 全局热键（keydown/keyup + 键码映射）。
- `sttClient.ts` / `llmClient.ts`：openai / @anthropic-ai/sdk 客户端。
- `textInjector.ts`：Electron clipboard + ffi-rs 调 `user32!keybd_event` 模拟 Ctrl+V。
- `config.ts`：配置加载/保存/迁移（legacy→providers、DEV_MODE、`build*Prompt`）；`shared/prompts.ts` 存默认 prompt。
- `db.ts` / `history.ts` / `candidates.ts`：better-sqlite3 历史与术语候选（共用一个 db 文件，表独立）。
- `tray.ts` / `updater.ts` / `autostart.ts`：托盘三态、electron-updater、开机自启。
- `errorMap.ts`：openai/anthropic API 异常 → 中文提示 + 严重标志。

### 配置与数据

- 配置：`~/.my-typeless/config.json`（与旧 Python 版同路径，无缝迁移）
- 历史：`~/.my-typeless/history.db`（better-sqlite3，最近 200 条）
- 日志：`~/.my-typeless/app.log`（electron-log）
- 开发模式：`MY_TYPELESS_DEV`（开发默认 "1"，打包后入口设为 "0"）。dev 下强制用代码中最新 LLM prompt + 跳过更新检查。

### 设置界面

React + Zustand + 本地 Tailwind（`@tailwindcss/forms`）。`src/renderer/store.ts` 持有配置草稿，
`src/renderer/pages/` 是 5 个页面（General/Stt/Llm/Glossary/History），`components/ProviderModal.tsx` 是 Provider 弹窗。
所有后端调用经 `window.api`（preload）→ `src/main/ipc.ts` 的 `ipcMain.handle`，1:1 对应旧版 `webview_api.py`。

### 版本管理

版本单一真源 = `package.json` 的 `version`；CI 注入；运行时 `app.getVersion()` 读取。

## Build & Release

`electron-builder.yml` 配置 NSIS 双架构（x64 + arm64）。CI（`.github/workflows/build-release.yml`）由 `v*` tag 触发，
用矩阵在 `windows-latest`(x64) 与 `windows-11-arm`(arm64) 各自**原生**构建：`npm ci` → `electron-rebuild`（为 Electron ABI 重建原生模块）→ `npm run build` → `electron-builder --publish`。
electron-updater 从 GitHub Releases 自动更新（x64 读 `latest.yml`，arm64 读 `latest-arm64.yml`）。

ort wasm 由 `scripts/copy-ort-wasm.mjs` 在 build 前从 node_modules 复制到 `resources/ort-wasm/`（gitignored），
运行时由 main 经 IPC 以 blob URL 提供给音频 worker（绕开 Vite asset 与 dev/打包跨协议问题）。

## Platform Constraints

仅支持 Windows（x64 + arm64）。原生模块：
- `better-sqlite3`（非 NAPI，需按 Electron ABI rebuild；本地 ARM 用 `prebuild-install -r electron`，CI 用 `electron-rebuild`）
- `uiohook-napi`、`ffi-rs`（NAPI，跨 Node/Electron ABI；按架构选 prebuilt 子包）
- `onnxruntime-web`（wasm，跨架构无原生依赖）

注意：uiohook 基于 `SetWindowsHookEx` 监听，**无法“吞键”**（不像旧 Python 版的 `return 1`），故热键不抑制按键传播；
默认 `right alt` 单按不激活系统菜单，影响可忽略。

### better-sqlite3 ABI 切换

`better-sqlite3` 是非 NAPI 模块，node(测试) 与 electron(运行/打包) 的 ABI 不同，需切换：

- `npm run rebuild:node` —— 切到 node ABI（跑 `npm test` 前）
- `npm run rebuild:electron` —— 切到 Electron ABI（跑 `npm run dev` 或打包前）

默认（`npm install` 后）是 node ABI。CI 在 `npm test`(node) 之后、打包之前执行 `electron-rebuild` 自动切换。
