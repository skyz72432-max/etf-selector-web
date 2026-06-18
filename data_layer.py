# -*- coding: utf-8 -*-
"""
数据层 · data_layer.py
负责从 ima 知识库拉取 Excel 数据、解析为 DataFrame、缓存

Table1 结构（行业概念-最佳匹配-指数ETF-完整版.xlsx）:
  - 多 sheet: 中信一级行业, 中信二级行业, 热门概念, 申万一级行业, 申万二级行业, 全部数据汇总
  - 两级表头: Row 0=大类, Row 1=字段名
  - 关键列(合并后): 类型, 行业概念名称, 行业概念代码, 跟踪指数名称, 跟踪指数代码,
     关联ETF数量, 走势相关度, 持仓相关度, 综合匹配度, 是否为最佳匹配指数,
     ETF名称, ETF代码, 基金管理人, 上市日期, 业绩比较基准,
     最新规模(字符串,含"亿"), 近半年日均成交额(字符串,含"万"),
     跟踪误差, 信息比率, 与跟踪指数收益相关性,
     同类排名_最新规模, 同类排名_成交额, 同类排名_跟踪误差, 同类排名_信息比率,
     同类排名_收益相关性, 同类ETF数量, 综合排名, 是否为最佳匹配ETF

Table2 结构（全部上市ETF-基本信息与近期业绩-知识库版.xlsx）:
  - 单级表头, 列名已带 ETF 前缀
  - ETF名称, ETF代码, ETF跟踪指数名称, ETF跟踪指数代码,
     ETF上市日期, ETF基金管理人, ETF业绩比较基准,
     ETF最新规模(字符串), ETF近半年日均成交额(字符串),
     ETF跟踪误差, ETF信息比率, ETF与跟踪指数收益相关性
"""

import os
import io
import re
import time
import requests
import streamlit as st
import pandas as pd
import numpy as np

# ════════════════════════════════════════════════════════════
# IMA 配置（从环境变量读取，不再硬编码密钥）
# ════════════════════════════════════════════════════════════
IMA_API_KEY = os.environ.get("IMA_API_KEY")
IMA_CLIENT_ID = os.environ.get("IMA_CLIENT_ID")
KNOWLEDGE_BASE_ID = os.environ.get("IMA_KB_ID")
IMA_BASE_URL = "https://ima.qq.com/openapi/wiki/v1"

# 增加校验，确保密钥已设置
if not all([IMA_API_KEY, IMA_CLIENT_ID, KNOWLEDGE_BASE_ID]):
    raise ValueError(
        "缺少 IMA 环境变量！请设置 IMA_API_KEY, IMA_CLIENT_ID, IMA_KB_ID。"
        "本地开发时请在 .env 文件中配置，部署时请在 Streamlit Secrets 中设置。"
    )

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get_ima_headers():
    return {
        "ima-openapi-apikey": IMA_API_KEY,
        "ima-openapi-clientid": IMA_CLIENT_ID,
        "Content-Type": "application/json",
    }


def _find_excel_media_ids():
    """通过 get_knowledge_list 查找知识库中的两个 Excel 文件"""
    headers = _get_ima_headers()
    payload = {"knowledge_base_id": KNOWLEDGE_BASE_ID, "cursor": "", "limit": 50}
    resp = requests.post(f"{IMA_BASE_URL}/get_knowledge_list", json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"get_knowledge_list 失败: {result.get('msg')}")

    items = result.get("data", {}).get("knowledge_list", [])
    excel_files = []
    for item in items:
        title = item.get("title", "")
        media_id = item.get("media_id", "")
        if title.endswith(".xlsx") and media_id:
            excel_files.append({"title": title, "media_id": media_id})

    if len(excel_files) < 2:
        raise RuntimeError(f"在知识库中找到 {len(excel_files)} 个 Excel 文件，期望 2 个。")
    return excel_files


def _download_excel(media_id):
    """通过 get_media_info 获取下载 URL 和 headers，然后下载 Excel 内容"""
    headers = _get_ima_headers()
    resp = requests.post(f"{IMA_BASE_URL}/get_media_info", json={"media_id": media_id}, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"get_media_info 失败: {result.get('msg')}")

    url_info = result.get("data", {}).get("url_info", {})
    download_url = url_info.get("url", "")
    download_headers = url_info.get("headers", {})
    if not download_url:
        raise RuntimeError(f"无法获取 media_id={media_id} 的下载 URL")

    dl_resp = requests.get(download_url, headers=download_headers, timeout=60)
    dl_resp.raise_for_status()
    return dl_resp.content


