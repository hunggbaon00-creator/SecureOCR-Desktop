# SecureOCR Desktop 项目交接与首版开发规格

## 1 项目目的

本项目拟将现有的本地 OCR、离线大模型总结和敏感内容审查能力封装为 Windows 桌面应用，降低非技术用户的部署和使用门槛。

首版核心目标是让用户不再手动激活 Python 虚拟环境、不再维护命令行参数，也不需要自行填写输入输出路径。用户通过桌面界面拖入文件、选择处理模式、启动任务并查看结果。

应用面向需要处理纸质打印件、扫描件、图片和 PDF 的单位用户，特别关注以下需求：

- 文件尽量只在本机处理；
- OCR 和大模型推理支持离线运行；
- 上传或外发前识别并屏蔽敏感内容；
- 记录处理过程、模型、文件哈希和输出结果；
- 对无法确认的内容进行阻断并要求人工复核；
- 同一套界面适配 CPU 和 NVIDIA GPU 机器。

本应用不得宣称能够自动认定文件“绝对安全”或“可以对外发布”。对于依法属于国家秘密的材料，应使用符合单位制度和保密要求的专用设备、系统及管理流程。本项目的软件检查只能作为技术辅助，不能替代保密审查和人工审批。

## 2 当前基础环境

现有工作目录为：

```text
C:\SecureOCR
```

已建立的主要目录和文件如下：

```text
C:\SecureOCR\
├── app\
│   ├── .venv\
│   ├── ocr.py
│   ├── workflow.py
│   └── secure_redact.py
├── config\
│   └── sensitive_terms.txt
├── input\
├── output\
├── README.md
├── README_CPU.md
├── README_GPU.md
├── USE_README.md
├── USE_README_CPU.md
├── USE_README_GPU.md
└── SECURE_REDACTION_README.md
```

已知运行环境：

- Windows；
- Python 3.11 虚拟环境：`C:\SecureOCR\app\.venv`；
- PaddlePaddle 3.2.2；
- PaddlePaddle 已编译 CUDA 支持；
- 已检测到 1 块 NVIDIA GPU；
- GPU Compute Capability 12.0；
- PaddlePaddle GPU 自检通过；
- OCR 使用 PP-StructureV3；
- 本地大模型运行服务使用 Ollama；
- 默认模型为 `qwen3.5:4b`；
- Ollama 默认地址为 `http://127.0.0.1:11434`。

当前 `ocr.py` 和 `workflow.py` 已配置使用 `device="gpu:0"`。`secure_redact.py` 默认参数同样为 `gpu:0`，同时允许通过参数选择 CPU。

PowerShell 脚本执行策略可能导致虚拟环境激活失败。桌面应用不得依赖用户手工运行 `Activate.ps1`，而应直接调用：

```text
C:\SecureOCR\app\.venv\Scripts\python.exe
```

## 3 已有处理能力

### 3.1 仅 OCR

`ocr.py` 用于将 PDF、PNG、JPG 等文件转换为 Markdown 文本。底层使用 PP-StructureV3，并支持文档方向校正、版面分析和文字识别。

### 3.2 OCR 与总结

`workflow.py` 先执行 OCR，再按文本块调用本机 Ollama 和 `qwen3.5:4b`，生成分块摘要与最终摘要。

### 3.3 OCR 与敏感内容审查

`secure_redact.py` 支持 PDF、图片、Markdown 和 TXT。主要能力包括：

- 限制 Ollama 地址为本机回环地址；
- 拒绝名称中含 `cloud` 的模型；
- 检查模型是否已安装在本机；
- 检查 `OLLAMA_NO_CLOUD=1` 或 Ollama 的云功能禁用配置；
- 使用正则规则和离线大模型进行双重识别；
- 识别涉密标志、内部信息、身份信息、联系方式、财务信息、网络系统信息、案件和信访信息、人事纪检信息、场所及行动方案、自定义敏感词；
- 标记 OCR 疑似错误；
- 对高置信度且不涉及敏感内容的 OCR 错误提供纠正稿；
- 对敏感内容生成屏蔽草稿；
- 对无法在原文中精确定位的模型结果进行阻断；
- 对明确密级或定密标志触发整篇阻断；
- 输出 SHA-256 文件哈希；
- 所有输出默认要求人工复核。

其输出包括：

```text
00_manifest.json
01_ocr_original_restricted.md
02_redacted_draft_REVIEW_REQUIRED.md
03_redacted_corrected_draft_REVIEW_REQUIRED.md
04_review_report_RESTRICTED.md
05_findings_index_RESTRICTED.json
ocr_page_json\
```

