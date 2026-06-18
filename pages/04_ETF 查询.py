# -*- coding: utf-8 -*-
"""
页面4 · ETF 查询
按代码/名称模糊搜索 + 质量雷达图(同类排名百分位) + 加入关注
- 风险项红色文字（非整行）
- 每行可加入关注
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

from data_layer import (
    load_data, etf_code_to_ft_link, check_risks,
    get_rank_percentile,
    build_attention_badge, format_rank_from_row,
)

# set_page_config 已移至 app.py

table1, table2, last_refresh = load_data()

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
            🔎 ETF 查询
        </h1>
        <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.55);">
            按代码 / 名称 模糊搜索，查看详细信息与质量雷达
        </p>
    </div>
    {badge}
</div>""")

# ── 搜索框 ────────────────────────────────────────────────
query = st.text_input(
    "输入 ETF 代码或名称",
    placeholder="例如：518880 / 黄金 / 沪深300",
    label_visibility="collapsed",
)

if not query:
    st.info("💡 输入关键词开始搜索，支持 ETF 代码（如 518880.SH）、名称（如黄金ETF）或跟踪指数")
    st.stop()

# ── 搜索逻辑 ────────────────────────────────────────────────
q = query.strip()

mask1 = (
    table1["ETF代码"].astype(str).str.contains(q, case=False, na=False) |
    table1["ETF名称"].astype(str).str.contains(q, case=False, na=False) |
    table1["跟踪指数名称"].astype(str).str.contains(q, case=False, na=False)
)
found_t1 = table1[mask1]
found_t1 = found_t1.drop_duplicates(subset=["ETF代码"], keep="first")

mask2 = (
    table2["ETF代码"].astype(str).str.contains(q, case=False, na=False) |
    table2["ETF名称"].astype(str).str.contains(q, case=False, na=False) |
    table2["ETF跟踪指数名称"].astype(str).str.contains(q, case=False, na=False)
)
found_t2 = table2[mask2]

found_codes_t1 = set(found_t1["ETF代码"].astype(str)) if len(found_t1) > 0 else set()
found_t2_only = found_t2[~found_t2["ETF代码"].astype(str).isin(found_codes_t1)] if len(found_t2) > 0 else pd.DataFrame()

total_found = len(found_t1) + len(found_t2_only)
st.markdown(f"##### 🔍 搜索「{q}」— 找到 **{total_found}** 只 ETF")

if total_found == 0:
    st.warning("未找到匹配的 ETF，请尝试其他关键词。")
    st.stop()

# ── 辅助：风险值红色渲染 ────────────────────────────────────
def _red_if_risk(val_str, risk_name, risks):
    if risk_name in risks:
        return f'<span style="color:#E74C3C;font-weight:600;">{val_str}</span>'
    return val_str

