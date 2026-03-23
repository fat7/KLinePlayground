# A股K线复盘训练 - PyWebView桌面版

这是A股K线复盘训练系统的PyWebView桌面版本，将原本的Web应用转换为独立的桌面应用程序。

## 功能特点

- **桌面应用**: 使用PyWebView将Web界面封装为原生桌面应用
- **独立运行**: 无需浏览器，直接运行桌面程序
- **完整功能**: 保留原版所有功能，包括K线训练、交易模拟、用户管理等
- **跨平台**: 支持Windows、macOS、Linux系统

## 系统要求

- Python 3.7+
- 操作系统: Windows 10+, macOS 10.14+, Ubuntu 18.04+

### Windows额外要求
- Microsoft Edge WebView2 Runtime (通常已预装)

### Linux额外要求
```bash
# Ubuntu/Debian
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0

# CentOS/RHEL/Fedora
sudo yum install python3-gobject gtk3-devel webkit2gtk3-devel
```

### macOS额外要求
- 无额外要求，使用系统内置的WebKit

## 安装步骤

1. **克隆或下载项目**
   ```bash
   # 如果是从压缩包解压，跳过此步骤
   git clone <项目地址>
   cd kline_trainer
   ```

2. **安装Python依赖**
   ```bash
   pip install -r requirements_pywebview.txt
   ```

3. **运行桌面应用**
   ```bash
   python main_pywebview.py
   ```

## 使用说明

### 启动应用
```bash
python main_pywebview.py
```

应用启动后会：
1. 检查依赖包
2. 创建必要的数据目录
3. 启动Flask后端服务
4. 打开PyWebView桌面窗口

### 应用界面
- 窗口标题: "A股K线复盘训练 - 桌面版"
- 默认尺寸: 1400x900像素
- 最小尺寸: 1200x800像素
- 支持窗口缩放和最大化

### 功能使用
桌面版保留了Web版的所有功能：
- 用户管理和设置
- 随机/指定股票训练
- K线图表显示
- 技术指标分析
- 模拟交易操作
- 训练报告生成

## 项目结构

```
kline_trainer/
├── main_pywebview.py          # PyWebView桌面版主程序
├── main_enhanced.py           # 原Web版主程序
├── requirements_pywebview.txt # PyWebView版依赖
├── requirements.txt           # 原版依赖
├── backend/                   # 后端代码
│   ├── app_enhanced.py       # Flask API服务
│   ├── data_manager.py       # 数据管理
│   ├── kline_processor_enhanced.py
│   ├── trade_simulator_enhanced.py
│   ├── user_manager_enhanced.py
│   └── history_manager.py
├── frontend/                  # 前端代码
│   ├── index_enhanced.html   # 主页面
│   ├── css/
│   └── js/
├── data/                     # 数据目录
└── users/                    # 用户数据目录
```

## 技术架构

### 后端架构
- **Flask**: Web框架，提供REST API
- **SQLite**: 用户数据和训练记录存储
- **Pandas/Numpy**: 数据处理和分析
- **AKShare**: 股票数据获取

### 前端架构
- **HTML/CSS/JavaScript**: 原生Web技术
- **Chart.js**: K线图表渲染
- **Bootstrap**: UI框架

### 桌面化方案
- **PyWebView**: 将Web界面封装为桌面应用
- **多进程架构**: Flask服务运行在后台线程
- **本地通信**: 前后端通过HTTP API通信

## 配置说明

### 端口配置
默认使用端口5000，如需修改可在`main_pywebview.py`中调整：
```python
self.port = 5000  # 修改为其他端口
```

### 窗口配置
可在`main_pywebview.py`中调整窗口参数：
```python
window = webview.create_window(
    title='A股K线复盘训练 - 桌面版',
    width=1400,      # 窗口宽度
    height=900,      # 窗口高度
    min_size=(1200, 800),  # 最小尺寸
    resizable=True,  # 是否可调整大小
    maximized=False, # 是否最大化启动
)
```

## 故障排除

### 常见问题

1. **PyWebView安装失败**
   - Windows: 确保已安装Microsoft Edge WebView2
   - Linux: 安装GTK和WebKit开发包
   - macOS: 通常无问题，如有问题请更新系统

2. **应用启动失败**
   - 检查Python版本是否3.7+
   - 确认所有依赖包已正确安装
   - 检查端口5000是否被占用

3. **数据加载问题**
   - 确保网络连接正常（获取股票数据需要网络）
   - 检查data目录权限
   - 查看控制台错误信息

4. **界面显示异常**
   - 尝试调整窗口大小
   - 检查前端文件是否完整
   - 清除浏览器缓存（重启应用）

### 日志查看
应用运行时会在控制台输出日志信息，包括：
- 依赖检查结果
- 服务启动状态
- 错误信息

## 开发说明

### 从Web版迁移到桌面版的主要变更

1. **主程序重构**
   - 原`main_enhanced.py`使用`webbrowser`打开浏览器
   - 新`main_pywebview.py`使用PyWebView创建桌面窗口

2. **服务器配置调整**
   - 绑定地址从`0.0.0.0`改为`127.0.0.1`（仅本地访问）
   - 禁用Flask调试模式和重载功能
   - 使用守护线程运行Flask服务

3. **依赖管理**
   - 新增PyWebView依赖
   - 创建独立的依赖文件`requirements_pywebview.txt`

4. **错误处理增强**
   - 添加依赖检查功能
   - 改进错误提示和异常处理

### 自定义开发
如需进一步定制，可以：
- 修改窗口样式和行为
- 添加系统托盘功能
- 集成原生文件对话框
- 添加快捷键支持

## 许可证

本项目遵循原项目的许可证条款。

## 更新日志

### v2.0 (PyWebView版)
- 将Web应用转换为PyWebView桌面应用
- 优化启动流程和错误处理
- 添加跨平台支持
- 创建独立的依赖管理

