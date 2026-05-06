import base64
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import requests
import webview
from flask import Flask, jsonify, request

CONFIG_FILE_NAME = ".ai_tester_config.enc"
CRYPT_KEY = "kline_trainer_secret_key"


def _xor_crypt(text: str, key: str = CRYPT_KEY) -> str:
    return "".join(chr(ord(char) ^ ord(key[index % len(key)])) for index, char in enumerate(text))


def get_runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def get_project_root() -> Path:
    base_dir = get_runtime_base_dir()
    if getattr(sys, "frozen", False):
        return base_dir
    return base_dir


def get_bundle_base() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_frontend_dir() -> Path:
    return get_bundle_base() / "webview_app" / "ai_tester_frontend"


def get_data_dir() -> Path:
    return get_project_root() / "data"


def get_api_info_path() -> Path:
    return get_data_dir() / "ai_api_info.json"


def get_config_path() -> Path:
    return get_data_dir() / CONFIG_FILE_NAME


def load_config() -> dict:
    config_path = get_config_path()
    if not config_path.exists():
        return {
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
            "bar_count": 80,
            "include_indicator": True,
            "indicator_type": "MACD",
            "include_chip": True,
            "strategy": "",
        }

    try:
        obfs = config_path.read_text(encoding="utf-8").strip()
        if not obfs:
            return {}
        json_str = _xor_crypt(base64.b64decode(obfs).decode("utf-8"))
        return json.loads(json_str)
    except Exception as exc:
        return {"error": f"读取配置失败: {exc}"}


def save_config(config: dict):
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(config, ensure_ascii=False)
    obfs = base64.b64encode(_xor_crypt(json_str).encode("utf-8")).decode("utf-8")
    config_path.write_text(obfs, encoding="utf-8")


def load_api_info() -> dict:
    info_path = get_api_info_path()
    if not info_path.exists():
        raise FileNotFoundError(f"未找到 {info_path}")
    return json.loads(info_path.read_text(encoding="utf-8"))


def normalize_connect_info() -> dict:
    info = load_api_info()
    base_url = info.get("api_base_url", "").rstrip("/")
    trainings = info.get("active_trainings", [])
    training_id = trainings[0] if trainings else ""
    return {
        "status": "connected" if base_url else "error",
        "base_url": base_url,
        "training_id": training_id,
        "trainings": trainings,
        "current_user": info.get("current_user", ""),
        "updated_at": info.get("updated_at", ""),
        "message": "已连接主程序" if base_url else "ai_api_info.json 缺少 API 地址",
    }


def _append_log(logs, message, level="info"):
    logs.append({"level": level, "message": message})


def force_next_internal(base_url: str, training_id: str) -> dict:
    next_url = f"{base_url}/training/{training_id}/next"
    response = requests.post(next_url, timeout=30)
    payload = response.json()
    if response.status_code != 200:
        raise RuntimeError(payload.get("error", "推进失败"))
    return payload


