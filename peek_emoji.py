import pandas as pd

df = pd.read_excel("sample_jobs.xlsx")

# 常见允许字符：中文、英文字母数字、空格及常见标点
allowed_punct = set("（）()【】[]·-_/、，,.！!？?：:%&+@#＆")

weird_chars = {}
for name in df["岗位名"].astype(str):
    for ch in name:
        if ch.isalnum() or ch.isspace() or ch in allowed_punct:
            continue
        if '\u4e00' <= ch <= '\u9fff':  # 常用汉字
            continue
        weird_chars.setdefault(ch, []).append(name)

print(f"发现 {len(weird_chars)} 种异常字符")
for ch, names in weird_chars.items():
    print(f"字符: {repr(ch)}  (U+{ord(ch):04X})  出现 {len(names)} 次，示例: {names[0]}")