# 开发文档

## 环境要求

- Python 3.13
- [uv](https://github.com/astral-sh/uv) 包管理器
- Windows 10/11（依赖 Win32 API）

## 常用命令

```bash
# 安装依赖
uv sync --group dev

# 运行应用
python -m my_typeless

# 打包可执行文件（注入版本 + SVG→ICO + PyInstaller）
python scripts/build.py --version 1.0.0

# 仅注入版本不构建
python scripts/build.py --version 1.0.0 --no-build
```

无测试套件、无 linter 配置。

## 数据流

```
按住热键 → 录音 (16 kHz / mono) → 静音分段 (600 ms)
        → STT 转录 (OpenAI 兼容 API)
        → LLM 润色
        → 剪贴板注入 (Ctrl+V)
```

音频分段在录音过程中增量处理（边录边转），而非等待录音结束后批量处理。

## 线程模型

| 线程 | 职责 |
|------|------|
| 主线程 | PyWebView 事件循环 + 设置界面 + 文本注入 |
| 热键线程 | Win32 低级键盘钩子 + 消息泵 |
| 录音线程 | PyAudio 采集 + 静音检测 |
| API 线程 | STT + LLM 请求（按会话临时创建） |
| 托盘线程 | pystray 系统托盘 |
| 更新线程 | GitHub Releases 轮询（4 小时间隔） |
| 信号线程 | Named Pipe 服务器（`\\.\pipe\MyTypeless_SingleInstance`，单实例通信） |

## 核心模块

`main.py` 中的 `MyTypelessApp` 是控制器，通过 `events.py` 的 `EventEmitter` 连接各组件：

- `hotkey.py` → 按键事件 → `worker.py` 开始/停止录音
- `worker.py` 协调 `recorder.py` → `stt_client.py` → `llm_client.py` → `text_injector.py`
- `worker.py` → 状态变化事件 → `tray.py` 更新图标（idle / recording / processing）
- `single_instance.py` 通过 Win32 Named Mutex 确保单实例，第二次启动通过 Named Pipe 通知第一个实例打开设置
- `webview_api.py` + `web/`：PyWebView 桥接 HTML/JS 前端（Tailwind CSS）
- `updater.py`：GitHub Releases 轮询与静默升级

## 配置与数据

- 配置文件：`~/.my-typeless/config.json`（dataclass 定义在 `config.py`）
- 历史记录：`~/.my-typeless/history.sqlite`（最近 200 条）
- 日志文件：`~/.my-typeless/app.log`

### 环境变量

| 变量 | 说明 |
|------|------|
| `MY_TYPELESS_DEV` | `1`（默认）每次启动强制使用代码中最新 system prompt；`0` 保留用户修改的 prompt |

## 版本管理

版本号不手动维护。CI/CD 通过 `scripts/build.py` 在发布时注入 `version.py`。本地开发时 version 为 `0.0.0.dev0`。

## 构建与发布

CI/CD 在 `.github/workflows/build-release.yml`，由 `v*` tag 触发：

1. `scripts/build.py` 注入版本 + 生成图标
2. PyInstaller 打包（配置见 `my_typeless.spec`）
3. Inno Setup 生成安装包（配置见 `installer.iss`）
4. 创建 GitHub Release 并上传产物