## 4 已确认的产品决策

### 4.1 先做使用阶段桌面应用

首阶段先将已经能够运行的 OCR、Ollama 和敏感审查流程封装为桌面工作台。原因是安装器依赖稳定的应用目录、依赖版本、模型策略、错误处理方式和升级策略。如果业务接口仍频繁变化，过早开发安装器会导致重复打包和大量环境兼容问题。

部署设计并非完全后置。首版就要实现环境检测页、固定目录规范、CPU/GPU探测和依赖检查；待工作台稳定后，再把这些能力包装成安装向导和离线安装包。

### 4.2 一套应用适配 CPU 与 GPU

界面和业务功能保持一致。应用启动后自动检测硬件和已安装的 Paddle 后端：

- 检测到可用 NVIDIA GPU 时，默认使用 GPU；
- 未检测到 GPU 时，自动使用 CPU，并将 GPU 选项置灰；
- GPU 环境异常时，显示具体原因并允许回退 CPU；
- 普通用户不需要填写 `gpu:0`、CUDA 版本或 Python 路径。

正式部署时，每台机器默认只安装一种 Paddle 后端：CPU 机器安装 `paddlepaddle`，GPU 机器安装与驱动和 CUDA 兼容的 `paddlepaddle-gpu`。不建议在同一个虚拟环境中混装 CPU 和 GPU 版本。

如未来确需在同一台电脑保留两套后端，应创建彼此独立的虚拟环境，并由应用选择相应运行时。这属于高级部署模式，不纳入首版范围。

### 4.3 使用 PySide6 开发 Windows 桌面应用

首版建议采用 PySide6。原因包括：

- 可开发原生 Windows 桌面界面；
- 支持文件拖放；
- 可使用 `QProcess` 启动现有 Python 工作流并读取实时输出；
- 无需为敏感文件额外启动本地网页服务；
- 后续可通过 Qt 官方部署工具或 PyInstaller 打包。

官方参考：

- Qt for Python：https://doc.qt.io/qtforpython-6/
- QProcess：https://doc.qt.io/qtforpython-6/PySide6/QtCore/QProcess.html
- Qt for Python 部署：https://doc.qt.io/qtforpython-6/deployment/index.html
- PyInstaller：https://pyinstaller.org/en/stable/operating-mode.html

## 5 首版用户界面

应用暂定名为 `SecureOCR Desktop`。

### 5.1 主工作台

```text
┌──────────────────────────────────────────────────────────────┐
│ SecureOCR Desktop     离线状态：●可处理   GPU：●可用         │
├──────────┬───────────────────────────────────────────────────┤
│ 工作台   │                                                   │
│ 历史任务 │       将 PDF、PNG、JPG、MD、TXT 拖到这里          │
│ 敏感规则 │              或［选择文件］                       │
│ 环境检测 │                                                   │
│ 设置     │                                                   │
│ 日志     │                                                   │
├──────────┼───────────────────────────────────────────────────┤
│          │ 处理模式                                          │
│          │ ○ 仅 OCR                                          │
│          │ ○ OCR 与内容总结                                  │
│          │ ● OCR 与敏感检查及脱敏                            │
│          │                                                   │
│          │ 计算设备：自动 NVIDIA GPU 0                       │
│          │ 模型：qwen3.5:4b 已安装本地模型                   │
│          │                                                   │
│          │              ［开始处理］                         │
├──────────┴───────────────────────────────────────────────────┤
│ 进度：正在识别第 3/18 页                           36%       │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 结果页面

结果页面至少包含：

- 原始 OCR 文本；
- 纠错稿或脱敏稿；
- 敏感项列表；
- 风险级别、类型、页码、行号、原文片段和处理理由；
- “已屏蔽”“待确认”“无法定位”等状态；
- 点击敏感项跳转到对应文本位置；
- 复制脱敏文本；
- 打开输出文件；
- 打开输出目录；
- 查看任务清单、文件哈希和运行日志；
- 明确显示“需要人工复核”。

### 5.3 状态颜色

- 绿色：关键离线检查通过，可以启动本地处理；
- 黄色：存在需要用户确认的风险，例如网卡仍启用；
- 红色：发现远程 Ollama、云模型、网络路径、同步目录或关键配置缺失，禁止启动敏感材料处理。

## 6 用户操作流程

```text
启动应用
  ↓
自动检查运行环境与离线状态
  ↓
拖入或选择文件
  ↓