# ── 结果展示 ────────────────────────────────────────────────
# 先展示 table1 结果（有排名数据，可画雷达图）
for idx_num, (_, row) in enumerate(found_t1.iterrows()):
    code = str(row.get("ETF代码", ""))
    name = str(row.get("ETF名称", ""))
    idx_name = str(row.get("跟踪指数名称", ""))
    fund = str(row.get("基金管理人", ""))
    scale_str = str(row.get("最新规模", ""))
    vol_str = str(row.get("近半年日均成交额", ""))
    scale_val = row.get("最新规模_数值", np.nan)
    vol_val = row.get("日均成交额_数值", np.nan)
    err_val = row.get("跟踪误差", np.nan)
    ir_val = row.get("信息比率", np.nan)
    corr_val = row.get("与跟踪指数收益相关性", np.nan)
    date_val = row["上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("上市日期")) else ""
    benchmark = str(row.get("业绩比较基准", ""))
    url = etf_code_to_ft_link(code)
    type_str = str(row.get("类型", ""))
    ind_str = str(row.get("行业概念名称", ""))
    match_val = row.get("综合匹配度", np.nan)
    best_idx = row.get("是否为最佳匹配指数", False)
    best_etf = row.get("是否为最佳匹配ETF", False)
    rank_str = format_rank_from_row(row, "综合排名", "同类ETF数量")

    risks = check_risks(row)

    with st.expander(
        f"{'⭐' if best_etf else ''} {code} &nbsp; {name} &nbsp;|&nbsp; 规模:{scale_str} &nbsp; 成交:{vol_str}",
        expanded=(total_found <= 5),
    ):
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("**📋 基本资料**")
            info_lines = [
                f"**ETF代码：** {code}",
                f"**ETF名称：** {name}",
                f"**跟踪指数：** {idx_name}",
                f"**基金管理人：** {fund}",
                f"**上市日期：** {date_val}",
                f"**业绩比较基准：** {benchmark}",
                f"**分类体系：** {type_str}",
                f"**行业/概念：** {ind_str}",
            ]
            if url:
                info_lines.append(f"**行情链接：** [查看最新行情]({url})")
            st.markdown("<br>".join(info_lines), unsafe_allow_html=True)

            st.markdown("**📊 业绩指标**")
            scale_display = _red_if_risk(scale_str, "小规模", risks)
            vol_display = _red_if_risk(vol_str, "低流动性", risks)
            err_display = _red_if_risk(f"{err_val:.2f}" if pd.notna(err_val) else "—", "跟踪偏差", risks)

            perf_lines = [
                f"**最新规模：** {scale_display}",
                f"**日均成交额：** {vol_display}",
                f"**跟踪误差：** {err_display}",
                f"**信息比率：** {ir_val:.2f}" if pd.notna(ir_val) else "**信息比率：** —",
                f"**收益相关性：** {corr_val:.2%}" if pd.notna(corr_val) else "**收益相关性：** —",
                f"**综合匹配度：** {match_val:.2%}" if pd.notna(match_val) else "**综合匹配度：** —",
                f"**是否最佳匹配指数：** {'✅ 是' if best_idx else '否'}",
                f"**是否最佳匹配ETF：** {'✅ 是' if best_etf else '否'}",
                f"**同类排名：** {rank_str}" if rank_str != "-" else "**同类排名：** —",
            ]
            st.markdown("<br>".join(perf_lines), unsafe_allow_html=True)

            if risks:
                risk_tags = " ".join([f'<span style="color:#E74C3C;font-weight:600;">⚠️ {r}</span>' for r in risks])
                st.markdown(risk_tags, unsafe_allow_html=True)

        with col_right:
            st.markdown("**🎯 同类排名百分位雷达图**")
            pct = get_rank_percentile(row, table1)
            categories = ["规模", "流动性", "跟踪精度", "信息比率", "收益相关性"]
            values = [pct["规模"], pct["流动性"], pct["跟踪精度"], pct["信息比率"], pct["收益相关性"]]

            fig_radar = go.Figure(go.Scatterpolar(
                r=values + [values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=name,
                line=dict(color="#4A90D9", width=2),
                fillcolor="rgba(74,144,217,0.15)",
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        tickvals=[0, 25, 50, 75, 100],
                        ticktext=["0%", "25%", "50%", "75%", "100%"],
                    ),
                ),
                height=300,
                margin=dict(l=40, r=40, t=30, b=30),
                showlegend=False,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            for cat, val in zip(categories, values):
                st.caption(f"  {cat}：{val:.1f}%")

        # 加入关注
        col_add, _ = st.columns([1, 3])
        with col_add:
            pool_codes = [c[0] for c in st.session_state.compare_pool]
            if code in pool_codes:
                st.info(f"✅ 已关注")
            else:
                if st.button(f"➕ 加入关注", key=f"add_{code}"):
                    st.session_state.compare_pool.append((code, name, idx_name))
                    st.success(f"✅ {code} 已加入关注（共 {len(st.session_state.compare_pool)} 只）")
                    st.rerun()

# 再展示 table2-only 结果
if len(found_t2_only) > 0:
    st.divider()
    st.markdown("##### 📋 其他匹配 ETF（无同类排名数据）")

    for _, row in found_t2_only.iterrows():
        code = str(row.get("ETF代码", ""))
        name = str(row.get("ETF名称", ""))
        idx_name = str(row.get("ETF跟踪指数名称", ""))
        fund = str(row.get("ETF基金管理人", ""))
        scale_str = str(row.get("ETF最新规模", ""))
        vol_str = str(row.get("ETF近半年日均成交额", ""))
        err_val = row.get("ETF跟踪误差", np.nan)
        ir_val = row.get("ETF信息比率", np.nan)
        corr_val = row.get("ETF与跟踪指数收益相关性", np.nan)
        date_val = row["ETF上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("ETF上市日期")) else ""
        url = etf_code_to_ft_link(code)

        risks = check_risks(row, prefix="ETF")

        with st.expander(
            f"{code} &nbsp; {name} &nbsp;|&nbsp; 规模:{scale_str}",
            expanded=False,
        ):
            col_l, col_r = st.columns([1, 1])

            with col_l:
                st.markdown("**📋 基本资料**")
                info_lines = [
                    f"**ETF代码：** {code}",
                    f"**ETF名称：** {name}",
                    f"**跟踪指数：** {idx_name}",
                    f"**基金管理人：** {fund}",
                    f"**上市日期：** {date_val}",
                ]
                if url:
                    info_lines.append(f"**行情链接：** [查看最新行情]({url})")
                st.markdown("<br>".join(info_lines), unsafe_allow_html=True)

            with col_r:
                st.markdown("**📊 业绩指标**")
                scale_display = _red_if_risk(scale_str, "小规模", risks)
                vol_display = _red_if_risk(vol_str, "低流动性", risks)
                err_display = _red_if_risk(f"{err_val:.2f}" if pd.notna(err_val) else "—", "跟踪偏差", risks)

                perf_lines = [
                    f"**最新规模：** {scale_display}",
                    f"**日均成交额：** {vol_display}",
                    f"**跟踪误差：** {err_display}",
                    f"**信息比率：** {ir_val:.2f}" if pd.notna(ir_val) else "**信息比率：** —",
                    f"**收益相关性：** {corr_val:.2%}" if pd.notna(corr_val) else "**收益相关性：** —",
                ]
                st.markdown("<br>".join(perf_lines), unsafe_allow_html=True)

                if risks:
                    risk_tags = " ".join([f'<span style="color:#E74C3C;font-weight:600;">⚠️ {r}</span>' for r in risks])
                    st.markdown(risk_tags, unsafe_allow_html=True)

            col_add, _ = st.columns([1, 3])
            with col_add:
                pool_codes = [c[0] for c in st.session_state.compare_pool]
                if code in pool_codes:
                    st.info("✅ 已关注")
                else:
                    if st.button(f"➕ 加入关注", key=f"add_t2_{code}"):
                        st.session_state.compare_pool.append((code, name, idx_name))
                        st.success(f"✅ {code} 已加入关注（共 {len(st.session_state.compare_pool)} 只）")
                        st.rerun()

st.divider()
st.caption(f"数据来源：ima 知识库 · 刷新时间：{last_refresh}")
st.caption("免责声明：本页数据仅供参考，不保证及时、准确、完整，不构成任何产品推荐或投资建议。")
st.caption("风险提示：证券市场存在不确定性，投资者需根据自身风险承受能力决策，自行承担投资风险。")
