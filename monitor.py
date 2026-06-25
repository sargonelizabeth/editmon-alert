#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
편집몬(editmon.com) '편집자 모집' 새 공고 → 텔레그램 알림.
- 재택근무 가능 공고만(기본) 필터해서 핵심요약+링크로 발송
- 글번호(watermark)로 새 공고만 감지, 중복 발송 방지
- 편집몬이 클라우드 IP를 차단하므로, GitHub Actions 등에서는
  실제 브라우저(Playwright)로 접속해 차단 페이지를 통과한다.
환경변수:
  TELEGRAM_BOT_TOKEN  (필수, 시크릿)
  TELEGRAM_CHAT_ID    (기본 8628024271)
  ONLY_REMOTE         (1=재택만[기본], 0=모든 새 공고)
  STATE_FILE          (기본 state.json)
  MAX_PER_RUN         (1회 최대 처리 수, 기본 20)
  USE_BROWSER         (1=브라우저로 접속. GitHub Actions에서는 자동 on)
"""
import os, sys, re, json, time, urllib.request, urllib.parse
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE = "https://editmon.com/m/content/"
LIST_URL = BASE + "work_employ_list.html"
def detail_url(no): return BASE + "work_employ_detail.html?no=%s" % no

TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "8628024271").strip()
STATE_FILE= os.environ.get("STATE_FILE", "state.json")
ONLY_REMOTE = os.environ.get("ONLY_REMOTE", "1") == "1"
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "20"))
# GitHub Actions 등 클라우드(차단 대상)에서는 브라우저 모드 자동 사용
USE_BROWSER = os.environ.get("USE_BROWSER", "").strip() == "1" or \
              os.environ.get("GITHUB_ACTIONS", "").strip() == "true"

CHALLENGE_MARKERS = ("보안절차", "prove that you are human", "자동등록방지")

# ---------- 브라우저(Playwright) 경로 ----------
_PG = {"page": None, "browser": None, "pw": None}

def _browser_page():
    if _PG["page"]:
        return _PG["page"]
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True,
                            args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = br.new_context(user_agent=UA, locale="ko-KR",
                         viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    _PG.update(pw=pw, browser=br, page=pg)
    return pg

def _browser_close():
    try:
        if _PG["browser"]: _PG["browser"].close()
        if _PG["pw"]: _PG["pw"].stop()
    except Exception:
        pass

def _looks_blocked(html):
    return any(m in html for m in CHALLENGE_MARKERS)

def fetch_browser(url, tries=4):
    pg = _browser_page()
    last = ""
    for i in range(tries):
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(3500)            # 차단 페이지 JS가 통과하도록 대기
            html = pg.content()
            if not _looks_blocked(html):
                return html
            # 아직 차단 페이지면 한 번 더 새로고침(쿠키 세팅 후)
            pg.wait_for_timeout(2500)
            pg.reload(wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(2500)
            html = pg.content()
            if not _looks_blocked(html):
                return html
            last = html
        except Exception as e:
            print("  browser fetch err:", str(e)[:120])
        time.sleep(2)
    return last

# ---------- 단순 HTTP 경로(가정용 IP에서만 통과) ----------
def fetch_http(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "ko,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml",
            })
            raw = urllib.request.urlopen(req, timeout=25).read()
            return raw.decode("euc-kr", "replace")
        except Exception as e:
            last = e; time.sleep(2 + i)
    raise last

def fetch(url):
    return fetch_browser(url) if USE_BROWSER else fetch_http(url)

# ---------- 파싱 ----------
def get_listing():
    html = fetch(LIST_URL)
    if _looks_blocked(html):
        print("  listing still blocked. head:", re.sub(r"\s+"," ",html)[:160])
        return []
    soup = BeautifulSoup(html, "html.parser")
    items, seen = [], set()
    for a in soup.select('a[href*="work_employ_detail.html?no="]'):
        m = re.search(r"no=(\d+)", a.get("href", ""))
        if not m: continue
        no = int(m.group(1))
        if no in seen: continue
        seen.add(no)
        comp = a.select_one(".company")
        subj = a.select_one(".subject")
        meta = a.select_one(".meta-info")
        items.append({
            "no": no,
            "company": comp.get_text(strip=True) if comp else "",
            "title":   subj.get_text(strip=True) if subj else "",
            "meta":    re.sub(r"\s+"," ",meta.get_text(" ",strip=True)) if meta else "",
        })
    return items

def get_detail(no):
    soup = BeautifulSoup(fetch(detail_url(no)), "html.parser")
    for t in soup(["script", "style"]): t.decompose()
    kv = {}
    for lab in soup.find_all(["th", "dt"]):
        k = lab.get_text(strip=True)
        sib = lab.find_next_sibling()
        v = sib.get_text(" ", strip=True) if sib else ""
        if k and v and len(k) < 12:
            kv[k] = re.sub(r"\s+", " ", v)[:140]
    body = ""
    lbl = soup.find(string=re.compile("상세모집내용"))
    if lbl:
        cont = lbl.find_parent()
        sib = cont.find_next_sibling()
        if not sib and cont.find_parent():
            sib = cont.find_parent().find_next_sibling()
        if sib:
            body = re.sub(r"\s+", " ", sib.get_text(" ", strip=True))
    return kv, body

def is_remote(kv):
    return "재택" in (kv.get("복리후생", "") + " " + kv.get("근무형태", ""))

# ---------- 텔레그램 ----------
def tg_send(text):
    if not TOKEN:
        print("(dry-run, no token) ----\n" + text + "\n----"); return True
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true",
    }).encode()
    url = "https://api.telegram.org/bot%s/sendMessage" % TOKEN
    for _ in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20).read().decode()
            if '"ok":true' in r: return True
        except Exception as e:
            print("send error:", e)
        time.sleep(2)
    print("send FAILED:", text[:60]); return False

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {}

def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

def fmt(item, kv, body):
    L = ["🆕 편집몬 새 재택 공고" if ONLY_REMOTE else "🆕 편집몬 새 공고", ""]
    L.append("📌 " + (item["title"] or "(제목 없음)"))
    L.append("🏢 " + (item["company"] or "-"))
    if kv.get("급여"):      L.append("💰 급여: " + kv["급여"])
    if kv.get("경력"):      L.append("📈 경력: " + kv["경력"])
    if kv.get("근무형태"):  L.append("🏠 근무형태: " + kv["근무형태"])
    if kv.get("편집가능툴"):L.append("🎬 편집툴: " + kv["편집가능툴"])
    if kv.get("복리후생"):  L.append("🎁 복리후생: " + kv["복리후생"])
    if kv.get("담당업무"):  L.append("📋 담당업무: " + kv["담당업무"])
    if kv.get("모집인원"):  L.append("👥 모집인원: " + kv["모집인원"])
    if kv.get("접수기간"):  L.append("🗓 마감: " + kv["접수기간"])
    if body:
        snip = body[:180] + ("…" if len(body) > 180 else "")
        L += ["", "📝 " + snip]
    L += ["", "🔗 " + detail_url(item["no"])]
    return "\n".join(L)

def main():
    print("USE_BROWSER =", USE_BROWSER)
    st = load_state()
    watermark = int(st.get("watermark", 0))
    try:
        items = get_listing()
    except Exception as e:
        print("listing fetch failed:", e); _browser_close(); return
    if not items:
        print("no items (blocked?); skip"); _browser_close(); return
    all_max = max(i["no"] for i in items)
    print("fetched %d items, max=%d" % (len(items), all_max))

    if watermark == 0:
        st["watermark"] = all_max; save_state(st)
        tg_send("🤖 편집몬 재택 공고 알림 시작!\n"
                "지금부터 새로 올라오는 '재택 가능' 편집자 모집 공고를 30분마다 확인해 알려드릴게요.\n"
                "(기준 글번호: %d)" % all_max)
        print("baseline set:", all_max); _browser_close(); return

    new = sorted([i for i in items if i["no"] > watermark], key=lambda x: x["no"])
    print("watermark=%d, new=%d" % (watermark, len(new)))
    processed = new[:MAX_PER_RUN]
    sent = 0
    for it in processed:
        try:
            kv, body = get_detail(it["no"])
        except Exception as e:
            print("detail fail", it["no"], e); continue
        if ONLY_REMOTE and not is_remote(kv):
            print("skip non-remote", it["no"]); time.sleep(0.4); continue
        if tg_send(fmt(it, kv, body)):
            sent += 1; print("sent", it["no"])
        time.sleep(0.6)
    new_wm = processed[-1]["no"] if len(new) > MAX_PER_RUN else all_max
    st["watermark"] = max(watermark, new_wm); save_state(st)
    print("done. sent=%d, watermark=%d" % (sent, st["watermark"]))
    _browser_close()

if __name__ == "__main__":
    main()
