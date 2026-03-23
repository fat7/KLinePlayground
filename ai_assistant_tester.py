import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import os
import requests
import threading
import base64

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import sys

# 告诉 Windows 这是一个独立的应用程序，而不是 python/tk 的子进程
# 这可以修复任务栏图标显示为 tk 默认图标的问题
try:
    myappid = 'klinetrainer.aitester.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    application_path = os.path.dirname(sys.executable)
    # 针对 PyInstaller 单文件打包，资源文件会被解压到 sys._MEIPASS
    bundle_dir = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = application_path

# 因为安装后 exe 在 bin 目录下，所以 data 目录在上一级
if getattr(sys, 'frozen', False):
    data_dir = os.path.join(application_path, '..', 'data')
else:
    data_dir = os.path.join(application_path, 'data')

CONFIG_FILE = os.path.join(data_dir, '.ai_tester_config.enc')
CRYPT_KEY = "kline_trainer_secret_key"

def _xor_crypt(text, key=CRYPT_KEY):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))

class AIInterventionTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KLine Trainer AI 策略测试客户端 V1.0")
        
        icon_path = os.path.join(bundle_dir, 'ai_assistant.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(default=icon_path)
        else:
            # 强烈建议加上这行打印！如果打包时忘记加 --add-data，它会在这里提醒你，而不是默默变成小羽毛
            print(f"警告: 找不到图标文件 {icon_path}")
        
        self.root.geometry("800x650")

        # 风格设置
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        
        style.configure("TButton", padding=6, font=("Microsoft YaHei", 9))
        style.configure("Primary.TButton", font=("Microsoft YaHei", 9, "bold"))
        style.configure("TLabel", font=("Microsoft YaHei", 9))
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", 9, "bold"), padding=[10, 5])
        
        # 内部状态
        self.api_info = None
        self.base_url = ""
        self.training_id = ""
        self.auto_mode = False
        
        self.create_widgets()
        self.load_config()
        
    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f:
                obfs = f.read().strip()
            if not obfs: return
            json_str = _xor_crypt(base64.b64decode(obfs).decode('utf-8'))
            data = json.loads(json_str)
            
            self.entry_base_url.delete(0, tk.END)
            self.entry_base_url.insert(0, data.get("base_url", "https://api.openai.com/v1"))
            
            self.entry_api_key.delete(0, tk.END)
            self.entry_api_key.insert(0, data.get("api_key", ""))
            
            self.entry_model.delete(0, tk.END)
            self.entry_model.insert(0, data.get("model", "gpt-3.5-turbo"))
            
            self.entry_bar_count.delete(0, tk.END)
            self.entry_bar_count.insert(0, str(data.get("bar_count", 80)))
            
            self.text_strategy.delete("1.0", tk.END)
            self.text_strategy.insert(tk.END, data.get("strategy", ""))
        except Exception as e:
            self.log(f"读取配置失败: {e}", "error")

    def save_config(self):
        try:
            bar_count = int(self.entry_bar_count.get().strip())
        except ValueError:
            bar_count = 80
            
        data = {
            "base_url": self.entry_base_url.get().strip(),
            "api_key": self.entry_api_key.get().strip(),
            "model": self.entry_model.get().strip(),
            "bar_count": bar_count,
            "strategy": self.text_strategy.get("1.0", tk.END).strip()
        }
        json_str = json.dumps(data)
        obfs = base64.b64encode(_xor_crypt(json_str).encode('utf-8')).decode('utf-8')
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                f.write(obfs)
        except Exception as e:
            self.log(f"保存配置失败: {e}", "error")

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # --- TAB 1: 运行控制台 ---
        tab_console = ttk.Frame(notebook)
        notebook.add(tab_console, text="🕹️ 运行与控制台")
        
        # 顶部连接面板
        conn_frame = ttk.LabelFrame(tab_console, text="主程序连接", padding=(10, 5))
        conn_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_connect = ttk.Button(conn_frame, text="🔄 刷新并读取接口状态", command=self.connect_to_trainer)
        self.btn_connect.grid(row=0, column=0, rowspan=2, padx=5, pady=5)
        
        self.lbl_status = ttk.Label(conn_frame, text="状态：尚未连接", foreground="gray")
        self.lbl_status.grid(row=0, column=1, sticky="w", padx=10)
        
        self.lbl_info = ttk.Label(conn_frame, text="会话：无", foreground="gray")
        self.lbl_info.grid(row=1, column=1, sticky="w", padx=10)
        
        # AI 控制面板
        ctrl_frame = ttk.LabelFrame(tab_console, text="AI 测试执行", padding=(10, 10))
        ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_analyze = tk.Button(ctrl_frame, text="🧠 单步分析并打单", command=self.start_ai_analysis, bg="#e6f7ff", font=("Microsoft YaHei", 9), relief="groove")
        self.btn_analyze.pack(side="left", padx=5)
        
        self.btn_auto = tk.Button(ctrl_frame, text="▶ 开启自动沉浸测试 (Auto Mode)", command=self.toggle_auto_mode, bg="#f6ffed", font=("Microsoft YaHei", 9), relief="groove")
        self.btn_auto.pack(side="left", padx=5)
        
        self.btn_next = tk.Button(ctrl_frame, text="⏭️ 强行下一天 (Next)", command=self.force_next, bg="#fffbe6", font=("Microsoft YaHei", 9), relief="groove")
        self.btn_next.pack(side="right", padx=5)
        
        # 日志区
        log_frame = ttk.Frame(tab_console)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ttk.Label(log_frame, text="实时执行日志:").pack(anchor="w")
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=60, height=15, state="disabled", font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill="both", expand=True, pady=2)
        
        # 定义日志标签颜色
        self.log_text.tag_config("info", foreground="#d4d4d4")
        self.log_text.tag_config("success", foreground="#4ec9b0")
        self.log_text.tag_config("error", foreground="#f44747")
        self.log_text.tag_config("highlight", foreground="#ce9178")
        self.log_text.tag_config("ai", foreground="#569cd6")
        
        # --- TAB 2: 配置中心 ---
        tab_config = ttk.Frame(notebook)
        notebook.add(tab_config, text="⚙️ AI 及策略配置")
        
        # LLM 设置
        llm_frame = ttk.LabelFrame(tab_config, text="大语言模型 (LLM) 接口设定", padding=(10, 10))
        llm_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(llm_frame, text="Base URL:").grid(row=0, column=0, sticky="e", pady=5)
        self.entry_base_url = ttk.Entry(llm_frame, width=50)
        self.entry_base_url.insert(0, "https://api.openai.com/v1")
        self.entry_base_url.grid(row=0, column=1, pady=5, sticky="w")
        
        ttk.Label(llm_frame, text="API Key:").grid(row=1, column=0, sticky="e", pady=5)
        self.entry_api_key = ttk.Entry(llm_frame, width=50, show="*")
        self.entry_api_key.grid(row=1, column=1, pady=5, sticky="w")
        
        ttk.Label(llm_frame, text="模型名称:").grid(row=2, column=0, sticky="e", pady=5)
        self.entry_model = ttk.Entry(llm_frame, width=50)
        self.entry_model.insert(0, "gpt-3.5-turbo")
        self.entry_model.grid(row=2, column=1, pady=5, sticky="w")
        
        ttk.Label(llm_frame, text="上送K线周期数 (20-80):").grid(row=3, column=0, sticky="e", pady=5)
        self.entry_bar_count = ttk.Spinbox(llm_frame, from_=20, to=80, width=48)
        self.entry_bar_count.insert(0, "80")
        self.entry_bar_count.grid(row=3, column=1, pady=5, sticky="w")
        
        # 策略设置
        strategy_frame = ttk.LabelFrame(tab_config, text="交易策略设定 (Strategy Prompt)", padding=(10, 10))
        strategy_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ttk.Label(strategy_frame, text="请在这里使用自然语言描述您希望 AI 遵守的交易策略或筛选条件。\n它将被融合进分析请求的 System 提示词中，用于指导 AI 动作。").pack(anchor="w", pady=2)
        
        self.text_strategy = scrolledtext.ScrolledText(strategy_frame, width=60, height=8, font=("Microsoft YaHei", 9))
        self.text_strategy.pack(fill="both", expand=True, pady=5)
        self.text_strategy.insert(tk.END, "请以稳健保护本金为前提。\n当前只做主升浪，遇到跌破 5 日均线请果断止损或减仓，金叉或放量突破时可适当加仓并注意仓位管理。")
        
        # 保存按钮
        save_frame = ttk.Frame(tab_config)
        save_frame.pack(fill="x", padx=10, pady=10)
        btn_save_config = ttk.Button(save_frame, text="💾 保存所有配置", command=self.save_config_manual, style="Primary.TButton")
        btn_save_config.pack(side="right")
        
    def save_config_manual(self):
        self.save_config()
        messagebox.showinfo("成功", "所有网络配置及交易策略已加密保存！")

    def log(self, msg, tag="info"):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        
    def connect_to_trainer(self):
        info_path = os.path.join(data_dir, 'ai_api_info.json')
        if not os.path.exists(info_path):
            self.lbl_status.config(text="状态：未找到 ai_api_info.json", foreground="red")
            self.log(f"未找到 {info_path}，请确认主程序已开启“AI 介入”开关", "error")
            return
            
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                self.api_info = json.load(f)
                
            self.base_url = self.api_info.get('api_base_url', '')
            trainings = self.api_info.get('active_trainings', [])
            
            if not self.base_url:
                self.lbl_status.config(text="状态：JSON 文件缺少 API 地址", foreground="red")
                return
                
            self.lbl_status.config(text=f"状态：已连接 ({self.base_url})", foreground="green")
            
            if trainings:
                self.training_id = trainings[0]
                self.lbl_info.config(text=f"会话绑定：[{self.training_id}]", foreground="blue")
                self.log(f"成功连接 KLine Trainer，锁定会话：{self.training_id}", "success")
            else:
                self.training_id = ""
                self.lbl_info.config(text="会话：无活跃训练", foreground="orange")
                self.log("连接成功。请在主程序中【新建训练】后再刷新状态。", "highlight")
                
        except Exception as e:
            self.lbl_status.config(text="状态：读取出现错误", foreground="red")
            self.log(f"读取异常: {e}", "error")

    def toggle_auto_mode(self):
        if not self.auto_mode:
            if not self.base_url or not self.training_id:
                messagebox.showwarning("警告", "尚未连接或无活跃训练会话！")
                return
            self.auto_mode = True
            self.btn_auto.config(text="⏹ 停止自动托管 (Stop)", bg="#ffa39e")
            self.log("="*40, "info")
            self.log("开始循环全自动复盘模式...", "highlight")
            self.start_ai_analysis()
        else:
            self.auto_mode = False
            self.btn_auto.config(text="▶ 开启自动沉浸测试 (Auto Mode)", bg="#f6ffed")
            self.log("已手动停止自动控制！", "highlight")
            
    def force_next_internal(self):
        if not self.base_url or not self.training_id:
            return False
        try:
            next_url = f"{self.base_url}/training/{self.training_id}/next"
            n_resp = requests.post(next_url)
            n_json = n_resp.json()
            if n_resp.status_code == 200:
                if n_json.get('finished'):
                    self.log("🏁 训练盘面已全部走完！任务结束！", "success")
                    return True
                else:
                    self.log(f"➡️ 成功步进至下一K线", "info")
                    return False
            else:
                self.log(f"❌ 步进失败：{n_json.get('error')}", "error")
                return False
        except Exception as e:
            self.log(f"网络异常: {e}", "error")
            return False

    def force_next(self):
        if not self.base_url or not self.training_id:
            messagebox.showwarning("提示", "未检测到有效连接。")
            return
        finished = self.force_next_internal()
        if finished and self.auto_mode:
            self.auto_mode = False
            self.log("自动模式随之终止。", "highlight")
            self.btn_auto.config(text="▶ 开启自动沉浸测试 (Auto Mode)", bg="#f6ffed")

    def start_ai_analysis(self):
        if not self.base_url or not self.training_id:
            messagebox.showwarning("提示", "未找到训练会话，请先检查连接。")
            if self.auto_mode: self.toggle_auto_mode()
            return
            
        api_key = self.entry_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "LLM API Key 不能为空，请在配置页补充。")
            if self.auto_mode: self.toggle_auto_mode()
            return
            
        self.save_config()
            
        self.btn_analyze.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.log("\n[" + "="*40 + "]", "info")
        self.log("正在打包当前盘面状态与策略配置...", "info")
        
        threading.Thread(target=self._ai_worker, daemon=True).start()
        
    def _ai_worker(self):
        try:
            data_resp = requests.get(f"{self.base_url}/training/{self.training_id}/data")
            acc_resp = requests.get(f"{self.base_url}/training/{self.training_id}/account")
            
            if data_resp.status_code != 200:
                self._update_log("错误：数据API拉取失败", "error")
                self.auto_mode = False
                return
            
            data_json = data_resp.json()
            acc_json = acc_resp.json()
            kline_list = data_json.get('kline_data', [])
            
            if not kline_list:
                self._update_log("错误：返回的K线盘面空白", "error")
                self.auto_mode = False
                return
                
            try:
                bar_count = int(self.entry_bar_count.get().strip())
                bar_count = max(20, min(80, bar_count))
            except ValueError:
                bar_count = 80
                
            recent_klines = kline_list[-bar_count:]
            context_data = []
            for k in recent_klines:
                import datetime
                dtStr = datetime.datetime.fromtimestamp(k['time']).strftime('%Y-%m-%d')
                context_data.append({
                    "Date": dtStr,
                    "Open": round(k['open'], 2), "High": round(k['high'], 2), 
                    "Low": round(k['low'], 2), "Close": round(k['close'], 2)
                })
                
            current_bar = context_data[-1]
            stock_name = data_json.get('stock_name', '未知')
            
            user_strategy = self.text_strategy.get("1.0", tk.END).strip()
            
            prompt = f"你是一台A股智能量化交易引擎。正在复盘测试标的：【{stock_name}】。\n\n"
            
            if user_strategy:
                prompt += f"【重要指示：用户的交易策略设定】\n请务必严格遵守以下策略思路或者操作指令：\n\"\"\"\n{user_strategy}\n\"\"\"\n\n"
            
            prompt += f"【当前账户与持仓状态】\n总资产：{acc_json.get('total_assets')}元 | 剩余可用资金：{acc_json.get('available_cash')}元\n"
            
            pos_summary = acc_json.get('position_summary')
            current_qty = pos_summary.get('total_shares', 0) if pos_summary else 0
            available_qty = pos_summary.get('available_shares', 0) if pos_summary else 0
            prompt += f"总持仓：{current_qty}股 (依据T+1规则，今日真正能够卖出的股数为：{available_qty}股)\n\n"
            
            prompt += f"【盘面数据】最近 {bar_count} 根日K线：\n{json.dumps(context_data, ensure_ascii=False, indent=2)}\n\n"
            prompt += f"【提示视窗】今日为 {current_bar['Date']}，当天最终收盘价：{current_bar['Close']}。\n\n"
            
            prompt += "【决策输出要求】务必结合策略、持仓与趋势情况进行评判，纯JSON回复格式如下：\n"
            prompt += '{"action": "sell/buy/next", "quantity": 100, "reason": "你的思考与抉择流"}\n\n'
            prompt += "- buy=买入开仓, quantity为100的整数倍；\n"
            prompt += "- sell=卖出平仓, 数量不得超过上述的【可卖出股数】；\n"
            prompt += "- hold=保持观望 / next=空仓无聊直接推翻至下一天。 (二者均使quantity失效)。\n"
            
            self._update_log("🚀 数据及用户策略参数已注入，向大模型中心传输推理请求...", "highlight")
            
            llm_url = self.entry_base_url.get().strip() + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.entry_api_key.get().strip()}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.entry_model.get().strip(),
                "messages": [
                    {"role": "system", "content": "You are a specialized mathematical trading AI returning ONLY an unformatted valid JSON payload."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            resp = requests.post(llm_url, headers=headers, json=payload, timeout=900)
            if resp.status_code != 200:
                self._update_log(f"网络阻断 (Status: {resp.status_code}) - {resp.text}", "error")
                self.auto_mode = False
                return
                
            resp_body = resp.json()
            content = resp_body['choices'][0]['message']['content'].strip()
            
            if content.startswith("```json"): content = content[7:-3].strip()
            elif content.startswith("```"): content = content[3:-3].strip()
                
            try:
                action_info = json.loads(content)
            except json.JSONDecodeError:
                self._update_log("解析异常：大模型返回了不合规的 JSON 框架。", "error")
                self._update_log(content, "info")
                self.auto_mode = False
                return
                
            action = action_info.get("action", "next").lower()
            qty = action_info.get("quantity", 100)
            reason = action_info.get("reason", "")
            
            self._update_log(f"💡 [AI 分析思路]：{reason}", "ai")
            self._update_log(f"🎯 [AI 推理打单指令]：{action.upper()} (股票数量额: {qty})", "success")
            
            if action in ['buy', 'sell']:
                qty_in_lots = max(1, int(qty) // 100)
                trade_url = f"{self.base_url}/training/{self.training_id}/trade"
                t_resp = requests.post(trade_url, json={"action": action, "quantity": qty_in_lots})
                t_json = t_resp.json()
                if t_resp.status_code == 200:
                    self._update_log("✅ 该委托单已被行情撮合接受并且成交记录在册。", "success")
                    if self.auto_mode:
                        finished = self.force_next_internal()
                        if finished: self.auto_mode = False
                else:
                    self._update_log(f"❌ 挂单遭拒收：{t_json.get('error')}", "error")
                    if self.auto_mode:
                        self._update_log("⚠️ 自动跳过无效订单并推进时间轴至未免卡死...", "error")
                        finished = self.force_next_internal()
                        if finished: self.auto_mode = False
                    
            elif action == 'hold':
                self._update_log("收到 Hold 观望信号，当日不做多空交易。", "info")
                if self.auto_mode:
                    finished = self.force_next_internal()
                    if finished: self.auto_mode = False
                
            elif action == 'next':
                finished = self.force_next_internal()
                if finished and self.auto_mode: self.auto_mode = False
                
            else:
                self._update_log(f"无法识别的自创指令: {action}", "error")
                if self.auto_mode:
                    finished = self.force_next_internal()
                    if finished: self.auto_mode = False
                
        except Exception as e:
            self._update_log(f"发生崩溃性错误或超时断连: {e}", "error")
            self.auto_mode = False
        finally:
            self.root.after(0, self._worker_completed)
            
    def _worker_completed(self):
        self.btn_analyze.config(state="normal")
        self.btn_next.config(state="normal")
        if self.auto_mode:
            self.btn_auto.config(text="⏹ 停止自动托管 (Stop)", bg="#ffa39e")
            self.log("-"*40, "info")
            self.root.after(2000, self.start_ai_analysis)
        else:
            self.btn_auto.config(text="▶ 开启自动沉浸测试 (Auto Mode)", bg="#f6ffed")

    def _update_log(self, msg, tag="info"):
        self.root.after(0, lambda: self.log(msg, tag))

if __name__ == "__main__":
    root = tk.Tk()
    app_tester = AIInterventionTesterApp(root)
    root.mainloop()
