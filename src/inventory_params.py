"""安全库存、ROP、EOQ 等库存参数计算模块。"""
import pandas as pd
import numpy as np

from src.abc import calc_abc


def calc_inventory_params(df, lead_time=4, ordering_cost=50, holding_rate=0.25,
                          ss_factor_A=2.0, ss_factor_B=1.0, ss_factor_C=0.5):
    """计算每个 SKU 的安全库存、ROP、EOQ 等参数。
    
    安全库存使用"订单量级安全系数法"（针对间歇性需求设计）。
    ROP = 日需求率 × 提前期 + 安全库存。
    """
    daily_demand = df.groupby(['Product ID', 'Order Date'])['Quantity'].sum().reset_index()
    daily_demand.columns = ['Product ID', 'Date', 'Daily_Qty']

    sku_stats = daily_demand.groupby('Product ID')['Daily_Qty'].agg(['mean', 'std', 'count', 'sum']).reset_index()
    sku_stats.columns = ['Product ID', 'daily_mean', 'daily_std', 'active_days', 'total_qty']
    sku_stats['daily_std'] = sku_stats['daily_std'].fillna(sku_stats['daily_std'].median())

    data_years = df['Order Date'].dt.year.nunique()
    sku_stats['annual_demand'] = sku_stats['total_qty'] / data_years

    sku_price = df.groupby('Product ID').apply(
        lambda x: x['Sales'].sum() / x['Quantity'].sum()
    ).reset_index(name='unit_price')
    sku_stats = sku_stats.merge(sku_price, on='Product ID', how='left')

    abc = calc_abc(df)
    sku_stats = sku_stats.merge(abc[['Product ID', 'ABC_Class']], on='Product ID', how='left')

    order_stats = daily_demand.groupby('Product ID')['Daily_Qty'].agg(['mean', 'max']).reset_index()
    order_stats.columns = ['Product ID', 'avg_order_qty', 'max_order_qty']
    sku_stats = sku_stats.merge(order_stats, on='Product ID', how='left')

    factor_map = {'A': ss_factor_A, 'B': ss_factor_B, 'C': ss_factor_C}
    sku_stats['ss_factor'] = sku_stats['ABC_Class'].map(factor_map)
    sku_stats['safety_stock'] = (sku_stats['avg_order_qty'] * sku_stats['ss_factor']).round(0)

    # ROP = 日需求率 × 提前期 + 安全库存
    # 间歇性需求下提前期需求极小，数值上接近安全库存，但公式逻辑完整
    sku_stats['daily_rate'] = sku_stats['annual_demand'] / 365
    sku_stats['rop'] = (sku_stats['daily_rate'] * lead_time + sku_stats['safety_stock']).round(2)

    sku_stats['holding_cost_per_unit'] = sku_stats['unit_price'] * holding_rate
    sku_stats['eoq'] = np.sqrt(
        2 * sku_stats['annual_demand'] * ordering_cost / sku_stats['holding_cost_per_unit']
    ).round(0)
    sku_stats['eoq'] = sku_stats['eoq'].fillna(10)

    sku_stats['orders_per_year'] = (sku_stats['annual_demand'] / sku_stats['eoq']).round(1).replace([np.inf, -np.inf], 0).fillna(0)
    sku_stats['avg_inventory'] = (sku_stats['eoq'] / 2 + sku_stats['safety_stock']).round(0)
    sku_stats['annual_holding_cost'] = (sku_stats['avg_inventory'] * sku_stats['holding_cost_per_unit']).round(2)
    sku_stats['annual_ordering_cost'] = (sku_stats['orders_per_year'] * ordering_cost).round(2)
    sku_stats['total_inventory_cost'] = (sku_stats['annual_holding_cost'] + sku_stats['annual_ordering_cost']).round(2)

    xyz = calc_xyz(df)
    sku_stats = sku_stats.merge(xyz, on='Product ID', how='left')

    return sku_stats


def calc_xyz(df):
    """按月度需求波动（CV）计算 XYZ 分类。

    X：需求稳定，CV < 0.5
    Y：中等波动，0.5 <= CV < 1.0
    Z：高波动，CV >= 1.0（间歇性需求通常落在此类）
    """
    tmp = df.copy()
    tmp['year'] = pd.to_datetime(tmp['Order Date']).dt.year
    tmp['month'] = pd.to_datetime(tmp['Order Date']).dt.month
    monthly = tmp.groupby(['Product ID', 'year', 'month'])['Quantity'].sum().reset_index()
    stats = monthly.groupby('Product ID')['Quantity'].agg(['mean', 'std']).reset_index()
    stats.columns = ['Product ID', 'monthly_mean', 'monthly_std']

    stats['cv'] = stats['monthly_std'] / stats['monthly_mean']
    stats.loc[stats['monthly_mean'] == 0, 'cv'] = float('inf')

    def xyz_class(cv):
        if cv < 0.5:
            return 'X'
        elif cv < 1.0:
            return 'Y'
        else:
            return 'Z'

    stats['XYZ_Class'] = stats['cv'].apply(xyz_class)
    # 只保留有全年月均值的 SKU 的列；无需求 SKU 默认 Z
    stats['XYZ_Class'] = stats['XYZ_Class'].fillna('Z')
    return stats[['Product ID', 'XYZ_Class']]
