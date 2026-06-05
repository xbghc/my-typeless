# My Typeless

Windows 平台的 AI 语音听写工具。按住热键说话，松开后自动转成书面文字粘贴到光标处。

## 特性

- 按住 `Right Alt` 说话，松开即得结果
- 边录边转，Silero VAD 静音自动分段，延迟低
- STT 转录后经 LLM 润色，去口头禅、补标点
- 兼容任意 OpenAI 风格接口，LLM 亦原生支持 Anthropic
- 系统托盘常驻，三态图标反映运行状态
- 自动检查并安装新版本

## 安装

前往 [Releases](https://github.com/xbghc/my-typeless/releases) 下载与你的 CPU 架构对应的
`MyTypeless-Setup-<version>-<arch>.exe`（`x64` 或 `arm64`）安装。

首次启动后在托盘打开设置，填入 STT / LLM 的 `base_url`、`api_key`、`model`。

## 平台

仅支持 Windows 10/11，提供 x64 与 arm64 两种安装包。

## 开发

基于 Electron + React + TypeScript（electron-vite 构建）。

```bash
npm install            # 安装依赖
npm run dev            # 开发模式（热更新）
npm test               # 单元测试 (vitest)
npm run typecheck      # TypeScript 类型检查
npm run dist           # 打包 x64 + arm64 安装器
```

详见 [AGENTS.md](AGENTS.md)。
