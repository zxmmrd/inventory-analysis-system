import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
import sys

# 让 Dashboard 能找到项目根目录下的 src/ 包（项目根目录 = Dashboard 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.abc import calc_abc
from src.inventory_params import calc_inventory_params
from src.simulation import run_simulation as _run_simulation
from src.forecast import build_forecast_eval as _build_forecast_eval, forecast_metrics
from src.data_loader import load_data as _load_data
from src.analysis import build_export_data, to_excel_download, build_disposal_analysis
from src.sensitivity import run_sensitivity_analysis as _run_sensitivity_analysis, find_elbow


@st.cache_data
def run_simulation(df, sku_stats, sim_year=2018, lead_time=4, stockout_cost_per_unit=20):
    """缓存包装：调用 src 中的模拟引擎，避免每次交互重复计算。"""
    return _run_simulation(df, sku_stats, sim_year, lead_time, stockout_cost_per_unit)
# ==========================================
# 页面配置
# ==========================================
st.set_page_config(
    page_title="智能库存分析与补货模拟系统",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# 数据加载与缓存
# ==========================================
@st.cache_data
def load_data():
    """缓存包装：调用 src 中的数据加载，自动定位项目根目录。"""
    return _load_data()


@st.cache_data
def run_sensitivity_analysis(df, sim_year=2018, lead_time=4, stockout_cost_per_unit=20):
    """缓存包装：调用 src 中的敏感性分析，避免每次交互重复计算。"""
    return _run_sensitivity_analysis(df, sim_year, lead_time, stockout_cost_per_unit)


@st.cache_data
def build_forecast_eval(df, sku_stats):
    """缓存包装：调用 src 中的预测评估，避免重复计算。"""
    return _build_forecast_eval(df, sku_stats)


def render_forecast_tab(df, sku_stats, forecast_df):
    """需求预测 Tab：Croston vs SMA 效果对比"""
    st.markdown("### 🔮 需求预测：Croston vs SMA")
    st.caption("用2015-2017历史订单训练，预测2018年需求量，对比两种方法在间歇性需求数据上的预测误差。")

    if forecast_df.empty:
        st.info("当前筛选条件下没有足够的训练数据（至少需要4次非零订单），请调整筛选条件后再查看。")
        return

    overall = forecast_metrics(forecast_df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔬 评估SKU数", f"{overall['SKU数']} 个")
    c2.metric("Croston MAE", f"{overall['Croston MAE']:.1f}")
    c3.metric("SMA MAE", f"{overall['SMA MAE']:.1f}")
    c4.metric("Croston MASE", f"{overall['Croston MASE']:.2f}")

    st.markdown("---")
    st.subheader("📊 预测误差对比")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**整体指标**")
        st.dataframe(pd.DataFrame([overall]), use_container_width=True, hide_index=True)
        st.markdown("**按ABC分类**")
        by_abc = forecast_df.groupby('ABC_Class').apply(forecast_metrics, include_groups=False).reset_index()
        st.dataframe(by_abc, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**按需求频率**")
        by_bucket = forecast_df.groupby('bucket').apply(forecast_metrics, include_groups=False).reset_index()
        st.dataframe(by_bucket, use_container_width=True, hide_index=True)
        st.markdown("**MAE 越小越好 · MASE < 1 说明优于上一年直接预测**")

    st.markdown("---")
    st.subheader("📌 实际 vs 预测")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=forecast_df['actual_total'], y=forecast_df['croston_pred'],
                             mode='markers', name='Croston', marker=dict(color='#3b82f6', opacity=0.6)))
    fig.add_trace(go.Scatter(x=forecast_df['actual_total'], y=forecast_df['sma_pred'],
                             mode='markers', name='SMA', marker=dict(color='#f59e0b', opacity=0.6)))
    max_val = max(forecast_df['actual_total'].max(),
                  forecast_df['croston_pred'].max(),
                  forecast_df['sma_pred'].max()) * 1.05
    fig.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode='lines',
                             name='完全准确', line=dict(dash='dash', color='#ef4444')))
    fig.update_layout(title='各SKU 2018年实际需求量 vs 预测需求量',
                      xaxis_title='实际需求量', yaxis_title='预测需求量', height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.info("💡 **方法解读**：当前数据为典型的间歇性需求（多数SKU年均≤3次订单），"
            "训练期内非零订单通常只有4~7次，Croston的优势需要更长的历史序列才能充分体现，"
            "因此在本数据上SMA更稳。若未来扩展到更长历史或更高频品类，可重新评估Croston/SBA等方法的适用性。")


# ==========================================
# Tab1: 策略模拟页面
# ==========================================
def render_strategy_tab(df, sku_stats, sim_results, daily_records, lead_time, ordering_cost, holding_rate,
                        ss_factor_A, ss_factor_B, ss_factor_C, sim_year, comparison, overall_cost):
    # ===== KPI卡片 =====
    col1, col2, col3, col4 = st.columns(4)
    total_skus = len(sim_results)
    avg_service = sim_results['service_rate'].mean()
    total_cost = overall_cost
    avg_turnover = sim_results['turnover_rate'].mean()

    col1.metric("📊 模拟SKU数", f"{total_skus} 个")
    col2.metric("🎯 平均服务水平", f"{avg_service:.2f}%")
    col3.metric("💰 年总成本(含缺货)", f"${total_cost:,.0f}")
    col4.metric("🔄 平均周转率", f"{avg_turnover:.2f} 次/年")

    st.markdown("---")

    # ===== ABC分类分析 =====
    st.subheader("📊 ABC分类分析")

    abc_sales = df.groupby('Product ID')['Sales'].sum().reset_index()
    abc_sales = abc_sales.merge(sku_stats[['Product ID', 'ABC_Class']], on='Product ID', how='left')
    abc_summary = abc_sales.groupby('ABC_Class').agg(
        SKU数=('Product ID', 'count'),
        总销售额=('Sales', 'sum')
    ).reset_index()
    abc_summary['销售额占比'] = (abc_summary['总销售额'] / abc_summary['总销售额'].sum() * 100).round(1)
    abc_summary['SKU占比'] = (abc_summary['SKU数'] / abc_summary['SKU数'].sum() * 100).round(1)

    col1, col2 = st.columns(2)

    with col1:
        sku_sales_sorted = abc_sales.sort_values('Sales', ascending=False).reset_index(drop=True)
        sku_sales_sorted['cum_pct'] = (sku_sales_sorted['Sales'].cumsum() / sku_sales_sorted['Sales'].sum() * 100).round(2)
        sku_sales_sorted['sku_idx'] = range(1, len(sku_sales_sorted) + 1)
        sku_sales_sorted['sku_pct'] = (sku_sales_sorted['sku_idx'] / len(sku_sales_sorted) * 100).round(2)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=sku_sales_sorted['sku_pct'], y=sku_sales_sorted['Sales'],
                             name='销售额', marker_color='#3b82f6', opacity=0.6))
        fig.add_trace(go.Scatter(x=sku_sales_sorted['sku_pct'], y=sku_sales_sorted['cum_pct'],
                                 name='累计占比', mode='lines', line=dict(color='#ef4444', width=2), yaxis='y2'))
        fig.add_hline(y=70, line_dash="dash", line_color="#22c55e", annotation_text="A类分界 70%", yref='y2')
        fig.add_hline(y=90, line_dash="dash", line_color="#f59e0b", annotation_text="B类分界 90%", yref='y2')
        fig.update_layout(
            title='帕累托曲线（ABC分类）',
            xaxis_title='SKU累计占比 (%)', yaxis_title='销售额',
            yaxis2=dict(title='累计销售额占比 (%)', overlaying='y', side='right', range=[0, 105]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure(data=[
            go.Bar(name='SKU占比 (%)', x=abc_summary['ABC_Class'], y=abc_summary['SKU占比'],
                   marker_color='#60a5fa', text=abc_summary['SKU占比'].astype(str) + '%', textposition='auto'),
            go.Bar(name='销售额占比 (%)', x=abc_summary['ABC_Class'], y=abc_summary['销售额占比'],
                   marker_color='#f59e0b', text=abc_summary['销售额占比'].astype(str) + '%', textposition='auto')
        ])
        fig.update_layout(title='ABC分类：SKU占比 vs 销售额占比', barmode='group', height=400,
                          xaxis_title='ABC类别', yaxis_title='占比 (%)')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ===== 补货模拟结果 =====
    st.subheader("📈 补货模拟结果")

    sim_summary = sim_results.groupby('ABC_Class').agg(
        SKU数=('Product ID', 'count'),
        平均服务水平=('service_rate', 'mean'),
        总缺货量=('stockout_qty', 'sum'),
        总订单数=('order_count', 'sum'),
        平均周转率=('turnover_rate', 'mean')
    ).round(2).reset_index()

    cost_summary = sku_stats[sku_stats['Product ID'].isin(sim_results['Product ID'])].groupby('ABC_Class').agg(
        年库存成本=('total_inventory_cost', 'sum')
    ).round(0).reset_index()
    sim_summary = sim_summary.merge(cost_summary, on='ABC_Class', how='left')

    col1, col2, col3 = st.columns(3)
    color_map = {'A': '#ef4444', 'B': '#f59e0b', 'C': '#22c55e'}
    colors = [color_map.get(c, '#3b82f6') for c in sim_summary['ABC_Class']]

    with col1:
        fig = go.Figure(data=[go.Bar(x=sim_summary['ABC_Class'], y=sim_summary['平均服务水平'],
                                     marker_color=colors, text=sim_summary['平均服务水平'].astype(str) + '%',
                                     textposition='auto')])
        fig.update_layout(title='各类别平均服务水平', yaxis=dict(range=[80, 100]), height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure(data=[go.Bar(x=sim_summary['ABC_Class'], y=sim_summary['平均周转率'],
                                     marker_color=colors, text=sim_summary['平均周转率'].round(2).astype(str),
                                     textposition='auto')])
        fig.update_layout(title='各类别平均库存周转率 (次/年)', height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col3:
        fig = go.Figure(data=[go.Bar(x=sim_summary['ABC_Class'], y=sim_summary['年库存成本'],
                                     marker_color=colors,
                                     text=['$' + f'{v:,.0f}' for v in sim_summary['年库存成本']],
                                     textposition='auto')])
        fig.update_layout(title='各类别年库存成本', height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ===== 单个SKU库存曲线 =====
    st.subheader("📉 单个SKU库存变化曲线")
    col1, col2 = st.columns([1, 3])

    with col1:
        selected_class = st.selectbox("选择ABC类别", ['A', 'B', 'C'], index=0, key='curve_class')
        class_skus = sim_results[sim_results['ABC_Class'] == selected_class]['Product ID'].tolist()
        selected_sku = st.selectbox("选择SKU", class_skus[:min(20, len(class_skus))], index=0, key='curve_sku')

    with col2:
        if selected_sku in daily_records:
            sku_data = daily_records[selected_sku]
            dates = [d['date'] for d in sku_data]
            invs = [d['inventory'] for d in sku_data]
            rop_val = sku_stats[sku_stats['Product ID'] == selected_sku]['rop'].values[0]
            ss_val = sku_stats[sku_stats['Product ID'] == selected_sku]['safety_stock'].values[0]
            eoq_val = sku_stats[sku_stats['Product ID'] == selected_sku]['eoq'].values[0]
            sku_result = sim_results[sim_results['Product ID'] == selected_sku].iloc[0]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=invs, mode='lines', name='库存水平',
                                     line=dict(color='#3b82f6', width=1.5),
                                     fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)'))
            fig.add_hline(y=rop_val, line_dash="dash", line_color="#f59e0b",
                          annotation_text=f'ROP = {rop_val:.0f}', annotation_position="right")
            fig.add_hline(y=ss_val, line_dash="dash", line_color="#ef4444",
                          annotation_text=f'安全库存 = {ss_val:.0f}', annotation_position="right")
            fig.update_layout(
                title=f'SKU: {selected_sku}  |  服务水平: {sku_result["service_rate"]}%  |  周转率: {sku_result["turnover_rate"]}次/年  |  EOQ: {eoq_val:.0f}',
                xaxis_title='日期', yaxis_title='库存量', height=400, hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ===== 成本-服务水平权衡 =====
    st.subheader("⚖️ 成本-服务水平权衡分析")
    st.markdown("调整左侧安全库存系数，观察服务水平与库存成本的变化关系")

    overall_service = sim_results['service_rate'].mean()
    overall_cost_val = overall_cost
    overall_turnover = sim_results['turnover_rate'].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("综合服务水平", f"{overall_service:.2f}%")
    col2.metric("年总成本(含缺货)", f"${overall_cost_val:,.0f}")
    col3.metric("综合周转率", f"{overall_turnover:.2f} 次/年")

    st.info("💡 **面试亮点提示**：通过滑动左侧的安全库存系数，可以直观展示「服务水平」与「库存成本」之间的权衡关系。"
            "A类商品提高安全系数（服务水平优先），C类降低安全系数（成本优先），这就是差异化库存管理的核心价值。")

    st.markdown("---")

    # ===== 策略对比分析 =====
    st.subheader("🔬 多策略对比分析")
    st.markdown("对比三种库存管理策略的综合表现，直观展示差异化管理的价值")

    st.dataframe(
        comparison.style.format({
            '服务水平(%)': '{:.2f}', '年库存成本($)': '${:,.0f}',
            '缺货成本($)': '${:,.0f}', '总成本($)': '${:,.0f}',
            '周转率(次/年)': '{:.2f}', '总缺货量': '{:,}', '总订单数': '{:,}'
        }),
        use_container_width=True, hide_index=True, height=180
    )

    col1, col2 = st.columns(2)

    with col1:
        radar_data = []
        for _, row in comparison.iterrows():
            radar_data.append({
                '策略': row['策略'],
                '服务水平': row['服务水平(%)'] / comparison['服务水平(%)'].max() * 100,
                '周转率': row['周转率(次/年)'] / comparison['周转率(次/年)'].max() * 100,
                '成本效率': (1 - row['总成本($)'] / comparison['总成本($)'].max()) * 100,
                '缺货控制': (1 - row['总缺货量'] / comparison['总缺货量'].max()) * 100,
                '订单效率': row['总订单数'] / comparison['总订单数'].max() * 100
            })
        radar_df = pd.DataFrame(radar_data)
        categories = ['服务水平', '周转率', '成本效率', '缺货控制', '订单效率']

        fig = go.Figure()
        colors = ['#3b82f6', '#f59e0b', '#ef4444']
        for i, row in radar_df.iterrows():
            fig.add_trace(go.Scatterpolar(
                r=[row[cat] for cat in categories], theta=categories, fill='toself',
                name=row['策略'], line=dict(color=colors[i], width=2),
                fillcolor=colors[i], opacity=0.2
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100]),
                       angularaxis=dict(tickfont=dict(size=12))),
            title='策略综合能力雷达图（值越高越好）',
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        colors_map = {'策略A: ABC差异化': '#3b82f6', '策略B: 统一安全库存': '#f59e0b', '策略C: 零安全库存': '#ef4444'}
        for _, row in comparison.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['总成本($)']], y=[row['服务水平(%)']],
                mode='markers+text', name=row['策略'],
                marker=dict(size=20, color=colors_map[row['策略']], line=dict(width=2, color='white')),
                text=[row['策略'].split(': ')[1]], textposition='top center', textfont=dict(size=11),
                hovertemplate=f"{row['策略']}<br>总成本: ${row['总成本($)']:,.0f}<br>服务水平: {row['服务水平(%)']}%<br>周转率: {row['周转率(次/年)']}次/年<extra></extra>"
            ))
        fig.update_layout(
            title='总成本-服务水平权衡矩阵',
            xaxis_title='总成本($) (含缺货成本)', yaxis_title='平均服务水平 (%)',
            yaxis=dict(range=[min(comparison['服务水平(%)']) - 5, 100]),
            height=450, showlegend=False, hovermode='closest'
        )
        st.plotly_chart(fig, use_container_width=True)

    delta_service = comparison.loc[0, '服务水平(%)'] - comparison.loc[1, '服务水平(%)'] 
    delta_cost = comparison.loc[0, '总成本($)'] - comparison.loc[1, '总成本($)']

    st.success(
        f"💡 **ABC差异化策略的价值**：与'一刀切'的统一安全库存相比，"
        f"ABC差异化策略在A类商品上多投入库存、C类少投入，"
        f"整体服务水平{'提升' if delta_service >= 0 else '下降'} **{abs(delta_service):.2f}%**，"
        f"同时总成本(含缺货成本){'增加' if delta_cost >= 0 else '节省'} **${abs(delta_cost):,.0f}**。"
        f"核心思路是：把有限的库存预算花在贡献最大销售额的A类商品上，实现资源的最优配置。"
    )

    st.markdown("---")

    # ===== SKU明细表格 =====
    st.subheader("📋 SKU库存参数明细")
    show_cols = ['Product ID', 'ABC_Class', 'annual_demand', 'safety_stock', 'rop', 'eoq',
                 'avg_inventory', 'total_inventory_cost']
    display_df = sku_stats[show_cols].copy()
    display_df.columns = ['SKU编号', 'ABC分类', '年需求量', '安全库存', '再订货点ROP', 'EOQ经济批量',
                          '平均库存', '年库存总成本']

    filter_class = st.multiselect("筛选ABC类别", ['A', 'B', 'C'], default=['A', 'B', 'C'], key='detail_filter')
    filtered_df = display_df[display_df['ABC分类'].isin(filter_class)]

    st.dataframe(
        filtered_df.style.format({
            '年需求量': '{:.0f}', '安全库存': '{:.0f}', '再订货点ROP': '{:.0f}',
            'EOQ经济批量': '{:.0f}', '平均库存': '{:.0f}', '年库存总成本': '${:,.2f}'
        }),
        use_container_width=True, height=300
    )

# ==========================================
# Tab2: 业务洞察页面
# ==========================================
def render_insight_tab(df, sku_stats, sim_results):
    st.markdown("### 🎯 核心经营指标")
    col1, col2, col3, col4 = st.columns(4)

    total_orders = len(df)
    total_sales = df['Sales'].sum()
    total_skus = df['Product ID'].nunique()
    data_years = df['year'].nunique()

    col1.metric("📦 总订单数", f"{total_orders:,} 单")
    col2.metric("💰 总销售额", f"${total_sales:,.0f}")
    col3.metric("🏷️ SKU数量", f"{total_skus} 个")
    col4.metric("📅 数据跨度", f"{data_years} 年")

    st.markdown("---")

    # 第1行：缺货TOP10 + 成本拆解
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📉 缺货量 TOP 10 SKU")
        top_stockout = sim_results.nlargest(10, 'stockout_qty')[['Product ID', 'ABC_Class', 'stockout_qty', 'service_rate']]
        top_stockout = top_stockout.sort_values('stockout_qty', ascending=True).reset_index(drop=True)

        fig = go.Figure(data=[go.Bar(
            y=[f'S{i+1} ({row.ABC_Class})' for i, row in top_stockout.iterrows()],
            x=top_stockout['stockout_qty'],
            orientation='h',
            marker_color='#ef4444',
            text=top_stockout['stockout_qty'].astype(int).astype(str),
            textposition='auto'
        )])
        fig.update_layout(title='缺货最严重的10个SKU', xaxis_title='缺货数量',
                          height=400, margin=dict(l=80))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("💸 库存成本结构拆解")
        valid_skus = sku_stats[sku_stats['Product ID'].isin(sim_results['Product ID'])]
        total_holding = valid_skus['annual_holding_cost'].sum()
        total_ordering = valid_skus['annual_ordering_cost'].sum()
        total_stockout_cost = sim_results['stockout_cost'].sum()

        fig = go.Figure(data=[go.Pie(
            labels=['持有成本 (仓储+资金+损耗)', '订货成本 (物流+手续)', '缺货成本 (缺货损失)'],
            values=[total_holding, total_ordering, total_stockout_cost],
            marker=dict(colors=['#3b82f6', '#f59e0b', '#ef4444']),
            hole=0.5,
            textinfo='label+percent',
            texttemplate='%{label}<br>%{percent:.1%}',
            textfont=dict(size=12)
        )])
        fig.update_layout(
            title='年库存总成本结构(含缺货)', height=400,
            annotations=[dict(text=f'总成本<br>${total_holding + total_ordering + total_stockout_cost:,.0f}',
                              x=0.5, y=0.5, font_size=14, showarrow=False)]
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 第2行：季节性趋势
    st.subheader("📅 月度销售季节性趋势")

    monthly_sales = df.groupby('month')['Sales'].sum().reset_index()
    monthly_qty = df.groupby('month')['Quantity'].sum().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly_sales['month'], y=monthly_sales['Sales'],
                         name='销售额', marker_color='#3b82f6', opacity=0.7))
    fig.add_trace(go.Scatter(x=monthly_qty['month'], y=monthly_qty['Quantity'],
                             name='销售数量', mode='lines+markers',
                             line=dict(color='#ef4444', width=2), yaxis='y2'))

    month_names = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    fig.update_layout(
        title='月度销售额与销量趋势（多年平均）',
        xaxis=dict(tickvals=list(range(1, 13)), ticktext=month_names),
        yaxis_title='销售额 ($)',
        yaxis2=dict(title='销售数量', overlaying='y', side='right'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 第3行：滞销SKU预警 + ABC销售贡献
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚠️ 滞销SKU预警")
        st.caption("年销售次数 ≤ 2 次的SKU（占用库存但周转极慢）")

        slow_moving = sku_stats[sku_stats['active_days'] / data_years <= 2].copy()
        slow_moving = slow_moving[['Product ID', 'ABC_Class', 'annual_demand', 'avg_inventory', 'total_inventory_cost']]
        slow_moving = slow_moving.sort_values('total_inventory_cost', ascending=False)

        st.metric("滞销SKU数量", f"{len(slow_moving)} 个",
                  delta=f"占比 {len(slow_moving)/len(sku_stats)*100:.1f}%")

        if len(slow_moving) > 0:
            slow_cost = slow_moving['total_inventory_cost'].sum()
            st.metric("占用库存成本", f"${slow_cost:,.0f}")

            st.dataframe(
                slow_moving.head(10).rename(columns={
                    'Product ID': 'SKU编号', 'ABC_Class': 'ABC分类',
                    'annual_demand': '年需求量', 'avg_inventory': '平均库存',
                    'total_inventory_cost': '年库存成本'
                }).style.format({
                    '年需求量': '{:.0f}', '平均库存': '{:.0f}', '年库存成本': '${:,.2f}'
                }),
                use_container_width=True, hide_index=True, height=300
            )

            st.info("💡 **优化建议**：对于C类滞销SKU，可考虑降低安全库存至0，采用MTO（按订单生产/采购）模式，"
                    "或直接淘汰长尾SKU，将释放的库存预算转移到A类商品。")

    with col2:
        st.subheader("🏷️ ABC类别销售贡献")

        abc_with_sales = sku_stats.merge(
            df.groupby('Product ID')['Sales'].sum().reset_index(),
            on='Product ID', how='left'
        )
        class_contribution = abc_with_sales.groupby('ABC_Class').agg(
            SKU数=('Product ID', 'count'),
            总销售额=('Sales', 'sum')
        ).reset_index()
        class_contribution['销售额占比'] = (class_contribution['总销售额'] / class_contribution['总销售额'].sum() * 100).round(1)
        class_contribution['SKU占比'] = (class_contribution['SKU数'] / class_contribution['SKU数'].sum() * 100).round(1)

        fig = go.Figure()
        color_map = {'A': '#ef4444', 'B': '#f59e0b', 'C': '#22c55e'}
        for _, row in class_contribution.iterrows():
            fig.add_trace(go.Bar(
                name=f'{row["ABC_Class"]}类',
                x=[row['ABC_Class']],
                y=[row['销售额占比']],
                text=[f'{row["销售额占比"]:.1f}%<br>({row["SKU占比"]:.1f}% SKU)'],
                textposition='auto',
                marker_color=color_map.get(row['ABC_Class'], '#3b82f6')
            ))
        fig.update_layout(
            title='ABC类别销售额贡献 (标注内为SKU占比)',
            yaxis=dict(range=[0, 100], title='销售额占比 (%)'),
            xaxis_title='ABC类别', height=400, showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        a_row = class_contribution[class_contribution['ABC_Class'] == 'A']
        if len(a_row) > 0:
            a = a_row.iloc[0]
            st.info(
                f"📊 **关键发现**：A类商品仅占 {a['SKU占比']:.1f}% 的SKU数量，"
                f"却贡献了 {a['销售额占比']:.1f}% 的销售额。"
                f"这正是ABC分类管理的依据——聚焦少数关键SKU，实现最大收益。"
            )

    st.markdown("---")

    # ===== 滞销SKU处置建议 =====
    st.subheader("🗑️ 滞销SKU处置建议")
    st.caption("对比「继续持有 / 降价清仓 / 淘汰下架」三种策略的财务影响，自动给出推荐。")

    disposal_df = build_disposal_analysis(sku_stats, data_years=data_years)
    if not disposal_df.empty:
        st.dataframe(
            disposal_df.head(20).style.format({
                '年需求量': '{:.0f}', '平均库存': '{:.1f}',
                '库存价值': '${:,.0f}', '年持有成本': '${:,.0f}',
                '继续持有成本': '${:,.0f}', '清仓损失': '${:,.0f}',
                '淘汰损失': '${:,.0f}'
            }),
            use_container_width=True, hide_index=True, height=320
        )

        strategy_counts = disposal_df['推荐策略'].value_counts()
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("建议继续持有", f"{strategy_counts.get('继续持有', 0)} 个")
        col_b.metric("建议降价清仓", f"{strategy_counts.get('降价清仓', 0)} 个")
        col_c.metric("建议淘汰下架", f"{strategy_counts.get('淘汰下架', 0)} 个")

        st.info(
            "💡 **阅读方式**：表格按「继续持有成本」从高到低排序，优先处理占用持有成本最高的滞销 SKU。"
            "「推荐策略」基于三项成本比较自动生成，实际决策还需结合品牌战略、供应商关系等业务因素。"
        )
    else:
        st.info("当前数据中没有满足滞销定义（年销售≤2次）的 SKU。")

    st.markdown("---")

    # ===== ABC-XYZ 二维分类矩阵 =====
    st.subheader("🧩 ABC-XYZ 二维分类矩阵")
    st.caption("XYZ 基于月度需求波动（CV=标准差/平均值）：X 稳定（<0.5）、Y 中等（0.5~1.0）、Z 极不稳定（>=1.0）")

    if 'XYZ_Class' in sku_stats.columns:
        matrix = sku_stats.groupby(['ABC_Class', 'XYZ_Class']).size().unstack(fill_value=0)
        matrix = matrix.reindex(columns=['X', 'Y', 'Z'], fill_value=0)
        matrix = matrix.reindex(index=['A', 'B', 'C'], fill_value=0)

        fig = go.Figure(data=go.Heatmap(
            z=matrix.values,
            x=['X 稳定', 'Y 中等波动', 'Z 极不稳定'],
            y=['A 高价值', 'B 中价值', 'C 低价值'],
            colorscale='Blues',
            text=matrix.values,
            texttemplate='%{text}',
            textfont={'color': 'white'},
            hovertemplate='ABC=%{y}<br>XYZ=%{x}<br>SKU数=%{z}<extra></extra>'
        ))
        fig.update_layout(
            title='ABC × XYZ：SKU 分布矩阵',
            xaxis_title='需求稳定性', yaxis_title='价值贡献',
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "💡 **矩阵解读**：A-X（高价值+稳定）应重点保障供应、保持高服务水平；"
            "A-Z（高价值+波动大）需要更高安全库存或多元化供应；"
            "C-Z（低价值+极不稳定）适合 MTO（按订单生产/采购）或淘汰策略，避免长期占用资金。"
        )

        with st.expander("📋 查看 ABC-XYZ 明细表"):
            detail_cols = ['Product ID', 'ABC_Class', 'XYZ_Class', 'annual_demand', 'safety_stock', 'eoq']
            detail_df = sku_stats[detail_cols].copy()
            detail_df.columns = ['SKU编号', 'ABC分类', 'XYZ分类', '年需求量', '安全库存', 'EOQ']
            st.dataframe(detail_df, use_container_width=True, hide_index=True, height=300)
    else:
        st.info("当前数据未计算 XYZ 分类，请先刷新库存参数计算。")

    st.markdown("---")

# ==========================================
# 主程序
# ==========================================
def main():
    st.sidebar.title("⚙️ 参数控制")
    st.sidebar.markdown("---")

    df_raw = load_data()

    # ===== 方向2：多维度筛选 =====
    st.sidebar.markdown("### 🔍 数据筛选")

    all_years = sorted(df_raw['year'].unique())
    selected_years = st.sidebar.multiselect("选择年份", all_years, default=all_years)

    if 'Category' in df_raw.columns:
        all_categories = sorted(df_raw['Category'].unique())
        selected_categories = st.sidebar.multiselect("选择品类", all_categories, default=all_categories)
    else:
        selected_categories = None

    if 'State' in df_raw.columns:
        all_states = sorted(df_raw['State'].unique())
        default_states = all_states[:10] if len(all_states) > 10 else all_states
        selected_states = st.sidebar.multiselect("选择地区 (State)", all_states, default=default_states)
    else:
        selected_states = None

    # 应用筛选
    df = df_raw[df_raw['year'].isin(selected_years)].copy()
    if selected_categories is not None:
        df = df[df['Category'].isin(selected_categories)]
    if selected_states is not None:
        df = df[df['State'].isin(selected_states)]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"当前筛选: {len(df):,} 条订单, {df['Product ID'].nunique()} 个SKU")
    st.sidebar.markdown("---")

    # 库存参数控制
    lead_time = st.sidebar.slider("补货提前期 (天)", 1, 14, 4, 1)
    ordering_cost = st.sidebar.slider("单次订货成本 (元)", 10, 200, 50, 10)
    holding_rate = st.sidebar.slider("年持有成本率", 0.10, 0.40, 0.25, 0.05, format="%.0f")

    st.sidebar.markdown("### 安全库存系数")
    ss_factor_A = st.sidebar.slider("A类系数", 0.5, 5.0, 2.0, 0.1)
    ss_factor_B = st.sidebar.slider("B类系数", 0.3, 3.0, 1.0, 0.1)
    ss_factor_C = st.sidebar.slider("C类系数", 0.1, 2.0, 0.5, 0.1)

    st.sidebar.markdown("### 缺货成本")
    stockout_cost_per_unit = st.sidebar.slider("单件缺货成本 (元)", 5, 100, 20, 5)
 
    # 空数据检查
    if len(df) == 0:
        st.warning("⚠️ 当前筛选条件下没有数据，请调整筛选条件")
        return

    # 计算 & 模拟
    sku_stats = calc_inventory_params(df, lead_time, ordering_cost, holding_rate,
                                       ss_factor_A, ss_factor_B, ss_factor_C)
    sim_year = df['year'].max()
    sim_results, daily_records = run_simulation(df, sku_stats, sim_year=sim_year, lead_time=lead_time,
                                                 stockout_cost_per_unit=stockout_cost_per_unit)
    forecast_df = build_forecast_eval(df, sku_stats)
    sensitivity_df = run_sensitivity_analysis(df, sim_year=sim_year, lead_time=lead_time,
                                               stockout_cost_per_unit=stockout_cost_per_unit)

    # ===== 方向4：导出功能 =====
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 数据导出")

    # 预计算策略对比数据（供导出使用）
    base_cost = sku_stats[sku_stats['Product ID'].isin(sim_results['Product ID'])]['total_inventory_cost'].sum()
    stockout_cost_total = sim_results['stockout_cost'].sum()
    overall_cost = base_cost + stockout_cost_total

    sku_stats_uniform = calc_inventory_params(
        df, lead_time, ordering_cost, holding_rate,
        ss_factor_A=ss_factor_B, ss_factor_B=ss_factor_B, ss_factor_C=ss_factor_B
    )
    sim_uniform, _ = run_simulation(df, sku_stats_uniform, sim_year=sim_year, lead_time=lead_time,
                                     stockout_cost_per_unit=stockout_cost_per_unit)
    strategy2_cost = sku_stats_uniform[sku_stats_uniform['Product ID'].isin(sim_uniform['Product ID'])]['total_inventory_cost'].sum()
    strategy2_stockout_cost = sim_uniform['stockout_cost'].sum()

    sku_stats_zero = calc_inventory_params(
        df, lead_time, ordering_cost, holding_rate,
        ss_factor_A=0.01, ss_factor_B=0.01, ss_factor_C=0.01
    )
    sim_zero, _ = run_simulation(df, sku_stats_zero, sim_year=sim_year, lead_time=lead_time,
                                 stockout_cost_per_unit=stockout_cost_per_unit)
    strategy3_cost = sku_stats_zero[sku_stats_zero['Product ID'].isin(sim_zero['Product ID'])]['total_inventory_cost'].sum()
    strategy3_stockout_cost = sim_zero['stockout_cost'].sum()

    comparison = pd.DataFrame([
        {'策略': '策略A: ABC差异化',
         '服务水平(%)': round(sim_results['service_rate'].mean(), 2),
         '年库存成本($)': round(overall_cost, 0),
         '缺货成本($)': round(stockout_cost_total, 0),
         '总成本($)': round(overall_cost, 0),
         '周转率(次/年)': round(sim_results['turnover_rate'].mean(), 2),
         '总缺货量': int(sim_results['stockout_qty'].sum()),
         '总订单数': int(sim_results['order_count'].sum())},
        {'策略': '策略B: 统一安全库存',
         '服务水平(%)': round(sim_uniform['service_rate'].mean(), 2),
         '年库存成本($)': round(strategy2_cost, 0),
         '缺货成本($)': round(strategy2_stockout_cost, 0),
         '总成本($)': round(strategy2_cost + strategy2_stockout_cost, 0),
         '周转率(次/年)': round(sim_uniform['turnover_rate'].mean(), 2),
         '总缺货量': int(sim_uniform['stockout_qty'].sum()),
         '总订单数': int(sim_uniform['order_count'].sum())},
        {'策略': '策略C: 零安全库存',
         '服务水平(%)': round(sim_zero['service_rate'].mean(), 2),
         '年库存成本($)': round(strategy3_cost, 0),
         '缺货成本($)': round(strategy3_stockout_cost, 0),
         '总成本($)': round(strategy3_cost + strategy3_stockout_cost, 0),
         '周转率(次/年)': round(sim_zero['turnover_rate'].mean(), 2),
         '总缺货量': int(sim_zero['stockout_qty'].sum()),
         '总订单数': int(sim_zero['order_count'].sum())}
    ])

    export_format = st.sidebar.radio("导出格式", ["Excel (多Sheet)", "CSV (单文件)"])

    if export_format == "Excel (多Sheet)":
        sheets_dict = build_export_data(sku_stats, sim_results, comparison, df)
        excel_bytes = to_excel_download("库存分析报告.xlsx", sheets_dict)
        st.sidebar.download_button(
            label="📥 下载完整报告 (Excel)",
            data=excel_bytes,
            file_name="智能库存分析报告.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key='download_excel'
        )
        st.sidebar.caption("包含4个Sheet：库存参数 / 模拟结果 / 策略对比 / ABC汇总")
    else:
        # CSV模式：导出主模拟结果
        csv_data = sim_results.copy()
        csv_data = csv_data.rename(columns={
            'Product ID': 'SKU编号', 'ABC_Class': 'ABC分类',
            'total_demand': '总需求量', 'stockout_days': '缺货天数',
            'stockout_qty': '缺货数量', 'service_rate': '服务水平(%)',
            'stockout_cost': '缺货成本',
            'order_count': '订货次数', 'avg_inventory': '平均库存',
            'turnover_rate': '周转率(次/年)'
        })
        csv_bytes = csv_data.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label="📥 下载模拟结果 (CSV)",
            data=csv_bytes,
            file_name="补货模拟结果.csv",
            mime="text/csv",
            use_container_width=True,
            key='download_csv'
        )

    st.sidebar.markdown("---")

    # ===== 标题 & Tab =====
    st.title("📦 智能库存分析与补货模拟系统")
    st.markdown("基于ABC分类 + 安全库存 + EOQ模型的库存策略仿真")
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 库存策略模拟", "🔍 业务洞察分析", "🔮 需求预测", "📈 敏感性分析"])

    with tab1:
        render_strategy_tab(df, sku_stats, sim_results, daily_records, lead_time, ordering_cost, holding_rate,
                            ss_factor_A, ss_factor_B, ss_factor_C, sim_year, comparison, overall_cost)

    with tab2:
        render_insight_tab(df, sku_stats, sim_results)

    with tab3:
        render_forecast_tab(df, sku_stats, forecast_df)

    with tab4:
        st.markdown("### 📈 敏感性分析：安全系数与服务成本权衡")
        st.caption("每次只变化一个类别的安全系数，观察服务水平与总成本的变化，自动标注拐点。")
        if sensitivity_df.empty:
            st.info("请先运行模拟后再查看敏感性分析。")
        else:
            for cat_name, col_name in [('A', 'factor_a'), ('B', 'factor_b'), ('C', 'factor_c')]:
                sub = sensitivity_df[sensitivity_df['label'].str.startswith(f'{cat_name}类系数')].copy()
                if sub.empty:
                    continue
                sub = sub.sort_values(col_name)
                st.markdown(f"**{cat_name}类安全系数**")
                col_left, col_right = st.columns([3, 1])
                with col_left:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=sub[col_name], y=sub['service_rate'], mode='lines+markers',
                                             name='服务水平', marker=dict(color='#3b82f6', size=8)))
                    fig.add_trace(go.Scatter(x=sub[col_name], y=sub['total_cost'] / sub['total_cost'].max() * 100,
                                             mode='lines+markers', name='总成本(归一化)',
                                             marker=dict(color='#ef4444', size=8), yaxis='y2'))
                    elbow_idx = find_elbow(sub['service_rate'].values)
                    if elbow_idx is not None:
                        fig.add_vline(x=sub[col_name].iloc[elbow_idx], line_dash='dash', line_color='#22c55e',
                                      annotation_text=f"拐点 ≈ {sub[col_name].iloc[elbow_idx]}")
                    fig.update_layout(title=f'{cat_name}类安全系数对服务水平与总成本的影响',
                                      xaxis_title=f'{cat_name}类安全系数', yaxis_title='服务水平 (%)',
                                      yaxis2=dict(title='总成本(归一化%)', overlaying='y', side='right'),
                                      height=380, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)
                with col_right:
                    display = sub[['label', 'service_rate', 'total_cost', 'turnover', 'avg_inventory']].copy()
                    display.columns = ['组合', '服务水平%', '总成本$', '周转率', '平均库存']
                    st.dataframe(display.set_index('组合').round(2), use_container_width=True, height=320)
            st.info("💡 **拐点解读**：拐点之后继续提高安全系数，服务水平的提升幅度明显放缓，但总成本仍持续上升。"
                    "建议把安全系数设定在拐点附近，兼顾服务水平与库存成本。")

    st.markdown("---")
    st.caption("📦 智能库存分析与补货模拟系统 | 基于 Streamlit + Plotly 构建")


if __name__ == '__main__':
    main()
