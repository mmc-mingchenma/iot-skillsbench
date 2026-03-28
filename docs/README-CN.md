<div align="center">

# 面向嵌入式与物联网系统开发的技能化 AI 智能体

[![Paper](https://img.shields.io/badge/Paper-ArXiv-red.svg)](https://arxiv.org/abs/2603.19583)
[![License](https://img.shields.io/badge/license-Apache%202-blue)](../LICENSE)

论文官方代码仓库：**"[Skilled AI Agents for Embedded and IoT Systems Development](https://arxiv.org/abs/2603.19583)"**。

🌐 语言： [English](../README.md) | **简体中文**

</div>

> **快速了解**
> - 一个可在真实硬件上“一次生成”嵌入式/物联网系统代码与应用的 AI 智能体。
> - 一个用于系统评估并比较不同 *skills* 等级智能体性能的 IoT-SkillsBench 基准。

## 📚 目录

- [✨ 亮点](#highlights)
  - [🧪 演示环境 #1：Arduino Mega 2560 + Arduino](#demo-setup-1)
  - [🧪 演示环境 #2：ESP32-S3 + ESP-IDF](#demo-setup-2)
- [🧰 开发板、框架与外设](#boards-frameworks-peripherals)
- [🗂️ 仓库结构](#repository-structure)
- [⚙️ 安装](#installation)
- [🚀 快速开始](#quick-start)
- [🛠️ 配置](#configuration)
- [📊 评测](#evaluation)
- [📚 引用](#citation)
- [💬 联系我们](#contact)

## 📌 概述

大语言模型（LLM）与智能体系统在自动化软件开发方面展现出巨大潜力。然而，在硬件在环（HIL）的嵌入式与物联网场景中，由于软件逻辑、时序约束与物理硬件行为之间高度耦合，这一问题仍然非常困难。代码“能编译”并不意味着“能在真实设备上稳定运行”。为此，我们提出了一个**面向嵌入式与物联网系统开发的技能化 AI 智能体框架**，以及完整的 **IoT-SkillsBench**。

<p align="center">
  <img src="assets/system-overview.png" alt="System Overview" width="75%" />
</p>

<a id="highlights"></a>

### ✨ 亮点

- **技能化智能体框架** —— 通过结构化、领域化知识注入，提升 LLM 智能体在嵌入式与物联网任务中的可靠性。
- **IoT-SkillsBench** —— 面向真实嵌入式编程场景的综合基准，覆盖 3 类平台、23 种外设、42 个任务与 3 个难度等级。
- **378 次硬件在环（HIL）实验** —— 每个任务均在三种智能体配置下（无技能、LLM 生成技能、人类专家技能）于真实硬件验证，结果表明人类专家技能可在无需检索或超长上下文推理的情况下实现近乎完美的成功率。

<a id="demo-setup-1"></a>

### 🧪 演示环境 #1：Arduino Mega 2560 + Arduino

💡 你可以参考下方连线图，并结合[外设清单](atmega2560-arduino-wiring.md)自由组合硬件，设计你自己的任务：

<p align="center">
  <img src="assets/atmega2560-arduino-wiring-15-peripherals-annotated.png" alt="Demo Mega2560 Combined" width="75%" />
</p>

示例任务 #1：
```
Set RTC to Mar. 3, 2025 at 14:53:28. 
Then, start collecting MPU6050 measurements every second.
Display the MPU6050 results and date/time on LCD1602 every second.
Also print results to Serial.
```

https://github.com/user-attachments/assets/ca4bb3ee-8449-4271-9f20-643701d79142

示例任务 #2：
```
Each time the push button is pressed, capture a measurement from the MPU6050 unit,
and display it on the LCD1602.
Also print the measurement to Serial.
```

https://github.com/user-attachments/assets/3c797eb3-16f1-48ed-b92d-458cca80204c

示例任务 #3：
```
Use the joystick to control the laser emitter and passive buzzer.
The joystick's x-axis controls the on/off of the laser emitter.
The joystick's y-axis controls the passive buzzer's tone at intervals of 100 Hz.
```

https://github.com/user-attachments/assets/85ade37b-2ef3-458b-83ae-494acf218387

示例任务 #4：
```
Use the ultrasonic distance sensor to measure distance every second.
If the distance is smaller than 1 meter, turn on the laser emitter and passive buzzer.
Set the passive buzzer tone frequency to be proportional to the measured distance.
If the distance is greater than 1 meter, turn off the laser emitter and passive buzzer.
```

https://github.com/user-attachments/assets/49abbc48-8237-4314-81ee-2237478c74d6

<a id="demo-setup-2"></a>

### 🧪 演示环境 #2：ESP32-S3 + ESP-IDF

示例任务：
```
Task: "Write the program that will read the password input from the 16-key keypad (password is set to "1234").
If the keypad input matches the password, the program will connect the relay to unlock the safebox.
The program will also display the input password on the LCD1602 display in the format.
```

![Demo ESP-IDF Safebox](assets/demo-esp-idf-safebox.webp)

<a id="boards-frameworks-peripherals"></a>

### 🧰 开发板、框架与外设

完整的支持矩阵（开发板、框架与外设覆盖）见：

- [boards-peripherals.md](boards-peripherals.md)

该文档可帮助你快速选择兼容的硬件组合来构建新任务。

---

## 🗂️ 仓库结构

```
.
├── docs/                         # 文档与资源
│   ├── assets
│   └── ...
├── scripts/
│   ├── batch_run.py              # 批量任务执行
│   ├── auto_test.py              # 自动编译重试（仅 Arduino）
│   └── run_task_single.py        # 单任务运行
├── skills-human-expert/          # 人类专家技能
├── skills-llm-generated/         # LLM 生成技能
├── src/                          # 智能体框架（如 LangGraph）
│   ├── ...
│   └── ...
├── tasks/                        # 按板卡/框架组织的任务定义
│   ├── level1/
│   ├── level2/
│   ├── level3/
│   └── single/
│       └── tmp_task.txt          # 单任务测试示例
├── output/                       # 运行时生成代码与元数据
├── config.template.yaml          # 配置模板（复制为 config.yaml）
├── config.yaml                   # 本地配置 —— 请勿提交
└── .env                          # 本地 API Key —— 请勿提交
```

---

## ⚙️ 安装

**前置要求：** Python 3.9+

1. **克隆仓库：**

```bash
git clone https://github.com/YOUR_ORG/YOUR_REPO.git
cd YOUR_REPO
```

2. **安装依赖：**

```bash
pip install -r requirements.txt
```

核心依赖包括 LangChain、LangGraph 以及对应的模型服务 SDK，详见 `requirements.txt`。

3. **配置 API Key：**

在项目根目录创建 `.env`：

```dotenv
OPENROUTER_API_KEY=your_key_here
```

该文件已在 `.gitignore` 中声明，避免提交。

4. **创建本地配置：**

```bash
cp config.template.yaml config.yaml
```

根据你的环境修改 `config.yaml`。模板中包含全部可用参数与默认值（见下方配置章节）。

若进行硬件在环评测，还需安装对应开发板工具链（见“评测”章节）。

---

## 🚀 快速开始

完成[安装](#installation)后，可按以下方式运行：

### 单任务运行（`tasks/single/tmp_task.txt`）

```bash
python scripts/run_task_single.py -o scripts/tmp_output
```

### 批量运行（基准任务文件 + 指定任务 ID）

```bash
python scripts/batch_run.py -i tasks/level3/level3-ATmega2560-Arduino.txt -t Safe_Box_with_display
```

输出路径：
```
output/tasks-{board}-{framework}/w_skills_{skills_dir}/{model.name}/{task_id}/
```

---

## 🛠️ 配置

所有设置通过 `config.yaml` 管理（由 `config.template.yaml` 复制得到）。

### 🧩 Skills

```yaml
graph:
  use_skills: true
  skills_dir: skills-human-expert/   # 或 skills-llm-generated/
  auto_pin_mapping: true             # 仅 Arduino；当任务未指定引脚时自动使用默认映射
```

### 🧠 图配置项

| Key | Type | 说明 |
|---|---|---|
| `use_skills` | `bool` | 是否启用技能注入。 |
| `skills_dir` | `str` | 技能目录（`skills-human-expert` 或 `skills-llm-generated`）。 |
| `auto_pin_mapping` | `bool` | 若为 `true`，Arduino 任务缺少引脚时启用 `pin_mapper` 回退映射。 |

### 🧱 开发板与框架

```yaml
input:
  board: esp32_s3_box_3
  framework: ESP-IDF
```

支持组合：

| Board                  | Framework |
|------------------------|-----------|
| `esp32_s3_box_3`       | ESP-IDF   |
| `arduino_mega_2560`    | Arduino   |
| `arduino_nano_33_ble`  | Zephyr    |

### 🤖 模型

```yaml
model:
  name: "claude-sonnet-4-5"
```

### 📦 运行产物

每次运行会生成：

- 任务输出目录下的源代码文件
- `manifest.lock.json`（产物清单）
- `metadata.json`（任务/配置/Token 统计）
- `debug.json`（节点级调试日志）

---

## 📊 评测

### 🔌 构建与烧录

代码生成后，请使用对应平台原生工具链进行编译与烧录：

- **ESP-IDF** — [ESP-IDF Get Started](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
- **Arduino** — [Arduino CLI Documentation](https://arduino.github.io/arduino-cli/latest/)
- **Zephyr** — [Zephyr Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html)

以 macOS 上 Arduino Mega 为例：

```bash
# 编译并上传
arduino-cli compile --upload --port /dev/cu.usbmodemxxxx --fqbn arduino:avr:mega ./

# 打开串口监视器
arduino-cli monitor -p /dev/cu.usbmodemxxxx --config 115200
```

Arduino 目标也可使用自动编译重试脚本：`scripts/auto_test.py`。

### 🧮 Token 统计

每次运行会在输出目录生成 `metadata.json`，其中包含按节点与总量统计的 token 使用信息。

```json
{
  "token_usage": {
    "per_node": [
      {"node": "manager", "usage": {"input_tokens": 512,  "output_tokens": 89,   "total_tokens": 601}},
      {"node": "coder",   "usage": {"input_tokens": 2048, "output_tokens": 1500, "total_tokens": 3548}}
    ],
    "total_input_tokens": 2560,
    "total_output_tokens": 1589,
    "total_tokens": 4149
  }
}
```

Token 跟踪基于 LangChain Core 的 [`AIMessage`](https://reference.langchain.com/python/langchain-core/messages/ai/AIMessage)。

---

## 📚 引用

如果本仓库或基准对你的研究有帮助，请引用：

```bibtex
@article{li2026skilledaiagentsembedded,
      title={Skilled AI Agents for Embedded and IoT Systems Development}, 
      author={Li, Yiming and Cheng, Yuhan and Ma, Mingchen and Zou, Yihang and Yang, Ningyuan and Cheng, Wei and Li, Hai "Helen" and Chen, Yiran and Chen, Tingjun},
      journal={arXiv preprint arXiv:2603.19583},
      year={2026}
}
```

---

## 📄 许可证

本项目采用 [Apache 2.0 License](../LICENSE)。

---

## 💬 联系我们

欢迎反馈、协作与贡献：

- 💬 在 Issues 中提交问题或需求
