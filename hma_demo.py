import pandas as pd
import numpy as np
import webview
import plotly.graph_objects as go
import math
import os

# ==========================================
# ⚙️ 全局显示配置 (你可以自由修改这里)
# ==========================================
SHOW_BF_MARKERS = False  # 设为 False 隐藏 BlackFlag 的三角号、粉色和绿色极值点
DEFAULT_ZOOM_BARS = 150  # 默认启动时显示最近的多少根 K 线


# ==========================================
# 1. 核心算法函数
# ==========================================
def wma(series, length):
    length = int(length)
    weights = np.arange(1, length + 1)
    return series.rolling(window=length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def hma(series, length):
    half_length = int(length / 2)
    sqrt_length = int(np.round(math.sqrt(length)))
    wmaf = wma(series, half_length)
    wmas = wma(series, length)
    raw_hma = 2 * wmaf - wmas
    return wma(raw_hma, sqrt_length)


# 【核心突破】降维打击：将真实的交叉时间强行压缩进上一个有效交易日内，彻底避开周末黑洞
def find_intersection_date(t1_pd, y1a, y2a, t2_pd, y1b, y2b):
    den = (y2a - y1a) - (y2b - y1b)
    if den == 0: return None, None
    f = (y1b - y1a) / den
    # 强行将交点投影在第一天的 24 小时内，完美绕过 Plotly 的周末 rangebreaks 剔除区
    t_int = t1_pd + pd.Timedelta(days=f)
    y_int = y1a + (y2a - y1a) * f
    return t_int, y_int


def calculate_blackflag_fts(df, atr_period=10, atr_factor=3):
    high = df['最高价'].values
    low = df['最低价'].values
    close = df['收盘价'].values
    n = len(df)

    high_1 = np.roll(high, 1)
    low_1 = np.roll(low, 1)
    close_1 = np.roll(close, 1)
    high_1[0], low_1[0], close_1[0] = high[0], low[0], close[0]

    h_minus_l = high - low
    sma_hl = pd.Series(h_minus_l).rolling(window=atr_period).mean().values
    HiLo = np.minimum(h_minus_l, 1.5 * np.nan_to_num(sma_hl, nan=h_minus_l))

    cond_href = low <= high_1
    href_true = high - close_1
    href_false = (high - close_1) - 0.5 * (low - high_1)
    HRef = np.where(cond_href, href_true, href_false)

    cond_lref = high >= low_1
    lref_true = close_1 - low
    lref_false = (close_1 - low) - 0.5 * (low_1 - high)
    LRef = np.where(cond_lref, lref_true, lref_false)

    trueRange = np.maximum(HiLo, np.maximum(HRef, LRef))

    wild_ma = np.zeros(n)
    wild = 0.0
    for i in range(n):
        wild = wild + (trueRange[i] - wild) / atr_period
        wild_ma[i] = wild

    loss = atr_factor * wild_ma
    Up = close - loss
    Dn = close + loss

    TrendUp = np.zeros(n)
    TrendDown = np.zeros(n)
    Trend = np.ones(n)
    trail = np.zeros(n)
    ex = np.zeros(n)

    for i in range(1, n):
        TrendUp[i] = max(Up[i], TrendUp[i - 1]) if close[i - 1] > TrendUp[i - 1] else Up[i]
        TrendDown[i] = min(Dn[i], TrendDown[i - 1]) if close[i - 1] < TrendDown[i - 1] else Dn[i]

        if close[i] > TrendDown[i - 1]:
            Trend[i] = 1
        elif close[i] < TrendUp[i - 1]:
            Trend[i] = -1
        else:
            Trend[i] = Trend[i - 1]

        trail[i] = TrendUp[i] if Trend[i] == 1 else TrendDown[i]

        if Trend[i] == 1 and Trend[i - 1] == -1:
            ex[i] = high[i]
        elif Trend[i] == -1 and Trend[i - 1] == 1:
            ex[i] = low[i]
        elif Trend[i] == 1:
            ex[i] = max(ex[i - 1], high[i])
        elif Trend[i] == -1:
            ex[i] = min(ex[i - 1], low[i])
        else:
            ex[i] = ex[i - 1]

    f1 = ex + (trail - ex) * 0.618
    f2 = ex + (trail - ex) * 0.786
    f3 = ex + (trail - ex) * 0.886

    l1, l2, l3 = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    s1, s2, s3 = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)

    for i in range(1, n):
        if Trend[i - 1] == 1:
            if close[i - 1] >= f1[i - 1] and close[i] < f1[i - 1]: l1[i] = True
            if close[i - 1] >= f2[i - 1] and close[i] < f2[i - 1]: l2[i] = True
            if close[i - 1] >= f3[i - 1] and close[i] < f3[i - 1]: l3[i] = True
        elif Trend[i - 1] == -1:
            if close[i - 1] <= f1[i - 1] and close[i] > f1[i - 1]: s1[i] = True
            if close[i - 1] <= f2[i - 1] and close[i] > f2[i - 1]: s2[i] = True
            if close[i - 1] <= f3[i - 1] and close[i] > f3[i - 1]: s3[i] = True

    atr_14 = pd.Series(trueRange).rolling(14).mean().values
    return Trend, trail, ex, f1, f2, f3, l1, l2, l3, s1, s2, s3, atr_14


