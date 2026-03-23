<img width="2752" height="1536" alt="Gemini_Generated_Image_l1lx5ol1lx5ol1lx" src="https://github.com/user-attachments/assets/9da63388-b17e-4235-a691-0e15c03c4fd3" />


一款专为A股投资者设计的专业级K线复盘与模拟交易训练工具。深度模拟真实交易环境，支持动态复权、多维度技术指标及AI辅助点评。

## 🌟 核心亮点

### 1. PyWebView 桌面版 (`main_pywebview.py`)
告别浏览器限制，基于 `pywebview` 打造的独立桌面应用。更强的性能、更稳定的本地API连接，提供原生软件般的复盘体验。

### 2. AI 介入测试与智能助理 (`ai_assistant_tester.py`)
首创 AI 介入模式。通过独立的 AI 策略测试器，您可以：
- 接入 AI 模型（如 GPT-4）进行实时行情分析。
- 自动化执行买入、卖出及观望操作。
- 零代码测试您的量化逻辑，或与 AI 共同完成实盘模拟。

---

## 🚀 最新功能

- **AI 智能策略**: 把软件交给AI大模型，让TA来执行你的策略/扮演设定的角色自动进行交易，探索更多策略。
- **AI 复盘点评**: 训练结束后一键生成 AI 点评，获取深度盘后分析建议。
- **专业级图表**: 删掉了大家反馈的MA标签遮挡。
- **自定义 MA 周期**: 支持增删改查最多 6 条均线（如 MA5, MA10, MA20, MA60, MA120, MA250），颜色自动配色。
- **离线数据接入**: 支持使用离线数据，告别网络接口的不稳定。


## ✨ 主要功能
*   **AI 智能策略**: 把软件交给AI大模型，让TA来执行你的策略/扮演设定的角色自动进行交易，探索更多策略。
*   **专业级图表**: 基于 TradingView Lightweight Charts，支持缩放、十字线同步及多维数据展示。
*   **全能指标库**: 集成 MACD、KDJ、RSI、BOLL 等核心技术指标，支持主附图自由切换。
*   **AI 复盘点评**: 训练结束后一键生成 AI 点评，获取深度盘后分析建议。
*   **多用户系统**: 支持创建和切换多个用户，每个用户的训练数据和交易设置都独立保存。
*   **两种训练模式**:
    *   **指定模式**: 用户可以自行选择任意A股代码和起始日期进行训练。
    *   **盲盒模式**: 系统随机抽取一只股票和起始时间，用于无偏见的“盲抽”式训练。
*   **高度仿真的交易环境**:
    *   **动态复权**: 支持不复权、前复权、后复权和**动态前复权**，确保价格的连续性和真实性。
    *   **成本计算**: 精确模拟交易佣金（可设置费率和最低佣金）和印花税。
    *   **T+1 规则**: 模拟A股市场的T+1交易制度，当日买入的股票次日才能卖出。
*   **丰富的图表与指标**:
    *   **专业K线图**: 使用 `Lightweight Charts` 渲染，性能优异，交互流畅。
    *   **技术指标**: 内置 `MACD`, `KDJ`, `RSI`, `BOLL` 等常用技术指标，并可在图表上动态切换。
    *   **自定义 MA 周期**: 支持增删改查最多 6 条均线（如 MA5, MA10, MA20, MA60, MA120, MA250），颜色自动配色。
    *   **交易标记**: 买卖点会在K线上自动标记，方便复盘。
*   **完善的复盘与统计**:
    *   **实时账户更新**: 总资产、可用资金、持仓市值、浮动盈亏等信息实时更新。
    *   **详细复盘报告**: 每局训练结束后，自动生成包含总收益率、交易明细、胜率等关键指标的复盘报告。
    *   **用户数据统计**: 自动追踪和展示用户的累计收益、总训练次数、局胜率等长期表现数据。
*   **高效的交互体验**:
    *   **回放控制**: 支持手动“下一根K线”或设置不同速度的自动播放。
    *   **键盘快捷键**: 支持使用 `B/S`、`空格`、`数字键` 等快捷键进行快速买卖和播放控制。
    *   **跨平台桌面应用**: 基于 `PyWebView`，可打包成Windows、macOS或Linux原生桌面应用，无需浏览器。


这是一个基于 `PyWebView`、`Flask` 和 `Lightweight Charts` 构建的A股K线复盘训练桌面应用。它允许用户在真实的历史行情数据上进行模拟交易，以训练和提升自己的盘感、策略和决策能力。

