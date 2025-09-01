
# A股K线复盘训练 - PyWebView桌面版

[![支持与服务](https://img.shields.io/badge/Support%20%26%20Services-联系作者-blue?style=for-the-badge )](https://github.com/fat7/KLinePlayground#%E2%9A%99%EF%B8%8F-%E6%94%AF%E6%8C%81%E4%B8%8E%E6%9C%8D%E5%8A%A1 )


这是一个基于 `PyWebView`、`Flask` 和 `Lightweight Charts` 构建的A股K线复盘训练桌面应用。它允许用户在真实的历史行情数据上进行模拟交易，以训练和提升自己的盘感、策略和决策能力。

该应用将Python后端（数据处理、交易逻辑）与现代Web前端（图表展示、用户交互）相结合，提供了一个功能丰富、响应迅速的本地化训练环境。
<img width="1375" height="859" alt="962c3469b4bea6fc3656c77b45218887" src="https://github.com/user-attachments/assets/0194ddb6-7d68-4e57-8b4d-8c000ce75d37" />
<img width="2748" height="1658" alt="image" src="https://github.com/user-attachments/assets/aed924c1-0883-431f-8b5e-f1edd7a3d907" />
<img width="1374" height="829" alt="c93a0a8832f5b95dfce83af950b188c4" src="https://github.com/user-attachments/assets/b00db3d4-4a60-490d-a1dc-966be6f6366e" />
<img width="1375" height="859" alt="73288681a0dac09c4f72ff8b2f4ecda1" src="https://github.com/user-attachments/assets/ef25345c-284c-47e7-91c0-dde613922065" />

## ✨ 主要功能

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
    *   **均线系统**: 默认提供 5、10、20日移动平均线。
    *   **交易标记**: 买卖点会在K线上自动标记，方便复盘。
*   **完善的复盘与统计**:
    *   **实时账户更新**: 总资产、可用资金、持仓市值、浮动盈亏等信息实时更新。
    *   **详细复盘报告**: 每局训练结束后，自动生成包含总收益率、交易明细、胜率等关键指标的复盘报告。
    *   **用户数据统计**: 自动追踪和展示用户的累计收益、总训练次数、局胜率等长期表现数据。
*   **高效的交互体验**:
    *   **回放控制**: 支持手动“下一根K线”或设置不同速度的自动播放。
    *   **键盘快捷键**: 支持使用 `B/S`、`空格`、`数字键` 等快捷键进行快速买卖和播放控制。
    *   **跨平台桌面应用**: 基于 `PyWebView`，可打包成Windows、macOS或Linux原生桌面应用，无需浏览器。

## 🛠️ 技术栈

*   **桌面应用框架**: `PyWebView` - 用于将Web前端打包成原生GUI应用。
*   **后端**: `Flask` - 提供API接口，处理数据请求和交易逻辑。
*   **前端**:
    *   `HTML5` / `CSS3` / `JavaScript (ES6+)`
    *   `Lightweight Charts™` - 用于高性能的金融图表绘制。
*   **数据处理**: `Pandas`, `Numpy` - 用于高效处理和计算K线数据。
*   **数据源**: `Akshare` - 用于获取A股历史行情数据。
*   **数据存储**: `SQLite` - 用于存储每个用户的交易历史、设置和统计数据。

## 🚀 如何运行

### 1. 环境准备

本项目主要在以下环境中开发和测试，可供参考：
*   **操作系统**: Windows 11
*   **Python 版本**: 3.13

### 2. 克隆项目

```bash
git clone https://github.com/fat7/KLinePlayground
cd KLinePlayground
```

### 3. 安装依赖

项目依赖项在 `main_pywebview.py` 中有自动检查机制，但建议您手动安装以确保环境纯净。

```bash
pip install flask flask-cors pandas numpy pywebview akshare
```

### 4. 启动应用

一切准备就绪后，运行主程序即可启动桌面应用：

```bash
cd webview_app
python main_pywebview.py
```

程序启动后，会依次执行以下步骤：
1.  检查依赖包是否完整。
2.  在后台启动Flask本地服务器。
3.  创建一个PyWebView窗口并加载前端界面。

关闭桌面应用的窗口即可完全退出程序。

## 📂 项目结构

```
├── webview_app/
│   └── main_pywebview.py       # 桌面应用主入口
├── frontend/
│   ├── index_enhanced.html # 前端主页面
│   ├── css/
│   │   └── style_enhanced.css # 样式表
│   └── js/
│       ├── main_enhanced.js  # 前端核心交互逻辑
│       └── lightweight-charts.standalone.production.js # 图表库
└── backend/
    ├── app_enhanced.py         # Flask后端API路由
    ├── data_manager.py         # 数据获取与管理 (Akshare)
    ├── kline_processor_enhanced.py # K线数据处理、复权、指标计算
    ├── trade_simulator_enhanced.py # 交易逻辑模拟、成本计算、T+1
    ├── user_manager_enhanced.py    # 用户创建、配置管理
    └── history_manager.py      # 基于SQLite的训练历史记录管理
```

## 📜 开源许可

本项目采用 [MIT License](LICENSE) 开源。

## ⚙️ 支持与服务

本项目是一个开源软件，作者投入了大量时间和精力进行开发和维护。如果您觉得这个项目对您有帮助，可以通过以下方式支持作者：

### 接受赞赏 (Sponsor)

您的支持是作者持续更新和改进项目的最大动力！欢迎通过支付宝或微信扫码赞赏。

| 支付宝 (Alipay) | 微信支付 (WeChat Pay) |
| :---: | :---: |
| <img src="https://github.com/user-attachments/assets/f7fa53b8-cdb1-4a0c-9677-ce5d0c60c1a7" alt="Alipay QR Code" width="180"> | <img src="https://github.com/user-attachments/assets/955c873f-de30-4496-ac16-9f0b3c2c39c8" alt="WeChat Pay QR Code" width="180"> |

### 商业服务 (Commercial Services)

除了开源版本外，本人（作者）也可以提供一系列付费的商业服务，以满足个人、团队或企业的深度需求。如果您有以下任何需求，欢迎通过 [GitHub Issues](https://github.com/fat7/KLinePlayground/issues) 或其他联系方式与我取得联系：

*   **技术支持服务**: 为您在使用过程中遇到的问题提供优先级的技术支持和解决方案。
*   **定制化开发**: 根据您的具体需求，对软件进行功能定制、添加新指标、对接特定数据源或API等。
*   **企业内训**: 为您的团队提供关于项目架构、量化交易基础、代码实现等方面的培训。
*   **咨询服务**: 提供与项目相关的技术选型、架构设计、策略实现等方面的专业咨询。