def _parse_scale_str(val):
    """将 '31.24亿' / '19986.35万' 转换为纯数字（亿元）"""
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    # 匹配数字（可能含小数点和逗号）
    m = re.match(r'([\d,.]+)\s*(亿|万)?', s)
    if not m:
        try:
            return float(s)
        except (ValueError, TypeError):
            return np.nan
    num_str = m.group(1).replace(',', '')
    unit = m.group(2)
    try:
        num = float(num_str)
    except (ValueError, TypeError):
        return np.nan
    if unit == '万':
        num /= 10000  # 万 → 亿
    return num  # 亿保持不变


@st.cache_data(ttl=3600, show_spinner="正在从ima知识库同步数据，请稍候...")
def load_data():
    """
    从 ima 知识库加载两个 Excel 表。
    返回 (table1_df, table2_df, refresh_time)
    """
    cache_path_t1 = os.path.join(CACHE_DIR, "table1.parquet")
    cache_path_t2 = os.path.join(CACHE_DIR, "table2.parquet")

    # 尝试缓存
    if os.path.exists(cache_path_t1) and os.path.exists(cache_path_t2):
        t1_mtime = os.path.getmtime(cache_path_t1)
        if time.time() - t1_mtime < 3600:
            try:
                t1 = pd.read_parquet(cache_path_t1)
                t2 = pd.read_parquet(cache_path_t2)
                refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t1_mtime))
                return t1, t2, refresh_time
            except Exception:
                pass

    excel_files = _find_excel_media_ids()

    table1, table2 = None, None
    for finfo in excel_files:
        content = _download_excel(finfo["media_id"])
        file_obj = io.BytesIO(content)
        is_table1 = len(content) > 500000  # 大文件 = 表1
        xl = pd.ExcelFile(file_obj, engine="openpyxl")

        if is_table1:
            table1 = _parse_table1(xl)
        else:
            table2 = _parse_table2(xl)

    if table1 is None or table2 is None or table1.empty or table2.empty:
        raise RuntimeError(
            f"Excel 解析失败: table1={len(table1) if table1 is not None else 'None'} rows, "
            f"table2={len(table2) if table2 is not None else 'None'} rows"
        )

    # 缓存
    try:
        table1.to_parquet(cache_path_t1, index=False)
        table2.to_parquet(cache_path_t2, index=False)
    except Exception:
        pass

    refresh_time = time.strftime("%Y-%m-%d %H:%M:%S")
    return table1, table2, refresh_time


# 标准29列映射（按位置索引，适用于所有 sheet）
# 基于 Row0+Row1 合并后的列名对应关系
_TABLE1_COL_MAP = {
    0: "类型",                     # 行业概念_类型
    1: "行业概念名称",              # 名称
    2: "行业概念代码",              # 代码
    3: "跟踪指数名称",              # 跟踪指数_名称
    4: "跟踪指数代码",              # 代码 (第2个)
    5: "关联ETF数量",               # 关联ETF数量
    6: "关联ETF总规模",             # 关联ETF总规模
    7: "走势相关度",                # 行业概念与跟踪指数_走势相关度
    8: "持仓相关度",                # 持仓相关度
    9: "综合匹配度",                # 综合匹配度
    10: "是否为最佳匹配指数",        # 是否为最佳匹配指数
    11: "ETF名称",                  # ETF基本资料_名称
    12: "ETF代码",                  # 代码 (第3个)
    13: "基金管理人",               # 基金管理人
    14: "上市日期",                 # 上市日期
    15: "业绩比较基准",             # 业绩比较基准
    16: "最新规模",                 # ETF业绩表现_最新规模
    17: "近半年日均成交额",         # 近半年日均成交额 (ETF业绩表现)
    18: "跟踪误差",                 # 跟踪误差 (ETF业绩表现)
    19: "信息比率",                 # 信息比率 (ETF业绩表现)
    20: "与跟踪指数收益相关性",     # 与跟踪指数收益相关性 (ETF业绩表现)
    21: "同类排名_规模",            # ETF同类排名_最新规模
    22: "同类排名_成交额",          # 近半年日均成交额 (ETF同类排名)
    23: "同类排名_跟踪误差",        # 跟踪误差 (ETF同类排名)
    24: "同类排名_信息比率",        # 信息比率 (ETF同类排名)
    25: "同类排名_收益相关性",      # 与跟踪指数收益相关性 (ETF同类排名)
    26: "综合排名",                 # 综合排名
    27: "同类ETF数量",              # 同类ETF数量
    28: "是否为最佳匹配ETF",        # 是否为最佳匹配ETF
}


