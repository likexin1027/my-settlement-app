import io
import pandas as pd
import streamlit as st
import requests  

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
        for plat in ["B站", "小红书", "抖音", "视频号"]:
            rows.append({"平台": plat, "阈值标签": lab, "阈值数值": t, "奖励金额": 0.0})
    df = pd.DataFrame(rows)
    return df

def load_default_mapping():
    try:
        try:
            mdf = pd.read_csv("奖励金额t.csv")
        except:
            mdf = pd.read_csv("奖励金额t.csv", encoding="gbk")
        cols = set(mdf.columns)
        need_plat = "平台" in cols
        has_val = "阈值数值" in cols
        has_lab = "阈值标签" in cols
        has_amt = "奖励金额" in cols
        if need_plat and has_amt and (has_val or has_lab):
            out = mdf.copy()
            if not has_val and has_lab:
                out["阈值数值"] = out["阈值标签"].apply(normalize_label_to_value)
            if not has_lab and has_val:
                out["阈值标签"] = out["阈值数值"].apply(value_to_label)
            out = out[out["平台"].isin(["B站", "小红书", "抖音", "视频号"])]
            out = out[["平台", "阈值标签", "阈值数值", "奖励金额"]].dropna(subset=["阈值数值", "奖励金额"])
            return out
        return create_default_mapping()
    except:
        return create_default_mapping()

def normalize_label_to_value(lab):
    if pd.isna(lab):
        return None
    s = str(lab).strip().lower().replace("≥", "").replace("+", "")
    s = s.replace("万", "w")
    if "w" in s:
        try:
            n = float(s.replace("w", ""))
            return int(n * 10000)
        except:
            return None
    try:
        return int(float(s))
    except:
        return None

def value_to_label(v):
    if v >= 1000000:
        return "≥100w"
    if v >= 500000:
        return "≥50w"
    if v >= 200000:
        return "≥20w"
    if v >= 100000:
        return "≥10w"
    if v >= 50000:
        return "≥5w"
    if v >= 30000:
        return "≥3w"
    if v >= 10000:
        return "≥1w"
    return f"≥{int(v)}"

def build_reward_lookup(df):
    d = {}
    for plat in df["平台"].unique():
        sub = df[df["平台"] == plat].sort_values("阈值数值", ascending=False)
        d[plat] = [(row["阈值数值"], float(row["奖励金额"])) for _, row in sub.iterrows()]
    return d

def describe_excel_error(err, filename):
    s = str(err).lower()
    reasons = []
    if "encrypted" in s or "password" in s:
        reasons.append("文件加密或受保护")
    if "not a zip file" in s or "unsupported file format" in s or "badzipfile" in s:
        reasons.append("文件损坏或并非标准xlsx/xls")
    if "calamine" in s and ("not installed" in s or "module" in s):
        reasons.append("缺少读取引擎，请安装python-calamine")
    if "openpyxl" in s and ("styles" in s or "fills" in s):
        reasons.append("复杂样式导致解析失败，建议重导出或简化样式")
    if filename.endswith(".xls") and ("xlrd" in s or "format" in s):
        reasons.append(".xls兼容性问题，建议另存为.xlsx后再上传")
    if "filetype" in s or "content-type" in s:
        reasons.append("扩展名与实际内容不匹配")
    msg = "Excel读取失败"
    if reasons:
        msg += "：" + "；".join(reasons)
    msg += f"。原始信息：{str(err)}"
    return msg

def read_xlsx_robust(bio):
    try:
        return pd.read_excel(bio, engine="calamine")
    except:
        bio.seek(0)
        try:
            return pd.read_excel(bio, engine="openpyxl")
        except:
            bio.seek(0)
            try:
                from openpyxl import load_workbook
                wb = load_workbook(bio, data_only=True, read_only=True)
                ws = wb.active
                data = []
                for row in ws.iter_rows(values_only=True):
                    data.append(list(row))
                if not data:
                    return pd.DataFrame()
                header = [str(x) if x is not None else "" for x in data[0]]
                rows = data[1:]
                return pd.DataFrame(rows, columns=header)
            except Exception as e:
                raise e

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
    tabs = st.tabs(["结算中心", "规则设置"])
    with tabs[1]:
        mapping = load_default_mapping()
        cfg = st.file_uploader("上传奖励配置（Excel/CSV）", type=["xlsx", "xls", "csv"], key="cfg")
        if cfg is not None:
            n = getattr(cfg, "name", "").lower()
            try:
                if n.endswith(".csv"):
                    try:
                        mdf = pd.read_csv(cfg)
                    except:
                        cfg.seek(0)
                        mdf = pd.read_csv(cfg, encoding="gbk")
                else:
                    data = cfg.read()
                    bio = io.BytesIO(data)
                    if n.endswith(".xlsx"):
                        try:
                            mdf = pd.read_excel(bio, engine="calamine")
                        except:
                            bio.seek(0)
                            mdf = pd.read_excel(bio, engine="openpyxl")
                    elif n.endswith(".xls"):
                        mdf = pd.read_excel(bio, engine="xlrd")
                    else:
                        bio.seek(0)
                        mdf = pd.read_excel(bio)
            except:
                mdf = None
            if mdf is not None:
                cols = set(mdf.columns)
                need_plat = "平台" in cols
                has_val = "阈值数值" in cols
                has_lab = "阈值标签" in cols
                has_amt = "奖励金额" in cols
                if need_plat and has_amt and (has_val or has_lab):
                    out = mdf.copy()
                    if not has_val and has_lab:
                        out["阈值数值"] = out["阈值标签"].apply(normalize_label_to_value)
                    if not has_lab and has_val:
                        out["阈值标签"] = out["阈值数值"].apply(value_to_label)
                    out = out[out["平台"].isin(["B站", "小红书", "抖音", "视频号"])]
                    out = out[["平台", "阈值标签", "阈值数值", "奖励金额"]].dropna(subset=["阈值数值", "奖励金额"])
                    mapping = out
        mapping = st.data_editor(mapping, num_rows="dynamic", width="stretch")
    with tabs[0]:
        uploaded = st.file_uploader("上传Excel或CSV文件", type=["xlsx", "xls", "csv"])
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
                df = read_xlsx_robust(bio)
            elif name.endswith(".xls"):
                df = pd.read_excel(bio, engine="xlrd")
            else:
                bio.seek(0)
                df = pd.read_excel(bio)
        except Exception as e:
            st.error(describe_excel_error(e, name))
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
    with tabs[0]:
        summary = result[result["是否计入结算"]].groupby("账号名称", as_index=False).agg({ "总奖励": "sum","播放量数值": "sum"}).rename(columns={"总奖励": "结算金额", "播放量数值": "总播放量"})

