import os
import time
import json
import requests
import pandas as pd
from pathlib import Path


def _load_dotenv():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

EXCEL_FILE = "jobs.xlsx"
PROFILE_FILE = "profile.md"
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "你是一个求职顾问，擅长分析候选人与职位的匹配程度。"
    "用户会提供个人背景和一条职位JD，请输出JSON格式分析，包含4个字段：\n"
    "- score: 整数 0-100，匹配度评分\n"
    "- strengths: 字符串，我有哪些符合该职位的经历/技能\n"
    "- gaps: 字符串，JD要求但我目前缺乏的能力或经验\n"
    "- recommendation: 字符串，一句话说明值不值得投递\n"
    "只输出JSON，不要有其他内容。"
)


def load_profile():
    with open(PROFILE_FILE, encoding="utf-8") as f:
        return f.read().strip()


def call_api(profile, job_content, job_requirements, api_key):
    user_msg = (
        f"## 我的背景\n{profile}\n\n"
        f"## 工作内容\n{job_content}\n\n"
        f"## 岗位要求\n{job_requirements}"
    )
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 800,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.json()["choices"][0]["message"]["content"])
    return (
        int(data.get("score", 0)),
        str(data.get("strengths", "未获取")),
        str(data.get("gaps", "未获取")),
        str(data.get("recommendation", "未获取")),
    )


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise SystemExit("未找到环境变量 DEEPSEEK_API_KEY，请先设置再运行。")

    profile = load_profile()
    df = pd.read_excel(EXCEL_FILE)

    # 新增列（若已存在则保留原值）；匹配度用 object dtype 以便同时存整数和"分析失败"字符串
    for col in ["匹配度", "优势", "差距", "推荐语"]:
        if col not in df.columns:
            df[col] = None
    df["匹配度"] = df["匹配度"].astype(object)

    total = len(df)
    done = 0
    skipped = 0

    for idx, row in df.iterrows():
        # 匹配度为空或 NaN 才需要分析；直接读 DataFrame 单元格，避免 iterrows 复制的 dtype 问题
        val = df.at[idx, "匹配度"]
        if not (pd.isna(val) or str(val).strip() in ("", "None", "分析失败")):
            skipped += 1
            continue

        job_name = str(row.get("岗位名", "")).strip() or f"第{idx+1}条"
        job_content = str(row.get("工作内容", "未获取")).strip()
        job_requirements = str(row.get("岗位要求", "未获取")).strip()

        print(f"[{idx+1}/{total}] 分析: {job_name} ...", end=" ", flush=True)
        try:
            score, strengths, gaps, recommendation = call_api(
                profile, job_content, job_requirements, api_key
            )
            df.at[idx, "匹配度"] = score
            df.at[idx, "优势"] = strengths
            df.at[idx, "差距"] = gaps
            df.at[idx, "推荐语"] = recommendation
            done += 1
            print(f"评分 {score}")
        except Exception as e:
            df.at[idx, "匹配度"] = "分析失败"
            df.at[idx, "优势"] = str(e)
            df.at[idx, "差距"] = ""
            df.at[idx, "推荐语"] = ""
            print(f"失败: {e}")

        time.sleep(1)

        if done % 10 == 0 and done > 0:
            df.to_excel(EXCEL_FILE, index=False)

    df.to_excel(EXCEL_FILE, index=False)
    print(f"\n完成：新分析 {done} 条，跳过 {skipped} 条已有结果。")


main()