def _parse_table1(xl):
    """解析 Table1（多 sheet，两级表头，按位置索引映射列名）"""
    all_sheets = []

    for sheet_name in xl.sheet_names:
        df_raw = pd.read_excel(xl, sheet_name=sheet_name, header=None, engine="openpyxl")
        if df_raw.empty or df_raw.shape[0] < 3:
            continue

        # 从第2行开始是数据
        df = df_raw.iloc[2:].copy()
        df.reset_index(drop=True, inplace=True)

        # 按位置索引映射标准列名
        new_cols = []
        for i in range(len(df.columns)):
            new_cols.append(_TABLE1_COL_MAP.get(i, f"_col_{i}"))
        df.columns = new_cols

        # 类型列用 sheet 名覆盖（比 Row0/Row1 的值更准确）
        df["类型"] = sheet_name.strip()
        all_sheets.append(df)

    if not all_sheets:
        return pd.DataFrame()

    df_t1 = pd.concat(all_sheets, ignore_index=True)

    # 移除未映射列
    drop_cols = [c for c in df_t1.columns if c.startswith('_col_')]
    df_t1 = df_t1.drop(columns=drop_cols, errors='ignore')

    # 数值转换
    numeric_map = {
        "关联ETF数量": int,
        "走势相关度": float,
        "持仓相关度": float,
        "综合匹配度": float,
        "跟踪误差": float,
        "信息比率": float,
        "与跟踪指数收益相关性": float,
        "同类排名_规模": int,
        "同类排名_成交额": int,
        "同类排名_跟踪误差": int,
        "同类排名_信息比率": int,
        "同类排名_收益相关性": int,
        "同类ETF数量": int,
        "综合排名": int,
    }
    for col, dtype in numeric_map.items():
        if col in df_t1.columns:
            df_t1[col] = pd.to_numeric(df_t1[col], errors='coerce')

    # 字符串→数值转换（规模/成交额含"亿"/"万"单位）
    if "最新规模" in df_t1.columns:
        df_t1["最新规模_数值"] = df_t1["最新规模"].apply(_parse_scale_str)
    if "近半年日均成交额" in df_t1.columns:
        df_t1["日均成交额_数值"] = df_t1["近半年日均成交额"].apply(_parse_scale_str)
    if "关联ETF总规模" in df_t1.columns:
        df_t1["关联ETF总规模_数值"] = df_t1["关联ETF总规模"].apply(_parse_scale_str)

    # 上市日期转换
    if "上市日期" in df_t1.columns:
        df_t1["上市日期"] = pd.to_datetime(df_t1["上市日期"], errors='coerce')

    return df_t1


def _parse_table2(xl):
    """解析 Table2（单 sheet，单级表头）"""
    df = pd.read_excel(xl, sheet_name=0, header=0, engine="openpyxl")
    df.columns = [str(c).strip().replace("\n", "").replace(" ", "") for c in df.columns]

    # 标准化列名
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "etf代码" in cl or (cl == "代码"):
            col_map[c] = "ETF代码"
        elif "etf名称" in cl or (cl == "名称"):
            col_map[c] = "ETF名称"
        elif "跟踪指数" in cl and "代码" in cl:
            col_map[c] = "ETF跟踪指数代码"
        elif "跟踪指数" in cl:
            col_map[c] = "ETF跟踪指数名称"
        elif "上市日期" in cl:
            col_map[c] = "ETF上市日期"
        elif "基金管理人" in cl or "管理人" in cl:
            col_map[c] = "ETF基金管理人"
        elif "业绩比较基准" in cl:
            col_map[c] = "ETF业绩比较基准"
        elif "最新规模" in cl:
            col_map[c] = "ETF最新规模"
        elif "成交额" in cl or "成交" in cl:
            col_map[c] = "ETF近半年日均成交额"
        elif "跟踪误差" in cl:
            col_map[c] = "ETF跟踪误差"
        elif "信息比率" in cl:
            col_map[c] = "ETF信息比率"
        elif "收益相关性" in cl:
            col_map[c] = "ETF与跟踪指数收益相关性"

    df = df.rename(columns=col_map)
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    # 数值转换
    if "ETF最新规模" in df.columns:
        df["ETF最新规模_数值"] = df["ETF最新规模"].apply(_parse_scale_str)
    if "ETF近半年日均成交额" in df.columns:
        df["ETF日均成交额_数值"] = df["ETF近半年日均成交额"].apply(_parse_scale_str)

    for nc in ["ETF跟踪误差", "ETF信息比率"]:
        if nc in df.columns:
            df[nc] = pd.to_numeric(df[nc], errors='coerce')
    if "ETF上市日期" in df.columns:
        df["ETF上市日期"] = pd.to_datetime(df["ETF上市日期"], errors='coerce')

    return df


