# -*- coding: utf-8 -*-
"""
页面6 · 我的关注
自选池管理 + 核心对比表格 + 柱状图（≥2只）+ 导出
- 风险单元格文字红色（非整行）
- 1只 ETF 仅表格不画图
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import io

from data_layer import (
    load_data, etf_code_to_ft_link, check_risks,
    build_attention_badge, build_risk_tag, build_th_with_tooltip,
    get_header_tooltip, TOOLTIP_CSS, inject_tooltip_css,
)

# set_page_config 已移至 app.py

table1, table2, last_refresh = load_data()

inject_tooltip_css()

if "compare_pool" not in st.session_state:
    st.session_state.compare_pool = []

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
            ⭐ 我的关注
        </h1>
        <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.55);">
            多维度对比，一目了然
        </p>
    </div>
    {badge}
</div>""")

pool = st.session_state.compare_pool

# ════════════════════════════════════════════════════════════
# 自选池管理
# ════════════════════════════════════════════════════════════
st.markdown(f"##### 📋 自选池（{len(pool)} 只 ETF）")

if len(pool) == 0:
    st.info("当前自选池为空，请先在前述页面勾选添加ETF。")
    st.stop()

for i, (code, name, idx) in enumerate(pool):
    col_item, col_rm = st.columns([9, 1])
    with col_item:
        url = etf_code_to_ft_link(code)
        link = (
            f'<a href="{url}" target="_blank" style="color:#4A90D9;font-weight:600;">{code}</a>'
            if url else code
        )
        st.markdown(
            f"**{i+1}. {link}** &nbsp; {name} &nbsp;|&nbsp; {idx}",
            unsafe_allow_html=True,
        )
    with col_rm:
        if st.button("✖️", key=f"rm_{code}_{i}"):
            st.session_state.compare_pool = [c for c in pool if c[0] != code]
            st.rerun()

st.divider()

# ── 查找详细数据 ────────────────────────────────────────────
pool_codes = [c[0] for c in pool]
detail_rows = []

