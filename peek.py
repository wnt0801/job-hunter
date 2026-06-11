import pandas as pd
df = pd.read_excel("sample_jobs.xlsx")
for name in df["岗位名"].head(15):
    print(name)