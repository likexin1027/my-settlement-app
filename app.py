import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="101俱乐部结算工具", layout="wide")

def normalize_platform(s):
    if pd.isna(s):
        return ""
    x = str(s).strip().lower()
    if "b站" in x or "bilibili" in x or "哔哩" in x:
        return "B站"
    if "小红书" in x or "red" in x:
        return "小红书"
    if "视频号" in x:
        return "视频号"
    if "抖音" in x or "douyin" in x:
        return "抖音"
    return s

def parse_number(v):
    if pd.isna(v):
        return 0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s.endswith("+"):
        s = s[:-1]
    m = 1.0
    if "亿" in s:
        s = s.replace("亿", "")
        m = 100000000.0
    elif "w" in s.lower():
        s = s.lower().replace("w", "")
        m = 10000.0
    elif "万" in s:
        s = s.replace("万", "")
        m = 10000.0
    try:
        return float(s) * m
    except:
        try:
            return float(s)
        except:
            return 0.0

def create_default_mapping():
    thresholds = [1000000, 500000, 200000, 100000, 50000, 30000, 10000]
    labels = ["≥100w", "≥50w", "≥20w", "≥10w", "≥5w", "≥3w", "≥1w"]
    rows = []
    for t, lab in zip(thresholds, labels):
        rows.append({"平台": "B站", "阈值标签": lab, "阈值数值": t, "奖励金额": 0})
        rows.append({"平台": "小红书", "阈值标签": lab, "阈值数值": t, "奖励金额": 0})
        rows.append({"平台": "抖音", "阈值标签": lab, "阈值数值": t, "奖励金额": 0})
        rows.append({"平台": "视频号", "阈值标签": lab, "阈值数值": t, "奖励金额": 0})
    df = pd.DataFrame(rows)
    df.loc[(df["平台"] == "B站") & (df["阈值标签"] == "≥100w"), "奖励金额"] = 1800
    df.loc[(df["平台"] == "小红书") & (df["阈值标签"] == "≥100w"), "奖励金额"] = 900
    df.loc[(df["平台"] == "抖音") & (df["阈值标签"] == "≥100w"), "奖励金额"] = 300
    df.loc[(df["平台"] == "视频号") & (df["阈值标签"] == "≥100w"), "奖励金额"] = 300
    return df

def build_reward_lookup(df):
    d = {}
    for plat in df["平台"].unique():
        sub = df[df["平台"] == plat].sort_values("阈值数值", ascending=False)
        d[plat] = [(row["阈值数值"], float(row["奖励金额"])) for _, row in sub.iterrows()]
    return d

def base_reward(plat, views, lookup):
    if plat not in lookup:
        return 0.0
    for th, amt in lookup[plat]:
        if views >= th:
            return amt
    return 0.0

def limited_time_bonus(views, typ):
    if views > 10000 and isinstance(typ, str):
        s = typ.lower()
        if ("热点推荐" in s) or ("新春主题" in s):
            return 50.0
    return 0.0

def excellence_bonus(plat, typ, likes, views):
    b = 0.0
    if isinstance(typ, str):
        s = typ
        if plat == "B站":
            if "热搜" in s:
                b += 100.0
            if "热门" in s:
                b += 200.0
        if "短视频" in s and likes >= 100000:
            b += 300.0
        if "短视频" in s and views >= 2000000:
            b += 1000.0
    return b

def pick_top5_per_author(df):
    df = df.copy()
    df["是否计入结算"] = False
    pos = df["总奖励"] > 0
    for author, group in df[pos].groupby("账号名称"):
        idx = group.sort_values("总奖励", ascending=False).head(5).index
        df.loc[idx, "是否计入结算"] = True
    return df

def filter_banned(df, text_cols):
    banned = ["BUG", "建议", "拉踩"]
    mask = pd.Series([False] * len(df))
    for col in text_cols:
        if col in df.columns:
            s = df[col].astype(str)
            for w in banned:
                mask = mask | s.str.contains(w, case=False, na=False)
    out = df.copy()
    out["排除原因"] = ""
    out.loc[mask, "排除原因"] = "包含敏感词"
    return out[~mask], out[mask]

