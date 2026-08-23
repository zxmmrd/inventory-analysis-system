"""ABC 分类模块。"""
import pandas as pd


def calc_abc(df):
    """按销售额计算每个 SKU 的 ABC 分类。
    
    A 类：累计销售额占比前 70%
    B 类：70% ~ 90%
    C 类：后 10%
    """
    sku_sales = df.groupby('Product ID')['Sales'].sum().sort_values(ascending=False).reset_index()
    sku_sales.columns = ['Product ID', 'Sales']
    sku_sales['cum_sales'] = sku_sales['Sales'].cumsum()
    sku_sales['cum_pct'] = sku_sales['cum_sales'] / sku_sales['Sales'].sum() * 100

    def abc_class(pct):
        if pct <= 70:
            return 'A'
        elif pct <= 90:
            return 'B'
        else:
            return 'C'

    sku_sales['ABC_Class'] = sku_sales['cum_pct'].apply(abc_class)
    return sku_sales
