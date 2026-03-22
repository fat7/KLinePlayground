from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import base64
import requests
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import numpy as np

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.data_manager import DataManager
from backend.kline_processor_enhanced import KLineProcessorEnhanced
from backend.trade_simulator_enhanced import TradeSimulatorEnhanced
from backend.user_manager_enhanced import UserManagerEnhanced

# 配置Flask以提供静态文件，支持开发环境和 PyInstaller 打包环境
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 打包后环境
    frontend_folder = os.path.join(sys._MEIPASS, 'frontend')
else:
    # 开发环境
    frontend_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

app = Flask(__name__, static_folder=frontend_folder, static_url_path='/')
CORS(app)  # 允许跨域请求

# 获取项目根目录，确保路径在项目内
if getattr(sys, 'frozen', False):
    # project_root = os.path.dirname(sys.executable)
    project_root = os.path.join(os.path.dirname(sys.executable), '..')
else:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
users_dir_path = os.path.join(project_root, 'users')
data_dir_path = os.path.join(project_root, 'data')

# 初始化管理器
data_manager = DataManager(data_dir=data_dir_path)
# user_manager = UserManager()
user_manager = UserManagerEnhanced(users_dir=users_dir_path)
active_trainings = {}  # 存储活跃的训练会话

@app.route('/')
def index():
    """提供前端入口页面"""
    return app.send_static_file('index_enhanced.html')