校验文件并复制到独立任务工作区
  ↓
计算输入文件 SHA-256
  ↓
选择仅 OCR、总结或敏感审查模式
  ↓
选择自动、CPU 或 GPU
  ↓
启动后台工作流
  ↓
实时显示阶段、页数、进度和日志
  ↓
生成结果并要求人工复核
  ↓
查看输出或打开输出目录
```

## 7 任务工作区规范

每次任务创建独立目录，避免覆盖或交叉污染：

```text
C:\SecureOCR\workspace\
└── 20260918_143025_文件名称\
    ├── input\
    ├── output\
    ├── logs\
    └── task.json
```

`task.json` 至少记录：

```json
{
  "task_id": "20260918_143025_xxxxxxxx",
  "created_at": "2026-09-18T14:30:25+08:00",
  "mode": "secure_redact",
  "device": "gpu:0",
  "model": "qwen3.5:4b",
  "ollama_host": "http://127.0.0.1:11434",
  "input_name": "sample.pdf",
  "input_sha256": "...",
  "security_preflight": "pass",
  "status": "pending_human_review",
  "exit_code": 0
}
```

原始文件名需要清理非法字符，并避免把原始文件名直接拼接进 shell 命令。所有进程调用都应使用参数数组，不得依赖字符串拼接执行命令。

## 8 建议的软件架构

```text
secureocr_desktop\
├── main.py
├── ui\
│   ├── main_window.py
│   ├── workspace_page.py
│   ├── results_page.py
│   ├── history_page.py
│   ├── rules_page.py
│   ├── diagnostics_page.py
│   └── settings_page.py
├── application\
│   ├── task_controller.py
│   ├── task_queue.py
│   ├── process_runner.py
│   └── progress_protocol.py
├── services\
│   ├── environment_service.py
│   ├── hardware_service.py
│   ├── offline_preflight.py
│   ├── workspace_service.py
│   ├── ollama_service.py
│   └── output_service.py
├── adapters\
│   ├── ocr_adapter.py
│   ├── workflow_adapter.py
│   └── secure_redact_adapter.py
├── domain\
│   ├── task.py
│   ├── finding.py
│   └── status.py
├── resources\
├── tests\
└── pyproject.toml
```

设计原则：

- UI 只负责展示和用户操作，不直接写 OCR 或敏感审查逻辑；
- 现有脚本通过适配器封装；
- 后台进程通过 `QProcess` 管理，避免界面阻塞；
- 工作区创建、文件复制、哈希和路径检查集中在服务层；
- 安全预检必须在任务启动前完成；
- 日志输出中避免记录完整敏感正文；
- 所有业务状态使用固定枚举，不依赖界面显示文字判断；
- 任务中断后保留状态和日志，允许人工检查或重新运行。

## 9 首先需要改造的脚本接口

当前脚本已能运行，但为桌面应用提供稳定进度前，需要统一参数和输出协议。建议调用形式：

```powershell
python secure_redact.py `
  --input "任务文件.pdf" `
  --output "任务输出目录" `
  --device "gpu:0" `
  --model "qwen3.5:4b" `
  --progress-json
```

兼容过渡期可以继续接受位置参数，但新接口应提供明确的命名参数。

脚本标准输出采用逐行 JSON 事件，例如：

```json
{"event":"stage_started","stage":"ocr"}
{"event":"progress","stage":"ocr","page":3,"total":18,"percent":16}
{"event":"progress","stage":"llm_review","chunk":2,"total":7,"percent":54}
{"event":"warning","code":"OCR_LOW_CONFIDENCE","message":"第 8 页存在低置信度文本"}
{"event":"finished","status":"pending_human_review","output_dir":"..."}
```

错误输出应包含稳定的错误代码，例如：

- `ENV_PYTHON_NOT_FOUND`；
- `PADDLE_IMPORT_FAILED`；
- `GPU_UNAVAILABLE`；
- `OLLAMA_NOT_RUNNING`；
- `OLLAMA_REMOTE_HOST_BLOCKED`；
- `MODEL_NOT_INSTALLED`；
- `INPUT_UNSUPPORTED`；
- `INPUT_NETWORK_PATH_BLOCKED`；
- `WORKFLOW_FAILED`；
- `OUTPUT_INCOMPLETE`。

App 根据错误代码显示中文解释和可执行的修复建议，不直接把 Python traceback 作为唯一提示。

## 10 离线安全预检

首版运行任务前至少检查：

