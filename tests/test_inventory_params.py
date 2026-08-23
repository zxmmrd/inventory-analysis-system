import sys
from pathlib import Path
import unittest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.inventory_params import calc_inventory_params


def make_df():
    """构造一个仅含一个 SKU 的最小订单表。"""
    records = []
    for date, qty in [
        ('2018-01-05', 10),
        ('2018-03-10', 6),
        ('2018-07-01', 8),
        ('2018-11-20', 12),
    ]:
        records.append({'Product ID': 'SKU-1', 'Order Date': pd.Timestamp(date), 'Quantity': qty, 'Sales': qty * 50})
    return pd.DataFrame(records)


class TestInventoryParams(unittest.TestCase):
    def test_output_rows_equal_skus(self):
        stats = calc_inventory_params(make_df())
        self.assertEqual(len(stats), 1)
        self.assertIn(stats['ABC_Class'].iloc[0], ['A', 'B', 'C'])

    def test_rop_formula(self):
        stats = calc_inventory_params(make_df(), lead_time=4)
        row = stats.iloc[0]
        expected_rop = row['daily_rate'] * 4 + row['safety_stock']
        self.assertAlmostEqual(row['rop'], expected_rop, places=2)

    def test_eoq_positive(self):
        stats = calc_inventory_params(make_df())
        self.assertTrue((stats['eoq'] > 0).all())
