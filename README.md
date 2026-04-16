# My Typeless

Windows 平台的 AI 语音听写工具。按住热键说话，松开后自动转成书面文字粘贴到光标处。

## 特性

- 按住 `Right Alt` 说话，松开即得结果
- 边录边转，静音自动分段，延迟低
- STT 转录后经 LLM 润色，去口头禅、补标点
- 兼容任意 OpenAI 风格接口，LLM 亦原生支持 Anthropic
- 系统托盘常驻，三态图标反映运行状态
- 自动检查并安装新版本

## 安装

前往 [Releases](https://github.com/xbghc/my-typeless/releases) 下载最新 `MyTypeless-Setup-v*.exe` 安装。

首次启动后在托盘打开设置，填入 STT / LLM 的 `base_url`、`api_key`、`model`。

## 平台

仅支持 Windows 10/11。

## 开发

见 [docs/development/readme.md](docs/development/readme.md)。
