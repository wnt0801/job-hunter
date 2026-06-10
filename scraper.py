from playwright.sync_api import sync_playwright
import time
import random
import re
import pandas as pd
from pathlib import Path
from datetime import datetime

KEYWORD = "数据分析"
CITY = "全国"
OUTPUT_FILE = "jobs.xlsx"
MAX_PAGES = 20

BASE_URL = "https://www.shixiseng.com"
LIEPIN_BASE = "https://www.liepin.com"

COLUMNS = [
    "岗位名", "公司名", "城市", "薪资", "链接",
    "公司行业", "公司规模", "每周工作天数", "最短实习时间",
    "工作内容", "岗位要求", "抓取时间"
]


def load_existing():
    if Path(OUTPUT_FILE).exists():
        df = pd.read_excel(OUTPUT_FILE)
        links = set(df["链接"].dropna().tolist()) if "链接" in df.columns else set()
        return df, links
    return None, set()


def try_get(el, selector):
    try:
        found = el.query_selector(selector)
        return found.inner_text().strip() if found else "未获取"
    except:
        return "未获取"


# ═══════════════════════════════ 实习僧 ════════════════════════════════════


def parse_list_item(card):
    try:
        link_el = card.query_selector("a.title.ellipsis.font")
        if not link_el:
            return None

        title = link_el.inner_text().strip()
        href = link_el.get_attribute("href") or ""
        link = href if href.startswith("http") else BASE_URL + href

        company = try_get(card, ".intern-detail__company a.title")
        city = try_get(card, "span.city.ellipsis")
        salary = try_get(card, "span.day.font")

        work_days = "未获取"
        min_duration = "未获取"
        industry = "未获取"
        scale = "未获取"

        try:
            for span in card.query_selector_all("span"):
                text = span.inner_text().strip()
                if work_days == "未获取" and re.search(r"\d+天/周", text):
                    work_days = text
                elif min_duration == "未获取" and re.search(r"\d+个月", text):
                    min_duration = text
        except:
            pass

        for sel in [".intern-detail__company .type", "span.industry", ".company-industry"]:
            try:
                el = card.query_selector(sel)
                if el:
                    industry = el.inner_text().strip()
                    break
            except:
                pass

        for sel in [".intern-detail__company .count", "span.scale", ".company-scale"]:
            try:
                el = card.query_selector(sel)
                if el:
                    scale = el.inner_text().strip()
                    break
            except:
                pass

        return {
            "岗位名": title, "公司名": company, "城市": city, "薪资": salary,
            "链接": link, "公司行业": industry, "公司规模": scale,
            "每周工作天数": work_days, "最短实习时间": min_duration,
        }
    except:
        return None


def scrape_detail_shixiseng(page, url):
    try:
        page.goto(url, timeout=20000)
        time.sleep(0.5)
    except:
        return "未获取", "未获取"

    content = "未获取"
    requirements = "未获取"

    try:
        sections = page.evaluate("""() => {
            const res = [];
            document.querySelectorAll('.con-job .job_til').forEach(til => {
                const part = til.nextElementSibling;
                const detail = part && part.querySelector('.job_detail');
                const text = detail && detail.innerText.trim();
                if (text) res.push({ title: til.innerText.trim(), text });
            });
            return res;
        }""")

        content_kws = ["工作内容", "岗位职责", "职位描述", "工作描述"]
        req_kws = ["岗位要求", "任职要求", "职位要求", "实习要求"]

        for sec in sections:
            title, text = sec["title"], sec["text"]
            if content == "未获取" and any(kw in title for kw in content_kws):
                content = text
            if requirements == "未获取" and any(kw in title for kw in req_kws):
                requirements = text

        if content != "未获取" and requirements == "未获取":
            for kw in ["岗位要求", "任职要求", "职位要求"]:
                if kw in content:
                    idx = content.index(kw)
                    requirements = content[idx:].strip()
                    content = content[:idx].strip() or content
                    break

        if content == "未获取" and sections:
            content = sections[0]["text"]

    except:
        pass

    return content, requirements