# ==========================================
# 2. 数据处理与指标计算
# ==========================================
print("正在计算数据与构建安全索引轴，请稍候...")
df = pd.read_csv(r'data\a_market_offline\000157.SZ.csv')
df = df.dropna(subset=['收盘价', '开盘价', '最高价', '最低价']).reset_index(drop=True)
df['交易日'] = pd.to_datetime(df['交易日'].astype(str))
df = df.sort_values(by='交易日').reset_index(drop=True)

df['HMA50'] = hma(df['收盘价'], 50)
df['HMA100'] = hma(df['收盘价'], 100)
df['HMA200'] = hma(df['收盘价'], 200)

df['diff'] = df['HMA50'] - df['HMA100']
regimes = []
current = np.nan
for val in df['diff']:
    if pd.isna(val):
        regimes.append(np.nan)
    elif val > 0:
        current = 1; regimes.append(1)
    elif val < 0:
        current = -1; regimes.append(-1)
    else:
        regimes.append(current)
df['regime'] = regimes

Trend, trail, ex, f1, f2, f3, l1, l2, l3, s1, s2, s3, atr_14 = calculate_blackflag_fts(df, atr_period=10, atr_factor=3)

df['BF_Trend'] = Trend
df['BF_Trail'] = trail
df['BF_ex'] = ex
df['BF_f1'] = f1
df['BF_f2'] = f2
df['BF_f3'] = f3
df['Trend_Block'] = (df['BF_Trend'] != df['BF_Trend'].shift(1)).cumsum()

# 提取休市日供黑名单使用
all_dates = pd.date_range(start=df['交易日'].min(), end=df['交易日'].max())
missing_dates = all_dates.difference(df['交易日']).strftime('%Y-%m-%d').tolist()

# ==========================================
# 3. 构建 Plotly 图表
# ==========================================
fig = go.Figure()

# A. 绘制 K 线
fig.add_trace(go.Candlestick(
    x=df['交易日'], open=df['开盘价'], high=df['最高价'], low=df['最低价'], close=df['收盘价'],
    increasing_line_color='#F6465D', increasing_fillcolor='#F6465D',
    decreasing_line_color='#0ECB81', decreasing_fillcolor='#0ECB81',
    name='K线'
))