# ════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════

def etf_code_to_ft_link(code):
    """ETF 代码 → 非凸科技行情页超链接"""
    if not code or pd.isna(code):
        return ""
    code_str = str(code).strip()
    suffix_map = {".SH": ".XSHG", ".SZ": ".XSHE", ".BJ": ".XBSE"}
    for old, new in suffix_map.items():
        if code_str.upper().endswith(old.upper()):
            symkey = code_str[:-len(old)] + new
            return f"https://market.ft.tech/etf/detail?symkey={symkey}"
    return f"https://market.ft.tech/etf/detail?symkey={code_str}"


def check_risks(row, prefix=""):
    """检查风险标签
    规模/成交额数值单位为亿元，阈值对应调整：
    - 小规模: 规模 < 2亿
    - 低流动性: 日均成交额 < 1000万 = 0.1亿
    - 跟踪偏差: 跟踪误差 > 1.0
    """
    risks = []
    scale_col = f"{prefix}最新规模_数值" if prefix else "最新规模_数值"
    vol_col = f"{prefix}日均成交额_数值" if prefix else "日均成交额_数值"
    err_col = f"{prefix}跟踪误差" if prefix else "跟踪误差"

    def _safe_float(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            return np.nan

    sv = _safe_float(row.get(scale_col, np.nan))
    vv = _safe_float(row.get(vol_col, np.nan))
    ev = _safe_float(row.get(err_col, np.nan))

    if pd.notna(sv) and sv < 2:
        risks.append("小规模")
    if pd.notna(vv) and vv < 0.1:  # 0.1亿 = 1000万
        risks.append("低流动性")
    if pd.notna(ev) and ev > 1.0:
        risks.append("跟踪偏差")
    return risks


def get_best_etf_subset(table1):
    """筛选「最佳匹配 ETF」子集"""
    if table1 is None or table1.empty:
        return pd.DataFrame()
    best = table1.copy()
    if "是否为最佳匹配ETF" in best.columns:
        best = best[best["是否为最佳匹配ETF"] == True]
    if "综合排名" in best.columns:
        best = best.sort_values("综合排名", ascending=True)
    return best


def get_industry_types(table1):
    """获取所有分类体系"""
    if table1 is None or "类型" not in table1.columns:
        return []
    return sorted(table1["类型"].dropna().unique().tolist())


def get_stats_cards_data(table1, table2):
    """返回统计卡片数据
    - 行业细分数量 = max{中信二级行业数量, 申万一二级行业数量}
    - 概念细分数量 = 热门概念去重数量
    - 最佳匹配ETF数量 = table1中是否为最佳匹配ETF=True的去重数量
    - 全市场ETF总数 = len(table2)
    """
    if table1 is None or table1.empty:
        return {"行业细分": 0, "概念细分": 0, "最佳匹配ETF": 0, "全市场ETF": len(table2) if table2 is not None else 0}

    type_col = "类型" if "类型" in table1.columns else None
    ind_col = "行业概念名称" if "行业概念名称" in table1.columns else None

    # 行业细分数量
    zx2_count = 0
    sw1_count = 0
    sw2_count = 0
    if type_col and ind_col:
        for t in table1[type_col].dropna().unique():
            t_str = str(t).strip()
            sub = table1[table1[type_col] == t]
            n = sub[ind_col].nunique()
            if "中信二级" in t_str:
                zx2_count = n
            elif "申万一级" in t_str:
                sw1_count = n
            elif "申万二级" in t_str:
                sw2_count = n

    industry_count = max(zx2_count, sw1_count, sw2_count)

    # 概念细分数量
    concept_count = 0
    if type_col and ind_col:
        concept_mask = table1[type_col].astype(str).str.contains("概念", na=False)
        concept_count = table1.loc[concept_mask, ind_col].nunique()

    # 最佳匹配ETF数量
    best_etf_count = 0
    if "是否为最佳匹配ETF" in table1.columns and "ETF代码" in table1.columns:
        best_mask = table1["是否为最佳匹配ETF"] == True
        best_etf_count = table1.loc[best_mask, "ETF代码"].nunique()

    # 全市场ETF总数（去重）
    total_etf = table2["ETF代码"].nunique() if table2 is not None and "ETF代码" in table2.columns else (len(table2) if table2 is not None else 0)

    return {
        "行业细分": industry_count,
        "概念细分": concept_count,
        "最佳匹配ETF": best_etf_count,
        "全市场ETF": total_etf,
    }


# ════════════════════════════════════════════════════════════
# 通用工具：同类排名格式化、分页、checkbox 交互
# ════════════════════════════════════════════════════════════

RANK_DISPLAY_COLS = [
    "同类排名_规模", "同类排名_成交额", "同类排名_跟踪误差",
    "同类排名_信息比率", "同类排名_收益相关性", "综合排名"
]

def format_rank(rank_val, total_val):
    """将同类排名格式化为 '分子 / 分母' 字符串"""
    if pd.isna(rank_val) or pd.isna(total_val) or total_val <= 0:
        return "-"
    try:
        return f"{int(float(rank_val))} / {int(float(total_val))}"
    except (ValueError, TypeError):
        return "-"


def format_rank_from_row(row, rank_col, total_col="同类ETF数量"):
    """从 DataFrame 行读取排名和总数，返回格式化字符串"""
    return format_rank(row.get(rank_col, np.nan), row.get(total_col, np.nan))


# ════════════════════════════════════════════════════════════
# 批量 checkbox 确认机制
#
# 方案：st.html(unsafe_allow_javascript=True) 渲染整段 HTML
#   - st.html 不被 iframe 化 → window.location.href 在主页面上下文，零沙箱导航
#   - unsafe_allow_javascript=True → <script> 经前端"重创建 script 节点"机制执行
#   - DOMPurify 的 ADD_ATTR 不含 on* → 内联 onclick 会被剥离，改用 addEventListener
#   - data-* 属性默认保留 → 用 data-etf-code 承载 code，外层 id 容器限定范围
# ════════════════════════════════════════════════════════════

def render_batch_table(table_html, page_id, pool_codes_list, row_count):
    """将表格 HTML 包装为带 checkbox 多选 + 确认按钮的可交互组件。
    用 st.html(unsafe_allow_javascript=True) 渲染：<script> 可执行、不 iframe 化、
    确认时 window.location.href 直接导航主页面。内联 onclick 会被 DOMPurify 剥离，
    故 checkbox 和按钮均改用 addEventListener 绑定。
    表头全选 checkbox 由 JS createElement 注入（绕过 DOMPurify 清洗，最可靠）。
    """
    import json
    pool_json = json.dumps(list(pool_codes_list), ensure_ascii=False)
    pool_count = len(pool_codes_list)

    # CSS for tooltips (embedded directly to ensure it applies in st.html context)
    tooltip_style = """<style>
.wb-tt-el, .wb-tt-risk { position: relative; cursor: help; }
.wb-tt-el::after, .wb-tt-risk::after {
    content: attr(data-wb-tt); position: absolute; bottom: 100%; left: 50%;
    transform: translateX(-50%); padding: 3px 8px; background: rgba(0,0,0,0.82);
    color: #fff; font-size: 11px; border-radius: 4px; white-space: nowrap;
    opacity: 0; pointer-events: none; z-index: 99999;
    transition: opacity 0.15s ease 0.2s; font-family: 'Microsoft YaHei', sans-serif;
    line-height: 1.4; margin-bottom: 4px;
}
.wb-tt-el:hover::after, .wb-tt-risk:hover::after { opacity: 1; }
table, thead, tbody, tr, th, td { overflow: visible !important; }
</style>"""

    full_html = f"""{tooltip_style}
<div id="bt_wrap_{page_id}">
{table_html}
<div style="display:flex;align-items:center;gap:14px;margin-top:14px;margin-bottom:20px;padding:0 2px;flex-wrap:wrap;">
    <span id="bc_{page_id}" style="font-size:13px;color:#666;">
    已选：{pool_count} 只 ETF → 去「我的关注」查看详情</span>
    <button id="bb_{page_id}" type="button"
     style="padding:7px 18px;background:#4CAF50;color:white;border:none;
     border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">
     ✅ 确认关注</button>
</div>
<script>
(function(){{
  var P=new Set({pool_json});
  var I={pool_json};

  // ── JS createElement 注入表头全选 checkbox（绕过 DOMPurify）──
  var headerTh=document.querySelector('#bt_wrap_{page_id} thead th:first-child');
  var sa=document.createElement('span');
  sa.id='sa_{page_id}';
  sa.style.cursor='pointer';
  sa.style.fontSize='16px';
  sa.style.color='#ccc';
  sa.textContent='\u2B1C';
  if(headerTh){{headerTh.innerHTML='';headerTh.appendChild(sa);}}

  function refresh(){{
    var n=P.size;
    var c=document.getElementById('bc_{page_id}');
    if(c)c.textContent='已选：'+n+' 只 ETF → 去「我的关注」查看详情';
    var b=document.getElementById('bb_{page_id}');
    if(b)b.textContent='\u2705 确认关注'+(n>0?'（'+n+'只）':'');
  }}
  function updateSelectAllState(){{
    var saEl=document.getElementById('sa_{page_id}');
    if(!saEl)return;
    var allCodes=document.querySelectorAll('#bt_wrap_{page_id} [data-etf-code]');
    if(!allCodes.length){{saEl.textContent='\u2B1C';saEl.style.color='#ccc';return;}}
    var allIn=true;
    allCodes.forEach(function(el){{if(!P.has(el.getAttribute('data-etf-code')))allIn=false;}});
    if(allIn){{saEl.textContent='☑️';saEl.style.color='#4CAF50';}}
    else{{saEl.textContent='\u2B1C';saEl.style.color='#ccc';}}
  }}
  function toggleAll(){{
    var allCodes=document.querySelectorAll('#bt_wrap_{page_id} [data-etf-code]');
    var allIn=true;
    allCodes.forEach(function(el){{if(!P.has(el.getAttribute('data-etf-code')))allIn=false;}});
    allCodes.forEach(function(el){{
      var c=el.getAttribute('data-etf-code');
      if(allIn){{P.delete(c);el.innerHTML='\u2B1C';el.style.color='#ccc';}}
      else{{P.add(c);el.innerHTML='☑️';el.style.color='#4CAF50';}}
    }});
    updateSelectAllState();
    refresh();
  }}
  function toggle(code){{
    var e=document.querySelector('#bt_wrap_{page_id} [data-etf-code="'+code+'"]');
    if(P.has(code)){{P.delete(code);if(e){{e.innerHTML='⬜';e.style.color='#ccc';}}}}
    else{{P.add(code);if(e){{e.innerHTML='☑️';e.style.color='#4CAF50';}}}}
    refresh();
    updateSelectAllState();
  }}
  function confirm(){{
    var b=document.getElementById('bb_{page_id}');
    b.textContent='\u2705 已提交...';b.disabled=true;b.style.opacity='0.7';b.style.cursor='default';
    var all=Array.from(P);
    if(all.length){{window.location.href='?set_pool='+encodeURIComponent(all.join(','));}}
    else{{b.textContent='\u2705 确认关注';b.disabled=false;b.style.opacity='1';b.style.cursor='pointer';}}
  }}
  document.querySelectorAll('#bt_wrap_{page_id} [data-etf-code]').forEach(function(el){{
    el.addEventListener('click', function(){{ toggle(el.getAttribute('data-etf-code')); }});
  }});
  var btn=document.getElementById('bb_{page_id}');
  if(btn)btn.addEventListener('click', confirm);
  if(sa)sa.addEventListener('click', toggleAll);
  updateSelectAllState();
}})();
</script>
</div>"""

    st.html(full_html, unsafe_allow_javascript=True)


# ════════════════════════════════════════════════════════════
# Query param 处理
# ════════════════════════════════════════════════════════════

def handle_checkbox_clicks(table1=None, table2=None):
    """处理 query param 中的 set_pool / add_pool / remove_pool / add / remove 操作，更新 compare_pool
    set_pool: 全量替换（批量确认按钮使用，确保跨页面不丢失）
    add_pool / remove_pool: 增量操作（逗号分隔多个代码，保留兼容）
    add / remove: 单次操作（保留兼容）
    """
    def _lookup(code):
        """从 table1/table2 查找 name 和 index"""
        name, idx_name = "", ""
        if table1 is not None:
            m = table1[table1["ETF代码"].astype(str) == code]
            if len(m) > 0:
                name = str(m.iloc[0].get("ETF名称", ""))
                idx_name = str(m.iloc[0].get("跟踪指数名称", ""))
        if (not name or not idx_name) and table2 is not None:
            m2 = table2[table2["ETF代码"].astype(str) == code]
            if len(m2) > 0:
                name = name or str(m2.iloc[0].get("ETF名称", ""))
                idx_name = idx_name or str(m2.iloc[0].get("ETF跟踪指数名称", ""))
        return name, idx_name

    qp = st.query_params
    modified = False

    # 全量替换（批量确认按钮使用）
    set_pool_raw = qp.get("set_pool")
    if set_pool_raw:
        codes = [c.strip() for c in set_pool_raw.split(",") if c.strip()]
        pool = []
        for code in codes:
            n, idx = _lookup(code)
            pool.append((code, n, idx))
        st.session_state.compare_pool = pool
        modified = True

    # 增量批量操作（保留兼容）
    add_pool_raw = qp.get("add_pool")
    remove_pool_raw = qp.get("remove_pool")

    if add_pool_raw or remove_pool_raw:
        pool = list(st.session_state.compare_pool)
        existing = {c[0] for c in pool}

        if remove_pool_raw:
            remove_set = set(c.strip() for c in remove_pool_raw.split(",") if c.strip())
            pool = [c for c in pool if c[0] not in remove_set]

        if add_pool_raw:
            add_list = [c.strip() for c in add_pool_raw.split(",") if c.strip()]
            for code in add_list:
                if code not in existing:
                    n, idx = _lookup(code)
                    pool.append((code, n, idx))

        st.session_state.compare_pool = pool
        modified = True

    # 单次操作（保留兼容）
    add_code = qp.get("add")
    remove_code = qp.get("remove")

    if add_code:
        existing = {c[0] for c in st.session_state.compare_pool}
        if add_code not in existing:
            n, idx = _lookup(add_code)
            st.session_state.compare_pool.append((add_code, n, idx))
            modified = True
    if remove_code:
        st.session_state.compare_pool = [c for c in st.session_state.compare_pool if c[0] != remove_code]
        modified = True

    if modified:
        st.query_params.clear()  # 触发 rerun


def build_pagination_controls(page_key, total_rows, page_size=20):
    """返回分页：当前页码 + 翻页按钮 HTML"""
    if f"{page_key}_page" not in st.session_state:
        st.session_state[f"{page_key}_page"] = 0
    page = st.session_state[f"{page_key}_page"]
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = min(page, total_pages - 1)
    st.session_state[f"{page_key}_page"] = page
    start = page * page_size
    end = min(start + page_size, total_rows)
    return page, total_pages, start, end


def render_pagination_buttons(page_key, total_pages, current_page):
    """渲染翻页按钮"""
    if total_pages <= 1:
        return
    c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
    with c2:
        if st.button("◀ 上一页", key=f"{page_key}_prev", disabled=current_page == 0, use_container_width=True):
            st.session_state[f"{page_key}_page"] = current_page - 1
            st.rerun()
    with c3:
        st.markdown(f'<div style="text-align:center;padding:5px;font-size:13px;color:#666;">第 {current_page+1} / {total_pages} 页，共 {total_pages * 20 if total_pages > 0 else 0}+ 条</div>', unsafe_allow_html=True)
    with c4:
        if st.button("下一页 ▶", key=f"{page_key}_next", disabled=current_page >= total_pages - 1, use_container_width=True):
            st.session_state[f"{page_key}_page"] = current_page + 1
            st.rerun()


def get_compare_pool_count():
    """返回对比池中 ETF 数量"""
    return len(st.session_state.get("compare_pool", []))


def build_attention_badge():
    """构建标题栏右侧的 '我关注的ETF' 徽章 HTML"""
    cnt = get_compare_pool_count()
    return f"""<div style="text-align:right;">
        <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.45);">我关注的ETF</p>
        <span style="font-size:28px;font-weight:bold;color:#4FC3F7;">{cnt}</span>
    </div>"""


def build_attention_footer():
    """构建表格下方的关注提示灰色小字"""
    cnt = get_compare_pool_count()
    return f"新增关注：{cnt} 只 ETF → 去「我的关注」查看详情"


def get_rank_percentile(row, table1):
    """返回同类排名百分位字典（用于雷达图）
    从 row 中读取同类排名_规模、同类排名_成交额、同类排名_跟踪误差、同类排名_信息比率、同类排名_收益相关性
    以及同类ETF数量
    计算每个维度的百分位：(1 - rank/total) * 100，跟踪误差反向处理
    返回 {"规模": percentile, "流动性": percentile, ...}
    """
    total = row.get("同类ETF数量", None)
    if pd.isna(total) or total is None or total <= 0:
        return {"规模": 50, "流动性": 50, "跟踪精度": 50, "信息比率": 50, "收益相关性": 50}
    total = int(total)

    def _pct(rank_val, reverse=False):
        if pd.isna(rank_val) or rank_val is None:
            return 50.0
        r = float(rank_val)
        if reverse:
            # 跟踪误差：rank=1最好(误差最小)，百分位 = (1 - (rank-1)/total) * 100
            return (1.0 - (r - 1) / total) * 100
        else:
            # 越大越好：rank=1最好，百分位 = (1 - (rank-1)/total) * 100
            return (1.0 - (r - 1) / total) * 100

    return {
        "规模": _pct(row.get("同类排名_规模", None)),
        "流动性": _pct(row.get("同类排名_成交额", None)),
        "跟踪精度": _pct(row.get("同类排名_跟踪误差", None), reverse=True),
        "信息比率": _pct(row.get("同类排名_信息比率", None)),
        "收益相关性": _pct(row.get("同类排名_收益相关性", None)),
    }


# ════════════════════════════════════════════════════════════
# Tooltip 全局 CSS 与辅助函数
# ════════════════════════════════════════════════════════════

TOOLTIP_CSS = """<style>
.wb-tt-el, .wb-tt-risk {
    position: relative;
    cursor: help;
}
.wb-tt-el::after, .wb-tt-risk::after {
    content: attr(data-wb-tt);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    padding: 3px 8px;
    background: rgba(0,0,0,0.82);
    color: #fff;
    font-size: 11px;
    border-radius: 4px;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    z-index: 99999;
    transition: opacity 0.15s ease 0.2s;
    font-family: 'Microsoft YaHei', sans-serif;
    line-height: 1.4;
    margin-bottom: 4px;
}
.wb-tt-el:hover::after, .wb-tt-risk:hover::after {
    opacity: 1;
}
table, thead, tbody, tr, th, td { overflow: visible !important; }
[data-testid="stMarkdownContainer"] { overflow: visible !important; }
</style>"""

_RISK_TOOLTIPS = {
    "小规模": "最新规模 < 2亿",
    "低流动性": "日均成交额 < 1000万",
    "跟踪偏差": "跟踪误差 > 1.0",
}

_HEADER_TOOLTIPS = {
    # 需求3：行业掘金-跟踪指数列表
    "走势相关度": "跟踪指数与行业概念价格变动的一致程度",
    "持仓相关度": "跟踪指数与行业概念成分股及权重的相似程度",
    "综合匹配度": "综合匹配度 = 走势相关度 × 50% + 持仓相关度 × 50%",
    # 需求6：行业掘金-ETF列表
    "收益相关性": "ETF与跟踪指数价格变动的一致程度",
    "同类排名": "同类排名 = 25%×最新规模排名+25%×日均成交额排名+20%×跟踪误差排名+20%×信息比率排名+10%×收益相关性排名",
    # 需求7：所有页面（通用列）
    "日均成交额(亿)": "ETF近半年的日均成交额",
    "跟踪误差": "ETF相对跟踪指数走势的偏离度（按不同区间长度加权计算），越小越好",
    "信息比率": "衡量超额收益与主动风险的性价比（按不同区间长度加权计算），越高越好",
}


def inject_tooltip_css():
    """注入全局 Tooltip CSS。每页调用一次。
    CSS 通过 st.markdown(unsafe_allow_html=True) 注入主文档。
    """
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)


