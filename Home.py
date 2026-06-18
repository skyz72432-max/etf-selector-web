# -*- coding: utf-8 -*-
"""
ETF智选专家 · 首页
统计概览、排行榜、行业全景、上新日历
- 风险单元格文字红色（非整行）
- 第一列 ☑/⬜ 加入关注
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from data_layer import (
    load_data, etf_code_to_ft_link, check_risks,
    get_industry_types, get_stats_cards_data,
    render_batch_table, handle_checkbox_clicks,
    build_pagination_controls, render_pagination_buttons,
    build_attention_badge,
    inject_tooltip_css, build_risk_tag, build_th_with_tooltip,
    get_header_tooltip,
)


def render_home():
    table1, table2, last_refresh = load_data()

    inject_tooltip_css()

    if "compare_pool" not in st.session_state:
        st.session_state.compare_pool = []

    # 处理 checkbox 点击
    handle_checkbox_clicks(table1, table2)

    # 检测 Treemap 点击跳转（由注入的 JS 通过 window.location.href 传入）
    treemap_click = st.query_params.get("treemap_click")
    treemap_type = st.query_params.get("treemap_type")
    if treemap_click and treemap_type:
        # 用 flag 防止重复跳转
        _nav_key = treemap_click + "|" + treemap_type
        if st.session_state.get("_last_treemap_click") != _nav_key:
            st.session_state["_last_treemap_click"] = _nav_key
            # 用 type+name 双重定位，避免同名行业跨分类歧义
            match = table1[
                (table1["行业概念名称"].astype(str) == treemap_click)
                & (table1["类型"] == treemap_type)
            ]
            if len(match) > 0:
                st.session_state["nav_industry_type"] = treemap_type
                st.session_state["nav_industry_name"] = treemap_click
                st.switch_page("pages/03_行业掘金.py")
        else:
            # 已处理过，清除残留的 query param（触发 rerun，下次不再进入分支）
            st.query_params.clear()

    # ════════════════════════════════════════════════════════════
    # 页面标题
    # ════════════════════════════════════════════════════════════
    badge = build_attention_badge()
    st.html(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);
                padding:20px 32px;border-radius:16px;margin-bottom:20px;
                display:flex;justify-content:space-between;align-items:center;">
        <div>
            <h1 style="margin:0;font-size:26px;color:white;font-family:'Microsoft YaHei';letter-spacing:1px;">
                📊 市场总览
            </h1>
            <p style="margin:6px 0 0;font-size:12px;color:rgba(255,255,255,0.55);">
                全市场ETF数据透视 · 行业概念全景 · 智能排行筛选 · 实时关注追踪
            </p>
        </div>
        {badge}
    </div>""")

    # ── 统计卡片 ────────────────────────────────────────────────
    stats = get_stats_cards_data(table1, table2)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏢 行业细分", f"{stats['行业细分']}", "主流行业")
    c2.metric("💡 概念细分", f"{stats['概念细分']}", "热门概念")
    c3.metric("⭐ 最佳匹配ETF", f"{stats['最佳匹配ETF']}", "行业概念精选 ETF")
    c4.metric("📈 全市场ETF", f"{stats['全市场ETF']}", "全部上市 ETF")

    st.divider()

    # ── Tab 切换区域 ────────────────────────────────────────────
    tab_rank, tab_treemap, tab_new = st.tabs(
        ["🏆 ETF市场排行", "🗺️ ETF行业全景", "📅 ETF上新日历"]
    )

    # ════════════════════════════════════════════════════════════
    # Tab 1: ETF市场排行
    # ════════════════════════════════════════════════════════════
    with tab_rank:
        etfs = table2.copy()

        rank_tabs = st.tabs(["按规模↓", "按成交额↓", "按跟踪误差↑", "按信息比率↓"])

        sort_configs = [
            ("ETF最新规模_数值", False),
            ("ETF日均成交额_数值", False),
            ("ETF跟踪误差", True),
            ("ETF信息比率", False),
        ]

        pool_codes_set = set(c[0] for c in st.session_state.compare_pool)

        for i, (sort_col, ascending) in enumerate(sort_configs):
            with rank_tabs[i]:
                top_n = st.selectbox(
                    "展示 Top N", [10, 20, 50, 100],
                    index=1, key=f"rank_topn_{i}"
                )

                ranked = etfs.sort_values(sort_col, ascending=ascending, na_position="last")
                display = ranked.head(top_n).copy()
                display = display.reset_index(drop=True)

                # ── 分页 ─────────────────────────────────────────
                page_key = f"home_rank_{i}"
                page, total_pages, start, end = build_pagination_controls(
                    page_key, len(display), page_size=20
                )
                display_page = display.iloc[start:end]

                # ── 风险单元格红色样式 ────────────────────────────
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

                # ── 构建 HTML 表格 ──────────────────────────────
                headers = ["", "ETF代码", "ETF名称", "跟踪指数",
                    "上市日期", "基金管理人",
                    "最新规模(亿)", "日均成交额(亿)", "跟踪误差", "信息比率", "潜在风险"]

                html_parts = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
                html_parts.append('<thead><tr>')
                for h in headers:
                    tooltip = get_header_tooltip(h)
                    html_parts.append(build_th_with_tooltip(h, tooltip))
                html_parts.append('</tr></thead><tbody>')

                for row_i, (_, row) in enumerate(display_page.iterrows()):
                    code = str(row.get("ETF代码", ""))
                    risks = check_risks(row, prefix="ETF")
                    risk_str = " ".join([build_risk_tag(r) for r in risks]) if risks else ""

                    url = etf_code_to_ft_link(code)
                    code_html = f'<a href="{url}" target="_blank" style="color:#4A90D9;font-weight:600;text-decoration:none;">{code}</a>' if url else code

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
                        ("ETF名称", str(row.get("ETF名称", "")), ""),
                        ("跟踪指数", str(row.get("ETF跟踪指数名称", "")), ""),
                        ("上市日期", row["ETF上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("ETF上市日期")) else "", ""),
                        ("基金管理人", str(row.get("ETF基金管理人", "")), ""),
                        ("最新规模(亿)", f"{row.get('ETF最新规模_数值', np.nan):.2f}" if pd.notna(row.get('ETF最新规模_数值')) else "", _risk_cell_style("最新规模(亿)", risks)),
                        ("日均成交额(亿)", f"{row.get('ETF日均成交额_数值', np.nan):.2f}" if pd.notna(row.get('ETF日均成交额_数值')) else "", _risk_cell_style("日均成交额(亿)", risks)),
                        ("跟踪误差", f"{row.get('ETF跟踪误差', np.nan):.2f}" if pd.notna(row.get('ETF跟踪误差')) else "", _risk_cell_style("跟踪误差", risks)),
                        ("信息比率", f"{row.get('ETF信息比率', np.nan):.2f}" if pd.notna(row.get('ETF信息比率')) else "", ""),
                        ("潜在风险", risk_str, ""),
                    ]

                    bg = "#FAFBFC" if row_i % 2 == 0 else "#F5F7FA"
                    html_parts.append(f'<tr style="background:{bg};">')
                    for col_key, val, style in cells:
                        extra = f' {style}' if style else ''
                        html_parts.append(f'<td style="padding:5px 8px;text-align:center;white-space:nowrap;{extra}">{val}</td>')
                    html_parts.append('</tr>')

                html_parts.append('</tbody></table>')
                table_html = "".join(html_parts)
                pool_codes_list = [c[0] for c in st.session_state.compare_pool]
                render_batch_table(table_html, f"home_rank_{i}", pool_codes_list, len(display_page))

                render_pagination_buttons(page_key, total_pages, page)

    # ════════════════════════════════════════════════════════════
    # Tab 2: ETF行业全景 Treemap
    # ════════════════════════════════════════════════════════════
    with tab_treemap:
        types = get_industry_types(table1)
        treemap_options = [t for t in types if t != "全部数据汇总"]

        # 清理 session_state 中可能残留的"市场全貌"（已删除该选项）
        if st.session_state.get("treemap_type") == "市场全貌":
            del st.session_state["treemap_type"]

        type_sel = st.selectbox("分类体系", treemap_options, key="treemap_type")

        sub = table1[table1["类型"] == type_sel].copy()
        title_suffix = type_sel

        agg = sub.groupby("行业概念名称").agg(
            总规模=("最新规模_数值", "sum"),
            ETF数量=("ETF代码", "count"),
        ).reset_index().sort_values("总规模", ascending=False)

        st.markdown(f"##### 🗺️ {title_suffix} ETF 规模分布（亿）")

        fig_tree = px.treemap(
            agg,
            path=["行业概念名称"],
            values="总规模",
            color="ETF数量",
            color_continuous_scale="Blues",
        )
        fig_tree.update_traces(
            textinfo="label+value",
            textfont=dict(size=13, family="Microsoft YaHei"),
            hovertemplate="<b>%{{label}}</b><br>总规模: %{{value:.1f}}亿<br>ETF数量: %{{color:.0f}}<extra></extra>",
        )
        fig_tree.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=600)
        st.plotly_chart(fig_tree, use_container_width=True, key="treemap_chart")

        # 蓝底提示
        st.html('<div style="background:#E6F1FB;border-left:4px solid #378ADD;padding:10px 16px;border-radius:6px;margin-top:6px;font-size:13px;color:#0C447C;">💡 点击色块可自动跳转至「行业掘金」页面深入分析对应行业/概念</div>')

        # 注入 JS 绑定 plotly_click 事件 → 点击色块导航至 ?treemap_click=LABEL&treemap_type=TYPE
        # 把当前分类体系 type_sel 注入 JS，跳转时一并传递，避免同名行业跨分类歧义
        import json as _json
        _type_js = _json.dumps(type_sel, ensure_ascii=False)
        st.html(f"""
<script>
(function(){{
  var TYPE = {_type_js};
  function bindClick(){{
    var plots = document.querySelectorAll('.js-plotly-plot');
    plots.forEach(function(pd){{
      if(!pd._treemap_nav_bound){{
        pd.on('plotly_click', function(data){{
          if(data.points && data.points.length > 0){{
            var label = data.points[0].label;
            if(label){{
              window.location.href = '?treemap_click=' + encodeURIComponent(label) + '&treemap_type=' + encodeURIComponent(TYPE);
            }}
          }}
        }});
        pd._treemap_nav_bound = true;
      }}
    }});
  }}
  setTimeout(bindClick, 300);
  setTimeout(bindClick, 1000);
  setTimeout(bindClick, 2500);
}})();
</script>
""", unsafe_allow_javascript=True)

    # ════════════════════════════════════════════════════════════
    # Tab 3: ETF上新日历
    # ════════════════════════════════════════════════════════════
    with tab_new:
        has_date = table2[table2["ETF上市日期"].notna()].copy()
        has_date = has_date.sort_values("ETF上市日期", ascending=False)

        months_back = st.selectbox("近N个月", [1, 3, 6, 12], index=1, key="new_months",
                                   format_func=lambda x: f"近{x}个月")

        cutoff = pd.Timestamp.now() - pd.DateOffset(months=months_back)
        shown = has_date[has_date["ETF上市日期"] >= cutoff].copy()
        shown = shown.reset_index(drop=True)

        st.markdown(f"##### 📅 近 {months_back} 个月上市的 ETF（共 {len(shown)} 只）")

        # ── 分页 ───────────────────────────────────────────────
        page_key = "home_new_cal"
        page, total_pages, start, end = build_pagination_controls(
            page_key, len(shown), page_size=20
        )
        shown_page = shown.iloc[start:end]

        # 用 HTML 表格渲染以支持超链接和风险红字
        pool_codes_set = set(c[0] for c in st.session_state.compare_pool)
        _new_rows = []
        for _, row in shown_page.iterrows():
            code = str(row.get("ETF代码", ""))
            url = etf_code_to_ft_link(code)
            code_html = (
                f'<a href="{url}" target="_blank" '
                f'style="color:#4A90D9;text-decoration:none;font-weight:600;">{code}</a>'
                if url else code
            )
            scale_val = row.get("ETF最新规模_数值", np.nan)
            d = row["ETF上市日期"].strftime("%Y-%m-%d") if pd.notna(row.get("ETF上市日期")) else ""

            risks = check_risks(row, prefix="ETF")
            risk_str = " ".join([build_risk_tag(r) for r in risks]) if risks else ""
            scale_style = 'style="color:#E74C3C;font-weight:600;"' if "小规模" in risks else ''
            vol_val = row.get("ETF日均成交额_数值", np.nan)
            vol_style = 'style="color:#E74C3C;font-weight:600;"' if "低流动性" in risks else ''
            err_val = row.get("ETF跟踪误差", np.nan)
            err_style = 'style="color:#E74C3C;font-weight:600;"' if "跟踪偏差" in risks else ''
            ir_val = row.get("ETF信息比率", np.nan)

            checked = code in pool_codes_set
            color = '#4CAF50' if checked else '#ccc'
            icon = '☑️' if checked else '⬜'
            checkbox_html = (
                f'<span data-etf-code="{code}" '
                f'style="cursor:pointer;font-size:16px;color:{color};">{icon}</span>'
            )

            _new_rows.append({
                "_checkbox": checkbox_html,
                "ETF代码": code_html,
                "ETF名称": str(row.get("ETF名称", "")),
                "跟踪指数": str(row.get("ETF跟踪指数名称", "")),
                "上市日期": d,
                "基金管理人": str(row.get("ETF基金管理人", "")),
                "最新规模(亿)": f'<span {scale_style}>{scale_val:.2f}</span>' if pd.notna(scale_val) else "",
                "日均成交额(亿)": f'<span {vol_style}>{vol_val:.2f}</span>' if pd.notna(vol_val) else "",
                "跟踪误差": f'<span {err_style}>{err_val:.2f}</span>' if pd.notna(err_val) else "",
                "信息比率": f"{ir_val:.2f}" if pd.notna(ir_val) else "",
                "潜在风险": risk_str,
            })

        new_headers = ["", "ETF代码", "ETF名称", "跟踪指数", "上市日期", "基金管理人", "最新规模(亿)", "日均成交额(亿)", "跟踪误差", "信息比率", "潜在风险"]
        html_new = ['<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:Microsoft YaHei,sans-serif;">']
        html_new.append('<thead><tr>')
        for h in new_headers:
            tooltip = get_header_tooltip(h)
            html_new.append(build_th_with_tooltip(h, tooltip))
        html_new.append('</tr></thead><tbody>')

        for row_i, nr in enumerate(_new_rows):
            bg = "#FAFBFC" if row_i % 2 == 0 else "#F5F7FA"
            html_new.append(f'<tr style="background:{bg};">')
            html_new.append(f'<td style="padding:5px 8px;text-align:center;white-space:nowrap;">{nr["_checkbox"]}</td>')
            for h in new_headers[1:]:
                val = nr.get(h, "")
                html_new.append(f'<td style="padding:5px 8px;text-align:center;white-space:nowrap;">{val}</td>')
            html_new.append('</tr>')

        html_new.append('</tbody></table>')
        table_html = "".join(html_new)
        pool_codes_list = [c[0] for c in st.session_state.compare_pool]
        render_batch_table(table_html, "home_new", pool_codes_list, len(shown_page))

        render_pagination_buttons(page_key, total_pages, page)

        if len(shown) == 0:
            st.info(f"近 {months_back} 个月内没有新上市的 ETF。")

    st.divider()
    st.caption(f"数据来源：ima 知识库 · 刷新时间：{last_refresh}")
    st.caption("免责声明：本页数据仅供参考，不保证及时、准确、完整，不构成任何产品推荐或投资建议。")
    st.caption("风险提示：证券市场存在不确定性，投资者需根据自身风险承受能力决策，自行承担投资风险。")


# 当被 st.Page 直接执行时调用
render_home()
