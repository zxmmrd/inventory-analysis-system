import sys
from pathlib import Path
import unittest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.forecast import build_forecast_eval, forecast_metrics


def make_df():
    records = []
    for year in range(2015, 2019):
        for month in (3, 7, 11):
            records.append({
                'Product ID': 'SKU-1',
                'Order Date': pd.Timestamp(f'{year}-{month:02d}-10'),
                'Quantity': 10 + (year - 2015),
                'Sales': 100,
            })
    return pd.DataFrame(records)


def make_sku_stats(df):
    return pd.DataFrame({
        'Product ID': ['SKU-1'],
        'ABC_Class': ['A'],
        'annual_demand': [20],
    })


class TestForecast(unittest.TestCase):
    def test_build_forecast_eval_columns(self):
        df = make_df()
        sku_stats = make_sku_stats(df)
        out = build_forecast_eval(df, sku_stats)
        expected = {'Product ID', 'ABC_Class', 'train_events', 'actual_total', 'prev_total',
                    'croston_pred', 'sma_pred', 'croston_error', 'sma_error', 'naive_error', 'bucket'}
        self.assertEqual(set(out.columns), expected)
        self.assertGreaterEqual(len(out), 1)

    def test_forecast_metrics_empty(self):
        empty = pd.DataFrame()
        metrics = forecast_metrics(empty)
        self.assertEqual(metrics['SKU数'], 0)

    def test_forecast_metrics_nonempty(self):
        df = make_df()
        sku_stats = make_sku_stats(df)
        out = build_forecast_eval(df, sku_stats)
        metrics = forecast_metrics(out)
        self.assertIn('SKU数', metrics)
        self.assertGreater(metrics['SKU数'], 0)
