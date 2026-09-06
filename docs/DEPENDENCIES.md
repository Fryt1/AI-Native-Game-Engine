# Runtime / Host / MCP 依赖总览

**状态：** Living dependency contract
**最后验证：** 2026-09-06
**适用范围：** 本仓库的 Python runtime、UE5、Blender、ComfyUI、Hugging Face、AssetsBridge、MCP 和外部工具

## 先看结论

这个仓库不是一个把所有外部软件打包在一起的桌面应用。它是一个 Agent-driven
WorkflowPlan runtime：仓库拥有 Python 校验、Project Tool 和 Workflow 定义；UE5、
Blender、ComfyUI、MCP Server 和 Agent MCP Client 是外部运行时依赖。

```text
本仓库
  ├─ Python runtime / Workflow / Project Tool
  ├─ UE5/Blender 的脚本执行适配器
  └─ requirements.yaml（声明依赖，不自动安装）

外部宿主/工具
  ├─ Unreal Engine + 目标 .uproject
  ├─ Blender + 需要的 Add-on
  ├─ ComfyUI 工作区 + 模型/custom nodes
  ├─ Hugging Face CLI/MCP（按模型获取和研究 Workflow）
  └─ AssetsBridge 两侧组件（按 Workflow）

Agent 连接层
  ├─ UE5 MCP Server（运行在 UnrealEditor.exe 内）
  ├─ Blender MCP Server（运行在 Blender 内）
  ├─ ComfyUI MCP Server（外置 comfy-mcp 进程）
  ├─ Hugging Face MCP Server（远程 Hub MCP）
  └─ Codex / Agent MCP Client 配置
```

## 依赖分层

| 层 | 负责内容 | 是否由本仓库安装 |
|---|---|---|
| Python runtime | WorkflowPlan、Tool Registry、校验、测试 | 是，`pip install -e .[dev]` |
| UE5 host | Unreal Editor、UE5 Python/命令执行 | 否，用户安装 |
| Blender host | Blender CLI、当前 Blender 上下文和 `bpy` | 否，用户安装 |
| ComfyUI host | ComfyUI 工作区、模型、custom nodes、生成 API | 否，用户安装 |
| Hugging Face CLI | 模型认证、下载、文件校验和落盘 | 否，用户安装 |
| Hugging Face MCP | Hub 资源搜索、模型/文档/数据集研究 | 否，Agent 配置 |
| Host integrations | UE5 MCP、Blender MCP、AssetsBridge | 部分源码 vendored；实际启用仍在宿主内完成 |
| MCP Servers | UE5/Blender/ComfyUI/Hugging Face 的 MCP 接入进程或宿主内 Server | 否，配置/安装在外部环境 |
| Agent MCP Client | 连接 MCP Server 并执行 `McpCall` | 否，配置在 Codex/Agent |

## 版本支持策略

### 核心 Python

```toml
requires-python = ">=3.11"
dev = ["pytest>=8", "ruff>=0.8"]
```

来源：`pyproject.toml`。本仓库的运行时 Python dependencies 当前为空；UE5、Blender、
ComfyUI 和 MCP 不通过本仓库的 Python package 安装。

### Blender / Blender MCP

| 项目 | 要求 |
|---|---|
| Blender | **5.1.0 或更高** |
| Blender MCP Add-on 包 | **1.0.0**（仓库 vendored 版本） |
| 已验证版本 | **Blender 5.2.1 LTS** + vendored Add-on |
| Transport | 本机 TCP socket `localhost:9876` |

Blender MCP Add-on 的版本下限来自：

```text
vendor/mcp/blender/package/blender_manifest.toml

schema_version = "1.0.0"
id = "mcp"
version = "1.0.0"
blender_version_min = "5.1.0"
```

不要因为 AssetsBridge Blender Add-on 说 Blender 4.0+，就把使用 Blender MCP 的
Workflow 降到 Blender 4.x；Blender MCP 的约束是 `>=5.1.0`。

### Unreal Engine / UE5 MCP

| 场景 | 版本策略 | 已验证 |
|---|---|---|
| UE5 Python / Project Tool | 不要求原生 UE MCP；按具体执行器配置 | UE5.7.1 |
| 原生 UE5 MCP | **UE 5.8.0+** | UE 5.8.2 |
| `blender-ue5-asset-roundtrip` 的 UE5 MCP | **UE 5.8.0+** | UE 5.8.2 |