for code in pool_codes:
    match2 = table2[table2["ETF代码"].astype(str) == code]
    if len(match2) > 0:
        row = match2.iloc[0]
        risks = check_risks(row, prefix="ETF")
        listing_date = row["ETF上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("ETF上市日期")) else ""
        detail_rows.append({
            "来源": "table2",
            "ETF代码": code,
            "ETF名称": str(row.get("ETF名称", "")),
            "跟踪指数": str(row.get("ETF跟踪指数名称", "")),
            "上市日期": listing_date,
            "基金管理人": str(row.get("ETF基金管理人", "")),
            "规模": row.get("ETF最新规模_数值", np.nan),
            "成交额": row.get("ETF日均成交额_数值", np.nan),
            "跟踪误差": row.get("ETF跟踪误差", np.nan),
            "信息比率": row.get("ETF信息比率", np.nan),
            "risks": risks,
        })
    else:
        match = table1[table1["ETF代码"].astype(str) == code]
        if len(match) > 0:
            row = match.iloc[0]
            risks = check_risks(row)
            listing_date = row["上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("上市日期")) else ""
            detail_rows.append({
                "来源": "table1",
                "ETF代码": code,
                "ETF名称": str(row.get("ETF名称", "")),
                "跟踪指数": str(row.get("跟踪指数名称", "")),
                "上市日期": listing_date,
                "基金管理人": str(row.get("基金管理人", "")),
                "规模": row.get("最新规模_数值", np.nan),
                "成交额": row.get("日均成交额_数值", np.nan),
                "跟踪误差": row.get("跟踪误差", np.nan),
                "信息比率": row.get("信息比率", np.nan),
                "risks": risks,
            })

df_detail = pd.DataFrame(detail_rows)

# ════════════════════════════════════════════════════════════
# 核心对比表格（HTML渲染，风险单元格红色字体）
# ════════════════════════════════════════════════════════════
st.markdown("##### 📊 核心指标对比")

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

comp_headers = ["ETF代码", "ETF名称", "跟踪指数", "上市日期", "基金管理人",
                "最新规模(亿)", "日均成交额(亿)", "跟踪误差", "信息比率", "潜在风险"]

html_comp = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
html_comp.append('<thead><tr>')
for h in comp_headers:
    tooltip = get_header_tooltip(h)
    html_comp.append(build_th_with_tooltip(h, tooltip, bg_color="#C0392B"))
html_comp.append('</tr></thead><tbody>')

for i, (_, r) in enumerate(df_detail.iterrows()):
    code_val = str(r.get("ETF代码", ""))
    url = etf_code_to_ft_link(code_val)
    code_html = f'<a href="{url}" target="_blank" style="color:#E74C3C;text-decoration:none;font-weight:700;">{code_val}</a>' if url else code_val
    risks = r.get("risks", [])
    risk_tags = " ".join([build_risk_tag(rt) for rt in risks]) if risks else ""

    cells = [
        ("ETF代码", code_html, ""),
        ("ETF名称", str(r.get("ETF名称", "")), ""),
        ("跟踪指数", str(r.get("跟踪指数", "")), ""),
        ("上市日期", str(r.get("上市日期", "")), ""),
        ("基金管理人", str(r.get("基金管理人", "")), ""),
        ("最新规模(亿)", f"{r['规模']:.2f}" if pd.notna(r.get("规模")) else "—", _risk_cell_style("最新规模(亿)", risks)),
        ("日均成交额(亿)", f"{r['成交额']:.2f}" if pd.notna(r.get("成交额")) else "—", _risk_cell_style("日均成交额(亿)", risks)),
        ("跟踪误差", f"{r['跟踪误差']:.2f}" if pd.notna(r.get("跟踪误差")) else "—", _risk_cell_style("跟踪误差", risks)),
        ("信息比率", f"{r['信息比率']:.2f}" if pd.notna(r.get("信息比率")) else "—", ""),
        ("潜在风险", risk_tags, ""),
    ]

    bg = "#FDF2F2" if i % 2 == 0 else "#F8E8E8"
    html_comp.append(f'<tr style="background:{bg};">')
    for col_key, val, style in cells:
        extra = f' {style}' if style else ''
        html_comp.append(f'<td style="padding:5px 8px;text-align:center;white-space:nowrap;{extra}">{val}</td>')
    html_comp.append('</tr>')

html_comp.append('</tbody></table>')
st.markdown(TOOLTIP_CSS + "".join(html_comp), unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# 柱状图（仅当 ≥ 2 只 ETF 时绘制）
# ════════════════════════════════════════════════════════════
if len(pool) >= 2:
    names_list = [str(r["ETF名称"])[:10] for _, r in df_detail.iterrows()]

    # 为不同 ETF 分配不同颜色
    distinct_colors = [
        "#4A90D9", "#E74C3C", "#2ECC71", "#F39C12", "#9B59B6",
        "#1ABC9C", "#E67E22", "#3498DB", "#E91E63", "#00BCD4"
    ]

    bar_metrics = [
        ("规模", "最新规模(亿)", ".2f"),
        ("成交额", "日均成交额(亿)", ".2f"),
        ("跟踪误差", "跟踪误差", ".2f"),
        ("信息比率", "信息比率", ".2f"),
    ]

    for key, title, fmt in bar_metrics:
        vals = []
        for _, r in df_detail.iterrows():
            v = r.get(key, np.nan)
            vals.append(float(v) if pd.notna(v) else 0)

        if fmt == ".2%":
            texts = [f"{v:.2%}" for v in vals]
        else:
            texts = [f"{v:{fmt}}" for v in vals]

        fig_bar = go.Figure()
        for j, (name, val, txt) in enumerate(zip(names_list, vals, texts)):
            fig_bar.add_trace(go.Bar(
                x=[name], y=[val],
                marker_color=distinct_colors[j % len(distinct_colors)],
                text=txt,
                textposition="outside",
                name=name,
                showlegend=(j == 0),  # only show first in legend
            ))
        fig_bar.update_layout(
            title=f"📊 {title}",
            height=350,
            margin=dict(l=40, r=20, t=50, b=40),
            xaxis_title="", yaxis_title=title.split(" 对比")[0],
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ── 导出 ────────────────────────────────────────────────────
buf = io.BytesIO()
export_df = df_detail.drop(columns=["来源", "risks"], errors="ignore")
export_df.to_excel(buf, index=False, engine="openpyxl")
buf.seek(0)
st.download_button(
    "📥 导出关注列表 Excel",
    data=buf,
    file_name="我的关注.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.divider()
st.caption(f"数据来源：ima 知识库 · 刷新时间：{last_refresh}")
st.caption("免责声明：本页数据仅供参考，不保证及时、准确、完整，不构成任何产品推荐或投资建议。")
st.caption("风险提示：证券市场存在不确定性，投资者需根据自身风险承受能力决策，自行承担投资风险。")
