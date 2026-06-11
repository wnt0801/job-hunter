import pandas as pd

df = pd.read_excel("jobs.xlsx")

import re

def clean_pua(text):
    if not isinstance(text, str):
        return text
    text = re.sub(r"[\uE000-\uF8FF]", "", text)
    # 清理图标删除后留下的空括号
    text = re.sub(r"[（(]\s*[）)]", "", text)
    # 清理开头/结尾孤立的符号（&、-、_、空格组合）
    text = re.sub(r"^[\s&\-_]+", "", text)
    text = re.sub(r"[\s&\-_]+$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

text_cols = df.select_dtypes(include="object").columns
for col in text_cols:
    df[col] = df[col].apply(clean_pua)

# 1. 过滤掉提到敏感项目/敏感表述的行
exclude_keywords = ["银行", "A股", "行业轮动", "非顶尖", "二本", "认购预测"]
mask = pd.Series(False, index=df.index)
for col in ["优势", "差距", "推荐语"]:
    for kw in exclude_keywords:
        mask |= df[col].astype(str).str.contains(kw, na=False)

clean_df = df[~mask].copy()
print(f"过滤前: {len(df)} 条，过滤后: {len(clean_df)} 条")

# 2. 删除链接列
clean_df = clean_df.drop(columns=["链接"])

# 3. 按匹配度分桶，尽量均匀抽样（覆盖高/中/低分）
clean_df["匹配度"] = pd.to_numeric(clean_df["匹配度"], errors="coerce")
bins = [0, 40, 60, 80, 100]
labels = ["低", "中低", "中高", "高"]
clean_df["分档"] = pd.cut(clean_df["匹配度"], bins=bins, labels=labels)

target_total = 90
sample_parts = []
for label, group in clean_df.groupby("分档", observed=True):
    n = min(len(group), max(1, target_total // 4))
    sample_parts.append(group.sample(n, random_state=42))

sample_df = pd.concat(sample_parts).drop(columns=["分档"])
sample_df = sample_df.sample(frac=1, random_state=1).reset_index(drop=True)  # 打乱顺序

print(f"抽样结果: {len(sample_df)} 条")
print(sample_df["分档"].value_counts() if "分档" in sample_df.columns else sample_df["匹配度"].describe())

sample_df.to_excel("sample_jobs.xlsx", index=False)
print("已保存 sample_jobs.xlsx")