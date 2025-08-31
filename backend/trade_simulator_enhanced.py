import sqlite3
import os
import json
from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd


def calculate_trade_performance(trade_history):
    """
    根据交易历史计算胜率 (考虑手数)。
    使用先进先出 (FIFO) 原则，并能处理部分平仓。
    """
    # 使用双端队列存储买入批次: {'quantity': X, 'net_amount': Y, ...其他信息}
    buy_batches = deque()

    completed_trades = []

    for trade in trade_history:
        # quantity=1 代表1手(100股)，所有计算基于'手'
        trade_qty = trade['quantity']

        if trade['action'] == 'buy':
            buy_batches.append(trade.copy())  # 存入副本
            continue

        # --- 处理卖出逻辑 ---
        if trade['action'] == 'sell':
            sell_qty_to_match = trade_qty
            total_sell_net_amount = trade['net_amount']
            avg_sell_price_per_unit = total_sell_net_amount / sell_qty_to_match

            while sell_qty_to_match > 0 and buy_batches:
                buy_batch = buy_batches[0]
                buy_qty_available = buy_batch['quantity']
                avg_buy_price_per_unit = buy_batch['net_amount'] / buy_qty_available

                qty_to_close = min(sell_qty_to_match, buy_qty_available)

                # 计算这部分平仓的盈亏
                cost = avg_buy_price_per_unit * qty_to_close
                revenue = avg_sell_price_per_unit * qty_to_close
                profit = revenue - cost

                completed_trades.append({
                    'profit': profit,
                    'is_win': profit > 0,
                    'quantity_closed': qty_to_close
                })

                # 更新持仓队列
                buy_batch['quantity'] -= qty_to_close
                buy_batch['net_amount'] -= cost

                if buy_batch['quantity'] <= 0:
                    buy_batches.popleft()  # 如果该批次已完全卖出，则移出队列

                sell_qty_to_match -= qty_to_close

    # --- 开始统计 ---
    total_completed_trades = len(completed_trades)
    if total_completed_trades == 0:
        return {'win_rate': 0, 'total_trades': 0, 'winning_trades': 0}

    winning_trades = sum(1 for t in completed_trades if t['is_win'])
    win_rate = (winning_trades / total_completed_trades) * 100

    return {
        'win_rate': win_rate,
        'total_trades': total_completed_trades,
        'winning_trades': winning_trades,
        'losing_trades': total_completed_trades - winning_trades,
        'completed_trades_details': completed_trades
    }


