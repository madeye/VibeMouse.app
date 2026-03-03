# VibeMouse

面向 macOS VibeCoding 的鼠标侧键语音输入工具。

English README: [`README.md`](./README.md)

## 这个项目解决什么问题

VibeMouse 把高频语音工作流绑定到 macOS 鼠标侧键：
- 前侧键：开始 / 结束录音
- 空闲态按后侧键：发送 Enter
- 录音态按后侧键：停止录音并把转写发送到 OpenClaw

核心目标是低摩擦、可日常稳定使用，并且每个环节失败时都有回退路径。

## 运行架构

整体是事件驱动，按职责拆分：

1. `vibemouse/main.py`
   - CLI 入口（`run` / `doctor`）
2. `vibemouse/app.py`
   - 编排按钮事件、录音状态、转写线程和输出路由
3. `vibemouse/mouse_listener.py`
   - 通过 NSEvent 全局监听器（Quartz/AppKit）捕获侧键与手势
4. `vibemouse/audio.py`
   - 通过 sounddevice 录音并写入临时 WAV
5. `vibemouse/transcriber.py`
   - SenseVoice ASR 后端选择与识别（默认 ONNX，可选 PyTorch）
6. `vibemouse/output.py`
   - 输入 / 剪贴板 / OpenClaw 路由与失败回退
7. `vibemouse/system_integration.py`
   - macOS 平台集成：Quartz CGEvent API、AppKit NSWorkspace、ApplicationServices 无障碍访问
8. `vibemouse/doctor.py`
   - 内置自检（环境、OpenClaw、辅助功能权限、音频输入）

## 快速开始

### 系统要求

- macOS 13+（Ventura 或更高）
- Python 3.10+
- 在系统设置 > 隐私与安全 > 辅助功能中为终端授权

### 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

默认安装走 ONNX 优先，部署体积更小。

可选后端：
- PyTorch/FunASR（支持 GPU）：`pip install -e ".[pt]"`
- Intel NPU/OpenVINO：`pip install -e ".[npu]"`

### 运行

```bash
vibemouse
```

## 默认映射与状态逻辑

- `VIBEMOUSE_FRONT_BUTTON` 默认：`x1`
- `VIBEMOUSE_REAR_BUTTON` 默认：`x2`

状态矩阵：
- 空闲 + 后侧键 -> Enter（由 `VIBEMOUSE_ENTER_MODE` 控制）
- 录音中 + 后侧键 -> 停止录音 + OpenClaw 路由

如果鼠标物理定义相反：

```bash
export VIBEMOUSE_FRONT_BUTTON=x2
export VIBEMOUSE_REAR_BUTTON=x1
```

## OpenClaw 集成

OpenClaw 路由可配置：
- `VIBEMOUSE_OPENCLAW_COMMAND`（默认 `openclaw`）
- `VIBEMOUSE_OPENCLAW_AGENT`（默认 `main`）
- `VIBEMOUSE_OPENCLAW_TIMEOUT_S`（默认 `20.0`）
- `VIBEMOUSE_OPENCLAW_RETRIES`（默认 `0`）

调度行为：
- 快速非阻塞派发，避免阻塞交互
- 返回路由原因（如 `dispatched`、`dispatched_after_retry_*`、`spawn_error:*`）
- 命令无效或拉起失败时自动回退到剪贴板

部署提示：如果你用自己的本地 AI 助手体系，把
`VIBEMOUSE_OPENCLAW_AGENT` 改成你自己的助手 ID。

## 内置自检 Doctor

运行：

```bash
vibemouse doctor
```

先执行安全自动修复再复检：

```bash
vibemouse doctor --fix
```

当前检查项：
- 配置加载是否有效
- OpenClaw 命令是否可执行 + agent 是否存在
- 麦克风输入设备可用性
- macOS 辅助功能权限状态
- pyobjc 框架可用性

只要存在 `FAIL`，命令退出码就是非零，方便自动化检测。

## 配置项

| 变量 | 默认值 | 作用 |
|---|---|---|
| `VIBEMOUSE_ENTER_MODE` | `enter` | 后侧键提交模式（`enter`、`ctrl_enter`、`shift_enter`、`none`） |
| `VIBEMOUSE_AUTO_PASTE` | `false` | 回退到剪贴板后是否自动粘贴 |
| `VIBEMOUSE_GESTURES_ENABLED` | `false` | 是否启用手势识别 |
| `VIBEMOUSE_GESTURE_TRIGGER_BUTTON` | `rear` | 手势触发键（`front`、`rear`、`right`） |
| `VIBEMOUSE_GESTURE_THRESHOLD_PX` | `120` | 手势识别阈值 |
| `VIBEMOUSE_PREWARM_ON_START` | `true` | 启动预热，降低首次识别延迟 |
| `VIBEMOUSE_PREWARM_DELAY_S` | `0.0` | 启动后延迟执行 ASR 预热，改善初始响应速度 |
| `VIBEMOUSE_STATUS_FILE` | `$TMPDIR/vibemouse-status.json` | 运行状态文件（状态栏读取） |

完整配置以 `vibemouse/config.py` 为准。

## 故障排查

### 侧键监听不到

在系统设置 > 隐私与安全 > 辅助功能中为终端应用授权，然后重启终端。

### OpenClaw 路由异常

```bash
openclaw agent --agent main --message "ping" --json
vibemouse doctor
```

### 无音频输入

检查麦克风是否可用且未静音。运行 `vibemouse doctor` 验证输入设备检测。

## License

项目源码采用 Apache-2.0，详见 `LICENSE`。

第三方依赖与模型资产声明见 `THIRD_PARTY_NOTICES.md`。