@app.route('/api/users', methods=['GET'])
def get_users():
    """获取用户列表"""
    try:
        users = user_manager.get_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': '用户名不能为空'}), 400
        
        if user_manager.user_exists(username):
            return jsonify({'error': '用户名已存在'}), 400
        
        user_manager.create_user(username)
        return jsonify({'message': '用户创建成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<username>', methods=['DELETE'])
def delete_user(username):
    """删除用户及其所有数据"""
    try:
        if not user_manager.user_exists(username):
            return jsonify({'error': '用户不存在'}), 404

        if user_manager.delete_user(username):
            return jsonify({'message': '用户删除成功'})
        else:
            return jsonify({'error': '删除用户失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/settings', methods=['GET'])
def get_user_settings(username):
    """获取用户设置"""
    try:
        config = user_manager.get_user_config(username)
        if config:
            return jsonify(config.get('settings', {}))
        else:
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/settings', methods=['POST'])
def update_user_settings(username):
    """更新用户设置"""
    try:
        data = request.get_json()
        config = user_manager.get_user_config(username)
        
        if not config:
            # 如果配置不存在，先创建默认配置，防止老用户数据丢失或缺失 config.json 导致无法保存
            user_manager.create_user(username)
            config = user_manager.get_user_config(username)
            if not config:
                return jsonify({'error': '用户不存在且创建配置失败'}), 404
        
        if 'settings' not in config:
            config['settings'] = {}
            
        # 更新设置
        config['settings'].update(data)
        
        if user_manager.update_user_config(username, config):
            return jsonify({'message': '设置更新成功'})
        else:
            return jsonify({'error': '设置更新失败'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/statistics', methods=['GET'])
def get_user_statistics(username):
    """获取用户统计信息"""
    try:
        stats = user_manager.get_user_statistics(username)
        if stats:
            return jsonify(stats)
        else:
            return jsonify({'error': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _update_api_info(user=None, enable=None):
    """更新或删除 api_info.json"""
    if getattr(sys, 'frozen', False):
        api_file_path = os.path.join(os.path.dirname(sys.executable), '..', 'data', 'ai_api_info.json')
    else:
        api_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'ai_api_info.json')
    
    if enable is None and user:
        user_config = user_manager.get_user_config(user)
        if user_config and 'settings' in user_config:
            enable = user_config['settings'].get('enable_ai_api', False)
        else:
            enable = False
            
    if not enable:
        if os.path.exists(api_file_path):
            try:
                os.remove(api_file_path)
            except Exception:
                pass
        return

    # 尝试获取base_url，如果不在请求上下文中可能为空
    try:
        base_url = request.host_url.rstrip('/') + "/api"
    except Exception:
        base_url = ""

    info = {
        "api_base_url": base_url,
        "active_trainings": list(active_trainings.keys()),
        "current_user": user,
        "endpoints": {
            "start_training": "POST /api/training/start",
            "next_bar": "POST /api/training/{training_id}/next",
            "execute_trade": "POST /api/training/{training_id}/trade",
            "adjustment": "POST /api/training/{training_id}/adjustment",
            "get_data": "GET /api/training/{training_id}/data",
            "get_account": "GET /api/training/{training_id}/account",
            "end_training": "POST /api/training/{training_id}/end"
        },
        "updated_at": datetime.now().isoformat()
    }
    
    try:
        with open(api_file_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"写入 ai_api_info.json 失败: {e}")

def get_ai_config():
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', '.ai_tester_config.enc')
    if not os.path.exists(config_file):
        return None
    try:
        with open(config_file, 'r') as f:
            obfs = f.read().strip()
        if not obfs: return None
        key = "kline_trainer_secret_key"
        json_str = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(base64.b64decode(obfs).decode('utf-8')))
        return json.loads(json_str)
    except Exception as e:
        print(f"Failed to load AI config: {e}")
        return None

def analyze_report_with_ai(report):
    ai_config = get_ai_config()
    if not ai_config:
        return "AI 配置未找到，请在 AI 测试器中配置。"
    
    base_url = ai_config.get("base_url", "https://api.openai.com/v1").rstrip('/')
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "gpt-3.5-turbo")
    
    if not api_key:
        return "AI API Key 未配置，无法进行分析。"
    
    prompt = f"""
请作为一位资深的股票交易教练，对以下A股K线训练的回放复盘报告进行分析、点评和评分（百分制）。

【训练基本信息】
- 股票代码: {report.get('stock_code')}
- 训练期间: {report.get('start_date')} 至 {report.get('end_date')}
- 初始资金: {report.get('initial_capital')}
- 最终资金: {report.get('final_capital')}
- 总收益率: {report.get('total_return')}%
- 最大回撤: {report.get('max_drawdown', 0)}%
- 总交易次数: {report.get('total_trades')}
- 交易胜率: {report.get('trade_win_rate')}%

【交易明细】
"""
    for t in report.get('trade_details', [])[:150]:
        prompt += f"- {t.get('date')} {t.get('action')} {t.get('quantity')}手 @ {t.get('price')} (Bar: {t.get('bar_id')})\n"
        
    prompt += "\n请给出专业的点评（包括优点、不足和改进建议），并在最后给出一个综合评分（0-100分）。要求语言简练、直击要害。"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位专业的量化和主观交易教练，擅长通过交易记录分析交易者的心理和策略问题。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return f"AI API请求失败: {response.status_code} {response.text}"
    except Exception as e:
        return f"AI 分析请求发生错误: {str(e)}"


@app.route('/api/system/api_info', methods=['POST', 'DELETE'])
def toggle_api_info():
    """手动切开/关 API暴露"""
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            user = data.get('user', None)
            _update_api_info(user=user, enable=True)
            return jsonify({'message': 'API info exposed'})
        else:
            _update_api_info(enable=False)
            return jsonify({'message': 'API info hidden'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/start', methods=['POST'])
def start_training():
    """开始新的训练"""
    try:
        data = request.get_json()
        user = data.get('user')
        mode = data.get('mode')
        data_source = data.get('data_source', 'akshare')
        initial_capital = data.get('initial_capital', 100000)
        
        if not user:
            return jsonify({'error': '用户名不能为空'}), 400
        
        # 创建训练会话
        training_id = f"{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if mode == 'random':
            # 随机模式
            sector = data.get('sector', 'all')
            year_range = data.get('year_range', '2020-2024')
            stock_code, start_date = data_manager.get_random_stock(sector, year_range, source=data_source)
        else:
            # 指定模式
            stock_code = data.get('stock_code')
            start_date = data.get('start_date')
            
            if not stock_code or not start_date:
                return jsonify({'error': '股票代码和起始日期不能为空'}), 400
        
        # 验证股票代码和日期
        if not data_manager.validate_stock_and_date(stock_code, start_date, source=data_source):
            return jsonify({'error': '无效的股票代码或日期'}), 400
        
        # 创建增强版K线处理器和交易模拟器
        kline_processor = KLineProcessorEnhanced(data_manager, stock_code, start_date, source=data_source)
        trade_simulator = TradeSimulatorEnhanced(user, initial_capital, stock_code)
        
        # 获取用户设置并应用到交易模拟器
        user_config = user_manager.get_user_config(user)
        if user_config and 'settings' in user_config:
            settings = user_config['settings']
            trade_simulator.set_commission_settings(
                settings.get('commission_rate', 0.0003),
                settings.get('min_commission', 5.0),
                settings.get('stamp_tax_rate', 0.001)
            )
        
        # 存储训练会话
        active_trainings[training_id] = {
            'user': user,
            'stock_code': stock_code,
            'start_date': start_date,
            'kline_processor': kline_processor,
            'trade_simulator': trade_simulator,
            'mode': mode,
            'created_at': datetime.now()
        }
        
        _update_api_info(user=user)
        
        return jsonify({
            'id': training_id,
            'stock_code': stock_code,
            'start_date': start_date,
            'mode': mode
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/data', methods=['GET'])
def get_training_data(training_id):
    """获取训练数据"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        # 获取当前可见的K线数据
        kline_data = kline_processor.get_visible_data()
        volume_data = kline_processor.get_volume_data()
        
        # 获取均线周期参数
        ma_periods_str = request.args.get('ma_periods', '5,10,20')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [5, 10, 20]
            
        ma_data = kline_processor.get_ma_data(ma_periods)
        
        # 获取股票名称
        stock_name = data_manager.get_stock_name(training['stock_code'])
        
        # 获取进度信息
        progress = kline_processor.get_progress()
        
        return jsonify({
            'stock_name': stock_name,
            'kline_data': kline_data,
            'volume_data': volume_data,
            'ma_data': ma_data,
            'progress': progress,
            'trade_markers': kline_processor.get_trade_markers()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/next', methods=['POST'])
def next_bar(training_id):
    """获取下一根K线"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        trade_simulator = training['trade_simulator']

        # 推进到下一根K线
        has_next = kline_processor.next_bar()
        
        if not has_next:
            # 训练结束，生成报告
            report = trade_simulator.generate_report(
                training['stock_code'],
                training['start_date'],
                kline_processor.get_current_date()
            )
            
            # 保存训练记录
            session_data = {
                'session_id': training_id,
                'stock_code': training['stock_code'],
                'stock_name': data_manager.get_stock_name(training['stock_code']),
                'start_date': training['start_date'],
                'end_date': kline_processor.get_current_date(),
                'mode': training['mode'],
                'initial_capital': report['initial_capital'],
                'final_capital': report['final_capital'],
                'total_return': report['total_return'],
                'total_trades': report['total_trades'],
                'trade_win_rate': report['trade_win_rate'],
                'session_win_rate': report['session_win_rate'],
                'status': 'completed'
            }
            user_manager.save_training_session(training['user'], session_data)
            
            return jsonify({
                'finished': True,
                'report': report
            })
        
        # 更新交易模拟器的当前价格和bar ID
        current_bar = kline_processor.get_current_bar()
        trade_simulator.update_current_price(current_bar['close'], current_bar['bar_id'])

        current_bar['lastClose'] = kline_processor.get_previous_close()

        res = {
            'finished': False,
            'new_bar': current_bar,
            'new_volume': kline_processor.get_current_volume(),
            'progress': kline_processor.get_progress()
        }

        color = '#000000'
        if res['new_bar']['close'] > res['new_bar']['open']:
            color = '#ff4d4f'
        elif res['new_bar']['close'] < res['new_bar']['open']:
            color = '#008000'  # 红涨绿跌

        res['new_volume']['color'] = color

        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/adjustment', methods=['POST'])
def update_adjustment(training_id):
    """更新复权设置"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        adjustment = data.get('adjustment', 'none')
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        # 更新复权设置
        kline_processor.set_adjustment(adjustment)
        
        # 获取均线周期参数
        ma_periods_str = request.args.get('ma_periods', '5,10,20')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [5, 10, 20]
            
        # 重新获取数据
        kline_data = kline_processor.get_visible_data()
        volume_data = kline_processor.get_volume_data()
        ma_data = kline_processor.get_ma_data(ma_periods)
        
        return jsonify({
            'kline_data': kline_data,
            'volume_data': volume_data,
            'ma_data': ma_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/full_data', methods=['GET'])
def get_full_data(training_id):
    """获取完整的K线数据和指标数据"""
    try:
        if training_id not in active_trainings:
            # 如果训练已结束且不在 active_trainings 中，尝试从历史记录重建所需的数据（这需要一些额外逻辑，目前先返回明确错误）
            # 或者我们可以考虑在 end_training 时不立即删除，而是标记为 ended，由客户端稍后清理
            return jsonify({'error': '训练会话已结束或不存在，无法获取完整走势'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        kline_data = kline_processor.get_full_data()
        
        # 获取均线周期参数
        ma_periods_str = request.args.get('ma_periods', '5,10,20')
        try:
            ma_periods = [int(p) for p in ma_periods_str.split(',') if p.strip()]
        except ValueError:
            ma_periods = [5, 10, 20]
            
        # We also need volume data for the full range
        volume_data = []
        ma_data = {p: [] for p in ma_periods}
        
        # Save current state
        original_index = kline_processor.current_index
        
        # Set to max to calculate everything
        kline_processor.current_index = kline_processor.max_index
        
        try:
            volume_data = kline_processor.get_volume_data()
            ma_data = kline_processor.get_ma_data(ma_periods)
        finally:
            # Restore state
            kline_processor.current_index = original_index
            
        return jsonify({
            'kline_data': kline_data,
            'volume_data': volume_data,
            'ma_data': ma_data,
            'trade_markers': kline_processor.get_trade_markers()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/trade', methods=['POST'])
def execute_trade(training_id):
    """执行交易"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        data = request.get_json()
        action = data.get('action')  # 'buy' or 'sell'
        quantity = data.get('quantity')
        
        if not action or not quantity:
            return jsonify({'error': '交易参数不完整'}), 400
        
        training = active_trainings[training_id]
        trade_simulator = training['trade_simulator']
        kline_processor = training['kline_processor']
        
        # 获取当前价格
        current_bar = kline_processor.get_current_bar()
        current_price = current_bar['close']
        current_date = kline_processor.get_current_date()
        
        # 执行交易
        if action == 'buy':
            result = trade_simulator.buy(quantity, current_price, current_date)
        elif action == 'sell':
            result = trade_simulator.sell(quantity, current_price, current_date)
        else:
            return jsonify({'error': '无效的交易操作'}), 400
        
        if result['success']:
            # 添加交易标记到K线图
            kline_processor.add_trade_marker(action, current_price)
            
            return jsonify({
                'success': True,
                'trade': result['trade'],
                'trade_markers': kline_processor.get_trade_markers()
            })
        else:
            return jsonify({'error': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/account', methods=['GET'])
def get_account_info(training_id):
    """获取账户信息"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        trade_simulator = training['trade_simulator']

        current_date = training['kline_processor'].get_current_date()

        account_info = trade_simulator.get_account_info(current_date)
        return jsonify(account_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/indicators/<indicator_type>', methods=['GET'])
def get_technical_indicators(training_id, indicator_type):
    """获取技术指标数据"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        indicators = kline_processor.get_technical_indicators(indicator_type.upper())
        return jsonify(indicators)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/sync_status', methods=['GET'])
def get_sync_status(training_id):
    """获取精简同步状态"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        kline_processor = training['kline_processor']
        
        return jsonify({
            'current_bar_id': kline_processor.get_current_bar_id(),
            'trade_markers_count': len(kline_processor.get_trade_markers())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/end', methods=['POST'])
def end_training(training_id):
    """结束训练"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        trade_simulator = training['trade_simulator']
        kline_processor = training['kline_processor']
        
        # Inject session_id into trade_simulator before generating report
        trade_simulator.session_id = training_id
        
        # 生成报告
        report = trade_simulator.generate_report(
            training['stock_code'],
            training['start_date'],
            kline_processor.get_current_date()
        )
        
        # 保存训练记录
        session_data = {
            'session_id': training_id,
            'stock_code': training['stock_code'],
            'stock_name': data_manager.get_stock_name(training['stock_code']),
            'start_date': training['start_date'],
            'end_date': kline_processor.get_current_date(),
            'mode': training['mode'],
            'initial_capital': report['initial_capital'],
            'final_capital': report['final_capital'],
            'total_return': report['total_return'],
            'total_trades': report['total_trades'],
            'trade_win_rate': report['trade_win_rate'],
            'session_win_rate': report['session_win_rate'],
            'status': 'ended'
        }
        user_manager.save_training_session(training['user'], session_data)
        
        # 清理训练会话
        # del active_trainings[training_id] # 不要立即删除，因为客户端可能还需要请求 full_data
        active_trainings[training_id]['status'] = 'ended'
        
        _update_api_info(user=training['user'])
        
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/cleanup', methods=['POST'])
def cleanup_training(training_id):
    """清理已结束的训练会话"""
    try:
        if training_id in active_trainings:
            del active_trainings[training_id]
        return jsonify({'message': '清理成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/reset', methods=['POST'])
def reset_training(training_id):
    """重置训练"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        
        # 重置K线处理器
        training['kline_processor'].reset()
        
        # 重置交易模拟器
        training['trade_simulator'].reset()
        
        return jsonify({'message': '训练已重置'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/<training_id>/history', methods=['GET'])
def get_training_history(training_id):
    """获取训练历史记录"""
    try:
        if training_id not in active_trainings:
            return jsonify({'error': '训练会话不存在'}), 404
        
        training = active_trainings[training_id]
        trade_simulator = training['trade_simulator']
        kline_processor = training['kline_processor']
        
        # 获取交易历史（包含bar ID）
        trade_history = trade_simulator.get_trade_history_with_bar_id()
        
        # 获取每个bar的账户状态历史
        progress = kline_processor.get_progress()
        
        return jsonify({
            'trade_history': trade_history,
            'progress': progress,
            'trade_markers': kline_processor.get_trade_markers()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/analyze_report', methods=['POST'])
def analyze_report():
    """使用AI分析复盘报告"""
    try:
        data = request.get_json()
        report = data.get('report')
        user = data.get('user')
        
        if not report or not user:
            return jsonify({'error': '缺少必要的参数'}), 400
            
        user_config = user_manager.get_user_config(user)
        if not user_config or not user_config.get('settings', {}).get('enable_ai_api', False):
            return jsonify({'error': '未开启AI分析功能'}), 403
            
        ai_commentary = analyze_report_with_ai(report)
        return jsonify({'ai_commentary': ai_commentary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'active_trainings': len(active_trainings)
    })

if __name__ == '__main__':
    # 确保数据目录存在
    os.makedirs('../data', exist_ok=True)
    os.makedirs('../users', exist_ok=True)
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)