1. Ollama 地址是否严格为 `127.0.0.1`、`localhost` 或 IPv6 回环地址；
2. 地址中是否存在远程主机名或局域网 IP；
3. 模型名是否带有 `cloud` 标志；
4. 模型是否已经安装在本机；
5. 是否检测到 `OLLAMA_NO_CLOUD=1` 或等效云功能禁用配置；
6. 输入、工作区和输出目录是否为 UNC、映射网络盘或 WebDAV 路径；
7. 路径是否位于常见云同步目录；
8. Python、PaddleOCR、PaddlePaddle 和 Ollama 是否可用；
9. 所选 GPU 是否可以被 PaddlePaddle 实际执行；
10. 输出目录是否具备写入权限和足够空间。

离线状态不能仅根据“互联网是否能访问”判断。即使网卡开启，只要所有处理服务均为本地，也可能处于本地推理状态；但对于高保密要求，应由单位网络隔离、终端管控和审批制度提供更高等级保障。

首版的绿色状态应描述为“本地处理检查通过”，不要描述为“绝对离线”或“绝对安全”。

## 11 CPU 与 GPU 策略

### 11.1 自动选择

启动时运行轻量检查：

- 导入 Paddle；
- 读取版本；
- 检查是否为 CUDA 构建；
- 获取 GPU 数量；
- 对目标 GPU 执行最小张量运算或使用 Paddle 官方检查方法；
- 保存检测结果，不在每个页面重复执行重型检查。

### 11.2 CPU 模式优化

CPU 机器应使用更保守的默认值：

- 优先读取 born-digital PDF 自带文本层；
- 仅对扫描页执行 OCR；
- 默认关闭公式、图表、印章等高成本识别；
- 降低并发和批量大小；
- 在界面显示预计较慢，但功能保持一致。

### 11.3 GPU 模式优化

GPU 可用时：

- OCR 默认使用 `gpu:0`；
- 根据显存动态设置批量大小；
- OCR 与 Ollama 不应无控制地同时占满显存；
- 出现显存不足时尝试降低批量或提示切换 CPU；
- 界面显示实际使用设备，而不是仅显示用户选择值。

## 12 首版功能范围

### 12.1 必须实现

- 原生 Windows 主窗口；
- 单文件和多文件拖拽；
- 文件队列；
- PDF、PNG、JPG、JPEG、MD、TXT 类型校验；
- 自动复制输入到任务工作区；
- 输入文件 SHA-256；
- 仅 OCR、总结、敏感审查三种模式；
- CPU/GPU 自动检测；
- 自动、CPU、GPU 设备选择；
- 本地 Ollama 状态和模型检查；
- 离线安全预检；
- 调用现有三个脚本；
- 实时进度、日志和错误提示；
- 输出文件列表；
- 内置 Markdown/TXT 预览；
- 打开输出文件和目录；
- 最近任务历史；
- 失败任务重新运行；
- 所有敏感审查结果明确要求人工复核。

### 12.2 首版不实现

- 在全新电脑自动安装全部 Python、Paddle、Ollama 和模型；
- 巨型全离线一体化安装包；
- 自动下载大模型；
- Windows 服务化；
- 联网自动更新；
- 多用户和组织级权限系统；
- 电子签名与正式档案系统；
- 自动认定文件可外发；
- 自动删除原始文件；
- 对真实涉密系统的合规认证。

## 13 开发阶段

### 阶段一 内部可运行版

- 建立 PySide6 项目骨架；
- 完成主窗口、拖拽区和任务列表；
- 完成固定 Python 运行时定位；
- 使用 `QProcess` 调用三个现有脚本；
- 显示原始标准输出、错误输出和退出码；
- 建立任务工作区；
- 显示输出文件并打开目录。

### 阶段二 日常可用版

- 统一脚本参数；
- 增加逐行 JSON 进度协议；
- 增加 CPU/GPU 检测；
- 增加 Ollama 和模型检测；
- 实现任务队列、取消、重试和历史记录；
- 增加结果预览和敏感项定位；
- 将错误码转换为用户可理解的修复建议。

### 阶段三 安全增强版

- 增加严格离线预检和阻断；
- 增加网络路径、同步目录和远程 Ollama 检查；
- 增加配置校验、文件哈希和审计日志；
- 限制日志中的敏感正文；
- 增加异常终止和残留文件检查；
- 增加自动化测试和安全回归测试。

### 阶段四 分发版

- 固定依赖版本；
- 先构建 Windows one-folder 应用；
- 验证无系统 Python 的测试机；
- 开发 CPU/GPU 安装检测与引导；
- 生成在线安装器和独立离线安装介质；
- 增加签名、版本记录和受控升级策略。

