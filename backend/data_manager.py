import csv
import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd

try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False

try:
    from mootdx.quotes import Quotes

    MOOTDX_AVAILABLE = True
except ImportError:
    MOOTDX_AVAILABLE = False


class DataManager:
    """管理股票数据下载、缓存、周K合成以及离线增量补数。"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.kline_dir = os.path.join(data_dir, "kline_raw")
        self.factor_dir = os.path.join(data_dir, "factor")
        self.dividend_dir = os.path.join(data_dir, "ex_dividend")
        self.offline_dir = os.path.join(data_dir, "a_market_offline")

        os.makedirs(self.kline_dir, exist_ok=True)
        os.makedirs(self.factor_dir, exist_ok=True)
        os.makedirs(self.dividend_dir, exist_ok=True)
        os.makedirs(self.offline_dir, exist_ok=True)

        self.stock_list = None
        self.stock_names: Dict[str, str] = {}
        self._offline_stock_codes_cache: Optional[List[str]] = None
        self._offline_date_range_cache: Dict[str, Optional[Tuple[pd.Timestamp, pd.Timestamp]]] = {}

    def download_stock_list(self) -> bool:
        """下载 A 股股票列表。"""
        try:
            stock_list = ak.stock_info_a_code_name()
            stock_list["code"] = stock_list["code"].astype(str).str.zfill(6)

            stock_list_path = os.path.join(self.data_dir, "stock_list.csv")
            stock_list.to_csv(stock_list_path, index=False, encoding="utf-8")

            self.stock_names = dict(zip(stock_list["code"], stock_list["name"]))
            with open(os.path.join(self.data_dir, "stock_names.json"), "w", encoding="utf-8") as f:
                json.dump(self.stock_names, f, ensure_ascii=False, indent=2)

            self.stock_list = stock_list
            return True
        except Exception as e:
            print(f"下载股票列表失败: {e}")
            return False

    def load_stock_list(self) -> bool:
        """加载股票列表缓存。"""
        try:
            stock_list_path = os.path.join(self.data_dir, "stock_list.csv")
            names_path = os.path.join(self.data_dir, "stock_names.json")

            if os.path.exists(stock_list_path) and os.path.exists(names_path):
                self.stock_list = pd.read_csv(stock_list_path, dtype={"code": str})
                with open(names_path, "r", encoding="utf-8") as f:
                    self.stock_names = json.load(f)
                return True

            return self.download_stock_list()
        except Exception as e:
            print(f"加载股票列表失败: {e}")
            return self.download_stock_list()

    def get_available_sources(self) -> List[Dict]:
        """返回当前可用数据源列表。"""
        return [
            {
                "value": "akshare",
                "label": "AKShare",
                "available": True,
                "kind": "online",
                "supports_incremental_sync": True,
                "supports_factor": True,
                "description": "免费公网源，默认推荐。",
            },
            {
                "value": "xtdata",
                "label": "XTQuant / xtdata",
                "available": XTDATA_AVAILABLE,
                "kind": "online",
                "supports_incremental_sync": True,
                "supports_factor": True,
                "description": "QMT 本地数据源，需要本机已安装相关环境。",
            },
            {
                "value": "mootdx",
                "label": "mootdx",
                "available": MOOTDX_AVAILABLE,
                "kind": "online",
                "supports_incremental_sync": True,
                "supports_factor": False,
                "description": "通达信协议源，适合作为补充在线源。",
            },
            {
                "value": "offline",
                "label": "本地离线数据",
                "available": True,
                "kind": "offline",
                "supports_incremental_sync": False,
                "supports_factor": True,
                "description": "读取 data/a_market_offline 中的本地文件。",
            },
        ]

    def _get_market_suffix(self, stock_code: str) -> str:
        if stock_code.startswith(("60", "68", "69")):
            return ".SH"
        if stock_code.startswith(("00", "30")):
            return ".SZ"
        if stock_code.startswith(("43", "83", "87", "92")):
            return ".BJ"
        return ".SZ"

    def _format_xt_code(self, stock_code: str) -> str:
        return f"{stock_code}{self._get_market_suffix(stock_code)}"

    def _get_tdx_market_code(self, stock_code: str) -> int:
        if stock_code.startswith(("60", "68", "69")):
            return 1
        return 0

    def _normalize_stock_code(self, stock_code: str) -> str:
        code = str(stock_code or "").strip().upper()
        if "." in code:
            code = code.split(".", 1)[0]
        digits = "".join(ch for ch in code if ch.isdigit())
        if not digits:
            return ""
        return digits[-6:].zfill(6)

    def _get_offline_file(self, stock_code: str) -> Optional[str]:
        stock_code = self._normalize_stock_code(stock_code)
        if not stock_code:
            return None
        for suffix in (".SZ", ".SH", ".BJ"):
            candidate = os.path.join(self.offline_dir, f"{stock_code}{suffix}.csv")
            if os.path.exists(candidate):
                return candidate
        return None

    def _read_csv_with_fallback(self, path: str, **kwargs) -> pd.DataFrame:
        last_error = None
        for encoding in ("utf-8", "utf-8-sig", "gbk"):
            try:
                return pd.read_csv(path, encoding=encoding, **kwargs)
            except UnicodeDecodeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        return pd.read_csv(path, **kwargs)

    def _coalesce_duplicate_columns(self, data: pd.DataFrame) -> pd.DataFrame:
        if data is None or data.empty:
            return data

        normalized_columns = [str(col).lstrip("\ufeff").strip() for col in data.columns]
        data = data.copy()
        data.columns = normalized_columns

        if not pd.Index(normalized_columns).duplicated().any():
            return data

        collapsed_columns: List[str] = []
        collapsed_series: Dict[str, pd.Series] = {}
        for column in normalized_columns:
            if column in collapsed_series:
                continue

            same_name_columns = data.loc[:, data.columns == column]
            if isinstance(same_name_columns, pd.Series) or same_name_columns.shape[1] == 1:
                collapsed_series[column] = same_name_columns.iloc[:, 0] if isinstance(same_name_columns, pd.DataFrame) else same_name_columns
            else:
                collapsed_series[column] = same_name_columns.bfill(axis=1).iloc[:, 0]
            collapsed_columns.append(column)

        return pd.DataFrame({column: collapsed_series[column] for column in collapsed_columns}, index=data.index)

    def _parse_date_series(self, series: pd.Series) -> pd.Series:
        raw = series.copy()
        if not isinstance(raw, pd.Series):
            raw = pd.Series(raw)

        raw_str = raw.astype(str).str.strip()
        raw_str = raw_str.replace({"": None, "nan": None, "NaT": None, "None": None})
        parsed = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
        numeric_mask = raw_str.notna() & raw_str.str.fullmatch(r"\d{8}")

        if numeric_mask.any():
            parsed.loc[numeric_mask] = pd.to_datetime(
                raw_str.loc[numeric_mask],
                format="%Y%m%d",
                errors="coerce",
            )

        if (~numeric_mask).any():
            parsed.loc[~numeric_mask] = pd.to_datetime(raw_str.loc[~numeric_mask], errors="coerce")

        return parsed

    def _read_last_nonempty_line(self, path: str, encoding: str) -> Optional[str]:
        with open(path, "rb") as file:
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            buffer = b""

            while file_size > 0:
                read_size = min(4096, file_size)
                file_size -= read_size
                file.seek(file_size)
                buffer = file.read(read_size) + buffer

                for raw_line in reversed(buffer.splitlines()):
                    stripped = raw_line.strip()
                    if stripped:
                        return stripped.decode(encoding, errors="ignore")

        return None

    def _extract_csv_field(self, line: str, index: int) -> Optional[str]:
        try:
            row = next(csv.reader([line]))
        except Exception:
            return None
        if index >= len(row):
            return None
        return row[index]

    def _get_offline_stock_codes(self) -> List[str]:
        if self._offline_stock_codes_cache is not None:
            return list(self._offline_stock_codes_cache)

        stock_codes = set()
        for filename in os.listdir(self.offline_dir):
            if not filename.lower().endswith(".csv"):
                continue
            stock_code = self._normalize_stock_code(os.path.splitext(filename)[0])
            if stock_code:
                stock_codes.add(stock_code)

        self._offline_stock_codes_cache = sorted(stock_codes)
        return list(self._offline_stock_codes_cache)

    def _filter_stock_codes_by_sector(self, stock_codes: List[str], sector: str) -> List[str]:
        if sector == "main":
            prefixes = ("60", "000", "001", "003")
            return [code for code in stock_codes if code.startswith(prefixes)]
        if sector == "gem":
            return [code for code in stock_codes if code.startswith("30")]
        if sector == "sme":
            return [code for code in stock_codes if code.startswith("002")]
        return list(stock_codes)

    def _resolve_training_range(self, date_start: str, date_end: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
        raw_start = str(date_start or "").strip()
        raw_end = str(date_end or "").strip()

        if len(raw_start) == 9 and raw_start[:4].isdigit() and raw_start[4] == "-" and raw_start[5:].isdigit():
            start_year = int(raw_start[:4])
            end_year = int(raw_start[5:])
            range_start = pd.Timestamp(year=start_year, month=1, day=1)
            range_end = pd.Timestamp(year=end_year, month=12, day=31)
        else:
            range_start = pd.to_datetime(raw_start)
            range_end = pd.to_datetime(raw_end or raw_start)

        if range_end < range_start:
            raise ValueError("结束日期不能早于开始日期")

        return range_start.normalize(), range_end.normalize()

    def _random_date_in_range(self, range_start: pd.Timestamp, range_end: pd.Timestamp) -> str:
        delta_days = max(0, (range_end.normalize() - range_start.normalize()).days)
        chosen = range_start.normalize() + timedelta(days=random.randint(0, delta_days))
        return chosen.strftime("%Y-%m-%d")

    def _get_offline_date_range(self, stock_code: str) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
        stock_code = self._normalize_stock_code(stock_code)
        if not stock_code:
            return None
        if stock_code in self._offline_date_range_cache:
            return self._offline_date_range_cache[stock_code]

        offline_path = self._get_offline_file(stock_code)
        if not offline_path:
            self._offline_date_range_cache[stock_code] = None
            return None

        last_error = None
        for encoding in ("utf-8", "utf-8-sig", "gbk"):
            try:
                with open(offline_path, "r", encoding=encoding, newline="") as file:
                    reader = csv.reader(file)
                    header = next(reader, None)
                    first_row = next(reader, None)

                if not header or not first_row:
                    self._offline_date_range_cache[stock_code] = None
                    return None

                normalized_header = [col.lstrip("\ufeff") for col in header]
                date_index = next(
                    (idx for idx, col in enumerate(normalized_header) if col in {"交易日", "交易日期", "date"}),
                    None,
                )
                if date_index is None:
                    self._offline_date_range_cache[stock_code] = None
                    return None

                first_date = first_row[date_index] if date_index < len(first_row) else None
                last_line = self._read_last_nonempty_line(offline_path, encoding)
                last_date = self._extract_csv_field(last_line, date_index) if last_line else None
                candidate_dates = [value for value in (first_date, last_date) if value]
                parsed_dates = self._parse_date_series(pd.Series(candidate_dates)).dropna()
                if parsed_dates.empty:
                    self._offline_date_range_cache[stock_code] = None
                    return None

                date_range = (parsed_dates.min(), parsed_dates.max())
                self._offline_date_range_cache[stock_code] = date_range
                return date_range
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error

        self._offline_date_range_cache[stock_code] = None
        return None

    def _get_stock_date_range(
        self,
        stock_code: str,
        source: str = "akshare",
        interval: str = "daily",
    ) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
        stock_code = self._normalize_stock_code(stock_code)
        if source == "offline":
            return self._get_offline_date_range(stock_code)

        data = self.get_stock_data(stock_code, source=source, interval=interval)
        if data is None or data.empty:
            return None
        return data["date"].min(), data["date"].max()

    def get_stock_universe(self, market: str = "all") -> List[str]:
        if self.stock_list is None:
            self.load_stock_list()

        market_key = (market or "all").lower()
        if self.stock_list is None or self.stock_list.empty:
            stock_codes = self._get_offline_stock_codes()
            if market_key == "sh":
                return [code for code in stock_codes if code.startswith(("60", "68", "69"))]
            if market_key == "sz":
                return [code for code in stock_codes if code.startswith(("00", "001", "002", "003", "30"))]
            if market_key == "bj":
                return [code for code in stock_codes if code.startswith(("43", "83", "87", "92"))]
            return stock_codes

        stock_codes = self.stock_list["code"].dropna().astype(str).str.zfill(6)
        if market_key == "sh":
            stock_codes = stock_codes[stock_codes.str.startswith(("60", "68", "69"))]
        elif market_key == "sz":
            stock_codes = stock_codes[stock_codes.str.startswith(("00", "001", "002", "003", "30"))]
        elif market_key == "bj":
            stock_codes = stock_codes[stock_codes.str.startswith(("43", "83", "87", "92"))]

        return stock_codes.drop_duplicates().tolist()

    def _normalize_daily_kline(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        if df is None or df.empty:
            return None

        data = self._coalesce_duplicate_columns(df.copy())
        if "股票代码" in data.columns:
            data = data.drop(columns=["股票代码"])

        if "日期" in data.columns:
            rename_map = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "change_pct",
                "涨跌额": "change_amount",
                "换手率": "turnover_rate",
            }
            data = data.rename(columns=rename_map)
        elif "datetime" in data.columns:
            rename_map = {
                "datetime": "date",
                "open": "open",
                "close": "close",
                "high": "high",
                "low": "low",
                "vol": "volume",
                "volume": "volume",
                "amount": "amount",
            }
            data = data.rename(columns=rename_map)
        elif "date" not in data.columns:
            columns = list(data.columns)
            expected = [
                "date",
                "open",
                "close",
                "high",
                "low",
                "volume",
                "amount",
                "amplitude",
                "change_pct",
                "change_amount",
                "turnover_rate",
            ]
            if len(columns) >= 6:
                data.columns = expected[: len(columns)]

        data = self._coalesce_duplicate_columns(data)
        data = data.drop(columns=["year", "month", "day", "hour", "minute", "code"], errors="ignore")

        required = ["date", "open", "close", "high", "low", "volume"]
        if not set(required).issubset(set(data.columns)):
            return None

        data["date"] = self._parse_date_series(data["date"])
        for col in ["open", "close", "high", "low", "volume", "amount", "turnover_rate"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        data = data.dropna(subset=["date", "open", "close", "high", "low", "volume"])
        data = data.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        return data

    def _normalize_factor_data(self, raw_df: Optional[pd.DataFrame], base_df: Optional[pd.DataFrame] = None) -> Optional[pd.DataFrame]:
        if raw_df is None or raw_df.empty:
            return None

        data = raw_df.copy()
        if "股票代码" in data.columns:
            data = data.drop(columns=["股票代码"])

        if "日期" in data.columns:
            rename_map = {
                "日期": "date",
                "收盘": "close_adj",
                "close": "close_adj",
            }
            data = data.rename(columns=rename_map)
        elif "date" not in data.columns and len(data.columns) >= 2:
            columns = list(data.columns)
            fallback = ["date", "open_adj", "close_adj", "high_adj", "low_adj", "volume", "amount"]
            data.columns = fallback[: len(columns)]

        if "date" not in data.columns:
            return None

        data["date"] = pd.to_datetime(data["date"])

        if "factor" in data.columns:
            factor_df = data[["date", "factor"]].copy()
        elif "close_adj" in data.columns and base_df is not None and not base_df.empty:
            merged = pd.merge(
                base_df[["date", "close"]],
                data[["date", "close_adj"]],
                on="date",
                how="inner",
            )
            merged["factor"] = merged["close_adj"] / merged["close"]
            factor_df = merged[["date", "factor"]]
        else:
            return None

        factor_df["factor"] = pd.to_numeric(factor_df["factor"], errors="coerce").fillna(1.0)
        factor_df = factor_df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        return factor_df

    def _normalize_offline_data(self, data: pd.DataFrame) -> Optional[pd.DataFrame]:
        if data is None or data.empty:
            return None

        df = self._coalesce_duplicate_columns(data.copy())
        rename_map = {
            "date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "amount": "amount",
            "turnover_rate": "turnover_rate",
            "factor": "factor",
            "交易日": "date",
            "交易日期": "date",
            "开盘价": "open",
            "最高价": "high",
            "最低价": "low",
            "收盘价": "close",
            "成交量（手）": "volume",
            "成交量(手)": "volume",
            "成交额（千元）": "amount",
            "成交额(千元)": "amount",
            "换手率（%）": "turnover_rate",
            "换手率(%)": "turnover_rate",
            "复权因子": "factor",
        }
        df = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})
        df = self._coalesce_duplicate_columns(df)

        if "date" not in df.columns:
            return None

        df["date"] = self._parse_date_series(df["date"])

        required = ["date", "open", "high", "low", "close", "volume"]
        if not set(required).issubset(df.columns):
            return None

        for col in ["open", "high", "low", "close", "volume", "amount", "turnover_rate", "factor"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=required)
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        return df

    def _resample_to_weekly(self, data: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        if data is None or data.empty:
            return data

        df = data.copy()
        df = df.sort_values("date").set_index("date")
        if set(df.columns) == {"factor"}:
            weekly_factor = df.resample("W-FRI").last().dropna().reset_index()
            return weekly_factor

        aggregations = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }

        if "amount" in df.columns:
            aggregations["amount"] = "sum"
        if "turnover_rate" in df.columns:
            aggregations["turnover_rate"] = "sum"
        if "factor" in df.columns:
            aggregations["factor"] = "last"

        weekly = df.resample("W-FRI").agg(aggregations)
        weekly = weekly.dropna(subset=["open", "high", "low", "close"])
        weekly = weekly.reset_index()
        return weekly

    def _slice_date_range(
        self,
        data: Optional[pd.DataFrame],
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
    ) -> Optional[pd.DataFrame]:
        if data is None or data.empty:
            return data

        frame = data.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        if start_date is not None:
            frame = frame[frame["date"] >= pd.to_datetime(start_date)]
        if end_date is not None:
            frame = frame[frame["date"] <= pd.to_datetime(end_date)]
        return frame.reset_index(drop=True)

    def _normalize_sync_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[pd.Timestamp, pd.Timestamp]:
        range_start = pd.to_datetime(start_date).normalize() if start_date else pd.Timestamp("2010-01-01")
        range_end = pd.to_datetime(end_date).normalize() if end_date else pd.Timestamp(datetime.now().date())
        if range_end < range_start:
            raise ValueError("补数结束日期不能早于开始日期")
        return range_start, range_end

    def _supports_factor_refresh(self, source: str) -> bool:
        return source in {"akshare", "xtdata"}

    def _fetch_stock_bundle(
        self,
        stock_code: str,
        start_date: str,
        source: str,
        end_date: Optional[str] = None,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        if source == "xtdata":
            return self._fetch_stock_bundle_xt(stock_code, start_date, end_date=end_date)
        if source == "mootdx":
            return self._fetch_stock_bundle_mootdx(stock_code, start_date, end_date=end_date)
        return self._fetch_stock_bundle_ak(stock_code, start_date, end_date=end_date)

    def _fetch_stock_bundle_ak(
        self,
        stock_code: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        end_date = (end_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        raw_daily = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date,
            adjust="",
        )
        daily_df = self._normalize_daily_kline(raw_daily)
        if daily_df is None or daily_df.empty:
            return {"kline": None, "factor": None}

        factor_df = None
        try:
            raw_qfq = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date,
                adjust="qfq",
            )
            factor_df = self._normalize_factor_data(raw_qfq, daily_df)
        except Exception as e:
            print(f"下载 {stock_code} 复权因子失败: {e}")

        return {"kline": daily_df, "factor": factor_df}

    def _fetch_stock_bundle_xt(
        self,
        stock_code: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtdata 不可用，请先安装并配置 xtquant。")

        xt_code = self._format_xt_code(stock_code)
        start_time = start_date.replace("-", "")
        end_time = (end_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")

        xtdata.download_history_data2(stock_list=[xt_code], period="1d", start_time=start_time, end_time=end_time)

        raw_dict = xtdata.get_market_data(
            field_list=["time", "open", "close", "high", "low", "volume", "amount"],
            stock_list=[xt_code],
            period="1d",
            start_time=start_time,
            end_time=end_time,
            dividend_type="none",
            fill_data=True,
        )
        if not raw_dict or raw_dict.get("time") is None or raw_dict["time"].empty:
            return {"kline": None, "factor": None}

        daily_df = pd.DataFrame(
            {
                "date": raw_dict["time"].T[xt_code],
                "open": raw_dict["open"].T[xt_code],
                "close": raw_dict["close"].T[xt_code],
                "high": raw_dict["high"].T[xt_code],
                "low": raw_dict["low"].T[xt_code],
                "volume": raw_dict["volume"].T[xt_code],
                "amount": raw_dict["amount"].T[xt_code],
            }
        )
        daily_df["date"] = pd.to_datetime(daily_df["date"], unit="ms", utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
        daily_df = self._normalize_daily_kline(daily_df)

        factor_df = None
        try:
            adj_dict = xtdata.get_market_data(
                field_list=["time", "close"],
                stock_list=[xt_code],
                period="1d",
                start_time=start_time,
                end_time=end_time,
                dividend_type="front",
                fill_data=True,
            )
            if adj_dict and adj_dict.get("close") is not None and not adj_dict["close"].empty:
                factor_raw = pd.DataFrame(
                    {
                        "date": adj_dict["time"].T[xt_code],
                        "close_adj": adj_dict["close"].T[xt_code],
                    }
                )
                factor_raw["date"] = pd.to_datetime(factor_raw["date"], unit="ms", utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
                factor_df = self._normalize_factor_data(factor_raw, daily_df)
        except Exception as e:
            print(f"xtdata 复权因子获取失败: {e}")

        return {"kline": daily_df, "factor": factor_df}

    def _fetch_stock_bundle_mootdx(
        self,
        stock_code: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        if not MOOTDX_AVAILABLE:
            raise RuntimeError("mootdx 不可用，请先安装 mootdx。")

        client = None
        try:
            for kwargs in ({"market": "std"}, {}):
                try:
                    client = Quotes.factory(**kwargs)
                    break
                except TypeError:
                    continue

            if client is None:
                client = Quotes.factory()

            bars_df = None
            start_day = pd.to_datetime(start_date).strftime("%Y-%m-%d")
            requested_end = pd.to_datetime(end_date).normalize() if end_date else pd.Timestamp(datetime.now().date())
            end_day = (requested_end + timedelta(days=1)).strftime("%Y-%m-%d")

            if hasattr(client, "get_k_data"):
                try:
                    bars_df = client.get_k_data(stock_code, start_day, end_day)
                except Exception:
                    bars_df = None

            if bars_df is None or bars_df.empty:
                market_code = self._get_tdx_market_code(stock_code)
                attempts = [
                    {"symbol": stock_code, "frequency": 9, "offset": 8000, "market": market_code},
                    {"symbol": stock_code, "frequency": "day", "offset": 8000, "market": market_code},
                    {"symbol": stock_code, "frequency": 9, "offset": 8000},
                    {"symbol": stock_code, "frequency": "day", "offset": 8000},
                ]

                last_error = None
                for kwargs in attempts:
                    try:
                        candidate = client.bars(**kwargs)
                        if candidate is not None and not candidate.empty:
                            bars_df = candidate
                            break
                    except TypeError:
                        continue
                    except Exception as exc:
                        last_error = exc

                if (bars_df is None or bars_df.empty) and last_error is not None:
                    raise last_error

            if bars_df is None or bars_df.empty:
                return {"kline": None, "factor": None}

            daily_df = self._normalize_daily_kline(bars_df)
            if daily_df is None or daily_df.empty:
                return {"kline": None, "factor": None}

            daily_df = self._slice_date_range(
                daily_df,
                start_date=pd.to_datetime(start_date),
                end_date=pd.to_datetime(end_date) if end_date else requested_end,
            )
            return {"kline": daily_df, "factor": None}
        finally:
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass

    def _fetch_factor_range(
        self,
        stock_code: str,
        source: str,
        start_date: str,
        end_date: str,
        base_df: Optional[pd.DataFrame] = None,
    ) -> Optional[pd.DataFrame]:
        if not self._supports_factor_refresh(source):
            return None

        start_dt = pd.to_datetime(start_date).normalize()
        end_dt = pd.to_datetime(end_date).normalize()
        base_frame = self._slice_date_range(base_df, start_dt, end_dt) if base_df is not None else None

        if source == "xtdata":
            if not XTDATA_AVAILABLE:
                return None

            xt_code = self._format_xt_code(stock_code)
            start_time = start_dt.strftime("%Y%m%d")
            end_time = end_dt.strftime("%Y%m%d")
            xtdata.download_history_data2(stock_list=[xt_code], period="1d", start_time=start_time, end_time=end_time)
            adj_dict = xtdata.get_market_data(
                field_list=["time", "close"],
                stock_list=[xt_code],
                period="1d",
                start_time=start_time,
                end_time=end_time,
                dividend_type="front",
                fill_data=True,
            )
            if not adj_dict or adj_dict.get("close") is None or adj_dict["close"].empty:
                return None

            factor_raw = pd.DataFrame(
                {
                    "date": adj_dict["time"].T[xt_code],
                    "close_adj": adj_dict["close"].T[xt_code],
                }
            )
            factor_raw["date"] = pd.to_datetime(factor_raw["date"], unit="ms", utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
            factor_df = self._normalize_factor_data(factor_raw, base_frame)
            return self._slice_date_range(factor_df, start_dt, end_dt)

        raw_qfq = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_dt.strftime("%Y%m%d"),
            end_date=end_dt.strftime("%Y%m%d"),
            adjust="qfq",
        )
        factor_df = self._normalize_factor_data(raw_qfq, base_frame)
        return self._slice_date_range(factor_df, start_dt, end_dt)

    def _attach_factor_column(
        self,
        kline_df: pd.DataFrame,
        factor_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        merged = kline_df.copy().drop(columns=["factor"], errors="ignore")

        if factor_df is not None and not factor_df.empty:
            factors = factor_df[["date", "factor"]].copy()
            factors["date"] = pd.to_datetime(factors["date"])
            factors["factor"] = pd.to_numeric(factors["factor"], errors="coerce")
            merged = pd.merge(merged, factors, on="date", how="left")

        if "factor" not in merged.columns:
            merged["factor"] = 1.0

        merged["factor"] = pd.to_numeric(merged["factor"], errors="coerce").ffill().bfill().fillna(1.0)
        return merged

    def _save_bundle_to_cache(
        self,
        stock_code: str,
        kline_df: Optional[pd.DataFrame],
        factor_df: Optional[pd.DataFrame],
    ) -> bool:
        if kline_df is None or kline_df.empty:
            return False

        kline_path = os.path.join(self.kline_dir, f"{stock_code}.csv")
        save_kline = kline_df.copy()
        save_kline["date"] = save_kline["date"].dt.strftime("%Y-%m-%d")
        save_kline.to_csv(kline_path, index=False, encoding="utf-8")

        if factor_df is not None and not factor_df.empty:
            factor_path = os.path.join(self.factor_dir, f"{stock_code}.csv")
            save_factor = factor_df.copy()
            save_factor["date"] = save_factor["date"].dt.strftime("%Y-%m-%d")
            save_factor.to_csv(factor_path, index=False, encoding="utf-8")

        return True

    def download_stock_data(self, stock_code: str, start_date: str = "2010-01-01", source: str = "akshare") -> bool:
        """下载并缓存单只股票的日线数据。"""
        stock_code = self._normalize_stock_code(stock_code)
        try:
            bundle = self._fetch_stock_bundle(stock_code, start_date, source)
            return self._save_bundle_to_cache(stock_code, bundle.get("kline"), bundle.get("factor"))
        except Exception as e:
            print(f"下载股票 {stock_code} 数据失败: {e}")
            return False

    def _load_cached_kline(self, stock_code: str) -> Optional[pd.DataFrame]:
        kline_path = os.path.join(self.kline_dir, f"{stock_code}.csv")
        if not os.path.exists(kline_path):
            return None
        data = pd.read_csv(kline_path)
        return self._normalize_daily_kline(data)

    def _load_cached_factor(self, stock_code: str) -> Optional[pd.DataFrame]:
        factor_path = os.path.join(self.factor_dir, f"{stock_code}.csv")
        if not os.path.exists(factor_path):
            return None
        data = pd.read_csv(factor_path)
        return self._normalize_factor_data(data)

    def get_stock_data(
        self,
        stock_code: str,
        source: str = "akshare",
        interval: str = "daily",
    ) -> Optional[pd.DataFrame]:
        """获取股票 K 线数据，支持日K与周K。"""
        stock_code = self._normalize_stock_code(stock_code)
        try:
            if source == "offline":
                offline_path = self._get_offline_file(stock_code)
                if not offline_path:
                    return None
                data = self._read_csv_with_fallback(offline_path)
                normalized = self._normalize_offline_data(data)
            else:
                normalized = self._load_cached_kline(stock_code)
                if normalized is None:
                    if not self.download_stock_data(stock_code, start_date="2010-01-01", source=source):
                        return None
                    normalized = self._load_cached_kline(stock_code)

            if normalized is None:
                return None

            normalized = normalized.drop(columns=["factor"], errors="ignore")

            if interval == "weekly":
                return self._resample_to_weekly(normalized)
            return normalized
        except Exception as e:
            print(f"获取股票 {stock_code} 数据失败: {e}")
            return None

    def get_factor_data(
        self,
        stock_code: str,
        source: str = "akshare",
        interval: str = "daily",
    ) -> Optional[pd.DataFrame]:
        """获取复权因子数据，周K会按周最后一个交易日聚合。"""
        stock_code = self._normalize_stock_code(stock_code)
        try:
            if source == "offline":
                offline_path = self._get_offline_file(stock_code)
                if not offline_path:
                    return None
                data = self._read_csv_with_fallback(offline_path)
                normalized = self._normalize_offline_data(data)
                if normalized is None or "factor" not in normalized.columns:
                    return None
                factor_df = normalized[["date", "factor"]].copy()
            else:
                factor_df = self._load_cached_factor(stock_code)

            if factor_df is None or factor_df.empty:
                return None

            if interval == "weekly":
                return self._resample_to_weekly(factor_df)
            return factor_df
        except Exception as e:
            print(f"获取复权因子 {stock_code} 失败: {e}")
            return None

    def get_dividend_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """获取除权除息数据。"""
        stock_code = self._normalize_stock_code(stock_code)
        try:
            dividend_path = os.path.join(self.dividend_dir, f"{stock_code}.csv")
            if os.path.exists(dividend_path):
                return pd.read_csv(dividend_path)
            return None
        except Exception as e:
            print(f"获取除权除息 {stock_code} 数据失败: {e}")
            return None

    def get_stock_name(self, stock_code: str) -> str:
        stock_code = self._normalize_stock_code(stock_code)
        if not self.stock_names:
            self.load_stock_list()
        return self.stock_names.get(stock_code, f"股票{stock_code}")

    def get_training_validation_error(
        self,
        stock_code: str,
        start_date: str,
        source: str = "akshare",
        interval: str = "daily",
    ) -> Optional[str]:
        stock_code = self._normalize_stock_code(stock_code)
        if not stock_code:
            return "股票代码不能为空"

        try:
            start_dt = pd.to_datetime(start_date)
        except Exception:
            return "起始日期格式无效"

        data = self.get_stock_data(stock_code, source=source, interval=interval)
        if data is None or data.empty:
            if source == "offline":
                if self._get_offline_file(stock_code) is None:
                    return "指定股票在离线数据中不存在"
                return "指定股票在离线数据中没有可用数据"
            return "指定股票暂无可用数据，请切换数据源或稍后重试"

        min_date = data["date"].min()
        max_date = data["date"].max()
        if start_dt < min_date or start_dt > max_date:
            if source == "offline":
                return f"起始日期不在该股票离线数据范围内（{min_date:%Y-%m-%d} ~ {max_date:%Y-%m-%d}）"
            return f"起始日期不在该股票数据范围内（{min_date:%Y-%m-%d} ~ {max_date:%Y-%m-%d}）"

        return None

    def validate_stock_and_date(
        self,
        stock_code: str,
        start_date: str,
        source: str = "akshare",
        interval: str = "daily",
    ) -> bool:
        """验证股票代码和起始日期是否有效。"""
        return self.get_training_validation_error(
            stock_code,
            start_date,
            source=source,
            interval=interval,
        ) is None

    def get_random_stock(
        self,
        sector: str = "all",
        date_start: str = "2024-01-01",
        date_end: str = "2026-01-01",
        source: str = "akshare",
        interval: str = "daily",
    ) -> Tuple[str, str]:
        """随机选择股票与起始日期。"""
        range_start, range_end = self._resolve_training_range(date_start, date_end)

        if source == "offline":
            stock_codes = self._filter_stock_codes_by_sector(self._get_offline_stock_codes(), sector)
            candidates: List[Tuple[str, pd.Timestamp, pd.Timestamp]] = []

            for stock_code in stock_codes:
                date_range = self._get_offline_date_range(stock_code)
                if date_range is None:
                    continue
                stock_start, stock_end = date_range
                available_start = max(range_start, stock_start)
                available_end = min(range_end, stock_end)
                if available_start <= available_end:
                    candidates.append((stock_code, available_start, available_end))

            if not candidates:
                raise ValueError("离线数据中没有符合板块与日期范围的股票")

            stock_code, available_start, available_end = random.choice(candidates)
            return stock_code, self._random_date_in_range(available_start, available_end)

        if self.stock_list is None:
            self.load_stock_list()

        if self.stock_list is None or self.stock_list.empty:
            raise ValueError("股票列表为空，无法随机选择股票")

        stock_codes = self.stock_list["code"].dropna().astype(str).str.zfill(6).drop_duplicates().tolist()
        stock_codes = self._filter_stock_codes_by_sector(stock_codes, sector)
        if not stock_codes:
            raise ValueError("所选板块下没有可用股票")

        random.shuffle(stock_codes)
        max_attempts = min(len(stock_codes), 80)
        for stock_code in stock_codes[:max_attempts]:
            date_range = self._get_stock_date_range(stock_code, source=source, interval=interval)
            if date_range is None:
                continue
            stock_start, stock_end = date_range
            available_start = max(range_start, stock_start)
            available_end = min(range_end, stock_end)
            if available_start <= available_end:
                return stock_code, self._random_date_in_range(available_start, available_end)

        raise ValueError("所选数据源中没有符合条件的股票，请调整板块或日期范围后重试")

    def _build_offline_path(self, stock_code: str) -> str:
        stock_code = self._normalize_stock_code(stock_code)
        existing_path = self._get_offline_file(stock_code)
        if existing_path:
            return existing_path
        return os.path.join(self.offline_dir, f"{stock_code}{self._get_market_suffix(stock_code)}.csv")

    def sync_offline_data(
        self,
        stock_code: str,
        source: str = "akshare",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_full: bool = False,
    ) -> Dict:
        """将在线数据源按日期区间增量同步到离线目录。"""
        stock_code = self._normalize_stock_code(stock_code)
        if source == "offline":
            raise ValueError("离线数据不能作为在线补数源。")

        existing = self.get_stock_data(stock_code, source="offline", interval="daily")
        existing_factor = self.get_factor_data(stock_code, source="offline", interval="daily")
        request_start, request_end = self._normalize_sync_range(start_date=start_date, end_date=end_date)
        offline_path = self._build_offline_path(stock_code)

        range_before = None
        previous_rows = 0
        segments_to_fetch: List[Tuple[pd.Timestamp, pd.Timestamp]] = []

        if existing is not None and not existing.empty:
            existing = existing.copy()
            existing["date"] = pd.to_datetime(existing["date"])
            previous_rows = len(existing)
            local_start = existing["date"].min().normalize()
            local_end = existing["date"].max().normalize()
            range_before = {
                "start": local_start.strftime("%Y-%m-%d"),
                "end": local_end.strftime("%Y-%m-%d"),
            }

            if force_full:
                segments_to_fetch.append((request_start, request_end))
            else:
                head_end = min(request_end, local_start - timedelta(days=1))
                if request_start <= head_end:
                    segments_to_fetch.append((request_start, head_end))

                tail_start = max(request_start, local_end + timedelta(days=1))
                if tail_start <= request_end:
                    segments_to_fetch.append((tail_start, request_end))
        else:
            segments_to_fetch.append((request_start, request_end))

        planned_ranges: List[Dict[str, str]] = []
        fetched_ranges: List[Dict[str, str]] = []
        missing_ranges: List[Dict[str, str]] = []
        fetched_kline_parts: List[pd.DataFrame] = []
        fetched_factor_parts: List[pd.DataFrame] = []

        for segment_start, segment_end in segments_to_fetch:
            if segment_end < segment_start:
                continue

            planned_ranges.append(
                {
                    "start": segment_start.strftime("%Y-%m-%d"),
                    "end": segment_end.strftime("%Y-%m-%d"),
                }
            )

            bundle = self._fetch_stock_bundle(
                stock_code,
                segment_start.strftime("%Y-%m-%d"),
                source,
                end_date=segment_end.strftime("%Y-%m-%d"),
            )
            segment_kline = self._slice_date_range(bundle.get("kline"), segment_start, segment_end)
            segment_factor = self._slice_date_range(bundle.get("factor"), segment_start, segment_end)

            if segment_kline is not None and not segment_kline.empty:
                fetched_kline_parts.append(segment_kline)
                fetched_ranges.append(
                    {
                        "start": pd.to_datetime(segment_kline["date"]).min().strftime("%Y-%m-%d"),
                        "end": pd.to_datetime(segment_kline["date"]).max().strftime("%Y-%m-%d"),
                    }
                )
            else:
                missing_ranges.append(
                    {
                        "start": segment_start.strftime("%Y-%m-%d"),
                        "end": segment_end.strftime("%Y-%m-%d"),
                    }
                )

            if segment_factor is not None and not segment_factor.empty:
                fetched_factor_parts.append(segment_factor)

        fetched_rows = sum(len(part) for part in fetched_kline_parts)

        if previous_rows > 0 and fetched_rows == 0 and not force_full:
            return {
                "success": True,
                "stock_code": stock_code,
                "source": source,
                "message": "在线源在待补区间未返回新数据，本地离线文件保持不变。",
                "added_rows": 0,
                "fetched_rows": 0,
                "rows_before": previous_rows,
                "rows_after": previous_rows,
                "total_rows": previous_rows,
                "latest_date": existing["date"].max().strftime("%Y-%m-%d"),
                "offline_path": offline_path,
                "requested_range": {
                    "start": request_start.strftime("%Y-%m-%d"),
                    "end": request_end.strftime("%Y-%m-%d"),
                },
                "range_before": range_before,
                "range_after": range_before,
                "planned_ranges": planned_ranges,
                "fetched_ranges": fetched_ranges,
                "missing_ranges": missing_ranges,
                "factor_refresh_mode": "unchanged",
                "local_file_changed": False,
            }

        if force_full:
            merged = pd.concat(fetched_kline_parts, ignore_index=True) if fetched_kline_parts else pd.DataFrame()
        elif existing is not None and not existing.empty:
            merged = pd.concat([existing] + fetched_kline_parts, ignore_index=True) if (existing is not None or fetched_kline_parts) else pd.DataFrame()
        else:
            merged = pd.concat(fetched_kline_parts, ignore_index=True) if fetched_kline_parts else pd.DataFrame()

        merged = self._normalize_daily_kline(merged) if merged is not None and not merged.empty else None

        if merged is None or merged.empty:
            if existing is not None and not existing.empty and not force_full:
                snapshot = self._attach_factor_column(existing, existing_factor)
                snapshot["source"] = source
                snapshot["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                save_snapshot = snapshot.copy()
                save_snapshot["date"] = save_snapshot["date"].dt.strftime("%Y-%m-%d")
                save_snapshot.to_csv(offline_path, index=False, encoding="utf-8")
                self._offline_stock_codes_cache = None
                self._offline_date_range_cache.pop(stock_code, None)

                return {
                    "success": True,
                    "stock_code": stock_code,
                    "source": source,
                    "message": "本地数据已覆盖所选区间，无需新增请求。",
                    "added_rows": 0,
                    "fetched_rows": 0,
                    "total_rows": len(snapshot),
                    "latest_date": snapshot["date"].max().strftime("%Y-%m-%d"),
                    "offline_path": offline_path,
                    "requested_range": {
                        "start": request_start.strftime("%Y-%m-%d"),
                        "end": request_end.strftime("%Y-%m-%d"),
                    },
                    "range_before": range_before,
                    "range_after": range_before,
                    "planned_ranges": planned_ranges,
                    "fetched_ranges": fetched_ranges,
                    "missing_ranges": missing_ranges,
                    "factor_refresh_mode": "unchanged",
                    "local_file_changed": False,
                }

            return {
                "success": True,
                "stock_code": stock_code,
                "source": source,
                "message": "没有获取到符合日期区间的在线数据。",
                "added_rows": 0,
                "fetched_rows": 0,
                "latest_date": existing["date"].max().strftime("%Y-%m-%d") if existing is not None and not existing.empty else None,
                "offline_path": offline_path,
                "requested_range": {
                    "start": request_start.strftime("%Y-%m-%d"),
                    "end": request_end.strftime("%Y-%m-%d"),
                },
                "range_before": range_before,
                "range_after": range_before,
                "planned_ranges": planned_ranges,
                "fetched_ranges": fetched_ranges,
                "missing_ranges": missing_ranges,
                "factor_refresh_mode": "none",
                "local_file_changed": False,
            }

        factor_refresh_mode = "carried_forward"
        merged_factor = None
        if self._supports_factor_refresh(source):
            try:
                merged_factor = self._fetch_factor_range(
                    stock_code=stock_code,
                    source=source,
                    start_date=merged["date"].min().strftime("%Y-%m-%d"),
                    end_date=merged["date"].max().strftime("%Y-%m-%d"),
                    base_df=merged,
                )
                if merged_factor is not None and not merged_factor.empty:
                    factor_refresh_mode = "full_range_refreshed"
            except Exception as exc:
                print(f"刷新 {stock_code} 全量复权因子失败: {exc}")
                merged_factor = None

        if merged_factor is None or merged_factor.empty:
            factor_candidates: List[pd.DataFrame] = []
            if not force_full and existing_factor is not None and not existing_factor.empty:
                factor_candidates.append(existing_factor)
            factor_candidates.extend(part for part in fetched_factor_parts if part is not None and not part.empty)
            merged_factor = pd.concat(factor_candidates, ignore_index=True) if factor_candidates else None
            if merged_factor is not None and not merged_factor.empty:
                merged_factor = merged_factor.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
            else:
                factor_refresh_mode = "default_ones"

        merged = self._attach_factor_column(merged, merged_factor)

        merged["source"] = source
        merged["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        save_df = merged.copy()
        save_df["date"] = save_df["date"].dt.strftime("%Y-%m-%d")
        save_df.to_csv(offline_path, index=False, encoding="utf-8")
        self._offline_stock_codes_cache = None
        self._offline_date_range_cache.pop(stock_code, None)

        added_rows = max(0, len(merged) - previous_rows)
        range_after = {
            "start": merged["date"].min().strftime("%Y-%m-%d"),
            "end": merged["date"].max().strftime("%Y-%m-%d"),
        }

        if force_full:
            message = "已按所选日期区间全量重建离线数据。"
        elif fetched_rows > 0:
            message = "已按本地时间范围增量补齐离线数据。"
        else:
            message = "本地数据已覆盖所选区间，仅刷新了离线文件。"

        return {
            "success": True,
            "stock_code": stock_code,
            "source": source,
            "message": message,
            "added_rows": added_rows,
            "fetched_rows": fetched_rows,
            "rows_before": previous_rows,
            "rows_after": len(merged),
            "total_rows": len(merged),
            "latest_date": merged["date"].max().strftime("%Y-%m-%d"),
            "offline_path": offline_path,
            "requested_range": {
                "start": request_start.strftime("%Y-%m-%d"),
                "end": request_end.strftime("%Y-%m-%d"),
            },
            "range_before": range_before,
            "range_after": range_after,
            "planned_ranges": planned_ranges,
            "fetched_ranges": fetched_ranges,
            "missing_ranges": missing_ranges,
            "factor_refresh_mode": factor_refresh_mode,
            "local_file_changed": True,
        }

    def batch_download_data(self, stock_codes: List[str] = None, start_date: str = "2010-01-01"):
        """批量下载股票数据。"""
        if stock_codes is None:
            if self.stock_list is None:
                self.load_stock_list()
            stock_codes = self.stock_list["code"].tolist()

        total = len(stock_codes)
        success_count = 0

        for index, stock_code in enumerate(stock_codes, start=1):
            print(f"进度: {index}/{total} - {stock_code}")
            if self.download_stock_data(stock_code, start_date):
                success_count += 1

        print(f"批量下载完成，成功 {success_count}/{total}")
        return success_count, total


def download_all_data():
    """示例脚本：下载部分股票日线缓存。"""
    data_manager = DataManager()
    data_manager.download_stock_list()
    sample_stocks = ["000001", "000002", "600000", "600036", "000858", "002415", "300059", "300750"]
    data_manager.batch_download_data(sample_stocks)


if __name__ == "__main__":
    download_all_data()