不要因为 Project Tool 在 UE5.7.1 上验证通过，就认为 UE5.7.1 满足原生 UE5 MCP
依赖；这两条路径的版本约束不同。

### ComfyUI MCP

| 项目 | 项目支持基线/策略 | 已验证 |
|---|---|---|
| ComfyUI 工作区 | 必须能启动并提供 HTTP API | ComfyUI v0.30.2 |
| comfy-cli | **>=1.14.0** | 1.18.0 |
| 官方 local MCP | `comfy-mcp`，升级后重新 handshake | 0.10.0 |
| MCP Server Python | **>=3.10** | bundled Python 3.13.11 |
| 默认 ComfyUI API | `http://127.0.0.1:8188` | 当前工作区使用该默认目标 |
| Agent 接入 | `mcp_servers.comfyui`，stdio | Codex 配置已写入 |

ComfyUI 的模型、custom nodes、显存和 workflow 依赖属于具体 Workflow，不作为本仓库
统一 runtime dependency 安装。Hugging Face CLI/MCP 也只在 Workflow 需要模型搜索或
下载时启用。

### Hugging Face CLI / MCP

Hugging Face 在本项目中负责模型研究和模型获取，不负责 ComfyUI workflow 执行：

```text
Hugging Face MCP → 搜索/查看模型、许可证、revision、文件和文档
hf CLI           → gated auth、下载模型文件、落盘和校验
ComfyUI MCP      → 发现本地模型、验证并执行 workflow
```

当前支持基线和本机验证：

```text
hf / huggingface_hub: 1.19.0
HF MCP: https://huggingface.co/mcp?login
Codex MCP status: enabled / OAuth
```

本机 `hf auth login` 仍由用户在自己的终端完成；token 不写入仓库、Workflow 或 Codex
配置。浏览器登录/同意 gated model 条款也不自动等于 CLI 已认证。

### AssetsBridge

完整的 Blender ↔ UE5 round-trip 需要两侧组件和同一个 bridge directory：

```text
vendor/assetsbridge/blender-addon/AssetsBridgeAddon/
vendor/assetsbridge/plugin-source/AssetsBridge/Plugins/AssetsBridge/
```

| 组件 | 作用 |
|---|---|
| AssetsBridge Blender Add-on | Blender 侧导入、修改、导出和资产关系维护 |
| AssetsBridge UE5 Plugin | UE5 侧导出、导入、资产管理和桥接接口 |
| bridge directory | 交换 JSON、glTF 和验证快照 |

只安装 Blender MCP 不能替代 AssetsBridge；只安装 AssetsBridge 也不能提供 Blender MCP
Server。`blender-ue5-asset-roundtrip` 同时依赖 Blender MCP、UE5 MCP 和 AssetsBridge
Project Tools。

## 按场景准备依赖

### 只运行 Python 单元测试

只需要：

```powershell
python -m pip install -e .[dev]
python -m pytest -q
```

不需要启动 UE5、Blender、ComfyUI 或任何 MCP Server，也不需要 Hugging Face 登录。

### 运行 Blender Project Tool / Blender MCP

需要：

1. Blender 可执行文件（5.1.0 或更高）；
2. 对应的 Blender Python 环境；
3. 根据 Toolset 选择 CLI、当前 Add-on 或两者；
4. 若使用 Blender MCP：从 `vendor/mcp/blender/package/` 安装并启用 MCP Add-on，
   在 Blender 内启动 socket bridge server（`localhost:9876`），并配置 Agent MCP
   Client 连接该 bridge；
5. 按 Workflow 要求准备 AssetsBridge Add-on（若使用 round-trip）。

仅安装 Add-on 源码不等于 bridge 已启动；`vendor/mcp/blender/` 只是源码。交互模式在
Blender Add-on 面板启动 bridge；后台模式：

```powershell
E:\blender\blender.exe --background <file.blend> --command blender_mcp
```

注意：当前 vendored 版本不支持 Streamable HTTP MCP transport，使用本机 TCP socket；
Agent MCP Client 需要能连接该 socket 的适配器。

### 运行 UE5 Project Tool / UE5 MCP

需要：

1. Unreal Engine 5.8.0+ 和目标 `.uproject`（含 `ModelContextProtocol` 插件启用；
   需要完整 Toolset 时启用 `AllToolsets`）；