class TradeSimulatorEnhanced:
    """增强版交易模拟器，支持持仓汇总、佣金设置、bar ID记录等功能"""
    
    def __init__(self, user: str, initial_capital: float, stock_code: str):
        self.user = user
        self.stock_code = stock_code
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_price = 0.0
        self.current_bar_id = 0  # 当前bar ID
        
        # 交易成本设置（可配置）
        self.commission_rate = 0.0003  # 万分之三佣金
        self.min_commission = 5.0      # 最低佣金5元
        self.stamp_tax_rate = 0.001    # 千分之一印花税（仅卖出）
        
        # 持仓信息（汇总模式）
        self.total_shares = 0          # 总持股数
        self.available_shares = 0      # 可卖出股数（T+1限制）
        self.average_cost = 0.0        # 平均成本价
        self.total_cost = 0.0          # 总成本
        
        # 持仓明细（用于T+1计算）
        self.position_lots = []        # 持仓批次列表
        
        # 交易记录
        self.trade_history = []
        
        # 数据库连接
        self.db_path = f'../users/{user}/trade_records.db'
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建交易记录表（增加bar_id字段）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                commission REAL NOT NULL,
                stamp_tax REAL NOT NULL,
                net_amount REAL NOT NULL,
                trade_date TEXT NOT NULL,
                bar_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建持仓批次表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS position_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                cost_price REAL NOT NULL,
                buy_date TEXT NOT NULL,
                buy_bar_id INTEGER NOT NULL,
                available_date TEXT NOT NULL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # 创建账户记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_assets REAL NOT NULL,
                available_cash REAL NOT NULL,
                position_value REAL NOT NULL,
                floating_pnl REAL NOT NULL,
                record_date TEXT NOT NULL,
                bar_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def set_commission_settings(self, commission_rate: float, min_commission: float, stamp_tax_rate: float):
        """设置佣金参数"""
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_tax_rate = stamp_tax_rate
    
    def update_current_price(self, price: float, bar_id: int):
        """更新当前股价和bar ID"""
        self.current_price = price
        self.current_bar_id = bar_id
        self._update_position_pnl()
    
    def _calculate_commission(self, amount: float) -> float:
        """计算佣金"""
        commission = round(amount * self.commission_rate,2)
        return max(commission, self.min_commission)
    
    def _calculate_stamp_tax(self, amount: float) -> float:
        """计算印花税（仅卖出时收取）"""
        return round(amount * self.stamp_tax_rate,2)
    
    def get_max_buyable_quantity(self) -> int:
        """根据可用资金、佣金、股价动态计算最大可买数量（手数）"""
        if self.current_price <= 0:
            return 0
        
        # 二分查找最大可买手数
        left, right = 0, int(self.current_capital / (self.current_price * 100))
        max_quantity = 0
        
        while left <= right:
            mid = (left + right) // 2
            shares = mid * 100
            amount = shares * self.current_price
            commission = self._calculate_commission(amount)
            total_cost = amount + commission
            
            if total_cost <= self.current_capital:
                max_quantity = mid
                left = mid + 1
            else:
                right = mid - 1
        
        return max_quantity
    
    def buy(self, quantity: int, price: float, trade_date: str) -> Dict:
        """买入股票（quantity为手数）"""
        try:
            # 验证买入数量
            if quantity <= 0:
                return {
                    'success': False,
                    'message': '买入数量必须大于0'
                }
            
            # 检查是否超过最大可买数量
            max_quantity = self.get_max_buyable_quantity()
            if quantity > max_quantity:
                return {
                    'success': False,
                    'message': f'超过最大可买数量，最大可买 {max_quantity} 手'
                }
            
            # 计算交易金额
            total_shares = quantity * 100
            amount = total_shares * price
            
            # 计算佣金
            commission = self._calculate_commission(amount)
            
            # 计算总成本
            total_cost = amount + commission
            
            # 检查资金是否充足
            if total_cost > self.current_capital:
                return {
                    'success': False,
                    'message': f'资金不足，需要 ¥{total_cost:.2f}，可用 ¥{self.current_capital:.2f}'
                }
            
            # 执行买入
            self.current_capital -= total_cost
            
            # 更新持仓汇总
            if self.total_shares > 0:
                # 计算新的平均成本
                new_total_cost = self.total_cost + amount
                new_total_shares = self.total_shares + total_shares
                self.average_cost = new_total_cost / new_total_shares
                self.total_cost = new_total_cost
                self.total_shares = new_total_shares
            else:
                # 首次买入
                self.average_cost = price
                self.total_cost = amount
                self.total_shares = total_shares
            
            # 添加持仓批次（T+1规则，次日才能卖出）
            next_day = (pd.to_datetime(trade_date) + timedelta(days=1)).strftime('%Y-%m-%d')
            position_lot = {
                'stock_code': self.stock_code,
                'quantity': total_shares,
                'cost_price': price,
                'buy_date': trade_date,
                'buy_bar_id': self.current_bar_id,
                'available_date': next_day,
                'status': 'active'
            }
            self.position_lots.append(position_lot)
            
            # 记录交易
            trade_record = {
                'stock_code': self.stock_code,
                'action': 'buy',
                'quantity': quantity,  # 记录手数
                'price': price,
                'amount': amount,
                'commission': commission,
                'stamp_tax': 0.0,  # 买入无印花税
                'net_amount': total_cost,
                'trade_date': trade_date,
                'bar_id': self.current_bar_id,
                'timestamp': datetime.now().isoformat()
            }
            self.trade_history.append(trade_record)
            
            # 保存到数据库
            self._save_trade_to_db(trade_record)
            self._save_position_lot_to_db(position_lot)
            
            return {
                'success': True,
                'trade': trade_record,
                'message': f'买入成功，成交 {quantity} 手，成本 ¥{total_cost:.2f}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'买入失败: {str(e)}'
            }
    
    def sell(self, quantity: int, price: float, trade_date: str) -> Dict:
        """卖出股票（quantity为手数）"""
        try:
            # 验证卖出数量
            if quantity <= 0:
                return {
                    'success': False,
                    'message': '卖出数量必须大于0'
                }
            
            # 计算实际股数
            total_shares = quantity * 100
            
            # 检查可卖出股数（T+1规则）
            available_shares = self._get_available_shares(trade_date)
            if total_shares > available_shares:
                return {
                    'success': False,
                    'message': f'可卖出股数不足，可卖 {available_shares//100} 手，尝试卖出 {quantity} 手'
                }
            
            # 计算交易金额
            amount = total_shares * price
            
            # 计算佣金和印花税
            commission = self._calculate_commission(amount)
            stamp_tax = self._calculate_stamp_tax(amount)
            
            # 计算净收入
            net_amount = amount - commission - stamp_tax
            
            # 执行卖出
            self.current_capital += net_amount
            
            # 更新持仓汇总（FIFO原则）
            self._reduce_positions(total_shares, trade_date)
            
            # 记录交易
            trade_record = {
                'stock_code': self.stock_code,
                'action': 'sell',
                'quantity': quantity,  # 记录手数
                'price': price,
                'amount': amount,
                'commission': commission,
                'stamp_tax': stamp_tax,
                'net_amount': net_amount,
                'trade_date': trade_date,
                'bar_id': self.current_bar_id,
                'timestamp': datetime.now().isoformat()
            }
            self.trade_history.append(trade_record)
            
            # 保存到数据库
            self._save_trade_to_db(trade_record)
            
            return {
                'success': True,
                'trade': trade_record,
                'message': f'卖出成功，成交 {quantity} 手，净收入 ¥{net_amount:.2f}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'卖出失败: {str(e)}'
            }
    
    def _get_available_shares(self, current_date: str) -> int:
        """获取可卖出股数（考虑T+1规则）"""
        current_dt = pd.to_datetime(current_date)
        available = 0
        
        for lot in self.position_lots:
            if lot['status'] == 'active':
                available_dt = pd.to_datetime(lot['available_date'])
                if current_dt >= available_dt:
                    available += lot['quantity']
        
        return available
    
    def _reduce_positions(self, sell_shares: int, trade_date: str):
        """减少持仓（FIFO原则）"""
        remaining_shares = sell_shares
        current_dt = pd.to_datetime(trade_date)
        
        # 按买入时间排序（FIFO）
        active_lots = [lot for lot in self.position_lots if lot['status'] == 'active']
        active_lots.sort(key=lambda x: x['buy_bar_id'])
        
        for lot in active_lots:
            if remaining_shares <= 0:
                break
                
            available_dt = pd.to_datetime(lot['available_date'])
            if current_dt >= available_dt:
                if lot['quantity'] <= remaining_shares:
                    # 完全卖出这个批次
                    remaining_shares -= lot['quantity']
                    lot['status'] = 'sold'
                else:
                    # 部分卖出
                    lot['quantity'] -= remaining_shares
                    remaining_shares = 0
        
        # 重新计算持仓汇总
        self._recalculate_position_summary()
        
        # 更新数据库中的持仓状态
        self._update_position_lots_in_db()
    
    def _recalculate_position_summary(self):
        """重新计算持仓汇总"""
        active_lots = [lot for lot in self.position_lots if lot['status'] == 'active']
        
        if not active_lots:
            self.total_shares = 0
            self.average_cost = 0.0
            self.total_cost = 0.0
            return
        
        total_shares = sum(lot['quantity'] for lot in active_lots)
        total_cost = sum(lot['quantity'] * lot['cost_price'] for lot in active_lots)
        
        self.total_shares = total_shares
        self.total_cost = total_cost
        self.average_cost = total_cost / total_shares if total_shares > 0 else 0.0
    
    def _update_position_pnl(self):
        """更新持仓盈亏"""
        if self.total_shares > 0:
            market_value = self.total_shares * self.current_price
            floating_pnl = market_value - self.total_cost
            return {
                'market_value': market_value,
                'floating_pnl': floating_pnl,
                'pnl_percent': (floating_pnl / self.total_cost) * 100 if self.total_cost > 0 else 0
            }
        return {'market_value': 0, 'floating_pnl': 0, 'pnl_percent': 0}
    
    def get_account_info(self, trade_date: str) -> Dict:
        """获取账户信息"""
        pnl_info = self._update_position_pnl()
        
        total_assets = self.current_capital + pnl_info['market_value']
        available_shares = self._get_available_shares(trade_date)
        
        return {
            'total_assets': total_assets,
            'available_cash': self.current_capital,
            'position_value': pnl_info['market_value'],
            'floating_pnl': pnl_info['floating_pnl'],
            'initial_capital': self.initial_capital,
            'total_return': ((total_assets - self.initial_capital) / self.initial_capital) * 100,
            'current_bar_id': self.current_bar_id,
            'max_buyable_quantity': self.get_max_buyable_quantity(),
            'position_summary': {
                'total_shares': self.total_shares,
                'available_shares': available_shares,
                'average_cost': self.average_cost,
                'current_price': self.current_price,
                'pnl_percent': pnl_info['pnl_percent']
            } if self.total_shares > 0 else None
        }
    
    def get_trade_history_with_bar_id(self) -> List[Dict]:
        """获取包含bar ID的交易历史"""
        return self.trade_history.copy()
    
    def generate_report(self, stock_code: str, start_date: str, end_date: str) -> Dict:
        """生成复盘报告"""
        account_info = self.get_account_info(end_date)
        
        # 计算交易统计
        buy_trades = [t for t in self.trade_history if t['action'] == 'buy']
        sell_trades = [t for t in self.trade_history if t['action'] == 'sell']

        total_trades = len(buy_trades) + len(sell_trades)
        
        # 计算胜率
        trade_performance = calculate_trade_performance(self.trade_history)
        win_count = trade_performance['winning_trades']
        total_sell_trades = trade_performance['total_trades']
        trade_win_rate = trade_performance['win_rate']
        
        # 以局为单位计算胜率（整体盈亏）
        session_win_rate = 100 if account_info['total_assets'] > self.initial_capital else 0

        # 计算总成本
        total_commission = sum(t['commission'] for t in self.trade_history)
        total_stamp_tax = sum(t['stamp_tax'] for t in self.trade_history)
        
        # 生成交易明细
        trade_details = []
        for trade in self.trade_history:
            trade_details.append({
                'bar_id': trade['bar_id'],
                'date': trade['trade_date'],
                'action': trade['action'],
                'price': trade['price'],
                'quantity': trade['quantity'],
                'amount': trade['amount'],
                'commission': trade['commission'],
                'stamp_tax': trade['stamp_tax'],
                'net_amount': trade['net_amount']
            })
        
        return {
            'stock_code': stock_code,
            'stock_name': f'股票{stock_code}',
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': self.initial_capital,
            'final_capital': account_info['total_assets'],
            'total_return': account_info['total_return'],
            'total_trades': total_trades,
            'trade_win_rate': trade_win_rate,  # 交易胜率
            'session_win_rate': session_win_rate,  # 局胜率
            'win_count': win_count,  # 盈利交易次数
            'total_sell_trades': total_sell_trades,  # 总卖出次数
            'total_commission': total_commission,
            'total_stamp_tax': total_stamp_tax,
            'trade_details': trade_details,
            'commission_settings': {
                'commission_rate': self.commission_rate,
                'min_commission': self.min_commission,
                'stamp_tax_rate': self.stamp_tax_rate
            }
        }
    
    def reset(self):
        """重置交易模拟器"""
        self.current_capital = self.initial_capital
        self.total_shares = 0
        self.available_shares = 0
        self.average_cost = 0.0
        self.total_cost = 0.0
        self.position_lots = []
        self.trade_history = []
        self.current_bar_id = 0
        
        # 清空数据库记录
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM trades')
        cursor.execute('DELETE FROM position_lots')
        cursor.execute('DELETE FROM account_history')
        conn.commit()
        conn.close()
    
    def _save_trade_to_db(self, trade: Dict):
        """保存交易记录到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (stock_code, action, quantity, price, amount, commission, stamp_tax, net_amount, trade_date, bar_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade['stock_code'],
            trade['action'],
            trade['quantity'],
            trade['price'],
            trade['amount'],
            trade['commission'],
            trade['stamp_tax'],
            trade['net_amount'],
            trade['trade_date'],
            trade['bar_id']
        ))
        
        conn.commit()
        conn.close()
    
    def _save_position_lot_to_db(self, lot: Dict):
        """保存持仓批次到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO position_lots (stock_code, quantity, cost_price, buy_date, buy_bar_id, available_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            lot['stock_code'],
            lot['quantity'],
            lot['cost_price'],
            lot['buy_date'],
            lot['buy_bar_id'],
            lot['available_date'],
            lot['status']
        ))
        
        conn.commit()
        conn.close()
    
    def _update_position_lots_in_db(self):
        """更新数据库中的持仓批次状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for lot in self.position_lots:
            cursor.execute('''
                UPDATE position_lots 
                SET quantity = ?, status = ?
                WHERE stock_code = ? AND buy_bar_id = ? AND status = 'active'
            ''', (lot['quantity'], lot['status'], lot['stock_code'], lot['buy_bar_id']))
        
        conn.commit()
        conn.close()

