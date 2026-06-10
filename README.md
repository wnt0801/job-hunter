# Job Hunter 求职自动化工具

抓取实习职位 → LLM 对照个人背景逐条打分 → Streamlit 看板筛选与投递追踪。

用工程手段解决求职初筛的真实痛点：逐条阅读 JD 效率极低。本工具单次处理 900+ 条职位，把初筛时间从数小时压缩到分钟级。

**完整项目说明（架构、设计决策、看板截图）：[wannantian.com/projects/job-hunter](https://wannantian.com/projects/job-hunter)**

## 架构

```
scraper.py  →  jobs.xlsx  →  analyzer.py  →  jobs.xlsx  →  app.py
（Playwright 抓取）          （LLM 打分）                 （Streamlit 看板）
```

三个模块解耦，各自可独立运行：

| 模块 | 职责 | 关键设计 |
|------|------|----------|
| `scraper.py` | 抓取实习僧职位列表 + 详情页 | Playwright 驱动 Chromium，链接去重增量抓取，随机延时，选择器多级回退 |
| `analyzer.py` | 调用 DeepSeek API 对每条 JD 打分 | 强制 JSON 输出（score/strengths/gaps/recommendation），每 10 条增量落盘，失败不中断、可断点续跑 |
| `app.py` | Streamlit 交互看板 | 汇总指标 + 城市/匹配度/投递状态三维筛选，投递状态写回数据文件 |

## 快速开始

```bash
# 1. 安装依赖
pip install playwright pandas openpyxl requests streamlit
playwright install chromium

# 2. 配置
# 在项目根目录创建 .env 文件，写入：
# DEEPSEEK_API_KEY=你的key
# 创建 profile.md，写入个人背景（技能、项目经历、证书等）

# 3. 依次运行
python scraper.py          # 抓取职位 → jobs.xlsx
python analyzer.py         # LLM 打分（增量，可中断续跑）
streamlit run app.py       # 启动看板
```

## LLM 打分输出

每条职位输出四个结构化字段：

- **score**：0-100 匹配度评分
- **strengths**：候选人符合该职位的经历/技能
- **gaps**：JD 要求但候选人目前缺乏的能力
- **recommendation**：一句话投递建议

## 已知局限

- 数据源目前稳定覆盖实习僧；猎聘已实现选择器回退与登录人工介入，但反爬限制下稳定性不足
- LLM 评分未做一致性校准，定位是初筛排序而非精确度量
- 存储层为 Excel，千条量级够用，不适合并发场景

## 技术栈

Python · Playwright · pandas · DeepSeek API · Streamlit

开发过程使用 Claude Code 辅助。