2. `UnrealEditor.exe` 或 `UnrealEditor-Cmd.exe`（5.8.0+）；
3. 按执行器要求加载项目插件和 Python 支持；
4. 若使用原生 UE5 MCP：正在运行的 UnrealEditor.exe 提供 HTTP Server
   `http://127.0.0.1:8000/mcp`，Agent 配置 `mcp_servers.unreal-mcp`。

UE5 MCP 不是 Python 依赖，也不是把 MCP Tool 列表复制进仓库就算安装完成。仓库根目录
没有 `.uproject`，`projects/fixtures/ue5/` 是 fixture，不等于 live MCP Editor。

### 运行 Hugging Face CLI / MCP

需要：

```text
Hub 研究       → hf-mcp-server enabled / OAuth
本地模型下载   → hf CLI + 已验证邮箱 + gated 访问 + Read token
下载落盘       → 目标模型目录和哈希证据
```

Hugging Face MCP 是远程 `McpCall`（streamable HTTP）；`hf` CLI 是本地外部命令。不要把
CLI token 放进 `requirements.yaml` 或仓库配置。

### 运行 ComfyUI MCP

需要同时满足：

```text
ComfyUI 工作区存在
  → models/custom_nodes 满足目标 Workflow
  → comfy-cli >= 1.14.0
  → comfy-mcp 能被 Agent MCP Client 启动
  → ComfyUI API 正在监听目标端口
  → MCP initialize/tools/list 成功
```

ComfyUI MCP 是外置 stdio Server；它不是 ComfyUI 内置插件，也不进入 Project Tool
Registry。当前采用的官方 local Server 通过 `comfy-cli` 驱动 ComfyUI。

### 运行 Blender ↔ UE5 MCP round-trip

需要同时满足：

```text
Python >= 3.11
Blender MCP Add-on >= 5.1.0
Unreal Engine >= 5.8.0
UE5 ModelContextProtocol enabled
Blender/UE5 AssetsBridge components
Agent MCP Client configured for Blender and UE5
shared bridge directory
```

### 运行"生成外部素材 → 应用到 Blender/UE5"工作流

需要：

```text
artifact_pipeline Route
  → 生成步骤使用普通 Project Tool 或 ComfyUI/其他 MCP Server 的 McpCall
  → Artifact Contract / 文件引用可读
  → Blender/UE5 apply Tool 或 McpCall
  → host-side read-back validation
```

这里的 `artifact_pipeline` 是 Route/Workflow 能力，不是新的 Tool 类型，也不要求
一个独立的 Artifact Provider Registry。

## 标准安装与验证流程

### Blender MCP

1. **确认 Blender 版本**：确认 `blender.exe` 为 5.1.0 或更高；本项目优先使用
   Blender 5.2.x LTS。
2. **安装 Add-on**：在 Blender 中从 `vendor/mcp/blender/package/` 安装 MCP Add-on。
3. **启用 Add-on**：启用名为 MCP 的 Add-on，并允许本地网络访问。
4. **启动 bridge server**：交互模式在 Blender Add-on 面板启动；后台模式使用
   `--command blender_mcp`。
5. **配置 Agent MCP Client**：为 `blender` server 配置可连接 9876 bridge 的客户端。
6. **做 live 验证**：确认端口可连接，并完成一次真实 Blender MCP 调用（例如
   `execute_blender_code` 读取场景信息）。

### UE5 MCP

1. **先确认引擎版本**：确认 `UnrealEditor.exe` 为 5.8.0 或更高；本项目优先使用 5.8.2。
2. **确认插件存在**：检查 `Engine/Plugins/Experimental/ModelContextProtocol/`。
3. **打开目标 UE 项目的 Plugins**：启用 `Model Context Protocol`；需要完整工具时再启用
   `All Toolsets`。
4. **重启 Unreal Editor**：插件启用、模块加载或引擎版本切换后不要复用旧进程。
5. **配置 Project Settings**：设置 MCP Server 的 URL path、端口和自动启动。
6. **配置 Agent MCP Client**：写入 `unreal-mcp` 的 HTTP URL。
7. **做 live 验证**：确认端口监听，并让 MCP Client 完成 `initialize`、`tools/list`；
   Tool Search 模式下，`tools/list` 只出现 `list_toolsets`、`describe_toolset`、
   `call_tool` 三个元工具是正常现象。

### ComfyUI MCP

1. **确认工作区**：确认目标目录包含 `main.py`、`models/`、`custom_nodes/`、
   `input/` 和 `output/`。