# B. 分块绘制 Blackflag FTS 色带与轨道
for block_id, group in df.groupby('Trend_Block'):
    group = group.dropna(subset=['BF_f1', 'BF_Trail'])
    if len(group) < 2: continue  # 防止孤立点导致渲染异常

    t = group['BF_Trend'].iloc[0]
    x_vals = group['交易日']

    if t == 1:
        fig.add_trace(
            go.Scatter(x=x_vals, y=group['BF_f1'], mode='lines', line=dict(color='gray', width=0.5), showlegend=False,
                       hoverinfo='skip'))
        fig.add_trace(
            go.Scatter(x=x_vals, y=group['BF_f2'], mode='lines', line=dict(color='gray', width=0.5), fill='tonexty',
                       fillcolor='rgba(0, 176, 80, 0.1)', showlegend=False, hoverinfo='skip'))
        fig.add_trace(
            go.Scatter(x=x_vals, y=group['BF_f3'], mode='lines', line=dict(color='gray', width=0.5), fill='tonexty',
                       fillcolor='rgba(0, 176, 80, 0.2)', showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=x_vals, y=group['BF_Trail'], mode='lines', line=dict(color='#00B050', width=1.5),
                                 fill='tonexty', fillcolor='rgba(0, 176, 80, 0.3)', showlegend=False))

        if SHOW_BF_MARKERS:  # 可选：绘制极值点
            fig.add_trace(go.Scatter(x=x_vals, y=group['BF_ex'], mode='markers', marker=dict(color='lime', size=4),
                                     showlegend=False, hoverinfo='skip'))
    elif t == -1:
        fig.add_trace(
            go.Scatter(x=x_vals, y=group['BF_f1'], mode='lines', line=dict(color='gray', width=0.5), showlegend=False,
                       hoverinfo='skip'))
        fig.add_trace(
            go.Scatter(x=x_vals, y=group['BF_f2'], mode='lines', line=dict(color='gray', width=0.5), fill='tonexty',
                       fillcolor='rgba(255, 82, 82, 0.1)', showlegend=False, hoverinfo='skip'))
        fig.add_trace(
            go.Scatter(x=x_vals, y=group['BF_f3'], mode='lines', line=dict(color='gray', width=0.5), fill='tonexty',
                       fillcolor='rgba(255, 82, 82, 0.2)', showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=x_vals, y=group['BF_Trail'], mode='lines', line=dict(color='#FF5252', width=1.5),
                                 fill='tonexty', fillcolor='rgba(255, 82, 82, 0.3)', showlegend=False))

        if SHOW_BF_MARKERS:  # 可选：绘制极值点
            fig.add_trace(go.Scatter(x=x_vals, y=group['BF_ex'], mode='markers', marker=dict(color='fuchsia', size=4),
                                     showlegend=False, hoverinfo='skip'))

# C. 可选：Fib 进场信号
if SHOW_BF_MARKERS:
    for cond, y_val, sym, color, name in [
        (l1, df['最低价'] - atr_14, 'triangle-up', 'yellow', 'LS1'),
        (l2, df['最低价'] - 1.5 * atr_14, 'triangle-up', 'yellow', 'LS2'),
        (l3, df['最低价'] - 2 * atr_14, 'triangle-up', 'yellow', 'LS3'),
        (s1, df['最高价'] + atr_14, 'triangle-down', 'purple', 'SS1'),
        (s2, df['最高价'] + 1.5 * atr_14, 'triangle-down', 'purple', 'SS2'),
        (s3, df['最高价'] + 2 * atr_14, 'triangle-down', 'purple', 'SS3')
    ]:
        idx = np.where(cond)[0]
        if len(idx) > 0:
            fig.add_trace(go.Scatter(x=df['交易日'].iloc[idx], y=y_val.iloc[idx], mode='markers',
                                     marker=dict(symbol=sym, color=color, size=9, line=dict(color='black', width=1)),
                                     name=name))

# D. 绘制 HMA 线与色带
fig.add_trace(
    go.Scatter(x=df['交易日'], y=df['HMA200'], mode='lines', line=dict(color='black', width=1.5), name='HMA 200'))
fig.add_trace(
    go.Scatter(x=df['交易日'], y=df['HMA100'], mode='lines', line=dict(color='black', width=1.5), fill='tonexty',
               fillcolor='rgba(160, 160, 160, 0.4)', name='HMA 100'))

current_x, current_y_hma50, current_y_hma100 = [], [], []
current_reg = None
cross_x, cross_y, cross_colors = [], [], []

