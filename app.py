跳转到内容
likexin1027
我的定居点应用
存储库导航
代码
议题
拉取请求
行动
项目
维基
安全性
见解
背景设定
commit ddaab00
likexin1027
likexin1027
作者
38 minutes ago
已验证
通过上传添加文件
主要角色
1 parent 
677d07f
 commit 
ddaab00
文件树
过滤文件......
app.py
1个文件更改
+
74
-
0
线路变更
代码内搜索
 
‎app.py‎
+74
台词变动：新增74条，删除0条
原始文件行编号	差分线号	差速器线路更换
@@ -60,6 +60,39 @@ def create_default_mapping():
    df.loc[(df["平台"] == "视频号") & (df["阈值标签"] == "≥100w"), "奖励金额"] = 300
    return df

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
@@ -124,6 +157,47 @@ def render():
    st.caption("上传数据，配置基础奖励，自动计算限时与优秀奖励，按作者限额输出结算结果")
    uploaded = st.file_uploader("上传Excel或CSV文件", type=["xlsx", "xls", "csv"])
    mapping = create_default_mapping()
    cfg = st.file_uploader("可选：上传奖励配置（Excel/CSV）", type=["xlsx", "xls", "csv"], key="cfg")
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
    st.subheader("基础奖励配置")
    mapping = st.data_editor(mapping, num_rows="dynamic", use_container_width=True)
    lookup = build_reward_lookup(mapping)
0条提交评论
评论
0
 (0)
评论
你不会收到本帖的通知。

