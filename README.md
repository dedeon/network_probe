# 🔵 小D网络拨测工具 NetProbe

**一站式 Windows 桌面网络拨测工具，支持 Ping / DNS / HTTP(S) / TCP 长连接四种协议**

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

---

## ✨ 功能特性

- 🏓 **Ping 拨测** — ICMP 探测，采集 RTT、TTL、丢包率
- 🌐 **DNS 拨测** — 域名解析查询，采集解析耗时、IP、RCODE、TTL
- 🔗 **HTTP(S) 拨测** — HTTP 请求探测，采集 DNS/TCP/TLS/TTFB 各阶段耗时
- 💓 **TCP 长连接拨测** — 纯 TCP 保活探测，采集建连 RTT、会话时长、断线/重连事件
- ⚡ **即时拨测** — 手动启停，实时滚动显示结果，成功绿色/失败红色
- ⏱ **长时间拨测** — 设定时长（1~1440 分钟）自动完成，生成统计报告 + 质量评级
- 📊 **统计分析** — 自动计算丢包率、P50/P90/P95/P99、抖动、标准差等指标
- ⭐ **质量评级** — 五级评分（优秀/良好/一般/较差/极差），TCP 长连接有专用评级算法
- 📋 **历史记录** — 每种模式保留最近 3 次记录，支持回看
- 📤 **日志导出** — 一键导出完整拨测数据和统计结果为 TXT 文件
- 📦 **免安装运行** — 单文件 exe（~25 MB），双击即用，无需 Python 环境

---

## 🚀 快速开始

### 直接使用（推荐）

1. 从 [Releases](../../releases) 下载 `小D网络拨测工具.exe`
2. 双击运行，无需安装任何依赖
3. 输入目标地址（格式：`地址:端口`），选择协议，点击开始

### 输入格式示例

```
8.8.8.8:53          # IPv4 + 端口
www.baidu.com:443   # 域名 + 端口
[::1]:80            # IPv6 + 端口
```

### 源码运行

```bash
cd network_probe
pip install -r requirements.txt
python main.py
```

---

## 🔨 构建指南

### 方法一：PowerShell 全自动构建（推荐）

```powershell
cd network_probe
powershell -ExecutionPolicy Bypass -File auto_build.ps1
```

脚本会自动完成：检测/下载 Python 3.11.9 → 安装依赖 → PyInstaller 打包 → 输出 exe。

### 方法二：双击 Bat 构建

双击 `network_probe/auto_build.bat`，等待 3~8 分钟，在 `dist/` 目录找到生成的 exe。

### 方法三：手动构建

```bash
cd network_probe
pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean netprobe_build.spec
```

构建产物：`dist/小D网络拨测工具.exe`（约 25 MB）

---

## 🏗 技术栈

| 技术 | 说明 |
|------|------|
| Python 3.11 | 编程语言 |
| PyQt6 | GUI 框架（Fusion 主题 + 自定义 QSS） |
| dnspython | DNS 查询库 |
| requests | HTTP 客户端库 |
| PyInstaller | 打包为 Windows exe |

---

## 📁 项目结构

```
network_probe/
├── main.py                         # 应用入口
├── requirements.txt                # 依赖清单
├── engines/                        # 拨测引擎层
│   ├── ping_engine.py              #   Ping (ICMP) 引擎
│   ├── dns_engine.py               #   DNS 查询引擎
│   ├── curl_engine.py              #   HTTP(S) 引擎
│   └── tcp_keepalive_engine.py     #   TCP 长连接引擎
├── ui/                             # 用户界面层
│   ├── main_window.py              #   主窗口
│   ├── instant_panel.py            #   即时拨测面板
│   └── longterm_panel.py           #   长时间拨测面板
├── storage/                        # 数据存储层
│   └── manager.py                  #   存储管理器
├── utils/                          # 工具层
│   ├── validators.py               #   输入校验
│   └── statistics.py               #   统计分析 + 质量评级
├── docs/                           # 文档
│   ├── 需求说明书.md
│   └── 开发技术总结.md
├── netprobe_build.spec             # PyInstaller 打包配置
├── auto_build.ps1                  # PowerShell 构建脚本
├── auto_build.bat                  # Bat 构建脚本
└── build.py                        # Python 构建脚本
```

---

## 📊 长时间拨测统计指标

### Ping 统计
发包统计（总数/成功/丢包/丢包率/最大连续丢包）、时延统计（最小/最大/平均/P50/P90/P95/P99）、抖动统计（平均抖动/最大抖动/标准差）

### DNS 统计
查询统计（总数/成功率/超时/SERVFAIL）、时延统计（最小/最大/平均/百分位）、解析结果（IP 变化次数/平均 TTL）

### HTTP(S) 统计
请求统计（总数/成功率/超时/TLS 错误/HTTP 状态码分布）、各阶段平均耗时（DNS/TCP/TLS/TTFB）、总耗时百分位

### TCP 长连接统计
建连统计（成功率/建连 RTT）、会话稳定性（断线次数/平均会话时长）、探活与重连（探活失败率/重连等待时间）

---

## ⭐ 质量评级

**Ping/DNS/Curl** — 基于丢包率、平均 RTT、平均抖动三维度，取最低评级（木桶效应）

**TCP 长连接** — 基于建连成功率、平均会话时长、建连 RTT 三维度，支持服务端固定超时智能检测

| 评级 | 说明 |
|------|------|
| ★★★★★ 优秀 | 网络状况极佳 |
| ★★★★☆ 良好 | 网络状况正常 |
| ★★★☆☆ 一般 | 存在轻微问题 |
| ★★☆☆☆ 较差 | 网络不稳定 |
| ★☆☆☆☆ 极差 | 严重问题 |

---

## 📝 系统要求

- **操作系统**：Windows 10 及以上
- **构建依赖**：Python 3.11+（全自动构建脚本可自动下载）
- **运行依赖**：无（单文件 exe 免安装）

---

## 📄 文档

- [需求说明书](network_probe/docs/需求说明书.md) — 完整的产品功能需求
- [开发技术总结](network_probe/docs/开发技术总结.md) — 架构设计、技术方案、打包经验

---

## 🤝 致谢

本项目使用 [CodeBuddy](https://codebuddy.ai/) AI 辅助开发。