for i in range(len(df)):
    r = df['regime'].iloc[i]
    if pd.isna(r): continue
    if current_reg is None: current_reg = r

    if r == current_reg:
        current_x.append(df['交易日'].iloc[i])
        current_y_hma50.append(df['HMA50'].iloc[i])
        current_y_hma100.append(df['HMA100'].iloc[i])
    else:
        t_int, y_int = find_intersection_date(
            df['交易日'].iloc[i - 1], df['HMA50'].iloc[i - 1], df['HMA50'].iloc[i],
            df['交易日'].iloc[i], df['HMA100'].iloc[i - 1], df['HMA100'].iloc[i]
        )

        if t_int is not None:
            current_x.append(t_int);
            current_y_hma50.append(y_int);
            current_y_hma100.append(y_int)
            cross_x.append(t_int);
            cross_y.append(y_int)
            cross_colors.append('#00B050' if r == 1 else '#FF5252')

        line_color = '#00B050' if current_reg == 1 else '#FF5252'
        cloud_color = 'rgba(0, 176, 80, 0.4)' if current_reg == 1 else 'rgba(255, 82, 82, 0.4)'

        if len(current_x) > 1:
            fig.add_trace(
                go.Scatter(x=current_x, y=current_y_hma100, mode='lines', line=dict(width=0), showlegend=False,
                           hoverinfo='skip'))
            fig.add_trace(
                go.Scatter(x=current_x, y=current_y_hma50, mode='lines', line=dict(color=line_color, width=2.5),
                           fill='tonexty', fillcolor=cloud_color, showlegend=False))

        current_x, current_y_hma50, current_y_hma100, current_reg = [], [], [], r
        if t_int is not None:
            current_x.append(t_int);
            current_y_hma50.append(y_int);
            current_y_hma100.append(y_int)

        current_x.append(df['交易日'].iloc[i])
        current_y_hma50.append(df['HMA50'].iloc[i])
        current_y_hma100.append(df['HMA100'].iloc[i])

if len(current_x) > 1:
    line_color = '#00B050' if current_reg == 1 else '#FF5252'
    cloud_color = 'rgba(0, 176, 80, 0.4)' if current_reg == 1 else 'rgba(255, 82, 82, 0.4)'
    fig.add_trace(go.Scatter(x=current_x, y=current_y_hma100, mode='lines', line=dict(width=0), showlegend=False,
                             hoverinfo='skip'))
    fig.add_trace(
        go.Scatter(x=current_x, y=current_y_hma50, mode='lines', line=dict(color=line_color, width=2.5), fill='tonexty',
                   fillcolor=cloud_color, showlegend=False))

fig.add_trace(go.Scatter(x=cross_x, y=cross_y, mode='markers',
                         marker=dict(color=cross_colors, size=10, line=dict(color='white', width=1.5)),
                         name='HMA 枢纽'))

# ==========================================
# 4. 自动缩放与最佳视角计算
# ==========================================
# 获取最后 150 根 K 线的数据窗口
if len(df) > DEFAULT_ZOOM_BARS:
    view_df = df.iloc[-DEFAULT_ZOOM_BARS:]
    x_range = [view_df['交易日'].iloc[0], view_df['交易日'].iloc[-1]]

    # 精准计算该窗口内 Y 轴的最值，实现自动完美拉伸
    y_max = max(view_df['最高价'].max(), view_df['HMA200'].max(), view_df['BF_Trail'].max())
    y_min = min(view_df['最低价'].min(), view_df['HMA200'].min(), view_df['BF_Trail'].min())
    padding = (y_max - y_min) * 0.08  # 上下留白 8%
    y_range = [y_min - padding, y_max + padding]
else:
    x_range = None
    y_range = None

fig.update_layout(
    title='HMA v420 + Blackflag',
    template='plotly_white',
    plot_bgcolor='#FFFFFF',
    dragmode='pan',
    xaxis_rangeslider_visible=False,
    xaxis=dict(
        range=x_range,
        gridcolor='#F0F3FA',
        rangebreaks=[dict(values=missing_dates)]  # 原生且完美的跳过休市日功能
    ),
    yaxis=dict(
        side='right',
        gridcolor='#F0F3FA',
        range=y_range,  # 初始自动适配最佳显示 Y 轴位置
        autorange=False if y_range else True
    ),
    margin=dict(l=20, r=50, t=50, b=20),
    showlegend=False
)

html_content = fig.to_html(include_plotlyjs='cdn', full_html=True, config={'scrollZoom': True, 'displayModeBar': False})

if __name__ == '__main__':
    print("图表生成完毕，正在写入本地缓冲...")
    temp_file_path = os.path.abspath("chart_render_temp.html")
    with open(temp_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("正在启动最佳视窗...")
    window = webview.create_window(
        '智能交易系统看板',
        url=temp_file_path,
        width=1400,
        height=900
    )
    webview.start()