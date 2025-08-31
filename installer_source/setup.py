# setup.py
import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from win32com.client import Dispatch
import ctypes
import winreg
import platform

APP_NAME = "KLineTrainer"
DEFAULT_INSTALL_PATH = f"C:\\Program Files\\{APP_NAME}"

# --- 1. 权限与环境检查 ---

def is_admin():
    """检查当前是否是管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_resource_path(relative_path):
    """获取资源的绝对路径（兼容打包后的情况）"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_webview2_version():
    """
    通过查询注册表来检查WebView2 Runtime是否安装及其版本。
    返回版本号字符串，如果未安装则返回None。
    """
    # 定义WebView2的注册表键信息
    # {F3017226-FE2A-4295-8BDF-00C3A9A7E4C5} 是 Evergreen Bootstrapper 的产品代码
    webview2_key_path_template = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

    # 在64位Windows上，32位应用的注册表项会被重定向到WOW6432Node下
    # 我们需要同时检查原生路径和WOW6432Node路径
    # platform.architecture()[0] 会返回 '64bit' 或 '32bit'
    is_64bit_windows = platform.architecture()[0] == '64bit'

    registry_paths = []
    if is_64bit_windows:
        registry_paths.append(
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
    registry_paths.append(r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")

    # 需要检查的注册表根键：HKEY_CURRENT_USER 和 HKEY_LOCAL_MACHINE
    registries = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]

    for reg in registries:
        for path in registry_paths:
            try:
                # 打开注册表键
                key = winreg.OpenKey(reg, path, 0, winreg.KEY_READ)

                # 读取名为 'pv' 的值，它存储了版本号
                version, _ = winreg.QueryValueEx(key, 'pv')

                # 关闭键
                winreg.CloseKey(key)

                # 如果版本号有效，则返回
                if version and version != "0.0.0.0":
                    return version
            except FileNotFoundError:
                # 如果键不存在，则继续检查下一个位置
                continue
            except Exception as e:
                # 捕获其他可能的异常
                print(f"检查注册表时发生错误: {e}")
                continue

    return None

# --- 2. 安装核心功能 ---

def install_webview2():
    """
    运行WebView2安装程序并等待其完成。
    """

    installer_path = get_resource_path("MicrosoftEdgeWebview2Setup.exe")

    if not os.path.exists(installer_path):
        print(f"错误：未在以下路径找到安装程序: {installer_path}")
        print("请确保 MicrosoftEdgeWebview2Setup.exe 与主程序在同一目录下。")
        input("按 Enter 键退出。")  # 暂停，让用户看到错误信息
        return False

    print("即将开始安装 WebView2 Runtime，请根据弹出的窗口提示完成安装...")

    try:
        # 使用 subprocess.run 来执行安装程序
        # shell=True 在某些情况下需要，但直接执行.exe通常不需要
        # capture_output=True 可以捕获输出，但安装程序是GUI，意义不大
        # check=True 会在返回非零退出码时抛出异常
        result = subprocess.run([installer_path], check=True, shell=True)
        print(f"安装程序已退出，返回码: {result.returncode}")
        return True
    except FileNotFoundError:
        print(f"严重错误：无法找到安装程序 {installer_path}。")
        input("按 Enter 键退出。")
        return False
    except subprocess.CalledProcessError as e:
        # 如果用户取消安装或安装失败，会返回非零退出码
        print(f"安装过程可能被取消或发生错误。返回码: {e.returncode}")
        input("按 Enter 键退出。")
        return False
    except Exception as e:
        print(f"运行安装程序时发生未知错误: {e}")
        input("按 Enter 键退出。")
        return False

def create_shortcut(target_path, shortcut_path):
    """在桌面创建快捷方式"""
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target_path
    shortcut.IconLocation = target_path # 使用 exe 的图标
    shortcut.WorkingDirectory = os.path.dirname(target_path)
    shortcut.save()

def main_install():
    """主安装逻辑"""
    # 步骤 1: 提权检查
    if not is_admin():
        messagebox.showerror("权限不足", "安装程序需要管理员权限，请右键以管理员身份运行。")
        return

    # 步骤 2: WebView2 检查与安装
    version = get_webview2_version()
    if version:
        print(f"检测到WebView2环境，版本号: {version}")
    else:
        print("未检测到WebView2环境。")
        print("请安装 Microsoft Edge WebView2 Runtime。")
        install_success = install_webview2()

        if not install_success:
            print("WebView2 安装未成功完成，程序无法继续运行。")
            return  # 退出程序

        # 安装后再次检查，确保安装成功
        print("再次检查WebView2环境...")
        version = get_webview2_version()
        if not version:
            print("安装后仍未检测到WebView2环境，请尝试重启程序或手动安装。")
            input("按 Enter 键退出。")
            return
        print(f"WebView2 安装成功！版本号: {version}")

    # 步骤 3: 选择安装路径
    print("请选择安装目录(该安装程序会自动创建新目录)")
    install_path = filedialog.askdirectory(
        title="请选择安装根路径",
        initialdir=DEFAULT_INSTALL_PATH
    )
    if not install_path:
        messagebox.showwarning("取消", "安装已取消。")
        return

    # 步骤 4: 复制文件和创建目录
    try:
        # 目标路径
        app_root_path = os.path.join(install_path, APP_NAME)
        bin_path = os.path.join(app_root_path, "bin")
        data_path = os.path.join(app_root_path, "data")
        user_path = os.path.join(app_root_path, "users")

        # 创建目录
        os.makedirs(bin_path, exist_ok=True)
        os.makedirs(data_path, exist_ok=True)
        os.makedirs(user_path, exist_ok=True)

        # 复制主程序文件
        source_app_files = get_resource_path("app_files")
        if os.path.exists(source_app_files):
            shutil.copytree(source_app_files, bin_path, dirs_exist_ok=True)
        else:
             messagebox.showerror("错误", "找不到应用文件，安装包可能已损坏。")
             return

    except Exception as e:
        messagebox.showerror("安装错误", f"创建文件或目录时发生错误: {e}")
        return

    # 步骤 5: 创建桌面快捷方式
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_file = os.path.join(desktop_path, f"{APP_NAME}.lnk")
        target_exe = os.path.join(bin_path, f"{APP_NAME}.exe")
        create_shortcut(target_exe, shortcut_file)
    except Exception as e:
        messagebox.showwarning("警告", f"创建桌面快捷方式失败: {e}\n但程序已安装成功。")

    # 步骤 6: 完成
    messagebox.showinfo("安装完成", f"{APP_NAME} 已成功安装到:\n{app_root_path}")


# --- 3. GUI 界面 ---
if __name__ == "__main__":

    root = tk.Tk()
    root.withdraw() # 我们不需要主窗口，只用对话框
    main_install()

