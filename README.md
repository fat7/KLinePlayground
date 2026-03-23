# A-Share K-Line Trainer (AI & Desktop Edition)

一款专为A股投资者设计的专业级K线复盘与模拟交易训练工具。深度模拟真实交易环境，支持动态复权、多维度技术指标及AI辅助点评，现已推出全功能桌面版。

## 🌟 核心亮点

### 1. PyWebView 桌面版 (`main_pywebview.py`)
告别浏览器限制，基于 `pywebview` 打造的独立桌面应用。更强的性能、更稳定的本地API连接，提供原生软件般的复盘体验。

### 2. AI 介入测试与智能助理 (`ai_assistant_tester.py`)
首创 AI 介入模式。通过独立的 AI 策略测试器，您可以：
- 接入 AI 模型（如 GPT-4）进行实时行情分析。
- 自动化执行买入、卖出及观望操作。
- 零代码测试您的量化逻辑，或与 AI 共同完成实盘模拟。

---

## 🚀 主要功能

- **专业级图表**: 基于 TradingView Lightweight Charts，支持缩放、十字线同步及多维数据展示。
- **自定义 MA 周期**: 支持增删改查最多 6 条均线（如 MA5, MA10, MA20, MA60, MA120, MA250），颜色自动配色。
- **动态复权系统**: 提供“不复权”、“前复权”、“后复权”及独有的“动态前复权”模式，完美模拟历史真实成交点。
- **深度交易模拟**: 严格执行 A 股 **T+1** 规则，内置滑点、印花税、佣金计算，还原最真实的盈亏曲线。
- **全能指标库**: 集成 MACD、KDJ、RSI、BOLL 等核心技术指标，支持主附图自由切换。
- **AI 复盘点评**: 训练结束后一键生成 AI 点评，获取深度盘后分析建议。
- **多用户配置**: 支持多账号、自定义起始资金及个性化偏好存储。

---

## 🛠️ 技术架构

- **后端**: Python 3.7+ / Flask / Pandas / AkShare
- **前端**: HTML5 / CSS3 / Vanilla JS / Lightweight Charts
- **桌面壳**: PyWebView
- **AI 集成**: OpenAI API / 本地 API 桥接

---

## 📦 安装与启动

### 环境准备
```bash
pip install -r requirements.txt
```

### 运行程序
1. **桌面客户端 (推荐)**:
   ```bash
   python webview_app/main_pywebview.py
   ```
2. **AI 介入测试器**:
   ```bash
   python ai_assistant_tester.py
   ```
3. **Web 服务版 (CLI模式)**:
   ```bash
   python main_enhanced.py
   ```

---

## 📂 推荐发布文件列表

为了保持项目的整洁与专业，建议在 GitHub 发布时包含以下核心文件（排除临时或未完成的开发文件）：

| 路径 | 说明 |
| :--- | :--- |
| `webview_app/` | 桌面版核心程序入口 |
| `ai_assistant_tester.py` | AI 介入与策略测试工具 |
| `backend/` | 包含 `app_enhanced.py` 等所有核心逻辑 |
| `frontend/` | 包含 `index_enhanced.html` 及其 JS/CSS 资源 |
| `stock_data_em/` | 东方财富/AkShare 数据处理逻辑 |
| `main_enhanced.py` | CLI/Web 模式启动入口 |
| `requirements.txt` | 环境依赖列表 |
| `data/` | (仅保留目录结构或最小化样本数据) |
| `users/` | (仅保留目录结构，不含个人信息) |

---

## 📜 许可证与免责声明

本项目仅供学习和投研交流使用，不构成任何投资建议。如需商用请联系作者。
**投资有风险，入市需谨慎。**
