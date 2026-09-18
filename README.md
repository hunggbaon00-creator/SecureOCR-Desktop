# SecureOCR Desktop

SecureOCR Desktop 是面向 Windows 的本地文档处理工作台，封装现有 OCR、本地模型总结和敏感内容审查流程。所有自动敏感审查结果都必须经过人工复核。

## Python 版本

本项目明确且仅使用 **Python 3.11**。不得使用本机同时存在的 Python 3.14 创建、运行或打包本项目。

桌面界面使用项目目录中的 `.venv`，现有 Paddle/OCR 后端继续使用：

```text
C:\SecureOCR\app\.venv\Scripts\python.exe
```

GUI 环境不安装 Paddle，从而确保一台设备仍只有一套 Paddle 环境。

## 当前能力

- 原生 PySide6 Windows 主界面；
- 文件拖放和多文件队列；
- “仅 OCR”、“OCR 与总结”、“OCR、敏感检查与脱敏”三种模式；
- 只读显示 CPU 或 GPU 计算环境，不提供设备切换；
- 主界面显示工具链、系统网络、工作区和云同步状态；
- 每个任务使用独立工作区并记录 SHA-256；
- 使用后台进程调用现有脚本，界面不会被长任务阻塞；
- 三种模式使用不同的结果文件优先顺序和风险提示；
- 最近任务、环境详情、自定义敏感词查看和运行日志。

## 开发运行

首次配置：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

启动：

```powershell
.\.venv\Scripts\python.exe -m secureocr_desktop
```

也可以双击 `run_secureocr.bat`。

## 安全边界

- “未检测到云同步路径”不是对第三方同步软件行为的绝对保证；
- Windows 网络状态检查不会主动访问互联网；
- 远程 Ollama、网络工作区或已知云同步目录会阻止敏感审查；
- 系统仍联网时会在敏感审查前要求用户确认；
- 软件不能自动认定材料无密、可以公开或可以上传公网。
