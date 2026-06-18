# -*- coding: utf-8 -*-
"""
页面5 · 机构档案
基金管理人列表 + 点击查看产品线 + 优势赛道 + 柱状图
- 风险单元格文字红色（非整行）
- 第一列 ☑/⬜ 加入关注
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import io
import numpy as np

from data_layer import (
    load_data, etf_code_to_ft_link, check_risks,
    render_batch_table, handle_checkbox_clicks,
    build_pagination_controls, render_pagination_buttons,
    build_attention_badge,
    inject_tooltip_css, build_risk_tag, build_th_with_tooltip,
    get_header_tooltip, TOOLTIP_CSS,
)

# set_page_config 已移至 app.py

table1, table2, last_refresh = load_data()

inject_tooltip_css()

if "compare_pool" not in st.session_state:
    st.session_state.compare_pool = []

# 处理 checkbox 点击
handle_checkbox_clicks(table1, table2)

# ════════════════════════════════════════════════════════════
# 页面标题
# ════════════════════════════════════════════════════════════
badge = build_attention_badge()
st.html(f"""
<div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);
            padding:20px 32px;border-radius:16px;margin-bottom:20px;
            display:flex;justify-content:space-between;align-items:center;">
    <div>
        <h1 style="margin:0;font-size:24px;color:white;font-family:'Microsoft YaHei';letter-spacing:1px;">
            🏛️ 机构档案
        </h1>
        <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.55);">
            按基金管理人查看旗下 ETF 产品线
        </p>
    </div>
    {badge}