def build_prompt(config: dict, data_json: dict, account_json: dict) -> tuple[str, str]:
    kline_list = data_json.get("kline_data", [])
    bar_count = int(config.get("bar_count", 80) or 80)
    bar_count = max(20, min(80, bar_count))
    recent_klines = kline_list[-bar_count:]

    indicator_data = {}
    chip_desc = ""
    connect = normalize_connect_info()
    base_url = connect["base_url"]
    training_id = connect["training_id"]

    if config.get("include_indicator"):
        indicator_type = config.get("indicator_type", "MACD")
        try:
            response = requests.get(f"{base_url}/training/{training_id}/indicators/{indicator_type}", timeout=30)
            if response.status_code == 200:
                indicator_list = response.json().get("data", [])
                recent_indicator = indicator_list[-bar_count:] if indicator_list else []
                for item in recent_indicator:
                    indicator_data[item["time"]] = {
                        key: round(value, 3)
                        for key, value in item.items()
                        if key not in ("time", "bar_id", "is_preview") and isinstance(value, (int, float))
                    }
        except Exception:
            pass

    if config.get("include_chip"):
        try:
            response = requests.get(f"{base_url}/training/{training_id}/chip_distribution?bins=80", timeout=30)
            if response.status_code == 200:
                chips = response.json().get("data", [])
                preview = ", ".join([f"{item['price']:.2f}:{item['volume']:.2f}" for item in chips[-20:]])
                chip_desc = f"【当前筹码分布】价格:成交量 = {preview}\n\n"
        except Exception:
            pass

    context_data = []
    for bar in recent_klines:
        dt_str = datetime.fromtimestamp(bar["time"]).strftime("%Y-%m-%d")
        item = {
            "Date": dt_str,
            "Open": round(bar["open"], 2),
            "High": round(bar["high"], 2),
            "Low": round(bar["low"], 2),
            "Close": round(bar["close"], 2),
        }
        if bar["time"] in indicator_data:
            item.update(indicator_data[bar["time"]])
        context_data.append(item)

    current_bar = context_data[-1]
    stock_name = data_json.get("stock_name", "未知标的")
    user_strategy = (config.get("strategy") or "").strip()

    position_summary = account_json.get("position_summary") or {}
    total_shares = position_summary.get("total_shares", 0)
    available_shares = position_summary.get("available_shares", 0)

    prompt = [f"你是一名 A 股交易 AI，当前复盘标的为《{stock_name}》。"]
    if user_strategy:
        prompt.append("【用户策略】请严格遵守以下自然语言策略：")
        prompt.append(user_strategy)
    prompt.append(
        f"【账户】总资产={account_json.get('total_assets')}，可用资金={account_json.get('available_cash')}，"
        f"总持仓={total_shares} 股，可卖={available_shares} 股。"
    )
    prompt.append(f"【最近{bar_count}根K线】\n{json.dumps(context_data, ensure_ascii=False, indent=2)}")
    if chip_desc:
        prompt.append(chip_desc)
    prompt.append(f"【当前时间】{current_bar['Date']}，最新收盘价={current_bar['Close']}")
    prompt.append(
        "请只返回一个合法 JSON，不要输出 Markdown。格式为："
        '{"action":"buy/sell/hold/next","quantity":100,"reason":"说明原因"}'
    )
    prompt.append("buy/sell 的 quantity 单位是股，必须是 100 的整数倍。")

    return "\n\n".join(prompt), stock_name


