# VibeMouse

面向 macOS VibeCoding 的鼠标侧键语音输入工具。

English README: [`README.md`](./README.md)

## 这个项目解决什么问题

VibeMouse 把高频语音工作流绑定到 macOS 鼠标侧键：
- 前侧键：开始 / 结束录音
- 空闲态按后侧键：发送 Enter
- 录音态按后侧键：停止录音并转写

核心目标是低摩擦、可日常稳定使用，并且每个环节失败时都有回退路径。

## 运行架构

整体是事件驱动，按职责拆分：

1. `vibemouse/app.py`
   - 编排按钮事件、录音状态、转写线程和输出路由
3. `vibemouse/mouse_listener.py`
   - 通过 NSEvent 全局监听器（Quartz/AppKit）捕获侧键与手势
4. `vibemouse/audio.py`
   - 通过 sounddevice 录音并写入临时 WAV
5. `vibemouse/transcriber.py`
   - SenseVoice ASR 后端选择与识别（默认 ONNX，可选 PyTorch）
6. `vibemouse/output.py`
   - 输入 / 剪贴板路由与失败回退
7. `vibemouse/system_integration.py`
   - macOS 平台集成：Quartz CGEvent API、AppKit NSWorkspace、ApplicationServices 无障碍访问

## 快速开始

### 系统要求

- macOS 13+（Ventura 或更高）
- Python 3.10+
- Xcode 命令行工具（`xcode-select --install`）

### 构建 VibeMouse.app

```bash
git clone https://github.com/anthropics/VibeMouse.app.git
cd VibeMouse.app

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev,download]"

# 下载 SenseVoice ONNX 模型（离线使用）
python scripts/download_model.py

# 使用 PyInstaller 构建 .app
pyinstaller --noconfirm --windowed \
  --name VibeMouse \
  --icon vibemouse/macos/resources/VibeMouse.icns \
  --add-data "vibemouse/models:vibemouse/models" \
  --add-data "vibemouse/macos/resources:vibemouse/macos/resources" \
  --osx-bundle-identifier com.vibemouse.app \
  vibemouse/macos_entry.py
```

构建产物位于 `dist/VibeMouse.app`。

### 安装

```bash
cp -R dist/VibeMouse.app /Applications/
```

### 运行

在 `/Applications` 中双击 **VibeMouse**，或通过命令行：

```bash
open /Applications/VibeMouse.app
```

VibeMouse 以菜单栏附件形式运行（不会出现在 Dock 中）。通过菜单栏图标选择输入设备、切换开机启动或退出。

### 权限

首次启动时，在 **系统设置 > 隐私与安全** 中授权：

- **辅助功能** — 捕获鼠标侧键与键盘合成所需
- **麦克风** — 录音所需

## 默认映射与状态逻辑

- `VIBEMOUSE_FRONT_BUTTON` 默认：`x1`
- `VIBEMOUSE_REAR_BUTTON` 默认：`x2`

状态矩阵：
- 空闲 + 后侧键 -> Enter（由 `VIBEMOUSE_ENTER_MODE` 控制）
- 录音中 + 后侧键 -> 停止录音 + 转写

如果鼠标物理定义相反：

```bash
export VIBEMOUSE_FRONT_BUTTON=x2
export VIBEMOUSE_REAR_BUTTON=x1
```

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

### 无音频输入

检查麦克风是否可用且未静音。

## License

项目源码采用 Apache-2.0，详见 `LICENSE`。

第三方依赖与模型资产声明见 `THIRD_PARTY_NOTICES.md`。
