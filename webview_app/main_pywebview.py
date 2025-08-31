"""
A股K线复盘训练 - PyWebView桌面版
主程序入口
"""

import os
import sys
import threading
import time
import webview
from pathlib import Path
from flask import Flask


# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入后端应用
from backend.app_enhanced import app

class KLineTrainerApp:
    def __init__(self):
        self.flask_app = app
        self.server = None
        self.port = 5000
        
    def start_flask_server(self):
        """启动Flask服务器"""
        try:
            # 确保数据目录存在
            data_dir = Path(__file__).parent / '..'  / 'data'
            users_dir = Path(__file__).parent / '..'  / 'users'
            data_dir.mkdir(exist_ok=True)
            users_dir.mkdir(exist_ok=True)
            
            # 启动Flask应用
            self.flask_app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"Flask服务器启动失败: {e}")
    
    def get_frontend_url(self):
        """获取前端URL"""
        return f"http://127.0.0.1:{self.port}"
    
    def check_dependencies(self):
        """检查依赖包"""
        required_packages = [
            'flask',
            'flask-cors',
            'pandas',
            'numpy',
            'pywebview'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                if package == 'pywebview':
                    import webview
                else:
                    __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"缺少依赖包: {', '.join(missing_packages)}")
            print("请运行以下命令安装依赖:")
            print(f"pip install {' '.join(missing_packages)}")
            return False
        
        return True

def get_resource_path(relative_path):
    """ 获取资源的绝对路径，兼容开发环境和 PyInstaller 打包环境 """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 打包后环境
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境
        base_path = Path(__file__).parent.parent # 从 main_pywebview.py 向上两级到项目根目录

    return base_path / relative_path

def main():
    """主函数"""
    print()
    print("=" * 60)
    print("A股K线复盘训练 - PyWebView桌面版 v2.0")
    print("=" * 60)
    print()
    
    app_instance = KLineTrainerApp()
    
    # 检查依赖
    print("检查依赖包...")
    if not app_instance.check_dependencies():
        sys.exit(1)
    print("依赖检查完成")
    print()
    
    # 启动Flask服务器（在后台线程中）
    print("启动后端服务...")
    flask_thread = threading.Thread(target=app_instance.start_flask_server, daemon=True)
    flask_thread.start()
    
    # 等待服务启动
    print("等待服务启动...")
    time.sleep(3)
    
    # 获取前端文件路径
    frontend_path = get_resource_path('frontend/index_enhanced.html')
    
    if not frontend_path.exists():
        print(f"错误: 前端文件不存在 {frontend_path}")
        sys.exit(1)
    
    # 创建PyWebView窗口
    print("启动桌面应用...")
    
    try:
        # 创建窗口
        window = webview.create_window(
            title='A股K线复盘训练 - 桌面版',
            url=f"file://{frontend_path.absolute()}",
            width=1400,
            height=900,
            # min_size=(1200, 800),
            # maximized=True,
            resizable=False,
            # on_top=False,
        )
        
        print()
        print("=" * 60)
        print("桌面应用已启动！")
        print("后端API: http://127.0.0.1:5000/api")
        print("关闭窗口即可退出程序")
        print("=" * 60)
        
        # 启动PyWebView
        webview.start(debug=False)
        
    except Exception as e:
        print(f"启动桌面应用失败: {e}")
        print("请确保已正确安装PyWebView及其依赖")
        sys.exit(1)
    
    print("\n程序已退出")

if __name__ == '__main__':
    main()

