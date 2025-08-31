import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

class KLineProcessorEnhanced:
    """增强版K线处理器，支持bar ID、前80根K线预览、技术指标等功能"""
    
    def __init__(self, data_manager, stock_code: str, start_date: str):
        self.data_manager = data_manager
        self.stock_code = stock_code
        self.start_date = pd.to_datetime(start_date)
        self.adjustment_mode = 'dynamic_forward'  # 'none', 'forward', 'backward', 'dynamic_forward'
        
        # 加载原始数据
        self.raw_data = data_manager.get_stock_data(stock_code)
        self.factor_data = data_manager.get_factor_data(stock_code)
        self.dividend_data = data_manager.get_dividend_data(stock_code)
        
        if self.raw_data is None or self.raw_data.empty:
            raise ValueError(f"无法获取股票 {stock_code} 的数据")
        
        # 找到起始日期的索引
        start_mask = self.raw_data['date'] >= self.start_date
        if not start_mask.any():
            raise ValueError(f"起始日期 {start_date} 之后没有数据")
        
        self.start_index = start_mask.idxmax()
        
        # 获取前80根K线用于预加载（如果有的话）
        self.preview_start_index = max(0, self.start_index - 80)
        
        # 筛选数据（包含前80根预览数据）
        self.full_data = self.raw_data.iloc[self.preview_start_index:].copy()
        self.full_data.reset_index(drop=True, inplace=True)
        
        if self.full_data.empty:
            raise ValueError(f"起始日期 {start_date} 之后没有数据")
        
        # 回放状态
        self.preview_bars = min(80, self.start_index - self.preview_start_index)  # 预览的bar数量，最多80个
        self.current_index = self.preview_bars  # 当前显示到第几根K线（从预览结束开始）
        self.max_index = len(self.full_data) - 1
        
        # Bar ID计算（从1开始，预览部分为负数或0）
        self.bar_id_offset = -self.preview_bars + 1  # bar ID偏移量
        
        # 预处理复权数据
        self._prepare_adjustment_data()
        
        # 交易标记
        self.trade_markers = []  # 存储交易标记 {'bar_id': int, 'type': 'B'/'S', 'price': float}
    
    def _prepare_adjustment_data(self):
        """预处理复权数据"""
        # 如果有复权因子数据，合并到原始数据中
        if self.factor_data is not None and not self.factor_data.empty:
            self.full_data = pd.merge(
                self.full_data, 
                self.factor_data[['date', 'factor']], 
                on='date', 
                how='left'
            )
            # 填充缺失的复权因子
            self.full_data['factor'] = self.full_data['factor'].fillna(1.0)
        else:
            # 如果没有复权因子数据，设置为1
            self.full_data['factor'] = 1.0
        
        # 处理除权除息数据
        if self.dividend_data is not None and not self.dividend_data.empty:
            # 这里可以添加更复杂的除权除息处理逻辑
            pass
    
    def _calculate_adjusted_prices(self, data: pd.DataFrame, mode: str) -> pd.DataFrame:
        """计算复权价格"""
        if mode == 'none':
            # 不复权，返回原始价格
            return data[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
        
        result = data.copy()
        
        if mode == 'forward':
            # 前复权：以当前时点为基准，调整历史价格
            current_factor = result.iloc[self.current_index]['factor'] if self.current_index < len(result) else 1.0
            
            # 计算调整比例
            result['adj_ratio'] = result['factor'] / current_factor
            
        elif mode == 'backward':
            # 后复权：以最早时点为基准，调整后续价格
            base_factor = result.iloc[0]['factor']
            
            # 计算调整比例
            result['adj_ratio'] = result['factor'] / base_factor
        elif mode == 'dynamic_forward':
            # 动态前复权：以当前显示的最后一根K线为基准，调整所有历史价格
            # self.current_index 总是指向当前可见K线的最后一根
            current_factor = self.full_data.iloc[self.current_index]['factor']
            result['adj_ratio'] = result['factor'] / current_factor
        
        # 应用复权调整
        if mode in ["forward", "backward", "dynamic_forward"]:
            result['open'] = round(result['open'] * result['adj_ratio'],2)
            result['high'] = round(result['high'] * result['adj_ratio'],2)
            result['low'] = round(result['low'] * result['adj_ratio'],2)
            result['close'] = round(result['close'] * result['adj_ratio'],2)
        
        return result[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    def set_adjustment(self, mode: str):
        """设置复权模式"""
        if mode in ["none", "forward", "backward", "dynamic_forward"]:
            self.adjustment_mode = mode
        else:
            raise ValueError(f"无效的复权模式: {mode}")
    
    def get_current_bar_id(self) -> int:
        """获取当前bar ID"""
        return self.current_index + self.bar_id_offset
    
    def get_visible_data(self) -> List[Dict]:
        """获取当前可见的K线数据（包括预览部分）"""
        # 获取当前可见的数据（从开始到当前索引）
        visible_data = self.full_data.iloc[:self.current_index + 1].copy()
        
        # 应用复权调整
        adjusted_data = self._calculate_adjusted_prices(visible_data, self.adjustment_mode)
        
        # 转换为前端图表格式
        chart_data = []
        for i, (_, row) in enumerate(adjusted_data.iterrows()):
            bar_id = i + self.bar_id_offset
            chart_data.append({
                'time': int(row['date'].timestamp()),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'bar_id': bar_id,
                'is_preview': bar_id <= 0  # 标记是否为预览数据
            })
        
        return chart_data
    
    def get_volume_data(self) -> List[Dict]:
        """获取成交量数据，根据K线颜色设置成交量颜色"""
        visible_data = self.full_data.iloc[:self.current_index + 1].copy()
        adjusted_data = self._calculate_adjusted_prices(visible_data, self.adjustment_mode)
        
        volume_data = []
        for i, (_, row) in enumerate(visible_data.iterrows()):
            bar_id = i + self.bar_id_offset
            
            # 获取对应的调整后价格数据
            adjusted_row = adjusted_data.iloc[i]
            
            # 根据K线颜色确定成交量颜色
            # 红色（上涨）：收盘价 > 开盘价
            # 绿色（下跌）：收盘价 < 开盘价
            is_up = adjusted_row['close'] > adjusted_row['open']
            is_down = adjusted_row['close'] < adjusted_row['open']
            color = '#000000'
            if is_up:
                color = '#ff4d4f'
            elif is_down:
                color = '#008000'  # 红涨绿跌
            
            volume_data.append({
                'time': int(row['date'].timestamp()),
                'value': float(row['volume']),
                'color': color,
                'bar_id': bar_id,
                'is_preview': bar_id <= 0
            })
        
        return volume_data
    
    def get_ma_data(self, periods: List[int] = [5, 10, 20]) -> Dict[int, List[Dict]]:
        """计算并返回移动平均线数据"""
        visible_data = self.full_data.iloc[:self.current_index + 1].copy()
        adjusted_data = self._calculate_adjusted_prices(visible_data, self.adjustment_mode)
        
        ma_data = {}
        
        for period in periods:
            ma_values = adjusted_data['close'].rolling(window=period).mean()
            ma_series = []
            
            for i, (_, row) in enumerate(adjusted_data.iterrows()):
                if not pd.isna(ma_values.iloc[i]):
                    bar_id = i + self.bar_id_offset
                    ma_series.append({
                        'time': int(row['date'].timestamp()),
                        'value': float(ma_values.iloc[i]),
                        'bar_id': bar_id,
                        'is_preview': bar_id <= 0
                    })
            
            ma_data[period] = ma_series
        
        return ma_data
    
    def get_current_bar(self) -> Dict:
        """获取当前K线数据"""
        if self.current_index >= len(self.full_data):
            return None
        
        current_row = self.full_data.iloc[self.current_index]
        
        # 应用复权调整
        adjusted_data = self._calculate_adjusted_prices(
            self.full_data.iloc[self.current_index:self.current_index + 1],
            self.adjustment_mode
        )
        # adjusted_data = self._calculate_adjusted_prices(
        #     self.full_data.iloc[:self.current_index + 1],
        #     self.adjustment_mode
        # )
        adjusted_row = adjusted_data.iloc[0]
        
        bar_id = self.get_current_bar_id()
        
        return {
            'time': int(current_row['date'].timestamp()),
            'open': float(adjusted_row['open']),
            'high': float(adjusted_row['high']),
            'low': float(adjusted_row['low']),
            'close': float(adjusted_row['close']),
            'volume': float(current_row['volume']),
            'bar_id': bar_id,
            'is_preview': bar_id <= 0
        }
    
    def get_current_volume(self) -> Dict:
        """获取当前成交量数据"""
        if self.current_index >= len(self.full_data):
            return None
        
        current_row = self.full_data.iloc[self.current_index]
        bar_id = self.get_current_bar_id()
        
        return {
            'time': int(current_row['date'].timestamp()),
            'value': float(current_row['volume']),
            'bar_id': bar_id,
            'is_preview': bar_id <= 0
        }
    
    def get_current_date(self) -> str:
        """获取当前日期"""
        if self.current_index >= len(self.full_data):
            return None
        
        return self.full_data.iloc[self.current_index]['date'].strftime('%Y-%m-%d')
    
    def get_previous_close(self) -> float:
        """获取前一日收盘价（用于计算涨跌幅）"""
        if self.current_index <= 0:
            return None
        
        previous_data = self._calculate_adjusted_prices(
            self.full_data.iloc[self.current_index-1:self.current_index], 
            self.adjustment_mode
        )
        
        if not previous_data.empty:
            return float(previous_data.iloc[0]['close'])
        return None
    
    def add_trade_marker(self, action: str, price: float):
        """添加交易标记"""
        bar_id = self.get_current_bar_id()
        marker = {
            'bar_id': bar_id,
            'type': 'B' if action == 'buy' else 'S',
            'price': price,
            'time': int(self.full_data.iloc[self.current_index]['date'].timestamp())
        }
        self.trade_markers.append(marker)
    
    def get_trade_markers(self) -> List[Dict]:
        """获取交易标记"""
        return self.trade_markers.copy()
    
    def next_bar(self) -> bool:
        """推进到下一根K线"""
        if self.current_index < self.max_index:
            self.current_index += 1
            
            # 检查是否跨越了除权除息日，如果是则可能需要重新计算复权价格
            self._check_dividend_adjustment()
            
            return True
        return False
    
    def _check_dividend_adjustment(self):
        """检查除权除息调整，并动态更新复权因子"""
        # 只有在动态前复权模式下才需要进行此检查
        if self.adjustment_mode != 'dynamic_forward':
            return

        # 当next_bar被调用时，self.current_index已经指向了下一个bar
        # 动态前复权的核心在于，每次显示K线时，都以当前显示的最后一根K线的复权因子为基准
        # 对之前的所有K线进行调整。_calculate_adjusted_prices 方法已经实现了这个逻辑。
        # 因此，_check_dividend_adjustment 方法在这里不需要做额外的计算或数据修改。
        # 它的存在主要是为了在每次推进K线时，提供一个钩子，确保复权逻辑被重新评估。
        # 只要 self.full_data 中的 'factor' 列是正确的，并且 _calculate_adjusted_prices
        # 能够正确地使用 self.current_index 的 factor 作为基准，动态前复权就能可靠实现。

        pass
    
    def has_next(self) -> bool:
        """是否还有下一根K线"""
        return self.current_index < self.max_index
    
    def reset(self):
        """重置到起始状态（保留预览）"""
        self.current_index = self.preview_bars
        self.trade_markers = []
    
    def jump_to_date(self, target_date: str) -> bool:
        """跳转到指定日期"""
        try:
            target_dt = pd.to_datetime(target_date)
            
            # 查找目标日期的索引
            mask = self.full_data['date'] <= target_dt
            if mask.any():
                self.current_index = mask.sum() - 1
                return True
            return False
        except Exception as e:
            print(f"跳转到日期失败: {e}")
            return False
    
    def get_progress(self) -> Dict:
        """获取回放进度信息"""
        # 计算实际训练进度（不包括预览部分）
        training_current = max(0, self.current_index - self.preview_bars)
        training_total = self.max_index - self.preview_bars
        
        return {
            'current_bar_id': self.get_current_bar_id(),
            'current_index': self.current_index,
            'total_bars': len(self.full_data),
            'training_progress': (training_current / training_total) * 100 if training_total > 0 else 0,
            'current_date': self.get_current_date(),
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.full_data.iloc[-1]['date'].strftime('%Y-%m-%d'),
            'preview_bars': self.preview_bars,
            'is_in_preview': self.get_current_bar_id() <= 0
        }
    
    def get_full_data(self) -> List[Dict]:
        """获取完整的K线数据（用于训练结束后查看完整走势）"""
        # 应用复权调整
        adjusted_data = self._calculate_adjusted_prices(self.full_data, self.adjustment_mode)
        
        # 转换为前端图表格式
        chart_data = []
        for i, (_, row) in enumerate(adjusted_data.iterrows()):
            bar_id = i + self.bar_id_offset
            chart_data.append({
                'time': int(row['date'].timestamp()),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'bar_id': bar_id,
                'is_preview': bar_id <= 0
            })
        
        return chart_data
    
    def get_technical_indicators(self, indicator_type: str = 'MACD') -> Dict:
        """计算技术指标"""
        visible_data = self.full_data.iloc[:self.current_index + 1].copy()
        adjusted_data = self._calculate_adjusted_prices(visible_data, self.adjustment_mode)
        
        if indicator_type == 'MACD':
            return self._calculate_macd(adjusted_data['close'])
        elif indicator_type == 'KDJ':
            return self._calculate_kdj(adjusted_data['high'], adjusted_data['low'], adjusted_data['close'])
        elif indicator_type == 'RSI':
            return self._calculate_rsi(adjusted_data['close'])
        elif indicator_type == 'BOLL':
            return self._calculate_boll(adjusted_data['close'])
        else:
            return {}
    
    def _calculate_macd(self, close_prices: pd.Series, fast=12, slow=26, signal=9) -> Dict:
        """计算MACD指标"""
        try:
            ema_fast = close_prices.ewm(span=fast).mean()
            ema_slow = close_prices.ewm(span=slow).mean()
            
            dif = ema_fast - ema_slow
            dea = dif.ewm(span=signal).mean()
            histogram = (dif - dea) * 2
            
            # 转换为图表格式
            result_data = []
            for i, (dif_val, dea_val, hist_val) in enumerate(zip(dif, dea, histogram)):
                if not (pd.isna(dif_val) or pd.isna(dea_val) or pd.isna(hist_val)):
                    bar_id = i + self.bar_id_offset
                    timestamp = int(self.full_data.iloc[i]['date'].timestamp())
                    result_data.append({
                        'time': timestamp,
                        'dif': float(dif_val),
                        'dea': float(dea_val),
                        'histogram': float(hist_val),
                        'bar_id': bar_id,
                        'is_preview': bar_id <= 0
                    })
            
            return {
                'type': 'MACD',
                'data': result_data
            }
        except Exception as e:
            print(f"计算MACD失败: {e}")
            return {'type': 'MACD', 'data': []}

    def _calculate_kdj(self, high_prices: pd.Series, low_prices: pd.Series, close_prices: pd.Series, n=9, m1=3,
                       m2=3) -> Dict:
        """计算KDJ指标，符合 (N, M1, M2) 标准，默认为 (9, 3, 3)"""
        try:
            # 1. 计算 RSV
            lowest_low = low_prices.rolling(window=n).min()
            highest_high = high_prices.rolling(window=n).max()
            # 避免除以零，并将NaN替换为50（一个中性值）
            rsv = (close_prices - lowest_low) / (highest_high - lowest_low) * 100
            rsv.fillna(50, inplace=True)

            # 2. 计算 K, D, J (使用简单移动平均 SMA)
            k = rsv.rolling(window=m1).mean()
            d = k.rolling(window=m2).mean()
            j = 3 * k - 2 * d

            # 3. 填充数据（与您的逻辑保持一致）
            result_data = []
            for i in range(len(close_prices)):
                k_val, d_val, j_val = k.get(i), d.get(i), j.get(i)
                bar_id = i + self.bar_id_offset
                timestamp = int(self.full_data.iloc[i]['date'].timestamp())

                if pd.isna(k_val) or pd.isna(d_val) or pd.isna(j_val):
                    result_data.append({
                        'time': timestamp,
                        'bar_id': bar_id, 'is_preview': bar_id <= 0
                    })
                else:
                    result_data.append({
                        'time': timestamp,
                        'k': float(k_val), 'd': float(d_val), 'j': float(j_val),
                        'bar_id': bar_id, 'is_preview': bar_id <= 0
                    })

            return {'type': 'KDJ', 'data': result_data}
        except Exception as e:
            print(f"计算KDJ失败: {e}")
            return {'type': 'KDJ', 'data': []}

    def _calculate_rsi(self, close_prices: pd.Series, periods=(6, 12, 24)) -> Dict:
        """计算多周期RSI指标，默认为 (6, 12, 24)"""
        try:
            result_data = []
            rsi_values = {}

            # 1. 对每个周期分别计算RSI
            for period in periods:
                delta = close_prices.diff()

                # 使用 ewm (指数移动平均) 是更标准的RSI算法
                gain = delta.where(delta > 0, 0).ewm(alpha=1 / period, adjust=False).mean()
                loss = -delta.where(delta < 0, 0).ewm(alpha=1 / period, adjust=False).mean()

                # 避免除以零
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_values[f'rsi{period}'] = rsi

            # 2. 组合数据
            for i in range(len(close_prices)):
                bar_id = i + self.bar_id_offset
                timestamp = int(self.full_data.iloc[i]['date'].timestamp())

                data_point = {
                    'time': timestamp,
                    'bar_id': bar_id,
                    'is_preview': bar_id <= 0
                }

                for period in periods:
                    rsi_val = rsi_values[f'rsi{period}'].get(i)
                    if not pd.isna(rsi_val):
                        data_point[f'rsi{period}'] = float(rsi_val)

                result_data.append(data_point)

            return {'type': 'RSI', 'periods': periods, 'data': result_data}
        except Exception as e:
            print(f"计算RSI失败: {e}")
            return {'type': 'RSI', 'data': []}

    def _calculate_boll(self, close_prices: pd.Series, period=20, std_dev=2) -> Dict:
        """计算布林带指标"""
        try:
            ma = close_prices.rolling(window=period).mean()
            std = close_prices.rolling(window=period).std()

            upper = ma + (std * std_dev)
            lower = ma - (std * std_dev)

            # 转换为图表格式
            result_data = []
            for i, (ma_val, upper_val, lower_val) in enumerate(zip(ma, upper, lower)):
                bar_id = i + self.bar_id_offset
                timestamp = int(self.full_data.iloc[i]['date'].timestamp())
                if not (pd.isna(ma_val) or pd.isna(upper_val) or pd.isna(lower_val)):
                    result_data.append({
                        'time': timestamp,
                        'middle': float(ma_val),
                        'upper': float(upper_val),
                        'lower': float(lower_val),
                        'bar_id': bar_id,
                        'is_preview': bar_id <= 0
                    })
                else:
                    result_data.append({
                        'time': timestamp,
                        'bar_id': bar_id,
                        'is_preview': bar_id <= 0
                    })

            return {
                'type': 'BOLL',
                'data': result_data
            }
        except Exception as e:
            print(f"计算BOLL失败: {e}")
            return {'type': 'BOLL', 'data': []}
