# -*- coding: utf-8 -*-
"""
页面3 · 行业掘金
两级展示：跟踪指数 → ETF
- 风险单元格文字红色（非整行）
- 第一列 ☑/⬜ 加入关注
- 最优ETF（最佳匹配指数 + 最佳匹配ETF）名称前加 ⭐
"""

import streamlit as st
import pandas as pd
import io
import numpy as np

from data_layer import (
    load_data, etf_code_to_ft_link, check_risks,
    get_industry_types,
    render_batch_table, handle_checkbox_clicks,
    build_attention_badge,
    build_pagination_controls, render_pagination_buttons,
    format_rank_from_row,
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
            ⛏️ 行业掘金
        </h1>
        <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.55);">
            按行业/概念深挖 ETF 机会
        </p>
    </div>
    {badge}
</div>""")

# ── 处理 Treemap 跳转 ──────────────────────────────────────
nav_type = st.session_state.pop("nav_industry_type", None)
nav_name = st.session_state.pop("nav_industry_name", None)

# 如果有 Treemap 跳转，强制覆盖 selectbox 的 session_state key
# （selectbox 有 key 时，index 参数会被 session_state 已有值覆盖）
if nav_type:
    st.session_state["dig_type"] = nav_type

# ── 选择分类体系和行业 ──────────────────────────────────────
types = get_industry_types(table1)
types = [t for t in types if t != "全部数据汇总"]
col_type, col_ind = st.columns([2, 3])

with col_type:
    sel_type = st.selectbox("分类体系", types, key="dig_type")

with col_ind:
    industries = sorted(table1[table1["类型"] == sel_type]["行业概念名称"].dropna().unique().tolist())
    if nav_name and nav_name in industries:
        st.session_state["dig_ind"] = nav_name
    sel_ind = st.selectbox("选择行业/概念", industries, key="dig_ind")

sub = table1[(table1["类型"] == sel_type) & (table1["行业概念名称"] == sel_ind)].copy()

# ── 概况卡片 ────────────────────────────────────────────────
total_scale = sub["最新规模_数值"].sum() if "最新规模_数值" in sub.columns else 0
best_count = len(sub[sub["是否为最佳匹配ETF"] == True]) if "是否为最佳匹配ETF" in sub.columns else 0

i1, i2, i3, i4 = st.columns(4)
i1.metric("💰 关联总规模", f"{total_scale:.1f}亿")
i2.metric("📊 跟踪指数", f"{sub['跟踪指数名称'].nunique()}只" if "跟踪指数名称" in sub.columns else "0只")
i3.metric("📋 关联ETF", f"{len(sub)}个")
i4.metric("⭐ 最佳匹配ETF", f"{best_count}个")

st.divider()

# ════════════════════════════════════════════════════════════
# 第一级：跟踪指数展示
# ════════════════════════════════════════════════════════════
st.markdown("##### 📊 跟踪指数列表")

cb_best_index = st.checkbox("仅最佳匹配跟踪指数", value=False, key="cb_best_index",
                          help="当前行业概念下综合匹配度最高的跟踪指数")

if cb_best_index and "是否为最佳匹配指数" in sub.columns:
    indices_sub = sub[sub["是否为最佳匹配指数"] == True]
else:
    indices_sub = sub

index_agg = indices_sub.groupby("跟踪指数名称").agg(
    ETF数量=("ETF代码", "count"),
    总规模=("最新规模_数值", "sum"),
    走势相关度=("走势相关度", "mean"),
    持仓相关度=("持仓相关度", "mean"),
    综合匹配度=("综合匹配度", "mean"),
    是否最佳=("是否为最佳匹配指数", lambda x: x.iloc[0] if len(x) > 0 else False),
).reset_index().sort_values("总规模", ascending=False)

# HTML 表格渲染跟踪指数
idx_headers = ["跟踪指数", "ETF数量", "关联ETF总规模(亿)", "走势相关度", "持仓相关度", "综合匹配度", "是否最佳"]
html_idx = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
html_idx.append('<thead><tr>')
for h in idx_headers:
    tooltip = get_header_tooltip(h)
    html_idx.append(build_th_with_tooltip(h, tooltip))
html_idx.append('</tr></thead><tbody>')

for i, (_, r) in enumerate(index_agg.iterrows()):
    bg = "#FAFBFC" if i % 2 == 0 else "#F5F7FA"
    idx_name = str(r.get("跟踪指数名称", ""))
    etf_count = str(int(r.get("ETF数量", 0)))
    total_scale = f"{r['总规模']:.2f}" if pd.notna(r.get("总规模")) else ""
    trend_corr = f"{r['走势相关度']:.2%}" if pd.notna(r.get("走势相关度")) else ""
    hold_corr = f"{r['持仓相关度']:.2%}" if pd.notna(r.get("持仓相关度")) else ""
    match_deg = f"{r['综合匹配度']:.2%}" if pd.notna(r.get("综合匹配度")) else ""
    best_mark = "✅" if r.get("是否最佳") else ""
    html_idx.append(f'<tr style="background:{bg};">')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{idx_name}</td>')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{etf_count}</td>')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{total_scale}</td>')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{trend_corr}</td>')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{hold_corr}</td>')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{match_deg}</td>')
    html_idx.append(f'<td style="padding:5px 8px;text-align:center;">{best_mark}</td>')
    html_idx.append('</tr>')

html_idx.append('</tbody></table>')
st.markdown(TOOLTIP_CSS + "".join(html_idx), unsafe_allow_html=True)

st.caption("综合匹配度：≥ 90% (优秀) —— 指数与行业概念高度一致；≥ 80% (良好) —— 指数能够较好地代表行业概念；≥ 60% (合格) —— 指数与行业概念有一定关联。")

st.divider()

# ════════════════════════════════════════════════════════════
# 第二级：ETF 列表
# ════════════════════════════════════════════════════════════
st.markdown("##### 📋 ETF 列表")

cb_best_etf = st.checkbox("仅最佳匹配ETF", value=False, key="cb_best_etf",
                         help="同一跟踪指数下同类排名最高的ETF，⭐ 表示最佳匹配跟踪指数下的最佳匹配ETF")

if cb_best_etf and "是否为最佳匹配ETF" in sub.columns:
    etf_sub = sub[sub["是否为最佳匹配ETF"] == True]
else:
    etf_sub = sub

etf_sub = etf_sub.sort_values("最新规模_数值", ascending=False)
etf_sub = etf_sub.reset_index(drop=True)

# ── 分页 ─────────────────────────────────────────────────
page_key_etf = "dig_etf_page"
page_e, total_pages_e, start_e, end_e = build_pagination_controls(
    page_key_etf, len(etf_sub), page_size=20
)
etf_sub_page = etf_sub.iloc[start_e:end_e]

pool_codes_set = set(c[0] for c in st.session_state.compare_pool)

# 找出最优ETF（同时是最佳匹配指数 + 最佳匹配ETF）
best_index_mask = (etf_sub["是否为最佳匹配指数"] == True) if "是否为最佳匹配指数" in etf_sub.columns else pd.Series(False, index=etf_sub.index)
best_etf_mask = (etf_sub["是否为最佳匹配ETF"] == True) if "是否为最佳匹配ETF" in etf_sub.columns else pd.Series(False, index=etf_sub.index)
optimal_mask = best_index_mask & best_etf_mask
optimal_codes = set(etf_sub.loc[optimal_mask, "ETF代码"].astype(str).values)

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

# ── 构建 HTML 表格（全部展开，不分页）──────────────────────
etf_headers = ["", "ETF代码", "ETF名称", "跟踪指数", "最新规模(亿)", "日均成交额(亿)",
               "跟踪误差", "信息比率", "收益相关性", "同类排名", "潜在风险"]

html_etf = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
html_etf.append('<thead><tr>')
for h in etf_headers:
    tooltip = get_header_tooltip(h)
    html_etf.append(build_th_with_tooltip(h, tooltip))
html_etf.append('</tr></thead><tbody>')

for i, (_, row) in enumerate(etf_sub_page.iterrows()):
    code = str(row.get("ETF代码", ""))
    name = str(row.get("ETF名称", ""))
    idx_name = str(row.get("跟踪指数名称", ""))
    scale_val = row.get("最新规模_数值", np.nan)
    vol_val = row.get("日均成交额_数值", np.nan)
    err_val = row.get("跟踪误差", np.nan)
    ir_val = row.get("信息比率", np.nan)
    corr_val = row.get("与跟踪指数收益相关性", np.nan)
    rank_str = format_rank_from_row(row, "综合排名", "同类ETF数量")

    url = etf_code_to_ft_link(code)
    code_html = f'<a href="{url}" target="_blank" style="color:#4A90D9;text-decoration:none;font-weight:600;">{code}</a>' if url else code

    risks = check_risks(row)
    risk_tags = " ".join([build_risk_tag(r) for r in risks]) if risks else ""

    # 最优ETF加⭐
    display_name = f"⭐ {name}" if code in optimal_codes else name

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
        ("ETF名称", display_name, ""),
        ("跟踪指数", idx_name, ""),
        ("最新规模(亿)", f"{scale_val:.2f}" if pd.notna(scale_val) else "", _risk_cell_style("最新规模(亿)", risks)),
        ("日均成交额(亿)", f"{vol_val:.2f}" if pd.notna(vol_val) else "", _risk_cell_style("日均成交额(亿)", risks)),
        ("跟踪误差", f"{err_val:.2f}" if pd.notna(err_val) else "", _risk_cell_style("跟踪误差", risks)),
        ("信息比率", f"{ir_val:.2f}" if pd.notna(ir_val) else "", ""),
        ("收益相关性", f"{corr_val:.2%}" if pd.notna(corr_val) else "", ""),
        ("同类排名", rank_str, ""),
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
render_batch_table(table_html, "dig_etf", pool_codes_list, len(etf_sub_page))

render_pagination_buttons(page_key_etf, total_pages_e, page_e)

# ── 导出 ────────────────────────────────────────────────────
st.divider()
bc1, bc2 = st.columns(2)

export_cols = ["ETF代码", "ETF名称", "跟踪指数名称", "最新规模", "近半年日均成交额",
               "跟踪误差", "信息比率", "与跟踪指数收益相关性", "综合匹配度", "同类排名"]
avail_cols = [c for c in export_cols if c in etf_sub.columns]
export_df = etf_sub[avail_cols].copy()
# 同类排名格式化
if "同类排名" in export_df.columns and "同类ETF数量" in etf_sub.columns:
    export_df["同类排名"] = etf_sub.apply(
        lambda r: format_rank_from_row(r, "综合排名", "同类ETF数量"), axis=1
    )
# 重命名
rename_map = {
    "与跟踪指数收益相关性": "收益相关性",
    "跟踪指数名称": "跟踪指数",
    "近半年日均成交额": "日均成交额(亿)",
    "最新规模": "最新规模(亿)",
}
export_df = export_df.rename(columns={k: v for k, v in rename_map.items() if k in export_df.columns})

with bc1:
    buf = io.BytesIO()
    export_df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button("📥 导出 Excel", data=buf, file_name=f"行业掘金_{sel_ind}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

with bc2:
    csv_data = export_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 导出 CSV", data=csv_data, file_name=f"行业掘金_{sel_ind}.csv",
                       mime="text/csv", use_container_width=True)

st.divider()
st.caption(f"数据来源：ima 知识库 · 刷新时间：{last_refresh}")
st.caption("免责声明：本页数据仅供参考，不保证及时、准确、完整，不构成任何产品推荐或投资建议。")
st.caption("风险提示：证券市场存在不确定性，投资者需根据自身风险承受能力决策，自行承担投资风险。")
