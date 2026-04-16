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

## 客户端更新

客户端通过轮询 GitHub Releases 获取更新，相关逻辑集中在 `updater.py`，由 `main.py` 的 `MyTypelessApp` 组装。

### 触发时机

- 应用启动后 `webview` 就绪时立即检查一次（`UpdateChecker.start(immediate=True)`）
- 此后每 4 小时轮询一次（`CHECK_INTERVAL_S`，`threading.Timer` 驱动，守护线程）
- 开发版本（`__version__` 含 `.dev`）跳过检查，避免本地调试触发升级

### 检查流程

1. 请求 `GET https://api.github.com/repos/xbghc/my-typeless/releases/latest`
   - `Accept: application/vnd.github+json`
   - `User-Agent: MyTypeless/<version>`
   - 超时 15 s
2. 在 `assets` 中匹配 **文件名以 `MyTypeless-Setup` 开头且以 `.exe` 结尾** 的安装包
3. 用 `is_newer()` 比较版本：去掉 `v` 前缀与 `-rc1` 等预发布后缀后，按点号拆成 `tuple[int, ...]` 比较
4. 若远端更新，发射 `update_available(ReleaseInfo)` 事件

### 下载与安装

1. `MyTypelessApp._on_update_available` 收到事件后：
   - 通过托盘气泡提示新版本号与文件大小
   - 立即调用 `UpdateChecker.download(release)` 在后台线程下载
2. 下载到系统临时目录（`tempfile.mkdtemp()`），写入时按 64 KB 分块，失败会清理临时文件
3. 下载成功发射 `update_downloaded(path)`；失败发射 `update_error(msg)`
4. `MyTypelessApp._on_update_downloaded` 调用 `apply_update()`：
   - 用 `/SILENT /SUPPRESSMSGBOXES` 参数静默启动 Inno Setup 安装程序
   - 启动成功后调用 `_quit()` 退出当前实例，让安装程序覆盖文件
5. 安装程序运行结束后由 Inno Setup 决定是否重启应用（见 `installer.iss`）

### 事件契约

`UpdateChecker.events`（`EventEmitter`）对外暴露三个事件：

| 事件 | 参数 | 说明 |
|------|------|------|
| `update_available` | `ReleaseInfo` | 发现新版本，尚未下载 |
| `update_downloaded` | `str` | 安装程序已下载，值为本地路径 |
| `update_error` | `str` | 网络或下载失败的错误描述 |

当前实现为"发现即自动下载自动安装"，用户只会看到托盘通知。如需改为用户确认再升级，在 `_on_update_available` 中去掉自动 `download()` 调用，并在 UI 侧增加交互入口即可，其它环节无需改动。