def render():
    st.title("101俱乐部活动奖金结算")
    st.caption("上传数据，配置基础奖励，自动计算限时与优秀奖励，按作者限额输出结算结果")
    uploaded = st.file_uploader("上传Excel或CSV文件", type=["xlsx", "xls", "csv"])
    mapping = create_default_mapping()
    st.subheader("基础奖励配置")
    mapping = st.data_editor(mapping, num_rows="dynamic", use_container_width=True)
    lookup = build_reward_lookup(mapping)
    if uploaded is None:
        return
    name = getattr(uploaded, "name", "").lower()
    if name.endswith(".csv"):
        try:
            df = pd.read_csv(uploaded)
        except:
            try:
                uploaded.seek(0)
                df = pd.read_csv(uploaded, encoding="gbk")
            except:
                st.error("CSV读取失败，请确认编码与文件格式")
                return
    else:
        try:
            data = uploaded.read()
            bio = io.BytesIO(data)
            if name.endswith(".xlsx"):
                try:
                    df = pd.read_excel(bio, engine="calamine")
                except:
                    bio.seek(0)
                    df = pd.read_excel(bio, engine="openpyxl")
            elif name.endswith(".xls"):
                df = pd.read_excel(bio, engine="xlrd")
            else:
                bio.seek(0)
                df = pd.read_excel(bio)
        except:
            st.error("Excel读取失败，请确认文件格式")
            return
    required = ["渠道", "播放量", "点赞", "作品类型", "账号名称"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        st.error("缺少字段: " + ", ".join(miss))
        return
    df["渠道"] = df["渠道"].apply(normalize_platform)
    df["播放量数值"] = df["播放量"].apply(parse_number)
    df["点赞数值"] = df["点赞"].apply(parse_number)
    text_cols = []
    for c in ["作品类型", "内容", "标题", "作品标题"]:
        if c in df.columns:
            text_cols.append(c)
    kept, removed = filter_banned(df, text_cols if text_cols else ["作品类型"])
    kept["基础奖励"] = kept.apply(lambda x: base_reward(x["渠道"], x["播放量数值"], lookup), axis=1)
    kept["限时奖励"] = kept.apply(lambda x: limited_time_bonus(x["播放量数值"], x["作品类型"]), axis=1)
    kept["优秀奖励"] = kept.apply(lambda x: excellence_bonus(x["渠道"], x["作品类型"], x["点赞数值"], x["播放量数值"]), axis=1)
    kept["总奖励"] = kept[["基础奖励", "限时奖励", "优秀奖励"]].sum(axis=1)
    kept = pick_top5_per_author(kept)
    result = kept.copy()
    result = result[["渠道", "账号名称", "播放量", "点赞", "作品类型", "基础奖励", "限时奖励", "优秀奖励", "总奖励", "是否计入结算"]]
    st.subheader("结算预览")
    st.dataframe(result, use_container_width=True)
    st.subheader("被排除内容")
    if not removed.empty:
        st.dataframe(removed, use_container_width=True)
    summary = result[result["是否计入结算"]].groupby("账号名称", as_index=False)["总奖励"].sum().rename(columns={"总奖励": "结算金额"})
    st.subheader("作者汇总")
    st.dataframe(summary, use_container_width=True)
    total_payout = summary["结算金额"].sum() if not summary.empty else 0.0
    st.metric("总结算金额", f"{total_payout:,.2f} 元")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        result.to_excel(writer, index=False, sheet_name="结算明细")
        summary.to_excel(writer, index=False, sheet_name="作者汇总")
        mapping.to_excel(writer, index=False, sheet_name="奖励配置")
    st.download_button("下载处理后的Excel", data=buffer.getvalue(), file_name="101俱乐部结算结果.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

render()
