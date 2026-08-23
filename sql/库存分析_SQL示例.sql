-- ==========================================
-- 库存分析 SQL 示例
-- 对应项目：智能库存分析与补货模拟系统
-- 数据库：SQLite（假设 orders 表结构与 train.csv 一致）
-- 说明：模拟结果表（simulation_results）由 Python 模拟生成，
--       使用时需先通过 run_simulation 产生该表。
-- ==========================================

-- 查询 1: ABC 分类（按销售额累计占比）
-- 对应项目：ABC 分类模块
-- 使用窗口函数计算累计销售额占比，按帕累托原则分 A/B/C 三类
SELECT
    "Product ID" AS sku_id,
    ROUND(SUM(Sales), 2) AS total_sales,
    ROUND(SUM(SUM(Sales)) OVER (ORDER BY SUM(Sales) DESC)
          / SUM(SUM(Sales)) OVER () * 100, 2) AS cum_pct,
    CASE
        WHEN SUM(SUM(Sales)) OVER (ORDER BY SUM(Sales) DESC)
             / SUM(SUM(Sales)) OVER () * 100 <= 70 THEN 'A'
        WHEN SUM(SUM(Sales)) OVER (ORDER BY SUM(Sales) DESC)
             / SUM(SUM(Sales)) OVER () * 100 <= 90 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM orders
GROUP BY "Product ID"
ORDER BY total_sales DESC;

-- 查询 2: 月度销售额与销量趋势
-- 对应项目：EDA 数据探索
SELECT
    strftime('%Y-%m', "Order Date") AS month,
    ROUND(SUM(Sales), 2) AS total_sales,
    SUM(Quantity) AS total_quantity,
    COUNT(DISTINCT "Order ID") AS order_count
FROM orders
GROUP BY month
ORDER BY month;

-- 查询 3: 缺货量 Top 10 SKU
-- 对应项目：补货模拟结果分析
-- 需先通过 Python 模拟生成 simulation_results 表
-- 该表包含字段：Product ID, ABC_Class, stockout_qty, service_rate
-- 真实业务中，该表来自每日库存水位计算
SELECT
    "Product ID" AS sku_id,
    "ABC_Class" AS abc_class,
    stockout_qty,
    ROUND(service_rate, 2) AS service_rate
FROM simulation_results
ORDER BY stockout_qty DESC
LIMIT 10;

-- 查询 4: 滞销 SKU 预警
-- 对应项目：业务洞察 - 滞销SKU预警
-- 条件：年均销售次数 ≤ 2 次（数据跨度 4 年，即 ≤ 8 次）
SELECT
    "Product ID" AS sku_id,
    COUNT(DISTINCT "Order Date") AS order_days,
    ROUND(COUNT(DISTINCT "Order Date") / 4.0, 1) AS avg_orders_per_year,
    SUM(Quantity) AS total_quantity,
    ROUND(SUM(Sales), 2) AS total_sales
FROM orders
GROUP BY "Product ID"
HAVING avg_orders_per_year <= 2
ORDER BY avg_orders_per_year;

-- 查询 5: ABC 类别服务水平与缺货汇总
-- 对应项目：策略对比分析
-- 需 simulation_results 表（包含 Product ID, ABC_Class, service_rate, stockout_qty）
SELECT
    "ABC_Class" AS abc_class,
    COUNT(*) AS sku_count,
    ROUND(AVG(service_rate), 2) AS avg_service_rate,
    SUM(stockout_qty) AS total_stockout,
    SUM(CASE WHEN stockout_qty > 0 THEN 1 ELSE 0 END) AS stockout_sku_count
FROM simulation_results
GROUP BY "ABC_Class"
ORDER BY abc_class;