def perform_ai_analysis(config: dict) -> dict:
    logs = []
    auto_mode = bool(config.get("auto_mode", False))
    connect_info = normalize_connect_info()
    base_url = connect_info.get("base_url", "")
    training_id = connect_info.get("training_id", "")

    if not base_url or not training_id:
        raise RuntimeError("未检测到有效训练会话，请先在主程序中开启训练。")

    api_key = (config.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("LLM API Key 不能为空。")

    _append_log(logs, "正在读取训练数据与账户状态...", "info")
    data_resp = requests.get(f"{base_url}/training/{training_id}/data", timeout=30)
    account_resp = requests.get(f"{base_url}/training/{training_id}/account", timeout=30)
    if data_resp.status_code != 200:
        raise RuntimeError("训练数据读取失败。")
    if account_resp.status_code != 200:
        raise RuntimeError("账户数据读取失败。")

    data_json = data_resp.json()
    account_json = account_resp.json()
    if not data_json.get("kline_data"):
        raise RuntimeError("当前训练没有可用 K 线数据。")

    prompt, stock_name = build_prompt(config, data_json, account_json)
    _append_log(logs, f"已组装 {stock_name} 的盘面上下文，正在请求模型推理...", "highlight")

    llm_url = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    payload = {
        "model": (config.get("model") or "gpt-4o-mini").strip(),
        "messages": [
            {
                "role": "system",
                "content": "You are a trading AI. Return only one valid JSON object with no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    llm_resp = requests.post(llm_url, headers=headers, json=payload, timeout=120)
    if llm_resp.status_code != 200:
        raise RuntimeError(f"模型请求失败: {llm_resp.status_code} {llm_resp.text}")

    content = llm_resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```json"):
        content = content[7:].strip()
    if content.startswith("```"):
        content = content[3:].strip()
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        action_info = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"模型返回的不是合法 JSON: {exc}: {content}")

    action = str(action_info.get("action", "next")).lower()
    quantity = int(action_info.get("quantity", 100) or 100)
    reason = str(action_info.get("reason", "") or "").strip()
    _append_log(logs, f"AI 理由: {reason or '未提供'}", "ai")
    _append_log(logs, f"AI 指令: {action.upper()} / 数量 {quantity}", "success")

    result = {
        "logs": logs,
        "action": action,
        "reason": reason,
        "quantity": quantity,
        "finished": False,
    }

    if action in {"buy", "sell"}:
        trade_resp = requests.post(
            f"{base_url}/training/{training_id}/trade",
            json={"action": action, "quantity": max(1, quantity // 100)},
            timeout=30,
        )
        trade_json = trade_resp.json()
        if trade_resp.status_code == 200:
            _append_log(logs, "委托已成交，已写入训练记录。", "success")
            result["trade"] = trade_json.get("trade")
        else:
            _append_log(logs, f"委托被拒绝: {trade_json.get('error', '未知错误')}", "error")

    should_advance = action == "next" or (auto_mode and action in {"hold", "buy", "sell"})
    if should_advance:
        next_result = force_next_internal(base_url, training_id)
        if next_result.get("finished"):
            _append_log(logs, "训练已走完，自动停止。", "success")
            result["finished"] = True
            result["report"] = next_result.get("report")
        else:
            _append_log(logs, "已推进到下一根 K 线。", "info")

    return result


class AITesterWebviewApp:
    def __init__(self):
        self.frontend_dir = get_frontend_dir()
        self.flask_app = Flask(__name__, static_folder=str(self.frontend_dir), static_url_path="")
        self.port = self.find_free_port()
        self._register_routes()

    @staticmethod
    def find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _register_routes(self):
        @self.flask_app.route("/")
        def index():
            return self.flask_app.send_static_file("index.html")

        @self.flask_app.route("/api/config", methods=["GET", "POST"])
        def config_api():
            if request.method == "GET":
                return jsonify(load_config())
            payload = request.get_json() or {}
            save_config(payload)
            return jsonify({"success": True})

        @self.flask_app.route("/api/connect", methods=["POST"])
        def connect_api():
            try:
                return jsonify(normalize_connect_info())
            except Exception as exc:
                return jsonify({"status": "error", "message": str(exc)}), 500

        @self.flask_app.route("/api/action/next", methods=["POST"])
        def next_api():
            payload = request.get_json() or {}
            try:
                result = force_next_internal(payload["base_url"], payload["training_id"])
                return jsonify(result)
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @self.flask_app.route("/api/action/analyze", methods=["POST"])
        def analyze_api():
            payload = request.get_json() or {}
            try:
                save_config(payload)
                return jsonify(perform_ai_analysis(payload))
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @self.flask_app.route("/api/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

    def start_server(self):
        get_data_dir().mkdir(parents=True, exist_ok=True)
        self.flask_app.run(host="127.0.0.1", port=self.port, debug=False, use_reloader=False)

    def wait_until_ready(self) -> bool:
        health_url = f"http://127.0.0.1:{self.port}/api/health"
        for _ in range(30):
            try:
                response = urllib.request.urlopen(health_url, timeout=1)
                if response.status == 200:
                    return True
            except (urllib.error.URLError, socket.timeout):
                pass
            time.sleep(0.3)
        return False

    def run(self):
        if not self.frontend_dir.exists():
            raise RuntimeError(f"AI tester 前端目录不存在: {self.frontend_dir}")

        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()
        if not self.wait_until_ready():
            raise RuntimeError("AI tester 本地服务启动超时。")

        icon_path = get_bundle_base() / "ai_assistant.ico"
        window = webview.create_window(
            title="KLine Trainer AI 策略测试器",
            url=f"http://127.0.0.1:{self.port}/",
            width=1380,
            height=920,
            text_select=True,
        )
        webview.start(debug=False)


def main():
    app = AITesterWebviewApp()
    app.run()


if __name__ == "__main__":
    main()