</div>""")

# ── 准备基金管理人数据 ──────────────────────────────────────
fund_col = "ETF基金管理人"
if fund_col not in table2.columns:
    st.error("全市场 ETF 表中未找到「基金管理人」字段，请检查数据源。")
    st.stop()

fund_summary = (
    table2.groupby(fund_col)
    .agg(
        ETF数量=("ETF代码", "count"),
        总规模=("ETF最新规模_数值", "sum"),
        平均规模=("ETF最新规模_数值", "mean"),
    )
    .reset_index()
    .sort_values("总规模", ascending=False)
)

sort_mode = st.radio("排序方式", ["按管理总规模↓", "按ETF数量↓"], horizontal=True, label_visibility="collapsed")
if "数量" in sort_mode:
    fund_summary = fund_summary.sort_values("ETF数量", ascending=False)

# ── 基金管理人列表（HTML表格，每20行翻页）─────────────────
st.markdown("##### 🏛️ 基金管理人列表")

# 分页
page_key_fund = "inst_fund_list"
page_f, total_pages_f, start_f, end_f = build_pagination_controls(
    page_key_fund, len(fund_summary), page_size=20
)
fund_summary_page = fund_summary.iloc[start_f:end_f]

f_headers = ["排名", "基金管理人", "ETF数量", "关联ETF总规模(亿)", "平均规模(亿)"]
html_fund = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
html_fund.append('<thead><tr>')
for h in f_headers:
    html_fund.append(f'<th style="background:#1a1a2e;color:white;padding:6px 8px;text-align:center;white-space:nowrap;font-size:11px;">{h}</th>')
html_fund.append('</tr></thead><tbody>')

for i, (_, r) in enumerate(fund_summary_page.iterrows()):
    global_idx = start_f + i
    bg = "#FAFBFC" if global_idx % 2 == 0 else "#F5F7FA"
    fund_name = str(r[fund_col])
    etf_cnt = str(int(r["ETF数量"]))
    total_sc = f"{r['总规模']:.2f}" if pd.notna(r.get("总规模")) else ""
    avg_sc = f"{r['平均规模']:.2f}" if pd.notna(r.get("平均规模")) else ""
    html_fund.append(f'<tr style="background:{bg};">')
    html_fund.append(f'<td style="padding:5px 8px;text-align:center;">{str(global_idx + 1)}</td>')
    html_fund.append(f'<td style="padding:5px 8px;text-align:center;">{fund_name}</td>')
    html_fund.append(f'<td style="padding:5px 8px;text-align:center;">{etf_cnt}</td>')
    html_fund.append(f'<td style="padding:5px 8px;text-align:center;">{total_sc}</td>')
    html_fund.append(f'<td style="padding:5px 8px;text-align:center;">{avg_sc}</td>')
    html_fund.append('</tr>')

html_fund.append('</tbody></table>')
st.markdown(TOOLTIP_CSS + "".join(html_fund), unsafe_allow_html=True)

render_pagination_buttons(page_key_fund, total_pages_f, page_f)

st.divider()

# ── 选择基金公司深入查看 ─────────────────────────────────────
funds = sorted(fund_summary[fund_col].dropna().unique().tolist())
sel_fund = st.selectbox("选择基金管理人深入查看", funds, key="sel_fund_detail")

fund_etfs = table2[table2[fund_col] == sel_fund].copy()
fund_etfs = fund_etfs.sort_values("ETF最新规模_数值", ascending=False)

# ── 概况卡片 ────────────────────────────────────────────────
total_scale = fund_etfs["ETF最新规模_数值"].sum()
avg_scale = fund_etfs["ETF最新规模_数值"].mean()
total_vol = fund_etfs["ETF日均成交额_数值"].sum() if "ETF日均成交额_数值" in fund_etfs.columns else 0

advantage_tracks = []
if len(table1) > 0 and "基金管理人" in table1.columns:
    fund_t1 = table1[table1["基金管理人"] == sel_fund]
    if "行业概念名称" in fund_t1.columns and "最新规模_数值" in fund_t1.columns:
        track_agg = (
            fund_t1.groupby("行业概念名称")
            .agg(总规模=("最新规模_数值", "sum"))
            .reset_index()
            .sort_values("总规模", ascending=False)
            .head(3)
        )
        advantage_tracks = track_agg["行业概念名称"].tolist()

fc1, fc2, fc3, fc4 = st.columns(4)
fc1.metric("💰 管理总规模", f"{total_scale:.1f}亿")
fc2.metric("📊 产品数量", len(fund_etfs))
fc3.metric("📐 平均规模", f"{avg_scale:.1f}亿")
fc4.metric("🏆 优势赛道", "、".join(advantage_tracks[:3]) if advantage_tracks else "—")

st.divider()

# ── 产品线列表 ──────────────────────────────────────────────
st.markdown(f"##### 📋 {sel_fund}  ETF 产品列表")

pool_codes_set = set(c[0] for c in st.session_state.compare_pool)

# ── 分页 ───────────────────────────────────────────────────
page_key_etf = "inst_etf_list"
page_e, total_pages_e, start_e, end_e = build_pagination_controls(
    page_key_etf, len(fund_etfs), page_size=20
)
fund_etfs_page = fund_etfs.iloc[start_e:end_e]

# ── 风险单元格红色样式 ──────────────────────────────────────
def _risk_cell_style(col_key, risks):
    if not risks:
        return ""
    if col_key == "最新规模(亿)" and "小规模" in risks:
        return "color:#E74C3C;font-weight:600;"
    if col_key == "日均成交额(亿)" and "低流动性" in risks:
        return "color:#E74C3C;font-weight:600;"
    if col_key == "跟踪误差" and "跟踪偏差" in risks:
        return "color:#E74C3C;font-weight:600;"
    return ""

# ── 构建 HTML 表格 ──────────────────────────────────────────
etf_headers = ["", "ETF代码", "ETF名称", "跟踪指数", "上市日期", "最新规模(亿)", "日均成交额(亿)",
               "跟踪误差", "信息比率", "潜在风险"]

html_etf = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
html_etf.append('<thead><tr>')
for h in etf_headers:
    tooltip = get_header_tooltip(h)
    html_etf.append(build_th_with_tooltip(h, tooltip))
html_etf.append('</tr></thead><tbody>')

for i, (_, row) in enumerate(fund_etfs_page.iterrows()):
    code = str(row.get("ETF代码", ""))
    name = str(row.get("ETF名称", ""))
    idx_name = str(row.get("ETF跟踪指数名称", ""))
    date_val = row["ETF上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("ETF上市日期")) else ""
    scale_val = row.get("ETF最新规模_数值", np.nan)
    vol_val = row.get("ETF日均成交额_数值", np.nan)
    err_val = row.get("ETF跟踪误差", np.nan)
    ir_val = row.get("ETF信息比率", np.nan)

    url = etf_code_to_ft_link(code)
    code_html = f'<a href="{url}" target="_blank" style="color:#4A90D9;text-decoration:none;font-weight:600;">{code}</a>' if url else code

    risks = check_risks(row, prefix="ETF")
    risk_tags = " ".join([build_risk_tag(r) for r in risks]) if risks else ""

    checked = code in pool_codes_set
    color = '#4CAF50' if checked else '#ccc'
    icon = '☑️' if checked else '⬜'
    checkbox_html = (
        f'<span data-etf-code="{code}" '
        f'style="cursor:pointer;font-size:16px;color:{color};">{icon}</span>'
    )

    cells = [
        ("", checkbox_html, ""),
        ("ETF代码", code_html, ""),
        ("ETF名称", name, ""),
        ("跟踪指数", idx_name, ""),
        ("上市日期", date_val, ""),
        ("最新规模(亿)", f"{scale_val:.2f}" if pd.notna(scale_val) else "", _risk_cell_style("最新规模(亿)", risks)),
        ("日均成交额(亿)", f"{vol_val:.2f}" if pd.notna(vol_val) else "", _risk_cell_style("日均成交额(亿)", risks)),
        ("跟踪误差", f"{err_val:.2f}" if pd.notna(err_val) else "", _risk_cell_style("跟踪误差", risks)),
        ("信息比率", f"{ir_val:.2f}" if pd.notna(ir_val) else "", ""),
        ("潜在风险", risk_tags, ""),
    ]

    bg = "#FAFBFC" if i % 2 == 0 else "#F5F7FA"
    html_etf.append(f'<tr style="background:{bg};">')
    for col_key, val, style in cells:
        extra = f' {style}' if style else ''
        html_etf.append(f'<td style="padding:5px 8px;text-align:center;white-space:nowrap;{extra}">{val}</td>')
    html_etf.append('</tr>')

html_etf.append('</tbody></table>')
table_html = "".join(html_etf)
pool_codes_list = [c[0] for c in st.session_state.compare_pool]
render_batch_table(table_html, "inst_etf", pool_codes_list, len(fund_etfs_page))

render_pagination_buttons(page_key_etf, total_pages_e, page_e)

# ── 各跟踪指数规模分布柱状图 ──────────────────────────────────
st.divider()
st.markdown(f"##### 📊 {sel_fund}  ETF 产品布局")

if "ETF跟踪指数名称" in fund_etfs.columns:
    idx_agg = (
        fund_etfs.groupby("ETF跟踪指数名称")
        .agg(数量=("ETF代码", "count"), 总规模=("ETF最新规模_数值", "sum"))
        .reset_index()
    )

    # 切换按钮
    chart_mode = st.radio("排序依据", ["按ETF规模↓", "按ETF数量↓"], horizontal=True, key="chart_sort_mode")
    if "数量" in chart_mode:
        idx_agg = idx_agg.sort_values("数量", ascending=False)
        color_col = "数量"
        x_col = "数量"
        title_prefix = "数量"
    else:
        idx_agg = idx_agg.sort_values("总规模", ascending=False)
        color_col = "总规模"
        x_col = "总规模"
        title_prefix = "规模"

    idx_agg = idx_agg.head(20)
    # 升序排列使水平柱状图从上到下由大到小
    idx_agg = idx_agg.sort_values(x_col, ascending=True)

    # 自定义颜色梯度：数值越大颜色越深（浅蓝→深蓝）
    custom_blues = [
        [0.0, "#90CAF9"],   # 浅蓝（最小值）
        [0.25, "#64B5F6"],
        [0.5, "#42A5F5"],
        [0.75, "#1E88E5"],
        [1.0, "#0D47A1"],   # 深蓝（最大值）
    ]

    fig_bar = px.bar(
        idx_agg, x=x_col, y="ETF跟踪指数名称", orientation="h",
        color=color_col,
        color_continuous_scale=custom_blues,
        title=f"ETF {title_prefix} 分布",
    )
    fig_bar.update_layout(
        height=max(400, len(idx_agg) * 24),
        margin=dict(l=160, r=40, t=50, b=20),
        coloraxis_colorbar=dict(title=title_prefix),
    )
    # 数量轴使用整数刻度
    if "数量" in chart_mode:
        fig_bar.update_xaxes(dtick=1)
    fig_bar.update_traces(marker=dict(line=dict(color="rgba(255,255,255,0.3)", width=0.5)))
    st.plotly_chart(fig_bar, use_container_width=True)

# ── 导出 ────────────────────────────────────────────────────
buf = io.BytesIO()
export_cols = ["ETF代码", "ETF名称", "ETF跟踪指数名称", "ETF最新规模",
               "ETF近半年日均成交额", "ETF跟踪误差"]
avail = [c for c in export_cols if c in fund_etfs.columns]
fund_etfs[avail].to_excel(buf, index=False, engine="openpyxl")
buf.seek(0)
st.download_button(
    "📥 导出本机构 ETF 数据", data=buf, file_name=f"机构档案_{sel_fund}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True,
)

st.divider()
st.caption(f"数据来源：ima 知识库 · 刷新时间：{last_refresh}")
st.caption("免责声明：本页数据仅供参考，不保证及时、准确、完整，不构成任何产品推荐或投资建议。")
st.caption("风险提示：证券市场存在不确定性，投资者需根据自身风险承受能力决策，自行承担投资风险。")
