import os
import json
import shutil
from typing import List, Dict, Optional
from datetime import datetime
from backend.history_manager import HistoryManager

class UserManagerEnhanced:
    """增强版用户管理器，集成历史记录管理功能"""
    
    def __init__(self, users_dir='../users'):
        self.users_dir = users_dir
        self.history_manager = HistoryManager(users_dir)
        os.makedirs(users_dir, exist_ok=True)
    
    def get_users(self) -> List[str]:
        """获取所有用户列表"""
        try:
            users = []
            for item in os.listdir(self.users_dir):
                user_path = os.path.join(self.users_dir, item)
                if os.path.isdir(user_path):
                    users.append(item)
            return sorted(users)
        except Exception as e:
            print(f"获取用户列表失败: {e}")
            return []
    
    def user_exists(self, username: str) -> bool:
        """检查用户是否存在"""
        user_dir = os.path.join(self.users_dir, username)
        return os.path.exists(user_dir)
    
    def create_user(self, username: str) -> bool:
        """创建新用户"""
        try:
            user_dir = os.path.join(self.users_dir, username)
            os.makedirs(user_dir, exist_ok=True)
            
            # 创建用户配置文件
            config_path = os.path.join(user_dir, 'config.json')
            default_config = {
                'username': username,
                'created_at': datetime.now().isoformat(),
                'settings': {
                    'commission_rate': 0.0003,  # 万分之3
                    'min_commission': 5.0,      # 最低5元
                    'stamp_tax_rate': 0.001,    # 千分之1
                    'adjustment_mode': 'dynamic_forward',  # 默认复权方式为动态前复权
                    'default_initial_capital': 100000 # 默认初始资金
                },
                'preferences': {
                    # 'default_capital': 100000,
                    'auto_save': True,
                    'playback_speed': 1.0
                }
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            # 初始化历史记录数据库
            self.history_manager._init_user_history_db(username)
            
            return True
        except Exception as e:
            print(f"创建用户失败: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """删除用户及其所有数据"""
        try:
            user_dir = os.path.join(self.users_dir, username)
            if os.path.exists(user_dir) and os.path.isdir(user_dir):
                shutil.rmtree(user_dir)  # 使用 shutil.rmtree 来递归删除整个目录
                print(f"用户 '{username}' 的目录已成功删除。")
                return True
            return False  # 如果目录不存在，也算成功或返回False均可
        except Exception as e:
            print(f"删除用户 '{username}' 失败: {e}")
            return False

    def get_user_config(self, username: str) -> Optional[Dict]:
        """获取用户配置"""
        try:
            config_path = os.path.join(self.users_dir, username, 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"获取用户配置失败: {e}")
            return None
    
    def update_user_config(self, username: str, config: Dict) -> bool:
        """更新用户配置"""
        try:
            config_path = os.path.join(self.users_dir, username, 'config.json')
            config['last_updated'] = datetime.now().isoformat()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"更新用户配置失败: {e}")
            return False
    
    def get_user_statistics(self, username: str) -> Optional[Dict]:
        """获取用户统计信息"""
        stats = self.history_manager.get_user_statistics(username)
        if stats:
            return stats
        
        # 如果没有统计数据，返回默认值
        return {
            'total_sessions': 0,
            'completed_sessions': 0,
            'success_rate': 0,
            'total_trades': 0,
            'avg_return': 0.0,
            'best_return': 0.0,
            'worst_return': 0.0,
            'avg_trade_win_rate': 0.0,
            'avg_session_win_rate': 0.0,
            'total_commission_paid': 0.0
        }
    
    def start_training_session(self, username: str, session_data: Dict) -> bool:
        """开始新的训练会话"""
        return self.history_manager.start_training_session(username, session_data)
    
    def record_bar_state(self, username: str, session_id: str, bar_data: Dict) -> bool:
        """记录每个bar的状态"""
        return self.history_manager.record_bar_state(username, session_id, bar_data)
    
    def record_trade(self, username: str, session_id: str, trade_data: Dict) -> bool:
        """记录交易"""
        return self.history_manager.record_trade(username, session_id, trade_data)
    
    def save_training_session(self, username: str, session_data: Dict) -> bool:
        """保存训练会话"""
        return self.history_manager.complete_training_session(username, session_data['session_id'], session_data)
    
    def get_training_history(self, username: str, limit: int = 20) -> List[Dict]:
        """获取训练历史"""
        return self.history_manager.get_training_history(username, limit)
    
    def get_session_detail(self, username: str, session_id: str) -> Optional[Dict]:
        """获取训练会话详情"""
        return self.history_manager.get_session_detail(username, session_id)
    
    def get_performance_analysis(self, username: str, days: int = 30) -> Dict:
        """获取用户表现分析"""
        return self.history_manager.get_performance_analysis(username, days)
    
    def delete_training_session(self, username: str, session_id: str) -> bool:
        """删除训练会话"""
        return self.history_manager.delete_session(username, session_id)
    
    def export_training_data(self, username: str, session_id: str, format: str = 'json') -> Optional[str]:
        """导出训练数据"""
        return self.history_manager.export_session_data(username, session_id, format)