def scrape_shixiseng(page, existing_links):
    new_jobs = []
    skipped = 0

    for page_num in range(1, MAX_PAGES + 1):
        url = f"{BASE_URL}/interns?keyword={KEYWORD}&city={CITY}&page={page_num}"
        print(f"\n[实习僧] 第 {page_num}/{MAX_PAGES} 页")
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(1.5)

        cards = page.query_selector_all(".intern-item")
        if not cards:
            print(f"  第 {page_num} 页无职位，停止翻页")
            break

        list_data = [d for card in cards if (d := parse_list_item(card)) and d.get("链接")]
        last_page = len(list_data) < 5
        print(f"  找到 {len(list_data)} 条职位" + ("（最后一页）" if last_page else ""))

        for i, data in enumerate(list_data, 1):
            link = data["链接"]
            if link in existing_links:
                skipped += 1
                continue

            print(f"  [{i}/{len(list_data)}] 抓取: {data['岗位名']}")
            data["工作内容"], data["岗位要求"] = scrape_detail_shixiseng(page, link)
            data["抓取时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_jobs.append(data)
            existing_links.add(link)
            time.sleep(random.uniform(0.5, 1.5))

        if last_page:
            break

    return new_jobs, skipped


# ═══════════════════════════════ 猎聘 ════════════════════════════════════
# 猎聘实习搜索页无需强制登录，但查看完整 JD 可能需要登录。
# 首次运行时会检测是否被拦截，提示用户手动登录后继续。


_LP_JOB_URL_PATTERN = re.compile(r"liepin\.com/job/\d+")


def _lp_check_captcha(page):
    title = page.title()
    if "验证" in title or "安全中心" in title or "security" in page.url.lower():
        print("\n[猎聘] 触发验证码，请在浏览器中手动完成验证")
        input("  完成后按回车继续 > ")
        time.sleep(2)
        return True
    return False

_LP_DETAIL_SELECTORS = [
    ".job-description",
    ".job-info-content",
    ".detail-content",
    ".job-detail-content",
    ".content-box",
    ".desc-container",
    ".job-introduction",
]


def _lp_find_cards(page):
    for sel in [".job-card-pc", ".job-list-item", ".p-data-info", ".job-card", ".list-item-pc"]:
        cards = page.query_selector_all(sel)
        if cards:
            return cards

    # JS 回退：扫描所有指向职位详情页的链接，向上找容器
    handles = page.evaluate_handle("""() => {
        const seen = new Set();
        const containers = [];
        document.querySelectorAll('a[href]').forEach(a => {
            if (!/liepin\\.com\\/job\\/\\d+/.test(a.href)) return;
            if (seen.has(a.href)) return;
            seen.add(a.href);
            let el = a.parentElement;
            for (let i = 0; i < 6 && el; i++) {
                if (el.querySelectorAll('span,p,div').length >= 3) { containers.push(el); break; }
                el = el.parentElement;
            }
        });
        return containers;
    }""")
    try:
        count = page.evaluate("arr => arr.length", handles)
        return [page.evaluate_handle(f"arr => arr[{i}]", handles) for i in range(count)]
    except:
        return []


def _lp_extract_card_data(card_el):
    try:
        raw = card_el.evaluate("""el => {
            const a = el.querySelector('a[href]');
            if (!a) return null;
            const heading = el.querySelector('h3,h4,h5,.title,.job-title,.position-name');
            const title = (heading || a).innerText.trim();
            const leaves = [];
            el.querySelectorAll('*').forEach(node => {
                if (node.children.length === 0) {
                    const t = node.innerText.trim();
                    if (t && t.length < 60 && !leaves.includes(t)) leaves.push(t);
                }
            });
            return { href: a.href, title, leaves };
        }""")
        return raw
    except:
        return None


def _lp_parse_raw(raw):
    if not raw or not raw.get("href"):
        return None
    href = raw["href"]
    if not _LP_JOB_URL_PATTERN.search(href):
        return None
    link = href if href.startswith("http") else LIEPIN_BASE + href
    title = raw.get("title") or "未获取"
    leaves = raw.get("leaves", [])

    city_kws = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京",
                "西安", "长沙", "厦门", "天津", "重庆", "苏州", "全国", "远程"]
    salary_kws = ["K", "k", "/天", "元/", "万/", "元每", "面议", "薪"]

    company, city, salary = "未获取", "未获取", "未获取"
    for t in leaves:
        if t == title:
            continue
        if city == "未获取" and any(kw in t for kw in city_kws):
            city = t
        elif salary == "未获取" and any(kw in t for kw in salary_kws):
            salary = t
        elif company == "未获取" and len(t) > 1:
            company = t

    return {
        "岗位名": title, "公司名": company, "城市": city, "薪资": salary,
        "链接": link, "公司行业": "未获取", "公司规模": "未获取",
        "每周工作天数": "未获取", "最短实习时间": "未获取",
    }