该应用将Python后端（数据处理、交易逻辑）与现代Web前端（图表展示、用户交互）相结合，提供了一个功能丰富、响应迅速的本地化训练环境。
<img width="1375" height="859" alt="962c3469b4bea6fc3656c77b45218887" src="https://github.com/user-attachments/assets/0194ddb6-7d68-4e57-8b4d-8c000ce75d37" />
<img width="2748" height="1658" alt="image" src="https://github.com/user-attachments/assets/aed924c1-0883-431f-8b5e-f1edd7a3d907" />
<img width="1374" height="829" alt="c93a0a8832f5b95dfce83af950b188c4" src="https://github.com/user-attachments/assets/b00db3d4-4a60-490d-a1dc-966be6f6366e" />
<img width="1375" height="859" alt="73288681a0dac09c4f72ff8b2f4ecda1" src="https://github.com/user-attachments/assets/ef25345c-284c-47e7-91c0-dde613922065" />

---

## 🛠️ 技术栈

*   **桌面应用框架**: `PyWebView` - 用于将Web前端打包成原生GUI应用。
*   **后端**: `Flask` - 提供API接口，处理数据请求和交易逻辑。
*   **前端**:
    *   `HTML5` / `CSS3` / `JavaScript (ES6+)`
    *   `Lightweight Charts™` - 用于高性能的金融图表绘制。
*   **数据处理**: `Pandas`, `Numpy` - 用于高效处理和计算K线数据。
*   **数据源**: `Akshare` - 用于获取A股历史行情数据。
*   **数据存储**: `SQLite` - 用于存储每个用户的交易历史、设置和统计数据。
*   **AI 集成**: OpenAI API / 本地 API 桥接
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

| 路径 | 说明 |
| :--- | :--- |
| `webview_app/` | 桌面版核心程序入口 |
| `ai_assistant_tester.py` | AI 介入与策略测试工具 |
| `backend/` | 包含 `app_enhanced.py` 等所有核心逻辑 |
| `frontend/` | 包含 `index_enhanced.html` 及其 JS/CSS 资源 |
| `main_enhanced.py` | CLI/Web 模式启动入口 |
| `requirements.txt` | 环境依赖列表 |


# A股K线复盘训练 - PyWebView桌面版

[![支持与服务](https://img.shields.io/badge/Support%20%26%20Services-联系作者-blue?style=for-the-badge )](https://github.com/fat7/KLinePlayground#%E2%9A%99%EF%B8%8F-%E6%94%AF%E6%8C%81%E4%B8%8E%E6%9C%8D%E5%8A%A1 )


## 📜 开源许可

本项目采用 [MIT License](LICENSE) 开源。

## ⚙️ 支持与服务

本项目是一个开源软件，作者投入了大量时间和精力进行开发和维护。如果您觉得这个项目对您有帮助，可以通过以下方式支持作者：

### 接受赞赏 (Sponsor)

您的支持是作者持续更新和改进项目的最大动力！欢迎通过支付宝或微信扫码赞赏。

| 支付宝 (Alipay) | 微信支付 (WeChat Pay) |
| :---: | :---: |
| <img src="https://github.com/user-attachments/assets/f7fa53b8-cdb1-4a0c-9677-ce5d0c60c1a7" alt="Alipay QR Code" width="180"> | <img src="https://github.com/user-attachments/assets/955c873f-de30-4496-ac16-9f0b3c2c39c8" alt="WeChat Pay QR Code" width="180"> |

### 离线数据包领取&技术讨论
| wx群聊 | 小红书群聊 |
| :---: | :---: |
| ![ea2273f5f0c9d1b3b9d0cce2102aad02](https://github.com/user-attachments/assets/d676a78d-6e3b-4946-b79a-70d0a0eda815) | ![59c98422eb5f24c57a0945caaf0f5470](https://github.com/user-attachments/assets/6ef688bf-e5e3-4cc5-8528-3ab59abfae19)
 |

### 商业服务 (Commercial Services)

除了开源版本外，本人（作者）也可以提供一系列付费的商业服务，以满足个人、团队或企业的深度需求。如果您有以下任何需求，欢迎通过 [GitHub Issues](https://github.com/fat7/KLinePlayground/issues) 或其他联系方式与我取得联系：

*   **技术支持服务**: 为您在使用过程中遇到的问题提供优先级的技术支持和解决方案。
*   **定制化开发**: 根据您的具体需求，对软件进行功能定制、添加新指标、对接特定数据源或API等。
*   **企业内训**: 为您的团队提供关于项目架构、量化交易基础、代码实现等方面的培训。
*   **咨询服务**: 提供与项目相关的技术选型、架构设计、策略实现等方面的专业咨询。
---

## 📜 许可证与免责声明

本项目仅供学习和投研交流使用，不构成任何投资建议。如需商用请联系作者。
**投资有风险，入市需谨慎。**