# 存入缓存，给 AI 看
        st.session_state["summary_data"] = summary
        total_payout = summary["结算金额"].sum() if not summary.empty else 0.0
        total_views = result[result["是否计入结算"]]["播放量数值"].sum() if "播放量数值" in result.columns else 0.0
        counted = int(result["是否计入结算"].sum())
        authors = summary.shape[0]
        cols = st.columns(4)
        cols[0].metric("总结算金额", f"{total_payout:,.2f} 元")
        cols[1].metric("总播放量", f"{int(total_views):,}")
        cols[2].metric("计入条目数", f"{counted}")
        cols[3].metric("作者数", f"{authors}")
        st.subheader("结算预览")
        st.dataframe(result, width="stretch")
        st.subheader("奖金Top5作者")
        top5 = summary.sort_values("结算金额", ascending=False).head(5)
        st.bar_chart(top5.set_index("账号名称"))
        st.subheader("被排除内容")
        if not removed.empty:
            st.dataframe(removed, width="stretch")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        result.to_excel(writer, index=False, sheet_name="结算明细")
        summary.to_excel(writer, index=False, sheet_name="作者汇总")
        mapping.to_excel(writer, index=False, sheet_name="奖励配置")
    st.download_button("下载处理后的Excel", data=buffer.getvalue(), file_name="101俱乐部结算结果.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.divider()
    st.subheader(" 101 结算智能助手")

    # 检查是否有计算好的数据
    if "summary_data" in st.session_state and st.session_state["summary_data"] is not None:
        summary_for_ai = st.session_state["summary_data"]
        context_text = summary_for_ai.to_string(index=False)
        
        # 初始化消息记录
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # 展示历史对话
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # 接收用户输入 (对话框在这里！)
        if prompt := st.chat_input("问我：谁的奖金最高？"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("AI 正在思考..."):
                    # 调用上面定义好的函数
                    response = chat_with_ai(prompt, context_text)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        st.info("💡 请先上传 Excel 文件并完成结算，AI 助手将自动开启。")
# --- 核心 AI 函数：确保左侧没有任何空格，顶格写 ---
def chat_with_ai(user_prompt, context_data):
    try:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # 1. 先定义人设指令变量
        system_prompt = (
            "你是101俱乐部专属的【首席财务审计官】。你的目标是基于提供的结算报表，给出极具专业性的财务洞察。\n\n"
            "## 核心技能：\n"
            "1. **计算ROI与效能**：通过（金额 / 播放量）计算每万次播放的成本，识别谁是‘高性价比创作者’。\n"
            "2. **异常数据识别**：指出播放量极高但奖金极低，或金额与播放量比例严重失衡的案例。\n"
            "3. **趋势总结**：快速概括哪些平台的表现更符合当前的奖励政策。\n\n"
            "## 沟通原则：\n"
            "- **数据驱动**：严禁解释名词，必须直接引用报表中的具体数字。\n"
            "- **简洁专业**：多用结论性短语，如‘数据倒挂’、‘转化效率最高’。"
        )

        # 2. 构造请求载体 (注意这里的 payload 只定义一次，且括号完全匹配)
        payload = {
            "model": "deepseek-chat", 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【当前结算报表数据】：\n{context_data}\n\n【用户提问】：{user_prompt}"}
            ],
            "temperature": 0.3
        }

        # 3. 发送请求并解析结果
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        
        if response.status_code != 200:
            return f"AI 暂时掉线了 (API错误): {res_json.get('error', {}).get('message', '未知错误')}"
            
        return res_json['choices'][0]['message']['content']

    except Exception as e:
        return f"AI 暂时掉线了 (系统错误): {str(e)}"
    render()
