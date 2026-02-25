import io
import pandas as pd
import streamlit as st
import requests

# ==========================================
# 1. 核心工具函数（保留原逻辑）
# ==========================================

def normalize_platform(s):
    if pd.isna(s): return ""
    x = str(s).strip().lower()
    if any(k in x for k in ["b站", "bilibili", "哔哩"]): return "B站"
    if any(k in x for k in ["小红书", "red"]): return "小红书"
    if "视频号" in x: return "视频号"
    if any(k in x for k in ["抖音", "douyin"]): return "抖音"
    return s

def parse_number(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(",", "")
    if s.endswith("+"): s = s[:-1]
    m = 1.0
    if "亿" in s:
        s = s.replace("亿", ""); m = 100000000.0
    elif "w" in s.lower():
        s = s.lower().replace("w", ""); m = 10000.0
    elif "万" in s:
        s = s.replace("万", ""); m = 10000.0
    try:
        return float(s) * m
    except:
        return 0.0

def normalize_label_to_value(lab):
    if pd.isna(lab): return None
    s = str(lab).strip().lower().replace("≥", "").replace("+", "").replace("万", "w")
    if "w" in s:
        try: return int(float(s.replace("w", "")) * 10000)
        except: return None
    try: return int(float(s))
    except: return None

def value_to_label(v):
    thresholds = [(1000000, "100w"), (500000, "50w"), (200000, "20w"), (100000, "10w"), (50000, "5w"), (30000, "3w"), (10000, "1w")]
    for t, l in thresholds:
        if v >= t: return f"≥{l}"
    return f"≥{int(v)}"

# ==========================================
# 2. 奖励结算核心逻辑（保留原功能）
# ==========================================

def build_reward_lookup(df):
    d = {}
    for plat in df["平台"].unique():
        sub = df[df["平台"] == plat].sort_values("阈值数值", ascending=False)
        d[plat] = [(row["阈值数值"], float(row["奖励金额"])) for _, row in sub.iterrows()]
    return d

def base_reward(plat, views, lookup):
    if plat not in lookup: return 0.0
    for th, amt in lookup[plat]:
        if views >= th: return amt
    return 0.0

def limited_time_bonus(views, typ):
    if views > 10000 and isinstance(typ, str):
        s = typ.lower()
        if "热点推荐" in s or "新春主题" in s: return 50.0
    return 0.0

def excellence_bonus(plat, typ, likes, views):
    b = 0.0
    if not isinstance(typ, str): return b
    if plat == "B站":
        if "热搜" in typ: b += 100.0
        if "热门" in typ: b += 200.0
    if "短视频" in typ:
        if likes >= 100000: b += 300.0
        if views >= 2000000: b += 1000.0
    return b

def pick_top5_per_author(df):
    df = df.copy()
    df["是否计入结算"] = False
    pos_mask = df["总奖励"] > 0
    for author, group in df[pos_mask].groupby("账号名称"):
        idx = group.sort_values("总奖励", ascending=False).head(5).index
        df.loc[idx, "是否计入结算"] = True
    return df

def filter_banned(df, text_cols):
    banned = ["BUG", "建议", "拉踩"]
    mask = pd.Series([False] * len(df), index=df.index)
    for col in text_cols:
        if col in df.columns:
            s = df[col].astype(str)
            for w in banned:
                mask |= s.str.contains(w, case=False, na=False)
    out = df.copy()
    out["排除原因"] = ""
    out.loc[mask, "排除原因"] = "包含敏感词"
    return out[~mask], out[mask]

# ==========================================
# 3. AI 审计功能
# ==========================================

def chat_with_ai(user_prompt, context_data):
    try:
        if "DEEPSEEK_API_KEY" not in st.secrets:
            return "未配置 API Key。"
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        
        system_prompt = (
            "你是101俱乐部首席财务审计官。请基于提供的结算报表数据进行分析。\n"
            "要求：1.计算每万次播放收益(金额/播放量)；2.指出数据倒挂（高播放低奖金）异常；3.严禁解释名词，直接引用具体数字。"
        )
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"报表数据：\n{context_data}\n\n问题：{user_prompt}"}
            ],
            "temperature": 0.3
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"AI 响应失败: {str(e)}"

# ==========================================
# 4. 主界面渲染
# ==========================================

