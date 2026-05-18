# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

My Typeless 是一个 Windows 平台的 AI 语音听写工具。用户按住热键说话，松开后语音经 STT 转录、LLM 润色，自动粘贴到光标位置。

## Development Commands

```bash
# 安装依赖（使用 uv 包管理器）
uv sync --group dev

# 运行应用
python -m my_typeless

# 构建可执行文件（注入版本 + SVG→ICO + PyInstaller）
python scripts/build.py --version 1.0.0

# 仅注入版本不构建
python scripts/build.py --version 1.0.0 --no-build

# 静态检查
uv run ruff check src
uv run pyright

# 运行测试
uv run pytest
```

测试位于 `tests/`，覆盖 `worker` 流水线（依赖注入 + mock STT/LLM/inject/history/candidates）、
`config` 默认值与旧版迁移、`updater` 线程生命周期与版本比较、`recorder` WAV 编码、
`vad` Silero ONNX 加载、`candidates` 自动缩写提取、`history` SQLite 读写与迁移。
依赖 Windows-only 模块（pyaudio、pywin32），CI 在 windows-latest 上运行。

## Architecture

### 数据流

```
按住热键 → 录音(16kHz/mono) → Silero VAD 分段(600ms 停顿)
        → STT 转录(OpenAI 兼容 API)
        → zhconv 繁→简 后处理
        → 拼接 → 整段 LLM 精修(含术语表)
        → 剪贴板注入(Ctrl+V)
        → 写历史 + 提取英文缩写到 glossary 候选
```

STT 在录音过程中分段进行（边录边转），松开热键后对完整转录做一次 LLM 精修——
分段 STT 降低端到端延迟，整段 LLM 让模型看到全文以做跨段去重、统一列表序号等全局整理。
Silero VAD（`vad.py`，ONNX 模型 `silero_vad.onnx` 约 2.3 MB）替代 RMS 静音检测，
在中文气口、背景噪声场景下更稳定。glossary 候选（`candidates.py`）从精修结果中
提取英文缩写，反复出现时通过设置界面提示加入术语表。

### 线程模型

- **主线程**: PyWebView 事件循环 + 设置界面 + 文本注入
- **热键线程**: Win32 低级键盘钩子 + 消息泵
- **录音线程**: PyAudio 音频采集 + 静音检测
- **API 线程**: STT + LLM 请求（每次录音会话临时创建）
- **托盘线程**: pystray 系统托盘
- **更新线程**: GitHub Releases 轮询（4小时间隔）
- **信号线程**: Named Pipe 服务器（`\\.\pipe\MyTypeless_SingleInstance`，用于单实例通信）

### 核心模块关系

`main.py` 中的 `MyTypelessApp` 是控制器，组装所有组件并通过 `events.py` 的 `EventEmitter` 连接事件：

- `hotkey.py` → 按键事件 → `worker.py` 开始/停止录音
- `worker.py` 协调 `recorder.py` → `stt_client.py` → `llm_client.py` → `text_injector.py`
- `worker.py` → 状态变化事件 → `tray.py` 更新图标（idle/recording/processing）
- `single_instance.py` 通过 Win32 Named Mutex 确保单实例，第二次启动通过 Named Pipe 通知第一个实例打开设置

### 设置界面

PyWebView 桥接 HTML/JS 前端（Tailwind CSS）与 Python 后端。`webview_api.py` 暴露方法供 `web/app.js` 调用。

### 配置与数据

- 配置文件: `~/.my-typeless/config.json`（dataclass 定义在 `config.py`）
- 历史记录: `~/.my-typeless/history.db`（最近 200 条）
- 开发模式: 环境变量 `MY_TYPELESS_DEV=1`，强制使用代码中的最新 LLM prompt

### 版本管理

`version.py` 在源树中始终为 `0.0.0.dev0`，永不手动修改。CI 通过环境变量 `MY_TYPELESS_VERSION` 调用 `scripts/build.py`，脚本生成 gitignored 的 `_version.py` 覆盖；运行时 `version.py` 优先 import `_version`，缺失时回落到 dev 值。本地构建可 `python scripts/build.py --version X.Y.Z`，同样只写 `_version.py`，源树保持干净。

## Build & Release

CI/CD 在 `.github/workflows/build-release.yml`，由 `v*` tag 触发：
1. `scripts/build.py` 注入版本 + 生成图标
2. PyInstaller 打包（配置见 `my_typeless.spec`）
3. Inno Setup 生成安装包（配置见 `installer.iss`）
4. 创建 GitHub Release 并上传产物

## Platform Constraints

仅支持 Windows。依赖 Win32 API（键盘钩子、剪贴板、Mutex）、pyaudio、keyboard 库。
