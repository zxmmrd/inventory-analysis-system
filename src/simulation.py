"""补货模拟引擎。"""
import pandas as pd
import numpy as np


def run_simulation(df, sku_stats, sim_year=2018, lead_time=4, stockout_cost_per_unit=20):
    """逐日滚动模拟补货过程，返回每个 SKU 的服务水平、缺货、库存、成本等指标。"""
    df_sim = df[df['Order Date'].dt.year == sim_year]
    daily_sales = df_sim.groupby(['Product ID', 'Order Date'])['Quantity'].sum().reset_index()
    daily_sales.columns = ['Product ID', 'Date', 'Demand']

    results = []
    daily_records = {}

    for _, row in sku_stats.iterrows():
        pid = row['Product ID']
        if pid not in daily_sales['Product ID'].values:
            continue

        rop = row['rop']
        eoq = row['eoq']
        safety_stock = row['safety_stock']

        sku_demand = daily_sales[daily_sales['Product ID'] == pid].set_index('Date')['Demand']
        date_range = pd.date_range(start=f'{sim_year}-01-01', end=f'{sim_year}-12-31', freq='D')
        full_demand = sku_demand.reindex(date_range, fill_value=0)

        # 简化处理：以稳态平均库存作为年初初始库存；真实业务应从盘点实值开始
        inventory = safety_stock + eoq / 2
        pending_orders = []
        stockout_count = 0
        stockout_qty = 0
        order_count = 0
        total_demand = 0
        daily_inv = []

        for date, demand in full_demand.items():
            arrived = sum(q for arr_date, q in pending_orders if arr_date <= date)
            if arrived > 0:
                inventory += arrived
                pending_orders = [(d, q) for d, q in pending_orders if d > date]

            total_demand += demand
            if inventory >= demand:
                inventory -= demand
            else:
                # 部分满足：用掉剩余库存，只把不足部分记为缺货量
                stockout_qty += demand - inventory
                stockout_count += 1
                inventory = 0

            if inventory <= rop and len(pending_orders) == 0:
                arrive_date = date + pd.Timedelta(days=lead_time)
                pending_orders.append((arrive_date, eoq))
                order_count += 1

            daily_inv.append({'date': date, 'inventory': inventory})

        service_rate = (1 - stockout_qty / total_demand) * 100 if total_demand > 0 else 100
        avg_inv = np.mean([d['inventory'] for d in daily_inv])
        turnover = total_demand / avg_inv if avg_inv > 0 else 0

        results.append({
            'Product ID': pid,
            'total_demand': total_demand,
            'stockout_days': stockout_count,
            'stockout_qty': stockout_qty,
            'stockout_cost': round(stockout_qty * stockout_cost_per_unit, 2),
            'service_rate': round(service_rate, 2),
            'order_count': order_count,
            'avg_inventory': round(avg_inv, 1),
            'turnover_rate': round(turnover, 2)
        })
        daily_records[pid] = daily_inv

    sim_results = pd.DataFrame(results)
    sim_results = sim_results.merge(sku_stats[['Product ID', 'ABC_Class']], on='Product ID', how='left')

    return sim_results, daily_records