2. **确认 comfy-cli**：执行 `comfy --version`；项目支持基线为 `>=1.14.0`。
3. **确认工作区选择**：执行 `comfy --json which`，确认 workspace 指向目标 ComfyUI。
4. **启动 ComfyUI**：使用发行版启动器或 `comfy launch`，确认 API 监听目标端口。
5. **确认 MCP Server**：执行 `comfy-mcp` 所在环境的启动检查；不要仅以进程存在判断
   ComfyUI 可用。
6. **配置 Agent MCP Client**：写入 `mcp_servers.comfyui`，绝对路径指向 `comfy-mcp`，
   并在需要时通过 `COMFY_BIN` 指向同一环境的 `comfy`。
7. **重载 Codex**：重启/重载配置，让 `comfyui` Server 出现在 MCP Server 列表。
8. **完成 MCP live handshake**：Agent MCP Client 执行 `initialize` 和 `tools/list`。
9. **完成 ComfyUI live 验证**：调用 `server_info`/`system_stats`，读取节点和模型，
   再运行一个最小 workflow，并确认 output 文件可读。
10. **写入 Workflow 证据**：记录 ComfyUI 版本、MCP Server 版本、目标地址、workflow、
    模型/节点和输出文件；不要把凭据提交到仓库。

### Hugging Face CLI / MCP

1. **浏览器确认账号**：邮箱已验证，资源条款已接受；
2. **确认 CLI**：`hf --version`、`hf auth whoami`；
3. **配置 CLI 认证**：必要时运行 `hf auth login`，不把 token 发给 Agent 或提交仓库；
4. **下载前 dry-run**：确认 repo、revision、文件名和大小；
5. **下载并校验**：写入 ComfyUI/目标宿主的正确模型目录；
6. **确认 HF MCP**：Codex `mcp list` 显示 `hf-mcp-server` enabled/OAuth；
7. **MCP discovery**：读取 `hf_fs` 或其他当前可用工具 schema；
8. **回到 ComfyUI MCP**：发现本地模型和节点，验证 workflow；
9. **记录证据**：模型 id、revision、license、文件路径、哈希、Workflow 和输出。

## 常见失败与判断

| 现象 | 优先检查 |
|---|---|
| 找不到 Blender MCP Add-on | Blender 版本、Add-on 是否实际安装/启用 |
| Blender Add-on 启用但连接被拒绝 | bridge server 是否启动、Host/Port 是否为 localhost:9876 |
| Blender 后台模式启动失败 | Blender 是否允许 `--command blender_mcp`、是否启用 Add-on |
| Agent 无法调用 `blender` server | Agent MCP Client 配置、客户端与 socket bridge 的适配 |
| 找不到 `ModelContextProtocol.uplugin` | 引擎版本、引擎根目录、是否误用了 UE 5.7 或更早版本 |
| UE 能打开但 MCP 连接被拒绝 | Editor 是否仍在运行、端口是否为 8000、是否启动了正确的项目 |
| UE `tools/list` 只有三个工具 | 检查是否启用了 Tool Search；这是 Tool Search 模式的正常返回 |
| `comfy-mcp` 能 handshake，但 `server_info` 失败 | ComfyUI 是否运行、目标端口、`COMFY_LOCAL_URL` 是否正确 |
| `comfy` 找不到 | `COMFY_BIN` 是否是 MCP 客户端环境可读的绝对路径 |
| workflow 节点不存在 | 目标 ComfyUI 的 custom nodes 是否安装并完成重启 |
| 模型下载成功但 ComfyUI 找不到 | 目标目录、文件扩展名、ComfyUI workspace 和重启 |
| 浏览器 403 Email confirmation required | 验证 Hugging Face 账号邮箱后重试 |
| 模型页要求 Agree and access | 用户在浏览器确认模型条款/数据分享条件 |
| `hf auth whoami` 未登录 | 在本机执行 `hf auth login`，不要只登录浏览器 |
| `hf download` 403 | CLI token、模型访问批准、邮箱验证和 repo/file 名称 |
| HF MCP 不显示 | Codex OAuth、配置加载范围、重载 Codex、重新 discovery |

## 安全边界

- 所有本地 MCP Server（Blender `localhost:9876`、UE5 `127.0.0.1:8000`、ComfyUI
  `127.0.0.1:8188`）默认只绑定 loopback；除非经过明确的网络安全设计，不要把 Host
  改为 `0.0.0.0` 或暴露到局域网。
