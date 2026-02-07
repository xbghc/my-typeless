# My Typeless - AI 智能语音输入法设计文档

## 项目概述

一款类似 Typeless 的 Windows 桌面语音输入工具。按住快捷键说话，松开后 AI 自动将口语转为精修的书面文字，粘贴到当前光标位置。

## 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.13 | 标准 GIL 版本，不需要 free-threaded |
| 包管理 | uv | 替代 pip + venv |
| UI 框架 | PyQt6 | 系统托盘 + 设置窗口 |
| 语音转文字 | OpenAI 兼容 API (Groq Whisper) | 可配置 base_url |
| 文本精修 | OpenAI 兼容 API (DeepSeek) | 可配置 base_url |
| 全局热键 | keyboard 库 | 监听按住/松开事件 |
| 录音 | pyaudio | 16kHz/16bit/单声道 |
| 文本注入 | win32clipboard + ctypes | 剪贴板粘贴方式 |
| Windows API | pywin32 | 剪贴板操作 |

### GIL 分析结论

不需要 free-threaded Python。原因：
- 音频采集是 C 扩展操作，不持有 GIL
- API 调用是 I/O 密集型，Python 在 socket 读写期间自动释放 GIL
- 没有 CPU 密集型的 Python 计算需要并行执行

## 架构设计

### 数据流

```
按住热键 → 麦克风录音 → 松开热键 → 音频发送 Whisper API
→ 原始文本 → 发送 LLM 精修 → 精修文本
→ 备份剪贴板 → 写入剪贴板 → 模拟 Ctrl+V → 还原剪贴板
```

### 线程模型

```
主线程(PyQt6)  ──热键事件──▶  录音线程  ──音频数据──▶  API线程
                                                      │
主线程 ◀──Qt Signal(精修文本)──────────────────────────┘
```

- **主线程**: PyQt6 事件循环 + UI + 文本注入
- **录音线程**: pyaudio 音频采集，避免阻塞 UI
- **API 线程**: STT + LLM 调用，通过 Qt Signal 回传结果

## 项目结构

```
my-typeless/
├── main.py                 # 入口，启动 PyQt6 应用
├── config.py               # 配置管理（读写 JSON）
├── hotkey.py               # 全局热键监听
├── recorder.py             # 麦克风录音
├── stt_client.py           # Whisper STT 客户端
├── llm_client.py           # LLM 文本精修客户端
├── text_injector.py        # 剪贴板粘贴注入
├── tray.py                 # 系统托盘 + 设置窗口
├── worker.py               # 后台处理线程（录音→STT→LLM→注入）
├── resources/              # 图标资源
│   ├── icon_idle.png
│   ├── icon_recording.png
│   └── icon_processing.png
├── pyproject.toml
└── docs/
    └── design/
        └── tray-icons.png
```

## 模块设计

### 1. config.py - 配置管理

配置文件路径: `~/.my-typeless/config.json`

```json
{
  "hotkey": "right alt",
  "stt": {
    "base_url": "https://api.groq.com/openai/v1",
    "api_key": "gsk_xxx",
    "model": "whisper-large-v3"
  },
  "llm": {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-xxx",
    "model": "deepseek-chat",
    "prompt": "你是一个文本精修助手。将用户的口语转为书面文字：去除口头禅和重复，保留最终意图，自动添加标点，保持原始语言。只输出精修后的文本，不要解释。"
  }
}
```

### 2. stt_client.py - 语音转文字

- 使用 `openai.OpenAI(base_url=..., api_key=...)` 创建独立客户端
- 调用 `client.audio.transcriptions.create(model=..., file=audio_bytes)`
- 输入: WAV 格式音频 (内存中的 BytesIO)
- 输出: 原始转录文本

### 3. llm_client.py - 文本精修

- 使用 `openai.OpenAI(base_url=..., api_key=...)` 创建独立客户端
- 调用 `client.chat.completions.create(model=..., messages=[...])`
- system prompt 配置 AI 精修行为（去口头禅、去重复、理解意图、自动格式化）
- 输入: 原始转录文本
- 输出: 精修后的书面文本

### 4. hotkey.py - 全局热键

- 使用 `keyboard` 库监听配置的热键
- `key_down` 事件 → 发出开始录音信号
- `key_up` 事件 → 发出停止录音信号
- 热键可通过设置界面修改

### 5. recorder.py - 麦克风录音

- 使用 `pyaudio` 录制音频
- 参数: 16kHz 采样率, 16bit, 单声道 (Whisper 推荐)
- 录音在独立线程运行，数据存内存 (`io.BytesIO`)
- 录音结束后转为 WAV 格式

### 6. text_injector.py - 文本注入

1. 用 `win32clipboard` 备份当前剪贴板内容
2. 将精修文本写入剪贴板
3. 用 `ctypes` 调用 Win32 API 模拟 `Ctrl+V`
4. 延迟 ~100ms 后还原剪贴板原内容

### 7. tray.py - 系统托盘

基于 `QSystemTrayIcon`:
- **托盘图标三种状态**:
  - Idle (待命): 灰色麦克风 `#374151`
  - Recording (录音中): 红色麦克风 `#EF4444`
  - Processing (处理中): 琥珀黄麦克风 `#F59E0B`
- **右键菜单**: 设置、关于、退出
- **设置窗口**: 配置热键、STT 参数、LLM 参数

### 8. worker.py - 后台处理

- 在独立 QThread 中运行完整处理流水线
- 通过 Qt Signal 与主线程通信
- 信号: 状态变更 (recording/processing/idle)、结果文本、错误信息

## UI 设计

### 托盘图标

已通过 Google Stitch 设计，见 `docs/design/tray-icons.png`。

### 设置窗口

待在 Stitch 中重新生成。设计要求:
- 左侧边栏导航，Windows 11 原生风格，浅色主题，约 500x600px
- **General 区**: 热键设置 (按键捕获按钮)、开机自启开关
- **Speech-to-Text 区**: base_url、api_key (密码遮罩+显隐切换)、model
- **Text Refinement 区**: base_url、api_key (密码遮罩+显隐切换)、model、system prompt (多行文本框)
- 底部 Save / Cancel 按钮

Stitch 项目 ID: `11987617409436038210`，可继续在 Stitch 中迭代设计。

## 依赖清单

```
PyQt6
openai
keyboard
pyaudio
pywin32
```

通过 `uv add PyQt6 openai keyboard pyaudio pywin32` 安装。

## MVP 范围

第一版只包含核心闭环:
- [x] 系统托盘常驻
- [x] 全局热键按住说话
- [x] Whisper API 转写
- [x] LLM 精修文本
- [x] 剪贴板粘贴输出
- [x] 设置界面 (API 配置)

**不包含** (后续迭代):
- 多语言自动检测
- 个人词典
- 按应用切换语气
- 听写历史记录
