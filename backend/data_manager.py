import os
import pandas as pd
import numpy as np
import akshare as ak
import json
import random
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

class DataManager:
    """数据管理器，负责股票数据的下载、存储和读取"""
    
    def __init__(self, data_dir='../data'):
        self.data_dir = data_dir
        self.kline_dir = os.path.join(data_dir, 'kline_raw')
        self.factor_dir = os.path.join(data_dir, 'factor')
        self.dividend_dir = os.path.join(data_dir, 'ex_dividend')
        
        # 确保目录存在
        os.makedirs(self.kline_dir, exist_ok=True)
        os.makedirs(self.factor_dir, exist_ok=True)
        os.makedirs(self.dividend_dir, exist_ok=True)
        
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
    
    def download_stock_data(self, stock_code: str, start_date: str = '2010-01-01'):
        """下载单只股票的历史数据"""
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
    
    def get_stock_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """获取股票K线数据"""
        try:
            kline_path = os.path.join(self.kline_dir, f'{stock_code}.csv')
            if os.path.exists(kline_path):
                data = pd.read_csv(kline_path)
                data['date'] = pd.to_datetime(data['date'])
                return data
            else:
                # 尝试下载数据
                if self.download_stock_data(stock_code):
                    return self.get_stock_data(stock_code)
                return None
        except Exception as e:
            print(f"获取股票 {stock_code} 数据失败: {e}")
            return None
    
    def get_factor_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """获取复权因子数据"""
        try:
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
    
    def validate_stock_and_date(self, stock_code: str, start_date: str) -> bool:
        """验证股票代码和日期的有效性"""
        try:
            # 检查股票是否存在
            data = self.get_stock_data(stock_code)
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
    
    def get_random_stock(self, sector: str = 'all', year_range: str = '2020-2024') -> Tuple[str, str]:
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
            if self.validate_stock_and_date(stock_code, start_date):
                return stock_code, start_date
            else:
                # 如果验证失败，递归重试
                return self.get_random_stock(sector, year_range)
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

