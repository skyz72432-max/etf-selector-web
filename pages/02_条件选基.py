# -*- coding: utf-8 -*-
"""
页面2 · 条件选基
多维度筛选 + 关注池 + 导出
- 风险单元格文字红色（非整行）
- 第一列 ☑/⬜ 加入关注
"""

import streamlit as st
import pandas as pd
import io
import numpy as np

from data_layer import (
    load_data, etf_code_to_ft_link, check_risks,
    render_batch_table, handle_checkbox_clicks,
    build_pagination_controls, render_pagination_buttons,
    build_attention_badge,
    inject_tooltip_css, build_risk_tag, build_th_with_tooltip,
    get_header_tooltip,
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
            🔍 条件选基
        </h1>
        <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.55);">
            多维度筛选，精准定位目标 ETF
        </p>
    </div>
    {badge}
</div>""")

# ── 筛选面板 ────────────────────────────────────────────────
scale_max = max(table2["ETF最新规模_数值"].max(), 100) if "ETF最新规模_数值" in table2.columns else 100
vol_max = max(table2["ETF日均成交额_数值"].max(), 10) if "ETF日均成交额_数值" in table2.columns else 10
err_max = max(table2["ETF跟踪误差"].max(), 5) if "ETF跟踪误差" in table2.columns else 5
fund_managers = sorted(table2["ETF基金管理人"].dropna().unique().tolist()) if "ETF基金管理人" in table2.columns else []

with st.expander("🔧 筛选条件", expanded=True):
    # 第一行：关键词搜索 | 上市日期范围 | 基金管理人（三列等宽，对齐第二行）
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        keyword = st.text_input("关键词搜索", placeholder="ETF代码、名称或跟踪指数", label_visibility="visible")
    with r1c2:
        date_range = st.date_input("上市日期范围", value=(), key="date_range_filter")
    with r1c3:
        fund_sel = st.multiselect("基金管理人", fund_managers, default=[])

    # 第二行：规模范围（亿）| 日均成交额范围（亿）| 跟踪误差范围
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        scale_range = st.slider("规模范围（亿）", 0.0, float(scale_max), (0.0, float(scale_max)), step=0.5, key="scale_range")
    with r2c2:
        vol_range = st.slider("日均成交额范围（亿）", 0.0, float(vol_max), (0.0, float(vol_max)), step=0.05, key="vol_range")
    with r2c3:
        err_range = st.slider("跟踪误差范围", 0.0, float(err_max), (0.0, float(err_max)), step=0.01, key="err_range",
                               help="跟踪误差：ETF相对跟踪指数走势的偏离度（按不同区间长度加权计算），越小越好")

# ── 应用筛选 ────────────────────────────────────────────────
filtered = table2.copy()

if keyword:
    q = keyword.strip()
    mask_kw = (
        filtered["ETF代码"].astype(str).str.contains(q, case=False, na=False) |
        filtered["ETF名称"].astype(str).str.contains(q, case=False, na=False) |
        filtered["ETF跟踪指数名称"].astype(str).str.contains(q, case=False, na=False)
    )
    filtered = filtered[mask_kw]
if "ETF最新规模_数值" in filtered.columns:
    filtered = filtered[(filtered["ETF最新规模_数值"] >= scale_range[0]) & (filtered["ETF最新规模_数值"] <= scale_range[1])]
if "ETF日均成交额_数值" in filtered.columns:
    filtered = filtered[(filtered["ETF日均成交额_数值"] >= vol_range[0]) & (filtered["ETF日均成交额_数值"] <= vol_range[1])]
if "ETF跟踪误差" in filtered.columns:
    filtered = filtered[(filtered["ETF跟踪误差"] >= err_range[0]) & (filtered["ETF跟踪误差"] <= err_range[1])]
if fund_sel and "ETF基金管理人" in filtered.columns:
    filtered = filtered[filtered["ETF基金管理人"].isin(fund_sel)]
if date_range and len(date_range) == 2:
    start_dt = pd.Timestamp(date_range[0])
    end_dt = pd.Timestamp(date_range[1])
    if "ETF上市日期" in filtered.columns:
        filtered = filtered[(filtered["ETF上市日期"] >= start_dt) & (filtered["ETF上市日期"] <= end_dt)]

filtered = filtered.sort_values("ETF最新规模_数值", ascending=False, na_position="last")
filtered = filtered.drop_duplicates(subset=["ETF代码"], keep="first")
filtered = filtered.reset_index(drop=True)

st.markdown(f"##### 📋 筛选结果：共 **{len(filtered)}** 只 ETF")

if len(filtered) == 0:
    st.warning("没有符合筛选条件的ETF，请调整筛选条件。")
    st.stop()

# ── 分页 ────────────────────────────────────────────────────
page_key = "cond_select"
page, total_pages, start, end = build_pagination_controls(page_key, len(filtered), page_size=20)
display = filtered.iloc[start:end]

pool_codes_set = set(c[0] for c in st.session_state.compare_pool)

# ── 辅助：风险单元格红色样式 ────────────────────────────────
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
# 列顺序：ETF代码 ETF名称 跟踪指数 基金管理人 上市日期 最新规模(亿) 日均成交额(亿) 跟踪误差 信息比率 潜在风险
headers = ["", "ETF代码", "ETF名称", "跟踪指数", "基金管理人",
           "上市日期", "最新规模(亿)", "日均成交额(亿)", "跟踪误差",
           "信息比率", "潜在风险"]

html_parts = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
html_parts.append('<thead><tr>')
for h in headers:
    tooltip = get_header_tooltip(h)
    html_parts.append(build_th_with_tooltip(h, tooltip))
html_parts.append('</tr></thead><tbody>')

for i, (_, row) in enumerate(display.iterrows()):
    code = str(row.get("ETF代码", ""))
    name = str(row.get("ETF名称", ""))
    idx_name = str(row.get("ETF跟踪指数名称", ""))
    date_val = row["ETF上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("ETF上市日期")) else ""
    fund = str(row.get("ETF基金管理人", ""))
    scale_val = row.get("ETF最新规模_数值", np.nan)
    vol_val = row.get("ETF日均成交额_数值", np.nan)
    err_val = row.get("ETF跟踪误差", np.nan)
    ir_val = row.get("ETF信息比率", np.nan)
    corr_val = row.get("ETF与跟踪指数收益相关性", np.nan)

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
        ("基金管理人", fund, ""),
        ("上市日期", date_val, ""),
        ("最新规模(亿)", f"{scale_val:.2f}" if pd.notna(scale_val) else "", _risk_cell_style("最新规模(亿)", risks)),
        ("日均成交额(亿)", f"{vol_val:.2f}" if pd.notna(vol_val) else "", _risk_cell_style("日均成交额(亿)", risks)),
        ("跟踪误差", f"{err_val:.2f}" if pd.notna(err_val) else "", _risk_cell_style("跟踪误差", risks)),
        ("信息比率", f"{ir_val:.2f}" if pd.notna(ir_val) else "", ""),
        ("潜在风险", risk_tags, ""),
    ]

    bg = "#FAFBFC" if i % 2 == 0 else "#F5F7FA"
    html_parts.append(f'<tr style="background:{bg};">')
    for col_key, val, style in cells:
        extra = f' {style}' if style else ''
        html_parts.append(f'<td style="padding:5px 8px;text-align:center;white-space:nowrap;{extra}">{val}</td>')
    html_parts.append('</tr>')

html_parts.append('</tbody></table>')
table_html = "".join(html_parts)
pool_codes_list = [c[0] for c in st.session_state.compare_pool]
render_batch_table(table_html, "cond_select", pool_codes_list, len(display))

render_pagination_buttons(page_key, total_pages, page)

# ── 底部操作栏 ──────────────────────────────────────────────
st.divider()
bc1, bc2 = st.columns([1, 1])

with bc1:
    export_cols = ["ETF代码", "ETF名称", "ETF跟踪指数名称", "ETF最新规模",
                   "ETF近半年日均成交额", "ETF跟踪误差", "ETF信息比率",
                   "ETF上市日期", "ETF基金管理人"]
    avail_cols = [c for c in export_cols if c in filtered.columns]
    export_df = filtered[avail_cols].copy()
    # 重命名列（导出用友好名）
    rename_map = {
        "ETF跟踪指数名称": "跟踪指数",
        "ETF近半年日均成交额": "日均成交额(亿)",
        "ETF最新规模": "最新规模(亿)",
        "ETF上市日期": "上市日期",
        "ETF基金管理人": "基金管理人",
    }
    export_df = export_df.rename(columns={k: v for k, v in rename_map.items() if k in export_df.columns})

    buf = io.BytesIO()
    export_df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        "📥 导出 Excel", data=buf, file_name="条件选基结果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with bc2:
    csv_data = export_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 导出 CSV", data=csv_data, file_name="条件选基结果.csv",
        mime="text/csv", use_container_width=True,
    )

st.divider()
st.caption(f"数据来源：ima 知识库 · 刷新时间：{last_refresh}")
st.caption("免责声明：本页数据仅供参考，不保证及时、准确、完整，不构成任何产品推荐或投资建议。")
st.caption("风险提示：证券市场存在不确定性，投资者需根据自身风险承受能力决策，自行承担投资风险。")