def render():
    st.set_page_config(page_title="101俱乐部结算工具", layout="wide")
    st.title("💰 101俱乐部财务结算中心")

    tabs = st.tabs(["📊 结算中心", "⚙️ 规则设置"])

    # --- 规则设置标签页 ---
    with tabs[1]:
        st.subheader("基础奖励阈值配置")
        # 默认配置逻辑
        thresholds = [1000000, 500000, 200000, 100000, 50000, 30000, 10000]
        rows = [{"平台": p, "阈值标签": value_to_label(t), "阈值数值": t, "奖励金额": 0.0} 
                for t in thresholds for p in ["B站", "小红书", "抖音", "视频号"]]
        default_map = pd.DataFrame(rows)
        mapping = st.data_editor(default_map, num_rows="dynamic", key="map_editor")
        lookup = build_reward_lookup(mapping)

    # --- 结算中心标签页 ---
    with tabs[0]:
        uploaded = st.file_uploader("上传 Excel 文件 (需包含：渠道, 播放量, 点赞, 作品类型, 账号名称)", type=["xlsx", "csv"])
        
        if uploaded:
            # 1. 读取数据
            try:
                if uploaded.name.endswith('.csv'):
                    df = pd.read_csv(uploaded, encoding='utf-8')
                else:
                    df = pd.read_excel(uploaded)
            except:
                uploaded.seek(0)
                df = pd.read_csv(uploaded, encoding='gbk')

            # 2. 字段检查与清洗
            required = ["渠道", "播放量", "点赞", "作品类型", "账号名称"]
            if not all(c in df.columns for c in required):
                st.error(f"Excel 缺少必要列，请检查是否包含: {required}")
                return

            df["渠道"] = df["渠道"].apply(normalize_platform)
            df["播放量数值"] = df["播放量"].apply(parse_number)
            df["点赞数值"] = df["点赞"].apply(parse_number)

            # 3. 敏感词过滤
            text_cols = [c for c in ["作品类型", "内容", "标题", "作品标题"] if c in df.columns]
            kept, removed = filter_banned(df, text_cols)

            # 4. 奖金计算
            kept["基础奖励"] = kept.apply(lambda x: base_reward(x["渠道"], x["播放量数值"], lookup), axis=1)
            kept["限时奖励"] = kept.apply(lambda x: limited_time_bonus(x["播放量数值"], x["作品类型"]), axis=1)
            kept["优秀奖励"] = kept.apply(lambda x: excellence_bonus(x["渠道"], x["作品类型"], x["点赞数值"], x["播放量数值"]), axis=1)
            kept["总奖励"] = kept[["基础奖励", "限时奖励", "优秀奖励"]].sum(axis=1)
            
            # 5. Top5 限制
            result = pick_top5_per_author(kept)
            
            # 6. 数据统计
            summary = result[result["是否计入结算"]].groupby("账号名称", as_index=False).agg({
                "总奖励": "sum", "播放量数值": "sum"
            }).rename(columns={"总奖励": "结算金额", "播放量数值": "总播放量"})
            
            st.session_state["summary_data"] = summary

            # 7. UI 展示看板
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("总结算金额", f"¥{summary['结算金额'].sum():,.2f}")
            m2.metric("总覆盖播放", f"{int(summary['总播放量'].sum()):,}")
            m3.metric("有效作者数", len(summary))
            m4.metric("被排除条目", len(removed))

            st.subheader("结算明细")
            st.dataframe(result, use_container_width=True)

            if not removed.empty:
                with st.expander("查看被排除的敏感词内容"):
                    st.dataframe(removed)

            # 8. 下载按钮
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                result.to_excel(writer, index=False, sheet_name="结算明细")
                summary.to_excel(writer, index=False, sheet_name="汇总")
            st.download_button("📥 下载结算结果", buffer.getvalue(), "101结算结果.xlsx")

            # 9. AI 助手界面
            st.divider()
            st.subheader("🤖 101 结算智能审计助手")
            
            if "messages" not in st.session_state:
                st.session_state.messages = []

            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_input := st.chat_input("问我关于结算数据的分析..."):
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.chat_message("user"): st.markdown(user_input)

                with st.chat_message("assistant"):
                    context = summary.to_string(index=False)
                    ans = chat_with_ai(user_input, context)
                    st.markdown(ans)
                    st.session_state.messages.append({"role": "assistant", "content": ans})

if __name__ == "__main__":
    render()