def build_risk_tag(risk_name):
    """构建带 tooltip 的红底气泡标签。"""
    tooltip = _RISK_TOOLTIPS.get(risk_name, "")
    return (
        f'<span class="wb-tt-risk" data-wb-tt="{tooltip}" '
        f'style="background:#E74C3C;color:white;font-weight:700;padding:1px 7px;'
        f'border-radius:10px;font-size:10px;display:inline-block;margin:1px 0;'
        f'position:relative;cursor:help;">{risk_name}</span>'
    )


def build_th_with_tooltip(header, tooltip="", bg_color="#1a1a2e"):
    """构建带 tooltip 的表头 <th> 标签。
    若 tooltip 为空，则返回普通 th。
    """
    base_style = (
        f"background:{bg_color};color:white;padding:6px 8px;"
        f"text-align:center;white-space:nowrap;font-size:11px;"
    )
    if tooltip:
        return (
            f'<th class="wb-tt-el" data-wb-tt="{tooltip}" '
            f'style="{base_style}position:relative;cursor:help;">{header}</th>'
        )
    return f'<th style="{base_style}">{header}</th>'


def get_header_tooltip(header):
    """返回表头对应的 tooltip 文本，若无则返回空字符串。"""
    return _HEADER_TOOLTIPS.get(header, "")
