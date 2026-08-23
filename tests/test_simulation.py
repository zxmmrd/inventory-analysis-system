import sys
from pathlib import Path
import unittest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.inventory_params import calc_inventory_params
from src.simulation import run_simulation


def make_df():
    records = []
    for year in range(2016, 2019):
        for month in range(1, 13):
            qty = 8 if (year == 2018 and month in (3, 7, 11)) else 2
            records.append({
                'Product ID': 'SKU-1',
                'Order Date': pd.Timestamp(f'{year}-{month:02d}-10'),
                'Quantity': qty,
                'Sales': qty * 50,
            })
    return pd.DataFrame(records)


class TestSimulation(unittest.TestCase):
    def test_service_rate_range(self):
        df = make_df()
        sku_stats = calc_inventory_params(df)
        sim, records = run_simulation(df, sku_stats, sim_year=2018, lead_time=4)
        row = sim.iloc[0]
        self.assertGreaterEqual(row['service_rate'], 0)
        self.assertLessEqual(row['service_rate'], 100)
        self.assertGreaterEqual(row['stockout_qty'], 0)

    def test_return_containers(self):
        df = make_df()
        sku_stats = calc_inventory_params(df)
        sim, daily_records = run_simulation(df, sku_stats, sim_year=2018)
        self.assertIsInstance(sim, pd.DataFrame)
        self.assertIsInstance(daily_records, dict)
