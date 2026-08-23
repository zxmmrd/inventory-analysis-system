"""回归验证：确认模拟基线指标不随重构改变。

用法（在项目根目录）：
    python scripts/regression_check.py

基线指标（Phase 1 验证通过的数值）：
- 整体服务水平 ≈ 93.79%
- 平均周转率 ≈ 1.75 次/年
- 平均库存 ≈ 13.4 件
- 总缺货量 ≈ 1158.5 件
"""
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.abc import calc_abc  # noqa: E402
from src.analysis import build_export_data, to_excel_download  # noqa: E402
from src.data_loader import load_data  # noqa: E402
from src.forecast import build_forecast_eval, forecast_metrics  # noqa: E402
from src.inventory_params import calc_inventory_params  # noqa: E402
from src.simulation import run_simulation  # noqa: E402


def main():
    ok = True

    df = load_data()
    sku_stats = calc_inventory_params(df)
    sim_results, _ = run_simulation(df, sku_stats, sim_year=2018, lead_time=4, stockout_cost_per_unit=20)

    total_demand = sim_results['total_demand'].sum()
    total_stockout = sim_results['stockout_qty'].sum()
    service_rate = (1 - total_stockout / total_demand) * 100
    turnover = sim_results['turnover_rate'].mean()
    avg_inv = sim_results['avg_inventory'].mean()

    checks = {
        '整体服务水平 ≈ 93.79%': (service_rate, 93.29, 94.29),
        '平均周转率 ≈ 1.75': (turnover, 1.65, 1.85),
        '平均库存 ≈ 13.4': (avg_inv, 13.0, 13.8),
        '总缺货量 ≈ 1158.5': (total_stockout, 1138.0, 1178.0),
    }

    print('=== 回归验证结果 ===')
    for label, (value, low, high) in checks.items():
        passed = low <= value <= high
        ok = ok and passed
        print(f'{"PASS" if passed else "FAIL"} | {label} | {value:.2f}')

    # 顺带检查 src 模块链路可用
    forecast_df = build_forecast_eval(df, sku_stats)
    print(f'INFO | 预测评估 SKU 数 | {len(forecast_df)}')
    sheets = build_export_data(sku_stats, sim_results, comparison=None)
    print(f'INFO | 导出 Sheet 数 | {len(sheets)}')

    print('\n' + ('REGRESSION OK' if ok else 'REGRESSION FAILED'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
