"""需求预测模块：Croston 与 SMA 对比评估。"""
import pandas as pd
import numpy as np

from src.config import (
    FORECAST_ALPHA,
    FORECAST_MIN_EVENTS,
    FORECAST_TRAIN_START,
    FORECAST_TRAIN_END,
    FORECAST_VAL_YEAR,
)


def build_forecast_eval(df, sku_stats):
    """用历史订单训练，预测验证年需求量，评估 Croston 与 SMA。
    
    返回每个 SKU 的预测值、实际值、误差及需求频率分组。
    """
    train_start = pd.Timestamp(FORECAST_TRAIN_START)
    train_end = pd.Timestamp(FORECAST_TRAIN_END)
    train_days = (train_end - train_start).days + 1
    val_days = 364  # 数据区间 2018-01-01 ~ 2018-12-30
    val_year = FORECAST_VAL_YEAR
    alpha = FORECAST_ALPHA
    min_events = FORECAST_MIN_EVENTS

    daily = df.groupby(['Product ID', 'Order Date'])['Quantity'].sum().reset_index()
    daily.columns = ['Product ID', 'Date', 'Qty']
    daily = daily.sort_values('Date')

    abc_map = dict(zip(sku_stats['Product ID'], sku_stats['ABC_Class']))
    rows = []

    for pid, grp in daily.groupby('Product ID'):
        train = grp[(grp['Date'] >= train_start) & (grp['Date'] <= train_end)]
        if len(train) < min_events:
            continue

        val_total = daily[(daily['Product ID'] == pid) & (daily['Date'].dt.year == val_year)]['Qty'].sum()
        prev_total = daily[(daily['Product ID'] == pid) & (daily['Date'].dt.year == val_year - 1)]['Qty'].sum()
        if val_total <= 0:
            continue

        dates = train['Date']
        sizes = train['Qty'].astype(float).values
        intervals = dates.diff().dt.days.dropna().astype(float).values

        # Croston：分别平滑“订单间隔”和“单次订单量”
        if len(intervals) > 0:
            s_interval = float(intervals[0])
            s_size = float(sizes[0])
            for interval, size in zip(intervals, sizes[1:]):
                s_interval = alpha * interval + (1 - alpha) * s_interval
                s_size = alpha * size + (1 - alpha) * s_size
            croston_rate = s_size / s_interval if s_interval > 0 else 0.0
        else:
            croston_rate = float(train['Qty'].mean()) / 30.0

        # SMA：训练期总销量 / 训练天数
        sma_rate = train['Qty'].sum() / train_days

        rows.append({
            'Product ID': pid,
            'ABC_Class': abc_map.get(pid, 'C'),
            'train_events': len(train),
            'actual_total': float(val_total),
            'prev_total': float(prev_total),
            'croston_pred': round(croston_rate * val_days, 1),
            'sma_pred': round(sma_rate * val_days, 1),
        })

    if not rows:
        return pd.DataFrame()

    fdf = pd.DataFrame(rows)
    fdf['croston_error'] = (fdf['croston_pred'] - fdf['actual_total']).abs()
    fdf['sma_error'] = (fdf['sma_pred'] - fdf['actual_total']).abs()
    fdf['naive_error'] = (fdf['prev_total'] - fdf['actual_total']).abs().where(fdf['prev_total'] > 0)
    fdf['bucket'] = np.where(fdf['train_events'] >= 8, '高频(训练事件>=8)', '低频(4~7次)')
    return fdf


def forecast_metrics(sub):
    """汇总预测误差指标。"""
    if sub.empty:
        return pd.Series({'SKU数': 0, 'Croston MAE': 0, 'SMA MAE': 0, 'Naive MAE': 0,
                          'Croston MASE': 0, 'SMA MASE': 0})
    n = len(sub)
    c_mae = sub['croston_error'].mean()
    s_mae = sub['sma_error'].mean()
    n_mae = sub['naive_error'].mean()
    mase_c = c_mae / n_mae if n_mae and n_mae > 0 else float('nan')
    mase_s = s_mae / n_mae if n_mae and n_mae > 0 else float('nan')
    return pd.Series({
        'SKU数': int(n),
        'Croston MAE': round(c_mae, 1),
        'SMA MAE': round(s_mae, 1),
        'Naive MAE': round(n_mae, 1),
        'Croston RMSE': round(np.sqrt((sub['croston_error'] ** 2).mean()), 1),
        'SMA RMSE': round(np.sqrt((sub['sma_error'] ** 2).mean()), 1),
        'Croston MASE': round(mase_c, 2),
        'SMA MASE': round(mase_s, 2),
    })
