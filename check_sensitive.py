import pandas as pd

df = pd.read_excel("jobs.xlsx")
print("列名:", df.columns.tolist())
print("行数:", len(df))
print("-" * 40)

keywords = ["九江", "学院", "万南天", "wnt0801", "181"]
text_cols = [c for c in df.columns if df[c].dtype == object]

for kw in keywords:
    parts = []
    for c in text_cols:
        n = int(df[c].astype(str).str.contains(kw, na=False).sum())
        if n:
            parts.append(f"{c}({n})")
    print(f"'{kw}':", ", ".join(parts) if parts else "未出现")