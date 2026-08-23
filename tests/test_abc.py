import sys
from pathlib import Path
import unittest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.abc import calc_abc


def make_df(sales_by_sku):
    """构造一个仅含 Product ID / Sales 的最小订单表。"""
    rows = []
    for sku_id, sales in sales_by_sku.items():
        rows.append({'Product ID': sku_id, 'Sales': sales})
    return pd.DataFrame(rows)


class TestCalcABC(unittest.TestCase):
    def test_three_skus_parito(self):
        df = make_df({
            'SKU-A': 700,
            'SKU-B': 200,
            'SKU-C': 100,
        })
        out = calc_abc(df)
        mapping = dict(zip(out['Product ID'], out['ABC_Class']))
        self.assertEqual(mapping['SKU-A'], 'A')
        self.assertEqual(mapping['SKU-B'], 'B')
        self.assertEqual(mapping['SKU-C'], 'C')

    def test_boundary_70_and_90(self):
        df = make_df({
            'SKU-1': 70,
            'SKU-2': 20,
            'SKU-3': 5,
            'SKU-4': 5,
        })
        out = calc_abc(df)
        mapping = dict(zip(out['Product ID'], out['ABC_Class']))
        self.assertEqual(mapping['SKU-1'], 'A')
        self.assertIn(mapping['SKU-3'], ('A', 'B', 'C'))

    def test_output_columns(self):
        df = make_df({'SKU-A': 100, 'SKU-B': 50})
        out = calc_abc(df)
        self.assertEqual(set(out.columns), {'Product ID', 'Sales', 'cum_sales', 'cum_pct', 'ABC_Class'})
