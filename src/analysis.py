"""汇总、对比与导出数据构建。"""
import pandas as pd
from io import BytesIO


def to_excel_download(filename, sheets_dict):
    """将多个 DataFrame 导出为 Excel 文件，返回 bytes。"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in sheets_dict.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output.getvalue()


def build_export_data(sku_stats, sim_results, comparison=None, df=None):
    """构建导出数据字典（多 Sheet），用于 Excel 下载。"""
    sheets = {}

    export_params = sku_stats.copy()
    export_params = export_params.rename(columns={
        'Product ID': 'SKU编号', 'ABC_Class': 'ABC分类',
        'annual_demand': '年需求量', 'avg_order_qty': '平均订单量',
        'daily_rate': '日平均需求率',
        'safety_stock': '安全库存', 'rop': '再订货点ROP',
        'eoq': 'EOQ经济批量', 'avg_inventory': '平均库存量',
        'total_inventory_cost': '年库存总成本',
        'orders_per_year': '年订货次数', 'turnover_rate': '库存周转率'
    })
    if 'ss_factor' in export_params.columns:
        export_params = export_params.drop(columns=['ss_factor'])
    sheets['SKU库存参数明细'] = export_params

    export_sim = sim_results.copy()
    export_sim = export_sim.rename(columns={
        'Product ID': 'SKU编号', 'ABC_Class': 'ABC分类',
        'total_demand': '总需求量', 'stockout_days': '缺货天数',
        'stockout_qty': '缺货数量', 'service_rate': '服务水平(%)',
        'stockout_cost': '缺货成本',
        'order_count': '订货次数', 'avg_inventory': '平均库存',
        'turnover_rate': '周转率(次/年)'
    })
    sheets['补货模拟结果'] = export_sim

    if comparison is not None:
        sheets['策略对比分析'] = comparison.copy()

    if comparison is not None:
        abc_summary = export_params.groupby('ABC分类').agg(
            SKU数量=('SKU编号', 'count'),
            年需求总量=('年需求量', 'sum'),
            安全库存总量=('安全库存', 'sum'),
            平均库存总量=('平均库存量', 'sum'),
            年库存总成本=('年库存总成本', 'sum')
        ).round(2).reset_index()
        sheets['ABC分类汇总'] = abc_summary

    return sheets
def build_disposal_analysis(sku_stats, data_years=4, discount_rate=0.5,
                            projected_years=2, future_years=1, future_sales_prob=0.2):
    """滞销SKU处置建议：对比继续持有、降价清仓、淘汰下架三种策略。
    
    滞销定义：年销售次数 ≤ 2 次（即 active_days / data_years ≤ 2）。
    - 继续持有：付出未来几年的持有成本
    - 降价清仓：一次性折价损失，但释放库存资金
    - 淘汰下架：放弃未来潜在销售（机会成本），按年需求 × 单价 × 概率估算
    """
    slow = sku_stats[sku_stats['active_days'] / data_years <= 2].copy()
    if slow.empty:
        return pd.DataFrame()

    slow['annual_holding'] = slow['annual_holding_cost']
    slow['inv_value'] = slow['avg_inventory'] * slow['unit_price']

    rows = []
    for _, row in slow.iterrows():
        hold_cost = row['annual_holding'] * projected_years
        clearance_loss = row['inv_value'] * discount_rate
        clearance_recovery = row['inv_value'] * (1 - discount_rate)
        # 机会成本：滞销不等于零需求，淘汰会损失未来可能发生的销售
        discontinue_loss = row['annual_demand'] * row['unit_price'] * future_years * future_sales_prob

        costs = {
            '继续持有': round(hold_cost, 2),
            '降价清仓': round(clearance_loss, 2),
            '淘汰下架': round(discontinue_loss, 2),
        }
        best = min(costs, key=costs.get)

        rows.append({
            'Product ID': row['Product ID'],
            'ABC_Class': row['ABC_Class'],
            '年需求量': int(row['annual_demand']),
            '平均库存': round(row['avg_inventory'], 1),
            '库存价值': round(row['inv_value'], 2),
            '年持有成本': round(row['annual_holding'], 2),
            '继续持有成本': costs['继续持有'],
            '清仓损失': costs['降价清仓'],
            '淘汰损失': costs['淘汰下架'],
            '推荐策略': best,
        })

    result = pd.DataFrame(rows)
    result = result.sort_values('继续持有成本', ascending=False).reset_index(drop=True)
    return result
