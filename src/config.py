"""项目默认参数与路径常量。

把散落在代码里的魔法数字集中到一处：以后调整模型参数，
只需要改这个文件，不需要翻遍所有代码。
"""
from pathlib import Path

# 项目根目录：src/ 的上一级就是项目的根目录
# 这样无论从哪里启动，都能准确定位到“数据/”“Dashboard/”等目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 模型默认参数
DEFAULT_LEAD_TIME = 4            # 补货提前期（天）
DEFAULT_ORDERING_COST = 50       # 单次订货成本（元）
DEFAULT_HOLDING_RATE = 0.25      # 年持有成本率
DEFAULT_SS_FACTOR_A = 2.0        # A 类安全系数
DEFAULT_SS_FACTOR_B = 1.0        # B 类安全系数
DEFAULT_SS_FACTOR_C = 0.5        # C 类安全系数
DEFAULT_STOCKOUT_COST = 20       # 单件缺货成本（元）

# 需求预测参数
FORECAST_ALPHA = 0.3             # Croston 平滑系数
FORECAST_MIN_EVENTS = 4          # 训练期至少需要的非零订单次数
FORECAST_TRAIN_START = '2015-01-01'
FORECAST_TRAIN_END = '2017-12-31'
FORECAST_VAL_YEAR = 2018