def scrape_detail_liepin(page, url):
    try:
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        time.sleep(1)
    except:
        return "未获取", "未获取"

    content = "未获取"
    requirements = "未获取"

    try:
        for sel in _LP_DETAIL_SELECTORS:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if len(text) > 20:
                    content = text
                    break

        if content == "未获取":
            content = page.evaluate("""() => {
                let best = '';
                document.querySelectorAll('p, div').forEach(el => {
                    if (el.children.length > 5) return;
                    const t = el.innerText.trim();
                    if (t.length > best.length) best = t;
                });
                return best || '未获取';
            }""")

        if content not in ("未获取", ""):
            for kw in ["任职要求", "岗位要求", "职位要求"]:
                if kw in content:
                    idx = content.index(kw)
                    requirements = content[idx:].strip()
                    content = content[:idx].strip() or content
                    break
    except:
        pass

    return content, requirements


def scrape_liepin(page, existing_links):
    new_jobs = []
    skipped = 0
    search_url = f"{LIEPIN_BASE}/zhaopin/?key={KEYWORD}实习&jobKind=2"

    print("\n[猎聘] 正在打开搜索页...")
    try:
        page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
    except:
        pass
    time.sleep(2)

    # 检测登录拦截
    if "login" in page.url or page.query_selector(".login-dialog"):
        print("[猎聘] 检测到登录拦截，请在浏览器窗口中完成登录")
        print("  登录后确认看到职位列表，再回到这里按回车")
        input("  按回车继续 > ")
        time.sleep(2)

    for page_num in range(MAX_PAGES):
        url = f"{search_url}&curPage={page_num}"
        print(f"\n[猎聘] 第 {page_num + 1}/{MAX_PAGES} 页")
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
        except:
            pass
        time.sleep(random.uniform(2.5, 4))
        _lp_check_captcha(page)

        cards = _lp_find_cards(page)
        if not cards:
            with open("liepin_debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"  第 {page_num + 1} 页未找到职位卡片，已保存 liepin_debug.html，停止翻页")
            break

        list_data = []
        seen = set()
        for card in cards:
            raw = _lp_extract_card_data(card)
            data = _lp_parse_raw(raw)
            if data and data.get("链接") and data["链接"] not in seen:
                seen.add(data["链接"])
                list_data.append(data)

        last_page = len(list_data) < 5
        print(f"  找到 {len(list_data)} 条职位" + ("（最后一页）" if last_page else ""))

        if not list_data:
            break

        for i, data in enumerate(list_data, 1):
            link = data["链接"]
            if link in existing_links:
                skipped += 1
                continue

            print(f"  [{i}/{len(list_data)}] 抓取: {data['岗位名']}")
            data["工作内容"], data["岗位要求"] = scrape_detail_liepin(page, link)
            data["抓取时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_jobs.append(data)
            existing_links.add(link)
            time.sleep(random.uniform(0.5, 1.5))

        if last_page:
            break

    return new_jobs, skipped


# ═══════════════════════════════ 主函数 ════════════════════════════════════


def main():
    existing_df, existing_links = load_existing()


    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        shixiseng_jobs, shixiseng_skipped = scrape_shixiseng(page, existing_links)
        liepin_jobs, liepin_skipped = scrape_liepin(page, existing_links)

        input("\n按回车关闭浏览器...")
        browser.close()

    all_new = shixiseng_jobs + liepin_jobs
    total_skipped = shixiseng_skipped + liepin_skipped

    if all_new:
        new_df = pd.DataFrame(all_new, columns=COLUMNS)
        combined = pd.concat([existing_df, new_df], ignore_index=True) if existing_df is not None else new_df
        combined.to_excel(OUTPUT_FILE, index=False)

    print(f"\n实习僧新增{len(shixiseng_jobs)}条，猎聘新增{len(liepin_jobs)}条，跳过{total_skipped}条重复")


main()
