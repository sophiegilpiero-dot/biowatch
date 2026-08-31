"""
BioWatch v2 — 한국 바이오/제약 공시 추적 (단일 파일)
소스: ClinicalTrials.gov / SEC EDGAR / CTIS(유럽)
사용법: python main.py --hours 48
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DB_PATH = Path(__file__).parent / "data" / "seen.db"

UA = {"User-Agent": "BioWatch research (biowatch.tracker@gmail.com)"}

CTIS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# 한국 기업/기관 키워드 (영문 위주 — 해외 공시는 영문)
KOREAN_KEYWORDS = [
    # ── 대형 제약 ──
    "celltrion", "samsung bioepis", "samsung biologics", "samsung biologic",
    "sk bioscience", "sk biopharm", "sk biopharmaceuticals", "sk life science",
    "lg chem", "lg chemistry", "lotte biologics", "lotte bio",
    "yuhan", "hanmi", "hanmi pharm", "hanmi pharmaceutical",
    "daewoong", "daewoong pharmaceutical", "daewoong bio",
    "boryung", "ildong", "il-dong",
    "chong kun dang", "chongkundang", "ckd pharma",
    "dong-a st", "dong-a socio", "dongbang",
    "jw pharmaceutical", "jw pharma",
    "gc biopharma", "gc pharma", "green cross",
    "hk inno.n", "hk inno",
    "samjin pharm", "kwangdong", "huons", "hyundai pharm",
    "taejoon pharm", "alvogen korea", "boryung biopharma",
    "cheiljedang", "cj bioscience", "cj healthcare",
    "dongkook pharm", "dongkook pharmaceutical",
    "ilyang pharm", "ilyang pharmaceutical",
    "korean drug", "korea united pharm",
    "namyang", "isu abxis", "isu chemical",
    "pharmbio", "pharmbio korea",
    "samchundang", "samchundang pharm",
    "shinpoong", "shin poong",
    "taeyoung pharm", "unimed pharma",
    "yuhan corporation",

    # ── 바이오텍 / 신약 ──
    "hugel", "medytox", "genexine", "alteogen", "helixmith",
    "kolon life science", "kolon tissuegene", "kolon tissue gene",
    "bridge biotherapeutics", "tiumbio", "tium bio",
    "medpacto", "gi innovation", "gi-innovation",
    "hanall", "hanall biopharma", "aprilbio", "april bio",
    "abl bio", "ablbio", "y-biologics", "ybiologics",
    "kangstem", "anterogen", "nature cell",
    "toolgen", "olipass", "pharos ibio",
    "abion", "eubiologics", "cellid", "curigin",
    "aribio", "ari bio",
    "cha biotech", "cha vaccine",
    "binex", "genosco", "oncobix",
    "selecxine", "vaxcell", "imbiologics",
    "brd medico", "hylabio", "hylab",
    "inventisbio", "inventis bio",
    "kainos medicine", "kainosbio",
    "legochem biosciences", "legochem bio", "ligachem",
    "meiji seika pharma korea",
    "medifrontier", "medi-frontier",
    "neogene therapeutics korea",
    "neurobiogen", "neuro biogen",
    "nextbio", "next bio research",
    "nik kim",
    "novacel", "novarix",
    "onconova korea",
    "orix bio", "orixbio",
    "oscotec", "osc biotech",
    "peptron", "pharosibio",
    "posco bioscience",
    "probiogen", "probiogics",
    "proteina", "qurient",
    "reyon pharmaceutical", "reyon pharma",
    "rexgene biotech",
    "roivant korea",
    "sbio therapeutics",
    "shin biogen",
    "stevia biotech", "steviabio",
    "therabest", "thera best",
    "thermogene", "theranos korea",
    "tizianalifesciences korea",
    "trilion bio",
    "trizell",
    "united bio", "unitedbio",
    "vig pharma",
    "viromed",
    "xencor korea",
    "yuhan bioscience",
    "zerecept bio",
    "ziopharm korea",
    "zymeworks korea",
    "olixx", "olix pharmaceuticals",
    "bo1 therapeutics",
    "geovax korea",
    "invivo therapeutics korea",
    "inventage",
    "pharmabcine",
    "i-mab korea",
    "neoimmuntech",
    "bo therapeutics",
    "onconova",
    "proteovant korea",
    "orum therapeutics",
    "genoptix korea",
    "genervon korea",
    "bighat biosciences korea",
    "bioatla korea",
    "merus korea",
    "bicycle therapeutics korea",
    "regeneron korea",
    "blueprint medicines korea",
    "agenus korea",
    "arcus biosciences korea",
    "turning point korea",

    # ── 항체 / 바이오시밀러 ──
    "celltrion healthcare",
    "samsung bioepis holdings",
    "prestige biopharma",
    "prestige biopharmaceuticals",
    "scinai immunotherapeutics korea",
    "inventisbio",
    "boryung antibody",
    "y-trap", "ytrap",
    "jw bioscience",

    # ── 진단 / AI / 의료기기 ──
    "seegene", "sd biosensor", "sugentech",
    "i-sens", "isens", "nanoentek",
    "macrogen", "theragen", "bioneer",
    "gencurix", "genematrix",
    "lunit", "vuno", "deepnoid",
    "coreline", "jlk inspection", "jlk inc",
    "classys", "jeisys", "lutronic",
    "wontech", "humedix",
    "biosig technologies korea",
    "inbody", "biospace",
    "medit", "megagen",
    "osteonic", "osstem",
    "vieworks", "viewworks",
    "medical ip", "medicalip",
    "kakao health", "kakaohealth",
    "naver health", "naverhealth",
    "kakao healthcare",
    "medibloc",
    "health2sync korea",
    "3billion", "three billion",
    "genome insight",
    "genomeinsight",
    "dxvx",
    "ezdiagnosis",
    "diquest",
    "insightful science korea",
    "insilico medicine korea",
    "standigm",
    "arontier",
    "pharmaai",
    "pharmai",
    "mediwhale",
    "synaps dx korea",
    "neurotrack korea",
    "s-ray", "sray",
    "rayence",
    "raymedical",

    # ── CMO / CDMO ──
    "samsung biologics",
    "lotte biologics",
    "celltrion manufacturing",
    "sk pharmteco",
    "bioxcel therapeutics korea",
    "hncp", "hn corporation",
    "daewoong biologics",
    "lg chem life science",

    # ── 기관 / 병원 ──
    "seoul national university", "snu hospital",
    "samsung medical center",
    "asan medical center",
    "severance hospital",
    "yonsei university",
    "korea university",
    "catholic university of korea",
    "national cancer center korea",
    "seoul st. mary",
    "bundang seoul national",
    "ajou university hospital",
    "kyungpook national university",
    "chonnam national university",
    "pusan national university",
    "konkuk university hospital",
    "ewha womans university hospital",
    "hallym university",
    "inha university hospital",
    "gachon university",
    "dongguk university hospital",
    "chungnam national university",
    "chungbuk national university",
    "wonkwang university",
    "jeonbuk national university",

    # ── 국가 표기 ──
    "republic of korea",
    "south korea",
    "seoul, korea",
    "korea institute",
    "korean institute",
]

SEC_FORMS = "6-K,20-F,8-K,10-K,10-Q,F-1,F-3,424B4,SC 13D,SC 13G"

# SEC 쿼리 그룹 (EDGAR 전문검색용, 그룹당 5개 이하 권장)
SEC_QUERY_GROUPS = [
    '"celltrion" OR "samsung bioepis" OR "samsung biologics" OR "sk biopharmaceuticals" OR "sk bioscience"',
    '"hanmi pharmaceutical" OR "yuhan" OR "daewoong" OR "lotte biologics" OR "gc biopharma"',
    '"hugel" OR "medytox" OR "alteogen" OR "genexine" OR "kolon tissuegene"',
    '"lunit" OR "seegene" OR "sd biosensor" OR "abl bio" OR "bridge biotherapeutics"',
    '"ligachem" OR "hanall biopharma" OR "aprilbio" OR "eubiologics" OR "cha biotech"',
    '"prestige biopharma" OR "olixx" OR "pharmabcine" OR "neoimmuntech" OR "orum therapeutics"',
    '"inventage" OR "qurient" OR "oscotec" OR "peptron" OR "viromed"',
    '"tiumbio" OR "medpacto" OR "gi innovation" OR "curigin" OR "cellid"',
    '"bioneer" OR "macrogen" OR "theragen" OR "gencurix" OR "genematrix"',
    '"standigm" OR "medibloc" OR "3billion" OR "genome insight" OR "dxvx"',
    '"sk pharmteco" OR "lg chem life science" OR "hn corporation" OR "jw bioscience" OR "boryung"',
    '"anterogen" OR "kangstem" OR "nature cell" OR "toolgen" OR "olipass"',
]


# ─────────────────────────────────────────────
# 중복 제거 캐시
# ─────────────────────────────────────────────
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, ts TEXT)"
    )
    return conn


def is_new(source: str, raw_id: str) -> bool:
    key = hashlib.sha256(f"{source}:{raw_id}".encode()).hexdigest()[:20]
    conn = _db()
    cur = conn.execute("SELECT 1 FROM seen WHERE id=?", (key,))
    if cur.fetchone():
        conn.close()
        return False
    conn.execute(
        "INSERT INTO seen VALUES (?, ?)", (key, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return True


# ─────────────────────────────────────────────
# 텔레그램
# ─────────────────────────────────────────────
def tg_send(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TG 미설정]", text[:200])
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except Exception as e:
        print("[TG 발송 실패]", e)


def alert(emoji, source, title, keyword, date, url, detail):
    tg_send(
        f"{emoji} <b>[{source}] 새 공시</b>\n\n"
        f"📅 {date}\n"
        f"🏢 키워드: <b>{keyword}</b>\n"
        f"📌 {title}\n\n"
        f"{detail}\n\n"
        f"🔗 <a href=\"{url}\">원문 보기</a>"
    )


def match_korean(text: str):
    low = text.lower()
    for kw in KOREAN_KEYWORDS:
        if kw in low:
            return kw
    return None


# ─────────────────────────────────────────────
# 1. ClinicalTrials.gov
# ─────────────────────────────────────────────
def run_clinicaltrials(cutoff_date: str) -> tuple[int, int]:
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {"sort": "LastUpdatePostDate:desc", "pageSize": 100, "format": "json"}
    scanned = matched = 0
    token = None

    for _ in range(30):
        if token:
            params["pageToken"] = token
        r = requests.get(url, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        data = r.json()
        studies = data.get("studies", [])
        if not studies:
            break

        stop = False
        for s in studies:
            scanned += 1
            upd = (
                s.get("protocolSection", {})
                .get("statusModule", {})
                .get("lastUpdatePostDateStruct", {})
                .get("date", "")
            )
            if upd and upd < cutoff_date:
                stop = True
                break

            kw = match_korean(json.dumps(s, ensure_ascii=False))
            if not kw:
                continue

            ps = s.get("protocolSection", {})
            nct = ps.get("identificationModule", {}).get("nctId", "")
            if not nct or not is_new("ct", nct):
                continue

            title = ps.get("identificationModule", {}).get("briefTitle", "N/A")
            sponsor = (
                ps.get("sponsorCollaboratorsModule", {})
                .get("leadSponsor", {})
                .get("name", "N/A")
            )
            status = ps.get("statusModule", {}).get("overallStatus", "N/A")
            phases = ", ".join(ps.get("designModule", {}).get("phases", []) or ["N/A"])
            conds = ", ".join(ps.get("conditionsModule", {}).get("conditions", [])[:3])

            alert(
                "🧪", "ClinicalTrials.gov", title, kw, upd,
                f"https://clinicaltrials.gov/study/{nct}",
                f"[{phases}] {conds}\n스폰서: {sponsor} | 상태: {status}",
            )
            matched += 1

        if stop:
            break
        token = data.get("nextPageToken")
        if not token:
            break

    return scanned, matched


# ─────────────────────────────────────────────
# 2. SEC EDGAR
# ─────────────────────────────────────────────
def run_sec(start_date: str, end_date: str) -> tuple[int, int]:
    url = "https://efts.sec.gov/LATEST/search-index"
    scanned = matched = 0
    seen_adsh = set()

    for q in SEC_QUERY_GROUPS:
        params = {
            "q": q,
            "forms": SEC_FORMS,
            "dateRange": "custom",
            "startdt": start_date,
            "enddt": end_date,
        }
        r = requests.get(url, params=params, headers=UA, timeout=30)
        if r.status_code != 200:
            tg_send(f"🚨 SEC 응답 {r.status_code}: {q[:50]}...")
            continue

        hits = r.json().get("hits", {}).get("hits", [])
        for h in hits:
            src = h.get("_source", {})
            adsh = src.get("adsh", "")
            scanned += 1
            if not adsh or adsh in seen_adsh:
                continue
            seen_adsh.add(adsh)
            if not is_new("sec", adsh):
                continue

            names = ", ".join(src.get("display_names", ["N/A"]))
            form = src.get("form", src.get("root_forms", ["?"])[0] if src.get("root_forms") else "?")
            fdate = src.get("file_date", "")
            kw = match_korean(names + " " + json.dumps(src)) or "쿼리매칭"
            ciks = src.get("ciks", [])
            cik = str(int(ciks[0])) if ciks else ""
            furl = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                f"{adsh.replace('-', '')}/{adsh}-index.htm"
                if cik else "https://efts.sec.gov/LATEST/search-index?q=" + adsh
            )

            alert("📋", "SEC EDGAR", f"[{form}] {names}", kw, fdate, furl,
                  f"공시유형: {form}\n접수번호: {adsh}")
            matched += 1

        time.sleep(0.5)

    return scanned, matched


# ─────────────────────────────────────────────
# 3. CTIS (유럽 임상시험)
# ─────────────────────────────────────────────
def run_ctis() -> tuple[int, int]:
    rss_url = "https://euclinicaltrials.eu/ctis-public-api/rss/updates.rss"
    scanned = matched = 0

    r = requests.get(rss_url, params={"search_criteria": "{}"}, headers=CTIS_HEADERS, timeout=30)
    if r.status_code != 200:
        tg_send(f"🚨 CTIS RSS 응답 {r.status_code}")
        return 0, 0

    ids = re.findall(r"EUCT=([\d-]+)", r.text)
    ids = list(dict.fromkeys(ids))[:60]

    for euct in ids:
        scanned += 1
        try:
            d = requests.get(
                f"https://euclinicaltrials.eu/ctis-public-api/retrieve/{euct}",
                headers=CTIS_HEADERS, timeout=20,
            )
            if d.status_code != 200:
                continue
            body = d.text
            kw = match_korean(body)
            if not kw:
                continue
            if not is_new("ctis", euct):
                continue

            try:
                j = d.json()
                title = str(j.get("shortTitle") or j.get("title") or euct)[:150]
            except Exception:
                title = euct

            alert(
                "🇪🇺", "CTIS (유럽)", title, kw,
                datetime.utcnow().strftime("%Y-%m-%d"),
                f"https://euclinicaltrials.eu/search-for-clinical-trials/?lang=en&EUCT={euct}",
                f"EUCT 번호: {euct}",
            )
            matched += 1
            time.sleep(0.3)
        except Exception:
            continue

    return scanned, matched


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=2)
    args = ap.parse_args()

    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=args.hours)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    print(f"[BioWatch v2] 시작 {now.isoformat()} UTC / lookback {args.hours}h (cutoff {cutoff})")
    results = {}

    for name, fn in [
        ("ClinicalTrials", lambda: run_clinicaltrials(cutoff)),
        ("SEC", lambda: run_sec(cutoff, today)),
        ("CTIS", lambda: run_ctis()),
    ]:
        try:
            scanned, matched = fn()
            results[name] = (scanned, matched)
            print(f"  {name}: {scanned}건 스캔 / {matched}건 알림")
        except Exception:
            err = traceback.format_exc()
            print(f"  {name}: 오류\n{err}")
            tg_send(f"🚨 <b>[BioWatch 오류] {name}</b>\n{err[:400]}")
            results[name] = (0, 0)

    total = sum(m for _, m in results.values())
    if total > 0:
        lines = [f"📊 <b>BioWatch 스캔 결과</b> ({now.strftime('%m-%d %H:%M')} UTC)\n"]
        for k, (s, m) in results.items():
            lines.append(f"• {k}: {s}건 스캔 → <b>{m}건</b> 알림")
        tg_send("\n".join(lines))

    print(f"[BioWatch v2] 완료. 총 {total}건 알림.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
