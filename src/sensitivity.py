"""敏感性分析：安全系数与服务成本权衡。"""
import pandas as pd
import numpy as np

from src.inventory_params import calc_inventory_params
from src.simulation import run_simulation


def run_sensitivity_analysis(df, sim_year=2018, lead_time=4,
                              stockout_cost_per_unit=20):
    """枚举安全系数组合，模拟并记录服务水平和总成本。
    
    每次只变动一个类别的系数，固定其他为默认值，减少组合数。
    """
    # 组合定义：只变动一个维度
    combos = []
    for a_val in [1.0, 1.5, 2.0, 2.5, 3.0]:
        combos.append({'label': f'A类系数={a_val}', 'A': a_val, 'B': 1.0, 'C': 0.5})
    for b_val in [0.5, 0.75, 1.0, 1.25, 1.5]:
        combos.append({'label': f'B类系数={b_val}', 'A': 2.0, 'B': b_val, 'C': 0.5})
    for c_val in [0.25, 0.5, 0.75]:
        combos.append({'label': f'C类系数={c_val}', 'A': 2.0, 'B': 1.0, 'C': c_val})

    results = []
    for combo in combos:
        sku_stats = calc_inventory_params(
            df, lead_time=lead_time, ordering_cost=50, holding_rate=0.25,
            ss_factor_A=combo['A'], ss_factor_B=combo['B'], ss_factor_C=combo['C'])
        sim, _ = run_simulation(
            df, sku_stats, sim_year=sim_year, lead_time=lead_time,
            stockout_cost_per_unit=stockout_cost_per_unit)

        total_demand = sim['total_demand'].sum()
        total_stockout = sim['stockout_qty'].sum()
        service_rate = (1 - total_stockout / total_demand) * 100
        base_cost = sku_stats[sku_stats['Product ID'].isin(sim['Product ID'])]['total_inventory_cost'].sum()
        total_cost = base_cost + sim['stockout_cost'].sum()

        results.append({
            'label': combo['label'],
            'factor_a': combo['A'],
            'factor_b': combo['B'],
            'factor_c': combo['C'],
            'service_rate': round(service_rate, 2),
            'total_cost': round(total_cost, 0),
            'turnover': round(sim['turnover_rate'].mean(), 2),
            'avg_inventory': round(sim['avg_inventory'].mean(), 1),
        })

    return pd.DataFrame(results)


def find_elbow(values):
    """找拐点：边际收益开始低于 0.5% 的点；没找到则返回 None。"""
    if len(values) < 3:
        return None
    margins = [values[i] - values[i-1] for i in range(1, len(values))]
    for i, m in enumerate(margins):
        if m < 0.5:
            return i  # 拐点索引（对应 values 的索引 i）
    return None


def sensitivity_summary(df):
    """返回一个可读的总结文本。"""
    parts = {}
    for col in ['factor_a', 'factor_b', 'factor_c']:
        sub = df[df[col] == df[col].dropna().iloc[0]] if col == 'factor_a' else df  # 简化
    pass