Paddle、OCR 模型、Qt 动态库和其他依赖体积较大，首个分发版建议采用 one-folder，而不是强行制作单文件 EXE。单文件程序可能需要在运行时解压到临时目录，也不利于大模型、OCR 模型和动态库的维护。

## 14 首版验收标准

首版达到以下条件即可认为完成：

1. 用户双击启动应用，不需要先打开 PowerShell；
2. 用户拖入 PDF 或图片即可创建独立任务；
3. 应用能够自动识别当前机器是否可用 GPU；
4. 无 GPU 时功能仍可运行且 GPU 选项不可用；
5. 应用能在运行前显示本地处理检查状态；
6. 红色安全状态下不能启动敏感审查任务；
7. 三种处理模式均能从界面启动；
8. 处理时界面保持响应，并显示阶段和进度；
9. 任务失败时显示具体原因而非只有 traceback；
10. 任务完成后可预览输出并打开输出目录；
11. 每个任务保存输入哈希、处理模式、设备、模型和状态；
12. 敏感审查输出始终标记为需要人工复核；
13. 不会因为重复文件名覆盖其他任务；
14. 应用不向远程地址发送文件或正文；
15. 日志默认不记录完整敏感文本。

## 15 测试要求

至少准备以下测试样本，禁止使用真实涉密材料参与开发测试：

- born-digital 英文论文 PDF；
- 纯扫描中文 PDF；
- 页面旋转的 PDF；
- 中英文混排图片；
- 手写内容图片；
- 含表格的 PDF；
- 含身份证号、手机号、邮箱和 IP 地址的合成文本；
- 含自定义敏感词的合成文本；
- 明确带有密级标志的合成样本；
- 损坏文件；
- 无写入权限目录；
- UNC 网络路径；
- 模型未安装；
- Ollama 未启动；
- GPU 不可用或显存不足；
- 用户中途取消任务。

测试需覆盖：

- 单元测试；
- 脚本适配器测试；
- 进度协议解析测试；
- 文件路径和工作区测试；
- 安全预检测试；
- CPU/GPU 环境测试；
- 主流程端到端测试；
- 任务中断和恢复测试。

## 16 后续开发开始前的检查清单

- [ ] 将本交接文档复制到新的项目工作区；
- [ ] 将现有三个脚本和配置文件复制到新项目的 `legacy` 或 `backend` 目录；
- [ ] 保留 `C:\SecureOCR` 作为现有可运行基线，不直接在唯一副本上大改；
- [ ] 初始化 Git 仓库；
- [ ] 建立 `.gitignore`，排除 `.venv`、模型、输入文件、输出文件、工作区和日志；
- [ ] 确认不把任何真实敏感文件提交到版本库；
- [ ] 固定 Python 和依赖版本；
- [ ] 先完成环境诊断脚本；
- [ ] 再统一三个后端脚本的参数和 JSON 进度输出；
- [ ] 最后接入 PySide6 界面；
- [ ] 使用合成测试数据验证全流程。

## 17 建议的首个开发任务

在新项目工作区中，第一批代码任务建议是：

1. 创建 PySide6 项目骨架和主窗口；
2. 创建 `EnvironmentService`，识别固定 Python、Paddle、GPU、Ollama 和模型；
3. 创建 `WorkspaceService`，负责安全复制、哈希和任务目录；
4. 创建 `ProcessRunner`，使用 `QProcess` 启动脚本并处理输出；
5. 为 `ocr.py` 增加统一参数和 JSON 进度；
6. 接入“仅 OCR”流程作为第一条端到端链路；
7. 通过后，再接入 `workflow.py` 和 `secure_redact.py`；
8. 最后实现结果预览和敏感项定位。

建议优先完成“拖入一个 PDF，执行仅 OCR，实时显示进度并打开输出目录”的垂直切片。该切片能够验证界面、工作区、进程管理、进度协议、错误处理和输出展示，是后续两种工作流的共同基础。

## 18 项目成功状态

日常用户能够完成以下操作，即达到首版产品目标：

```text
双击应用
→ 查看本地处理检查状态
→ 拖入文件
→ 选择处理模式
→ 点击开始
→ 查看进度
→ 人工复核结果
→ 打开输出目录
```

整个过程中，用户不需要激活虚拟环境、不需要输入命令、不需要编辑文件路径，也不需要理解 Paddle、CUDA、Ollama API 或 Python 参数。
