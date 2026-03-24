import os
import pandas as pd
import numpy as np
import akshare as ak
import json
import random
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

try:
    from xtquant import xtdata
    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False


class DataManager:
    """数据管理器，负责股票数据的下载、存储和读取"""
    
    def __init__(self, data_dir='./data'):
        self.data_dir = data_dir
        self.kline_dir = os.path.join(data_dir, 'kline_raw')
        self.factor_dir = os.path.join(data_dir, 'factor')
        self.dividend_dir = os.path.join(data_dir, 'ex_dividend')
        self.offline_dir = os.path.join(data_dir, 'a_market_offline')
        
        # 确保目录存在
        os.makedirs(self.kline_dir, exist_ok=True)
        os.makedirs(self.factor_dir, exist_ok=True)
        os.makedirs(self.dividend_dir, exist_ok=True)
        os.makedirs(self.offline_dir, exist_ok=True)
        
        # 股票列表缓存
        self.stock_list = None
        self.stock_names = {}
    
    def download_stock_list(self):
        """下载股票列表"""
        try:
            print("正在下载股票列表...")
            # 获取A股股票列表
            stock_list = ak.stock_info_a_code_name()
            
            # 保存到文件
            stock_list_path = os.path.join(self.data_dir, 'stock_list.csv')
            stock_list.to_csv(stock_list_path, index=False, encoding='utf-8')
            
            # 创建股票名称映射
            self.stock_names = dict(zip(stock_list['code'], stock_list['name']))
            names_path = os.path.join(self.data_dir, 'stock_names.json')
            with open(names_path, 'w', encoding='utf-8') as f:
                json.dump(self.stock_names, f, ensure_ascii=False, indent=2)
            
            self.stock_list = stock_list
            print(f"股票列表下载完成，共 {len(stock_list)} 只股票")
            return True
        except Exception as e:
            print(f"下载股票列表失败: {e}")
            return False
    
    def load_stock_list(self):
        """加载股票列表"""
        try:
            stock_list_path = os.path.join(self.data_dir, 'stock_list.csv')
            names_path = os.path.join(self.data_dir, 'stock_names.json')
            
            if os.path.exists(stock_list_path) and os.path.exists(names_path):
                self.stock_list = pd.read_csv(stock_list_path, dtype={'code': str})
                with open(names_path, 'r', encoding='utf-8') as f:
                    self.stock_names = json.load(f)
                return True
            else:
                return self.download_stock_list()
        except Exception as e:
            print(f"加载股票列表失败: {e}")
            return self.download_stock_list()
    
    def _format_xt_code(self, stock_code: str) -> str:
        """为xtdata格式化股票代码，添加市场后缀"""
        if stock_code.startswith(('60', '68', '69')):
            return f"{stock_code}.SH"
        elif stock_code.startswith(('00', '30')):
            return f"{stock_code}.SZ"
        elif stock_code.startswith(('43', '83', '87', '92')):
            return f"{stock_code}.BJ"
        return stock_code
        
    def _get_offline_file(self, stock_code: str) -> Optional[str]:
        """获取离线数据文件路径"""
        if not os.path.exists(self.offline_dir):
            return None
        for suffix in ['.SZ', '.SH', '.BJ']:
            path = os.path.join(self.offline_dir, f"{stock_code}{suffix}.csv")
            if os.path.exists(path):
                return path
        return None

    def download_stock_data(self, stock_code: str, start_date: str = '2010-01-01', source: str = 'akshare') -> bool:
        """下载单只股票的历史数据，支持akshare和xtdata双源"""
        if source == 'xtdata':
            return self._download_stock_data_xt(stock_code, start_date)
        return self._download_stock_data_ak(stock_code, start_date)

    def _download_stock_data_xt(self, stock_code: str, start_date: str) -> bool:
        """使用 xtquant 的 xtdata 下载数据"""
        if not XTDATA_AVAILABLE:
            print("xtquant 未安装或无法导入。")
            return False
            
        try:
            print(f"正在通过 xtdata 下载 {stock_code} 的历史数据...")
            xt_code = self._format_xt_code(stock_code)
            start_time = start_date.replace('-', '')
            end_time = datetime.now().strftime('%Y%m%d')
            
            # 尝试下载
            xtdata.download_history_data2(
                stock_list=[xt_code], period='1d', start_time=start_time, end_time=end_time
            )
            
            # 获取未复权原始数据
            raw_dict = xtdata.get_market_data(
                field_list=['time', 'open', 'close', 'high', 'low', 'volume', 'amount'],
                stock_list=[xt_code], period='1d',
                start_time=start_time, end_time=end_time,
                dividend_type='none', fill_data=True
            )
            
            # dataframe转换
            df_raw = pd.DataFrame({
                'date': raw_dict['time'].T[xt_code],
                'open': raw_dict['open'].T[xt_code],
                'close': raw_dict['close'].T[xt_code],
                'high': raw_dict['high'].T[xt_code],
                'low': raw_dict['low'].T[xt_code],
                'volume': raw_dict['volume'].T[xt_code],
                'amount': raw_dict['amount'].T[xt_code]
            })
            
            if df_raw.empty:
                print(f"实时/历史缓存中未获取到 {stock_code} 数据")
                return False
                
            # 重命名列并格式化时间
            df_raw['date'] = df_raw['date'].astype(str).str[:13]
            df_raw['date'] = pd.to_datetime(df_raw['date'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d')
            
            # 获取前复权数据以计算复权因子
            adj_dict = xtdata.get_market_data(
                field_list=['time', 'close'],
                stock_list=[xt_code], period='1d',
                start_time=start_time, end_time=end_time,
                dividend_type='front', fill_data=True
            )
            
            # 保存K线
            kline_path = os.path.join(self.kline_dir, f'{stock_code}.csv')
            df_raw.to_csv(kline_path, index=False, encoding='utf-8')
            
            if not adj_dict['close'].empty:
                df_adj = pd.DataFrame({'date': adj_dict['time'][xt_code], 'close_adj': adj_dict['close'][xt_code]})
                df_adj['date'] = df_adj['date'].astype(str).str[:8]
                df_adj['date'] = pd.to_datetime(df_adj['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                
                # 合并计算因子 factor
                merged = pd.merge(df_raw[['date', 'close']], df_adj[['date', 'close_adj']], on='date')
                merged['factor'] = merged['close_adj'] / merged['close']
                
                factor_path = os.path.join(self.factor_dir, f'{stock_code}.csv')
                merged[['date', 'factor']].to_csv(factor_path, index=False, encoding='utf-8')
            
            print(f"xtdata 获取并处理股票 {stock_code} 数据完成")
            return True
        except Exception as e:
            print(f"通过 xtdata 下载 {stock_code} 失败: {e}")
            return False

    def _download_stock_data_ak(self, stock_code: str, start_date: str = '2010-01-01') -> bool:
        """旧版 akshare 下载逻辑"""
        try:
            print(f"正在下载 {stock_code} 的历史数据...")
            
            # 下载日K线数据
            kline_data = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=datetime.now().strftime('%Y%m%d'),
                adjust=""  # 不复权
            )
            
            if kline_data.empty:
                print(f"股票 {stock_code} 无数据")
                return False

            kline_data.drop('股票代码', axis=1, inplace=True)

            # 重命名列
            kline_data.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'turnover', 'amplitude', 'change_pct', 'change_amount', 'turnover_rate']
            
            # 保存K线数据
            kline_path = os.path.join(self.kline_dir, f'{stock_code}.csv')
            kline_data.to_csv(kline_path, index=False, encoding='utf-8')
            
            # 下载复权因子数据
            try:
                factor_data = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date.replace('-', ''),
                    end_date=datetime.now().strftime('%Y%m%d'),
                    adjust="qfq"  # 前复权
                )
                
                if not factor_data.empty:
                    factor_data.drop('股票代码', axis=1, inplace=True)
                    # 计算复权因子
                    factor_data.columns = ['date', 'open_adj', 'close_adj', 'high_adj', 'low_adj', 'volume', 'turnover', 'amplitude', 'change_pct', 'change_amount', 'turnover_rate']
                    
                    # 合并数据计算复权因子
                    merged = pd.merge(kline_data[['date', 'close']], factor_data[['date', 'close_adj']], on='date')
                    merged['factor'] = merged['close_adj'] / merged['close']
                    
                    factor_path = os.path.join(self.factor_dir, f'{stock_code}.csv')
                    merged[['date', 'factor']].to_csv(factor_path, index=False, encoding='utf-8')
            except Exception as e:
                print(f"下载复权因子失败: {e}")
            
            # # 下载除权除息数据
            # try:
            #     dividend_data = ak.stock_div_df(symbol=stock_code)
            #     if not dividend_data.empty:
            #         dividend_path = os.path.join(self.dividend_dir, f'{stock_code}.csv')
            #         dividend_data.to_csv(dividend_path, index=False, encoding='utf-8')
            # except Exception as e:
            #     print(f"下载除权除息数据失败: {e}")
            
            print(f"股票 {stock_code} 数据下载完成")
            return True
        except Exception as e:
            print(f"下载股票 {stock_code} 数据失败: {e}")
            return False
    
    def get_stock_data(self, stock_code: str, source: str = 'akshare') -> Optional[pd.DataFrame]:
        """获取股票K线数据"""
        try:
            if source == 'offline':
                offline_path = self._get_offline_file(stock_code)
                if offline_path:
                    data = pd.read_csv(offline_path, encoding='utf-8')
                    # 适配离线数据列名
                    if '交易日' in data.columns:
                        data = data.rename(columns={
                            '交易日': 'date', '开盘价': 'open', '最高价': 'high', 
                            '最低价': 'low', '收盘价': 'close', '成交量（手）': 'volume', 
                            '成交额（千元）': 'amount'
                        })
                    if 'date' in data.columns:
                        data['date'] = data['date'].astype(str)
                        if data['date'].iloc[0].isdigit() and len(data['date'].iloc[0]) == 8:
                            data['date'] = pd.to_datetime(data['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                        data['date'] = pd.to_datetime(data['date'])
                        data = data.sort_values('date').reset_index(drop=True)
                        return data
                    return None
                else:
                    print(f"找不到离线数据: {stock_code}")
                    return None

            kline_path = os.path.join(self.kline_dir, f'{stock_code}.csv')
            if os.path.exists(kline_path):
                data = pd.read_csv(kline_path)
                data['date'] = pd.to_datetime(data['date'])
                return data
            else:
                # 尝试下载数据
                if self.download_stock_data(stock_code, start_date='2010-01-01', source=source):
                    return self.get_stock_data(stock_code, source=source)
                return None
        except Exception as e:
            print(f"获取股票 {stock_code} 数据失败: {e}")
            return None
    
    def get_factor_data(self, stock_code: str, source: str = 'akshare') -> Optional[pd.DataFrame]:
        """获取复权因子数据"""
        try:
            if source == 'offline':
                offline_path = self._get_offline_file(stock_code)
                if offline_path:
                    data = pd.read_csv(offline_path, encoding='utf-8')
                    if '交易日' in data.columns and '复权因子' in data.columns:
                        data = data[['交易日', '复权因子']].rename(columns={'交易日': 'date', '复权因子': 'factor'})
                    elif 'date' in data.columns and 'factor' in data.columns:
                        data = data[['date', 'factor']]
                    else:
                        print(f"离线数据 {stock_code} 中找不到复权因子列")
                        return None
                    
                    data['date'] = data['date'].astype(str)
                    if data['date'].iloc[0].isdigit() and len(data['date'].iloc[0]) == 8:
                        data['date'] = pd.to_datetime(data['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                    data['date'] = pd.to_datetime(data['date'])
                    data = data.sort_values('date').reset_index(drop=True)
                    return data
                return None

            factor_path = os.path.join(self.factor_dir, f'{stock_code}.csv')
            if os.path.exists(factor_path):
                data = pd.read_csv(factor_path)
                data['date'] = pd.to_datetime(data['date'])
                return data
            return None
        except Exception as e:
            print(f"获取复权因子 {stock_code} 失败: {e}")
            return None
    
    def get_dividend_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """获取除权除息数据"""
        try:
            dividend_path = os.path.join(self.dividend_dir, f'{stock_code}.csv')
            if os.path.exists(dividend_path):
                data = pd.read_csv(dividend_path)
                return data
            return None
        except Exception as e:
            print(f"获取除权除息 {stock_code} 数据失败: {e}")
            return None
    
    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        if not self.stock_names:
            self.load_stock_list()
        
        return self.stock_names.get(stock_code, f"股票{stock_code}")
    
    def validate_stock_and_date(self, stock_code: str, start_date: str, source: str = 'akshare') -> bool:
        """验证股票代码和日期的有效性"""
        try:
            # 检查股票是否存在
            data = self.get_stock_data(stock_code, source)
            if data is None or data.empty:
                return False
            
            # 检查日期是否在数据范围内
            start_dt = pd.to_datetime(start_date)
            if start_dt < data['date'].min() or start_dt > data['date'].max():
                return False
            
            return True
        except Exception as e:
            print(f"验证股票和日期失败: {e}")
            return False
    
    def get_random_stock(self, sector: str = 'all', year_range: str = '2020-2024', source: str = 'akshare') -> Tuple[str, str]:
        """随机选择股票和起始日期"""
        try:
            if self.stock_list is None:
                self.load_stock_list()
            
            # 根据板块筛选股票
            if sector == 'main':
                # 主板股票（60开头和000开头）
                filtered_stocks = self.stock_list[
                    self.stock_list['code'].str.startswith(('60', '000'))
                ]
            elif sector == 'gem':
                # 创业板股票（30开头）
                filtered_stocks = self.stock_list[
                    self.stock_list['code'].str.startswith('30')
                ]
            elif sector == 'sme':
                # 中小板股票（002开头）
                filtered_stocks = self.stock_list[
                    self.stock_list['code'].str.startswith('002')
                ]
            else:
                # 全部股票
                filtered_stocks = self.stock_list
            
            # 随机选择股票
            if filtered_stocks.empty:
                # 如果筛选后没有股票，使用全部股票
                filtered_stocks = self.stock_list
            
            stock_code = random.choice(filtered_stocks['code'].tolist())
            
            # 根据年份范围随机选择起始日期
            year_start, year_end = map(int, year_range.split('-'))
            
            # 随机选择年份和月份
            random_year = random.randint(year_start, year_end)
            random_month = random.randint(1, 12)
            random_day = random.randint(1, 28)  # 使用28避免月份天数问题
            
            start_date = f"{random_year}-{random_month:02d}-{random_day:02d}"
            
            # 验证选择的股票和日期
            if self.validate_stock_and_date(stock_code, start_date, source=source):
                return stock_code, start_date
            else:
                # 如果验证失败，递归重试
                return self.get_random_stock(sector, year_range, source=source)
        except Exception as e:
            print(f"随机选择股票失败: {e}")
            # 返回默认值
            return '000001', '2020-01-01'
    
    def batch_download_data(self, stock_codes: List[str] = None, start_date: str = '2010-01-01'):
        """批量下载股票数据"""
        if stock_codes is None:
            if not self.stock_list:
                self.load_stock_list()
            stock_codes = self.stock_list['code'].tolist()
        
        total = len(stock_codes)
        success_count = 0
        
        for i, stock_code in enumerate(stock_codes):
            print(f"进度: {i+1}/{total} - {stock_code}")
            if self.download_stock_data(stock_code, start_date):
                success_count += 1
        
        print(f"批量下载完成，成功: {success_count}/{total}")
        return success_count, total

# 数据下载脚本
def download_all_data():
    """下载全部A股数据的脚本"""
    data_manager = DataManager()
    
    print("开始下载A股数据...")
    print("1. 下载股票列表...")
    data_manager.download_stock_list()
    
    print("2. 下载股票历史数据...")
    # 可以选择下载全部股票或部分股票
    # data_manager.batch_download_data()  # 下载全部
    
    # 或者下载部分热门股票作为示例
    sample_stocks = ['000001', '000002', '600000', '600036', '000858', '002415', '300059', '300750']
    data_manager.batch_download_data(sample_stocks)
    
    print("数据下载完成！")

if __name__ == '__main__':
    download_all_data()

