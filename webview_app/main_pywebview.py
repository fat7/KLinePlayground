"""
A股K线复盘训练 - PyWebView桌面版
主程序入口
"""

import os
import sys
import threading
import time
import socket
import urllib.request
import urllib.error
import webview
from pathlib import Path
from flask import Flask


# 添加项目根目录到Python路径，以便能够导入同级的 backend 模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入后端应用
from backend.app_enhanced import app

class KLineTrainerApp:
    def __init__(self):
        self.flask_app = app
        self.server = None
        self.port = self.find_free_port()
        
    def find_free_port(self):
        """查找可用端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]
        
    def start_flask_server(self):
        """启动Flask服务器"""
        try:
            # 确保数据目录存在
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent.parent
            data_dir = base_dir / 'data'
            users_dir = base_dir / 'users'
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
    print("A股K线复盘训练 - 桌面版 v3.0")
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
    max_retries = 30
    is_ready = False
    health_url = f"http://127.0.0.1:{app_instance.port}/api/health"
    
    for _ in range(max_retries):
        try:
            response = urllib.request.urlopen(health_url, timeout=1)
            if response.status == 200:
                is_ready = True
                break
        except (urllib.error.URLError, socket.timeout):
            pass
        time.sleep(0.5)
        
    if not is_ready:
        print(f"错误: 后端服务启动超时，无法在端口 {app_instance.port} 访问。")
        sys.exit(1)
        
    print("服务已就绪！")
    
    # 创建PyWebView窗口
    print("启动桌面应用...")
    
    try:
        # 创建窗口
        window = webview.create_window(
            title='A股K线复盘训练 - 桌面版',
            url=f"http://127.0.0.1:{app_instance.port}/",
            width=1400,
            height=900,
            # min_size=(1200, 800),
            # maximized=True,
            # resizable=False,
            # on_top=False,
        )
        
        print()
        print("=" * 60)
        print("桌面应用已启动！")
        print(f"后端API: http://127.0.0.1:{app_instance.port}/api")
        print("关闭窗口即可退出程序")
        print("=" * 60)
        
        # 启动PyWebView
        # webview.start(debug=True)
        webview.start(debug=False)
        
    except Exception as e:
        print(f"启动桌面应用失败: {e}")
        print("请确保已正确安装PyWebView及其依赖")
        sys.exit(1)
    
    print("\n程序已退出")

if __name__ == '__main__':
    main()

