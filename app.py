import streamlit as st
import pandas as pd
from pathlib import Path

JOBS_FILE = "jobs.xlsx"
SAMPLE_FILE = "sample_jobs.xlsx"

# === 改动 1：自动判断 demo 模式 ===
# 本地有 jobs.xlsx 时正常使用真实数据；云端只放 sample_jobs.xlsx 时自动切换 demo 模式
DEMO_MODE = not Path(JOBS_FILE).exists() and Path(SAMPLE_FILE).exists()
EXCEL_FILE = SAMPLE_FILE if DEMO_MODE else JOBS_FILE

STATUS_OPTIONS = ["未投递", "已投递", "已读", "约面", "已拒"]

st.set_page_config(page_title="求职追踪看板", layout="wide")
st.title("求职追踪看板")

# === 改动 2：demo 模式说明横幅 ===
if DEMO_MODE:
    st.info(
        "📊 当前展示的是脱敏抽样数据（88 条，原始数据 923 条），"
        "用于演示看板功能。完整项目说明见 "
        "[wannantian.com/projects/job-hunter](https://wannantian.com/projects/job-hunter)。"
    )


def load_data() -> pd.DataFrame:
    if not Path(EXCEL_FILE).exists():
        return pd.DataFrame()
    df = pd.read_excel(EXCEL_FILE)
    if "投递状态" not in df.columns:
        df["投递状态"] = "未投递"
    df["投递状态"] = df["投递状态"].fillna("未投递")
    return df


def save_status(orig_idx: int, new_status: str) -> None:
    # 每次写入前重新读文件，避免覆盖其他字段的改动
    df = pd.read_excel(EXCEL_FILE)
    if "投递状态" not in df.columns:
        df["投递状态"] = "未投递"
    df.at[orig_idx, "投递状态"] = new_status
    df.to_excel(EXCEL_FILE, index=False)


# ── 数据加载（需要刷新时重新读文件）────────────────────────────────────────────
if st.session_state.get("needs_reload", True):
    st.session_state.df = load_data()
    st.session_state.needs_reload = False

df: pd.DataFrame = st.session_state.df

if df.empty:
    st.warning("jobs.xlsx 不存在或为空，请先运行 scraper.py 和 analyzer.py")
    st.stop()

# 匹配度转数值（"分析失败"等非数字值变为 NaN）
df["_score"] = pd.to_numeric(df.get("匹配度"), errors="coerce")

# ── 保存后的提示（一次性消息）──────────────────────────────────────────────────
msg = st.session_state.get("flash_msg", "")
if msg:
    st.success(msg)
    st.session_state.flash_msg = ""

# ── 汇总指标 ──────────────────────────────────────────────────────────────────
avg_score = df["_score"].mean()
c1, c2, c3, c4 = st.columns(4)
c1.metric("总职位数", len(df))
c2.metric("已投递", int(df["投递状态"].isin({"已投递", "已读", "约面"}).sum()))
c3.metric("约面数", int((df["投递状态"] == "约面").sum()))
c4.metric("平均匹配度", f"{avg_score:.1f}" if pd.notna(avg_score) else "—")

st.divider()

# ── 筛选栏 ────────────────────────────────────────────────────────────────────
f1, f2, f3 = st.columns([2, 3, 2])

with f1:
    all_cities = sorted(df["城市"].dropna().unique()) if "城市" in df.columns else []
    sel_cities = st.multiselect("城市", all_cities, placeholder="全部城市")

with f2:
    vals = df["_score"].dropna()
    s_min = int(vals.min()) if not vals.empty else 0
    s_max = int(vals.max()) if not vals.empty else 100
    if s_min == s_max:
        s_min, s_max = 0, 100
    score_range = st.slider("匹配度区间", 0, 100, (s_min, s_max))

with f3:
    sel_statuses = st.multiselect("投递状态", STATUS_OPTIONS, placeholder="全部状态")

# ── 过滤逻辑 ──────────────────────────────────────────────────────────────────
mask = pd.Series(True, index=df.index)
if sel_cities:
    mask &= df["城市"].isin(sel_cities)
# 没有匹配度分数的行（未分析）不被分数筛选器排除
mask &= df["_score"].isna() | (
    (df["_score"] >= score_range[0]) & (df["_score"] <= score_range[1])
)
if sel_statuses:
    mask &= df["投递状态"].isin(sel_statuses)

filtered = df[mask]
orig_indices = filtered.index.tolist()

# ── 职位列表表格 ──────────────────────────────────────────────────────────────
TABLE_COLS = ["岗位名", "公司名", "城市", "匹配度", "推荐语", "投递状态"]
show_cols = [c for c in TABLE_COLS if c in filtered.columns]

st.caption(f"共 {len(filtered)} 条（筛选后）")
display_df = filtered[show_cols].reset_index(drop=True).copy()
if "匹配度" in display_df.columns:
    display_df["匹配度"] = display_df["匹配度"].astype(str)
event = st.dataframe(
    display_df,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    hide_index=True,
)

# ── 详情面板（点击行后展开）──────────────────────────────────────────────────
sel = event.selection.rows
if not sel:
    st.stop()

orig_idx = orig_indices[sel[0]]
row = df.loc[orig_idx]

st.divider()
st.subheader(f"{row.get('岗位名', '')}  ·  {row.get('公司名', '')}")

link = str(row.get("链接", ""))
if link.startswith("http"):
    st.markdown(f"[查看原职位]({link})")

# 优势 / 差距
da, db = st.columns(2)
with da:
    st.markdown("**优势**")
    st.info(str(row.get("优势", "未获取")))
with db:
    st.markdown("**差距**")
    st.warning(str(row.get("差距", "未获取")))

with st.expander("工作内容"):
    st.write(str(row.get("工作内容", "未获取")))

with st.expander("岗位要求"):
    st.write(str(row.get("岗位要求", "未获取")))

# 投递状态更新
st.markdown("---")
current = str(row.get("投递状态", "未投递"))
if current not in STATUS_OPTIONS:
    current = "未投递"

with st.form(key=f"form_{orig_idx}"):
    new_status = st.selectbox(
        "更新投递状态",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(current),
    )
    if st.form_submit_button("保存"):
        # === 改动 3：demo 模式下不写文件 ===
        if DEMO_MODE:
            st.session_state.flash_msg = "演示模式下投递状态不会持久保存（云端文件系统为临时存储）"
        else:
            save_status(orig_idx, new_status)
            st.session_state.flash_msg = f"已将「{row.get('岗位名', '')}」更新为「{new_status}」"
        st.session_state.needs_reload = True
        st.rerun()