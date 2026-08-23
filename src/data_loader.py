"""数据加载模块。"""
import pandas as pd

from src.config import BASE_DIR


def load_data():
    """加载清洗后的订单数据，并补充年/月列。"""
    data_path = BASE_DIR / '数据' / 'df_cleaned.pkl'
    df = pd.read_pickle(data_path)

    if df['Order Date'].dtype != 'datetime64[ns]':
        df['Order Date'] = pd.to_datetime(df['Order Date'])
    if 'Ship Date' in df.columns and df['Ship Date'].dtype != 'datetime64[ns]':
        df['Ship Date'] = pd.to_datetime(df['Ship Date'])

    df['year'] = df['Order Date'].dt.year
    df['month'] = df['Order Date'].dt.month
    return df