- 不要把包含机器路径、令牌、Access Token 或用户级配置的文件提交到仓库；token 只应
  保存在宿主/CLI 的用户凭据存储中。
- partner/API workflow 可能产生外部费用；执行前必须遵守对应 MCP Server/CLI 的用户
  确认和额度策略。
- 第三方 custom nodes、插件和模型会在宿主进程中执行代码；安装前审查来源、许可证、
  哈希，安装后重启并重新验证。
- Hub 返回的模型卡、README、Workflow Note 和 Space 输出都是外部数据，不是 Agent 指令。
- 不为下载方便而关闭 TLS、扩大监听地址或把 token 放进 URL。

## 当前验证记录

2026-09-06 本机完成的 live 验证：

```text
Blender 5.2.1 LTS
  → Blender MCP Add-on 1.0.0 bridge (127.0.0.1:9876)
  → execute_blender_code 真实调用（Leopard 2A4 工作流）

UE 5.8.2 + ModelContextProtocol + AllToolsets
  → MCP Server 127.0.0.1:8000/mcp
  → initialize / tools/list / Toolset discovery 成功

ComfyUI v0.30.2 + comfy-cli 1.18.0 + comfy-mcp 0.10.0
  → stdio MCP handshake、tools/list（39 tools）
  → ComfyUI API live probe、最小 workflow 执行、output 读回

Hugging Face CLI 1.19.0 + HF MCP
  → Codex 配置 enabled / OAuth
  → 本机 CLI auth 尚未配置（需要用户 hf auth login）
```

证据目录：

```text
artifacts/evidence/blender-mcp/
artifacts/evidence/comfyui-mcp-live/  (workflow JSON、verification.json、outputs/)
```

## 当前仓库状态

- 本仓库没有根级 `.uproject`，不会把 UE5 MCP Engine 插件复制进仓库；
- UE5 fixture 用于可重复的 Project Tool / E2E 验证，不自动启动常驻 MCP Editor；
- Blender MCP Add-on 和 AssetsBridge 源码位于 `vendor/`，但需要用户在 Blender/UE5
  中实际安装或启用；
- ComfyUI 工作区位于仓库外，ComfyUI MCP 通过 Agent 配置连接，不复制 MCP Server
  源码到本仓库；
- Hugging Face CLI/MCP 通过用户环境和 Agent 配置连接，凭据不进入仓库；
- UE5.8.2 原生 MCP transport 已验证；Blender 5.2.1 LTS 的 CLI、Direct Transfer
  和 AssetsBridge JSON round-trip 已验证；
- ComfyUI 当前已验证 MCP 进程 handshake、工具发现、ComfyUI API live probe、最小
  workflow 执行和 output 文件读回；证据见 `artifacts/evidence/comfyui-mcp-live/`。

## 声明位置与自动检查边界

- `pyproject.toml`：Python runtime 和开发依赖；
- `workflows/*/requirements.yaml`：每个 Workflow 的声明性依赖；
- `vendor/mcp/blender/package/blender_manifest.toml`：Blender MCP Add-on 的版本下限；
- `vendor/assetsbridge/`：AssetsBridge 两侧依赖源码；
- Agent 配置：Codex/Agent MCP Client 的 `mcp_servers` 配置，不属于 Python package。

当前 Workflow validator 只验证 Workflow 文件结构和声明存在性，不会自动安装宿主、
模型、custom nodes、MCP Server，也不会自动完成 MCP handshake。`requirements.yaml`
中的版本号是前置条件声明，不是运行时证明。需要硬阻断时必须运行额外的 preflight：

```text
检查 Python 版本
  → 检查 Blender / UnrealEditor / ComfyUI / Hugging Face CLI 版本
  → 检查插件、Add-on 或 MCP Server 文件
  → 检查目标项目/工作区启用状态
  → 检查 Agent MCP 配置（ComfyUI / UE5 / Blender / Hugging Face）
  → 完成 MCP initialize / tools discovery
  → 完成宿主 API live probe
```

## 相关文档

- `README.md`：仓库安装入口和边界说明；
- `projects/fixtures/ue5/README.md`：UE5 fixture 与 live MCP 的边界；
- `vendor/assetsbridge/README.md`：AssetsBridge 依赖源码说明；
- `workflows/blender-ue5-asset-roundtrip/requirements.yaml`：Blender ↔ UE5 round-trip 声明；
- `workflows/blender-mcp-tank-separated/requirements.yaml`：Blender MCP 版本声明。
