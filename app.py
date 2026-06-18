# -*- coding: utf-8 -*-
"""
ETF智选专家 - 主入口
使用 st.navigation + st.Page 精确控制侧边栏页面名称
"""

import streamlit as st
from dotenv import load_dotenv
import os

# 加载本地 .env 文件中的环境变量（开发环境使用）
load_dotenv()

# ═══ 页面配置 ═══
st.set_page_config(
    page_title="ETF智选专家",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══ 自定义 CSS ═══
st.markdown("""
<style>
    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }

    /* ═══ 侧边栏顶部标题 - 用 ::before 伪元素注入到导航上方 ═══ */
    [data-testid="stSidebarNav"]::before {
        content: "ETF 智选专家";
        display: block;
        padding: 16px 18px 12px 18px;
        font-size: 22px;
        font-weight: 800;
        color: #1a1a2e;
        letter-spacing: 1px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* 主标题栏 */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }

    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }

    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1rem;
    }

    /* 统计卡片 */
    .stat-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        border-left: 4px solid #667eea;
    }

    .stat-card .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #333;
    }

    .stat-card .stat-label {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.3rem;
    }

    /* 风险标签 */
    .risk-tag {
        background: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* ETF代码链接 */
    a.etf-link {
        color: #4A90D9 !important;
        text-decoration: none;
        font-weight: 600;
    }
    a.etf-link:hover {
        text-decoration: underline;
    }

    /* 页脚 */
    .footer {
        text-align: center;
        padding: 1.5rem;
        color: #999;
        font-size: 0.85rem;
        border-top: 1px solid #eee;
        margin-top: 2rem;
    }

    /* Skill 按钮呼吸动画 */
    @keyframes skill-pulse {
        0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(102,126,234,0.4); }
        50% { transform: scale(1.04); box-shadow: 0 0 14px 3px rgba(102,126,234,0.25); }
    }
    .skill-btn {
        display: block;
        width: 100%;
        text-align: center;
        padding: 10px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 14px;
        font-weight: 700;
        text-decoration: none;
        border-radius: 10px;
        animation: skill-pulse 2.5s ease-in-out infinite;
        letter-spacing: 1px;
    }
    .skill-btn:hover {
        animation-play-state: paused;
        background: linear-gradient(135deg, #7b8ff0 0%, #8b5fbf 100%);
        color: white;
        text-decoration: none;
    }
</style>
""", unsafe_allow_html=True)

# ═══ 使用 st.navigation 定义页面 ═══
home = st.Page("Home.py", title="市场总览", icon="📊")
page_02 = st.Page("pages/02_条件选基.py", title="条件选基", icon="🎯")
page_03 = st.Page("pages/03_行业掘金.py", title="行业掘金", icon="⛏️")
page_04 = st.Page("pages/04_ETF 查询.py", title="ETF 查询", icon="🔍")
page_05 = st.Page("pages/05_机构档案.py", title="机构档案", icon="🏛️")
page_06 = st.Page("pages/06_我的关注.py", title="我的关注", icon="⭐")

pg = st.navigation([home, page_02, page_03, page_04, page_05, page_06])

# ═══ 侧边栏内容（放在 pg.run() 之前，确保所有页面都能渲染） ═══
with st.sidebar:
    # 导航与Skill按钮之间的间距（保持紧凑）
    st.html('<div style="height:4px;"></div>')

    # Skill 推广按钮
    st.html(
        '<a href="https://skillhub.cn/skills/etf-selector-expert" target="_blank" class="skill-btn">'
        '体验 Skill ⚡ <span style="font-size:18px;">→</span></a>'
    )

    st.html('<div style="height:4px;"></div>')

    # 作者二维码
    st.markdown(
        "<div style='text-align:center;font-size:13px;color:#888;margin-bottom:8px;'>"
        "关注作者：语研（公众号）</div>",
        unsafe_allow_html=True,
    )
    st.image("assets/qrcode.jpg", use_container_width=True)

pg.run()
