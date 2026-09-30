"""
BioWatch v4 — 한국 바이오/제약 공시 추적 (단일 파일)
소스: ClinicalTrials.gov / SEC EDGAR / CTIS(유럽)
사용법: python main.py --hours 48

v4 변경사항
  - [중요] CT.gov 중복 제거 키를 'NCT 번호' → 'NCT 번호 + 최종 업데이트 게시일'로 변경
           → 같은 임상의 후속 등록정보 변경(기관 철회, 인원·일정 변경 등)도 다시 알림
  - CT.gov 알림을 '신규 등록' / '등록정보 변경'으로 구분, 변경 이력(History) 링크 추가
  - CT.gov 조회를 API 날짜 필터(filter.advanced) + 페이지당 1000건으로 변경
           → 하루 3000건 이상 업데이트되는 날에도 누락 없이 전수 스캔
  - CT.gov 날짜(미 동부 기준)와 UTC 차이, 예약 실행 누락에 대비해 조회 범위를 하루 더 넉넉히
  - 스캔이 페이지 상한에 걸려 잘리면 요약 메시지에 경고 표시
  - CTIS도 'EUCT 번호 + RSS 게시시각' 기준으로 후속 업데이트 알림
  - v3 → v4 전환 첫 실행 시, v3에서 이미 알림이 나간 건은 조용히 기준선 등록(알림 폭탄 방지)
  - 요약 메시지에 한국시간(KST) 병기, 소요 시간 표시

v3 변경사항
  - SEC EDGAR forms 파라미터를 콤마 구분 단일값으로 수정 (500 에러 해결)
  - SEC 요청 실패 시 최대 3회 재시도
  - 신흥/비상장/예심단계 바이오텍 키워드 약 100개 추가
  - 키워드 매칭을 정규식 단일 패스로 변경 (속도 개선)
  - 매칭 0건이어도 요약 발송 (고장 vs 조용한 정상 구분)
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

# ─────────────────────────────────────────────
# 한국 기업/기관 키워드 (영문 위주 — 해외 공시는 영문)
# ─────────────────────────────────────────────
KOREAN_KEYWORDS = [
    # ══════════ 대형 제약 ══════════
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
    "jeil pharmaceutical", "daewon pharmaceutical",
    "dong wha pharm", "hanlim pharm", "ahn-gook pharmaceutical",
    "yungjin pharm", "samil pharm", "kukje pharma",

    # ══════════ 바이오텍 / 신약 (기존) ══════════
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
    "medifrontier", "medi-frontier",
    "neurobiogen", "neuro biogen",
    "nextbio", "next bio research",
    "novacel", "novarix",
    "orix bio", "orixbio",
    "oscotec", "osc biotech",
    "peptron", "pharosibio",
    "posco bioscience",
    "probiogen", "probiogics",
    "proteina", "qurient",
    "reyon pharmaceutical", "reyon pharma",
    "rexgene biotech",
    "sbio therapeutics",
    "shin biogen",
    "stevia biotech", "steviabio",
    "therabest", "thera best",
    "thermogene",
    "trilion bio", "trizell",
    "united bio", "unitedbio",
    "vig pharma", "viromed",
    "yuhan bioscience",
    "zerecept bio",
    "olixx", "olix pharmaceuticals",
    "inventage", "pharmabcine",
    "neoimmuntech", "orum therapeutics",
    "prestige biopharma", "prestige biopharmaceuticals",
    "y-trap", "ytrap", "jw bioscience",

    # ══════════ ① IPO 예심 청구 / 상장 임박 ══════════
    "intocell", "into cell",                      # 인투셀 — ADC 링커 '오파스'
    "nex-i", "nexai therapeutics",                # 넥스아이 — 오노약품 L/O
    "innovo therapeutics",                        # 이노보테라퓨틱스 — AI '딥제마'
    "organoid sciences",                          # 오가노이드사이언스 — 초격차 1호
    "nextgen bioscience",                         # 넥스트젠바이오사이언스
    "immuneoncia",                                # 이뮨온시아 — 유한 자회사
    "gc genome",                                  # 지씨지놈
    "mbd co", "medical & bio decision",           # 엠비디 — 코디알피
    "lemon healthcare",                           # 레몬헬스케어
    "inocras",                                    # 이노크라스 — 암 유전체, 美 본사
    "neuracle genetics",                          # 뉴라클제네틱스 — AAV
    "neuracle science",                           # 뉴라클사이언스
    "sovargen",                                   # 소바젠 — 안젤리니 L/O
    "gfc life science",                           # 지에프씨생명과학

    # ══════════ ② 2026년 신규 상장 ══════════
    "kanaph therapeutics",                        # 카나프테라퓨틱스
    "ingenia therapeutics",                       # 인제니아테라퓨틱스
    "recens medical",                             # 리센스메디컬 — FDA De Novo
    "inventera",                                  # 인벤테라
    "mezoo",                                      # 메쥬
    "msbio",                                      # 엠에스바이오
    "xcell therapeutics",                         # 엑셀세라퓨틱스 — CGT 배지
    "aimedbio", "aimed bio",                      # 에임드바이오 — ADC
    "rznomics",                                   # 알지노믹스 — RNA 치환효소
    "livsmed",                                    # 리브스메드

    # ══════════ ③ ADC / 표적단백질분해 ══════════
    "pinotbio", "pinot bio",                      # 피노바이오
    "novelty nobility",                           # 노벨티노빌리티 — c-KIT
    "abclon", "ab clon",                          # 앱클론 — CAR-T
    "illimis therapeutics",                       # 일리미스테라퓨틱스
    "cellengene",                                 # 셀렌진

    # ══════════ ④ 세포·유전자치료제 ══════════
    "curocell",                                   # 큐로셀 — CAR-T
    "gc cell", "gccell",                          # 지씨셀
    "scm lifescience",                            # 에스씨엠생명과학
    "eutilex",                                    # 유틸렉스
    "corestem", "corestem chemon",                # 코아스템켐온
    "pharmicell",                                 # 파미셀
    "cellabmed",                                  # 셀랩메드
    "vaxcell bio",                                # 백스셀바이오
    "cellatoz",                                   # 셀라토즈테라퓨틱스
    "novacell technology",                        # 노바셀테크놀로지
    "cellico",                                    # 셀리코

    # ══════════ ⑤ 방사성의약품 (RPT) ══════════
    "cellbion",                                   # 셀비온 — Lu-177 전립선암
    "futurechem",                                 # 퓨쳐켐
    "duchembio", "du chem bio",                   # 듀켐바이오 — RPT CDMO

    # ══════════ ⑥ 신약개발 ══════════
    "voronoi",                                    # 보로노이 — 표적항암
    "genuv",                                      # 지뉴브 — ALS 항체
    "onconic therapeutics",                       # 온코닉테라퓨틱스 — 자큐보
    "aptabio",                                    # 압타바이오 — NOX
    "panolos bioscience",                         # 파노로스바이오사이언스
    "progen co",                                  # 프로젠
    "bioorchestra",                               # 바이오오케스트라
    "immunoforge",                                # 이뮤노포지
    "immunabs",                                   # 이뮨어브스
    "nkmax", "nk max",                            # 엔케이맥스
    "genome and company", "genome & company",     # 지놈앤컴퍼니
    "cellivery",                                  # 셀리버리
    "bioleaders",                                 # 바이오리더스
    "cell biotech",                               # 셀바이오텍
    "nibec",                                      # 나이벡 — 펩타이드
    "enzychem lifesciences",                      # 엔지켐생명과학
    "syntekabio",                                 # 신테카바이오
    "novmetapharma",                              # 노브메타파마
    "epibiotech",                                 # 에피바이오텍
    "sillajen",                                   # 신라젠
    "therasid bioscience",                        # 테라시드바이오사이언스
    "vaxdigm",                                    # 백스디그엠
    "neurobo biosciences",                        # 뉴로보바이오사이언스 — 동아ST
    "hyundai bioscience",                         # 현대바이오사이언스
    "sk plasma",                                  # SK플라즈마
    "aprogen",                                    # 아프로젠

    # ══════════ ⑦ AI 신약개발 / 오믹스 ══════════
    "deargen",                                    # 디어젠
    "pharmcadd", "pharm cadd",                    # 팜캐드
    "oncocross",                                  # 온코크로스
    "portrai",                                    # 포트라이
    "bertis",                                     # 베르티스
    "proteomtech",                                # 프로테옴텍
    "standigm", "arontier", "pharmaai", "pharmai",

    # ══════════ ⑧ 의료AI / 디지털헬스 ══════════
    "neurophet",                                  # 뉴로핏
    "airs medical",                               # 에어스메디컬
    "promedius",                                  # 프로메디우스
    "curexo",                                     # 큐렉소 — 수술로봇
    "koh young technology",                       # 고영테크놀러지
    "hurotics",                                   # 휴로틱스
    "cosmo robotics", "cosmorobotics",            # 코스모로보틱스
    "mediwhale", "medibloc", "health2sync korea",

    # ══════════ ⑨ 진단 / 의료기기 ══════════
    "seegene", "sd biosensor", "sugentech",
    "i-sens", "isens", "nanoentek",
    "macrogen", "theragen", "bioneer",
    "gencurix", "genematrix",
    "lunit", "vuno", "deepnoid",
    "coreline", "jlk inspection", "jlk inc",
    "classys", "jeisys", "lutronic",
    "wontech", "humedix",
    "inbody", "biospace",
    "medit", "megagen",
    "osteonic", "osstem",
    "vieworks", "viewworks",
    "medical ip", "medicalip",
    "3billion", "three billion",
    "genome insight", "genomeinsight",
    "dxvx", "ezdiagnosis",
    "rayence", "raymedical",
    "philosys",                                   # 필로시스
    "genoss",                                     # 제노스
    "optolane",                                   # 옵토레인
    "geninus",                                    # 지니너스
    "curiosis",                                   # 큐리오시스
    "biomedlab",                                  # 바이오메드랩

    # ══════════ ⑩ CDMO ══════════
    "sk pharmteco", "lg chem life science",
    "celltrion manufacturing", "daewoong biologics",
    "cellontech",                                 # 셀론텍
    "prostemics",                                 # 프로스테믹스

    # ══════════ 기관 / 병원 ══════════
    "seoul national university", "snu hospital",
    "samsung medical center", "asan medical center",
    "severance hospital", "yonsei university",
    "korea university", "catholic university of korea",
    "national cancer center korea", "seoul st. mary",
    "bundang seoul national", "ajou university hospital",
    "kyungpook national university", "chonnam national university",
    "pusan national university", "konkuk university hospital",
    "ewha womans university hospital", "hallym university",
    "inha university hospital", "gachon university",
    "dongguk university hospital", "chungnam national university",
    "chungbuk national university", "wonkwang university",
    "jeonbuk national university",

    # ══════════ 국가 표기 ══════════
    "republic of korea", "south korea", "seoul, korea",
    "korea institute", "korean institute",
]

# 중복 제거 후 긴 키워드부터 매칭 (더 구체적인 이름 우선)
KOREAN_KEYWORDS = sorted(set(KOREAN_KEYWORDS), key=len, reverse=True)

# 정규식 단일 패스로 컴파일 — 키워드 300개여도 한 번만 스캔
_KW_PATTERN = re.compile("|".join(re.escape(k) for k in KOREAN_KEYWORDS))

# SEC 폼 타입 (콤마 구분 단일 파라미터로 전달)
SEC_FORMS = [
    "6-K", "20-F", "8-K", "10-K", "10-Q",
    "F-1", "F-3", "424B4", "SC 13D", "SC 13G",
]

# SEC 쿼리 그룹 (EDGAR 전문검색용, 그룹당 5개 이하)
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
    '"sk pharmteco" OR "lg chem life science" OR "jw bioscience" OR "boryung" OR "gc cell"',
    '"anterogen" OR "kangstem" OR "nature cell" OR "toolgen" OR "olipass"',
    # ── 신흥/비상장 추가 그룹 ──
    '"intocell" OR "aimedbio" OR "pinotbio" OR "novelty nobility" OR "abclon"',
    '"voronoi" OR "genuv" OR "curocell" OR "eutilex" OR "onconic therapeutics"',
    '"inocras" OR "rznomics" OR "bioorchestra" OR "sovargen" OR "neuracle"',
    '"immuneoncia" OR "kanaph therapeutics" OR "xcell therapeutics" OR "aptabio" OR "nkmax"',
    '"cellbion" OR "futurechem" OR "duchembio" OR "organoid sciences" OR "genome and company"',
]



# ─────────────────────────────────────────────
# 중복 제거 캐시
# ─────────────────────────────────────────────
KST = timedelta(hours=9)


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, ts TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    return conn


def _key(source: str, raw_id: str) -> str:
    return hashlib.sha256(f"{source}:{raw_id}".encode()).hexdigest()[:20]


def was_seen(source: str, raw_id: str) -> bool:
    """기록만 조회 (저장하지 않음)"""
    conn = _db()
    cur = conn.execute("SELECT 1 FROM seen WHERE id=?", (_key(source, raw_id),))
    hit = cur.fetchone() is not None
    conn.close()
    return hit


def mark_seen(source: str, raw_id: str):
    conn = _db()
    conn.execute("INSERT OR IGNORE INTO seen VALUES (?, ?)",
                 (_key(source, raw_id), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def is_new(source: str, raw_id: str) -> bool:
    """처음 보는 건이면 기록하고 True, 이미 본 건이면 False"""
    if was_seen(source, raw_id):
        return False
    mark_seen(source, raw_id)
    return True


def meta_get(k: str):
    conn = _db()
    row = conn.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    conn.close()
    return row[0] if row else None


def meta_set(k: str, v: str):
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


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


def alert(emoji, source, title, keyword, date, url, detail, label="새 공시"):
    tg_send(
        f"{emoji} <b>[{source}] {label}</b>\n\n"
        f"📅 {date}\n"
        f"🏢 키워드: <b>{keyword}</b>\n"
        f"📌 {title}\n\n"
        f"{detail}\n\n"
        f"🔗 <a href=\"{url}\">원문 보기</a>"
    )


def match_korean(text: str):
    """정규식 단일 패스로 첫 매칭 키워드 반환 (없으면 None)"""
    m = _KW_PATTERN.search(text.lower())
    return m.group(0) if m else None


# ─────────────────────────────────────────────
# 1. ClinicalTrials.gov
# ─────────────────────────────────────────────
CT_URL = "https://clinicaltrials.gov/api/v2/studies"
CT_PAGE_SIZE = 1000   # API 최대값
CT_MAX_PAGES = 50     # 최대 5만 건 — 사실상 무제한
CT_V4_FLAG = "ct_v4_seeded"


def _ct_get(params: dict) -> dict:
    r = requests.get(CT_URL, params=params, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()


def run_clinicaltrials(cutoff_date: str, warnings: list) -> tuple[int, int]:
    """
    cutoff_date(YYYY-MM-DD) 이후 LastUpdatePostDate를 가진 임상을 전수 스캔.
    중복 제거 키 = NCT + 최종 업데이트 게시일 → 같은 임상의 후속 변경도 알림.
    """
    base = {
        "sort": "LastUpdatePostDate:desc",
        "pageSize": CT_PAGE_SIZE,
        "format": "json",
        "countTotal": "true",
        # API 단계에서 날짜 필터 → 페이지 상한에 걸려 잘리는 문제 방지
        "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{cutoff_date},MAX]",
        # 결과(resultsSection) 등을 빼서 응답 크기 축소 — 키워드 매칭엔 protocolSection이면 충분
        "fields": "protocolSection",
    }

    # 일부 파라미터가 거부되면(400) 단계적으로 빼고 재시도 — 기존 방식으로 자동 후퇴
    attempts = [
        dict(base),
        {k: v for k, v in base.items() if k != "fields"},
        {k: v for k, v in base.items() if k not in ("fields", "filter.advanced")},
    ]
    data = None
    params = None
    for p in attempts:
        try:
            data = _ct_get(p)
            params = p
            break
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                continue
            raise
    if data is None:
        raise RuntimeError("CT.gov API가 모든 파라미터 조합을 거부함")
    if "filter.advanced" not in params:
        warnings.append("CT.gov 날짜 필터 미지원 → 기존 방식으로 스캔")

    # v3 → v4 전환 첫 실행: v3에서 이미 알린 NCT는 조용히 기준선 등록
    seeding = meta_get(CT_V4_FLAG) is None
    seeded_silently = 0

    total = data.get("totalCount")
    scanned = matched = 0
    pages = 0
    truncated = False

    while True:
        pages += 1
        studies = data.get("studies", [])
        if not studies:
            break

        stop = False
        for s in studies:
            ps = s.get("protocolSection", {})
            status_mod = ps.get("statusModule", {})
            upd = status_mod.get("lastUpdatePostDateStruct", {}).get("date", "")

            # 날짜 필터가 적용 안 된 후퇴 모드일 때만 필요한 안전장치
            if upd and upd < cutoff_date:
                stop = True
                break
            scanned += 1

            kw = match_korean(json.dumps(s, ensure_ascii=False))
            if not kw:
                continue

            nct = ps.get("identificationModule", {}).get("nctId", "")
            if not nct:
                continue

            dedup_id = f"{nct}:{upd}"
            if was_seen("ct", dedup_id):
                continue

            if seeding and was_seen("ct", nct):
                # v3 키(NCT 단독)로 이미 알림이 나간 건 → 알림 없이 기준선만 등록
                mark_seen("ct", dedup_id)
                seeded_silently += 1
                continue

            mark_seen("ct", dedup_id)

            title = ps.get("identificationModule", {}).get("briefTitle", "N/A")
            sponsor = (
                ps.get("sponsorCollaboratorsModule", {})
                .get("leadSponsor", {})
                .get("name", "N/A")
            )
            status = status_mod.get("overallStatus", "N/A")
            phases = ", ".join(ps.get("designModule", {}).get("phases", []) or ["N/A"])
            conds = ", ".join(ps.get("conditionsModule", {}).get("conditions", [])[:3])
            first_post = status_mod.get("studyFirstPostDateStruct", {}).get("date", "")

            is_first = bool(first_post) and first_post == upd
            label = "신규 등록" if is_first else "등록정보 변경"
            emoji = "🆕" if is_first else "🧪"
            history = (
                "" if is_first
                else f"\n📜 <a href=\"https://clinicaltrials.gov/study/{nct}?tab=history\">변경 이력 보기</a>"
            )

            alert(
                emoji, "ClinicalTrials.gov", title, kw, upd,
                f"https://clinicaltrials.gov/study/{nct}",
                f"[{phases}] {conds}\n스폰서: {sponsor} | 상태: {status}\n"
                f"NCT: {nct} | 최초 게시: {first_post or 'N/A'}{history}",
                label=label,
            )
            matched += 1

        if stop:
            break
        token = data.get("nextPageToken")
        if not token:
            break
        if pages >= CT_MAX_PAGES:
            truncated = True
            break
        params = dict(params, pageToken=token)
        data = _ct_get(params)

    if truncated:
        warnings.append(
            f"CT.gov 페이지 상한({CT_MAX_PAGES * CT_PAGE_SIZE:,}건) 도달 — 일부 미스캔 가능"
        )
    if isinstance(total, int) and "filter.advanced" in params and scanned < total and not truncated:
        warnings.append(f"CT.gov 스캔 {scanned:,}건 < 전체 {total:,}건")

    if seeding:
        meta_set(CT_V4_FLAG, datetime.utcnow().isoformat())
        if seeded_silently:
            tg_send(
                f"🔧 <b>BioWatch v4 전환 완료</b>\n"
                f"v3에서 이미 알림이 나간 {seeded_silently}건은 기준선으로 조용히 등록했습니다.\n"
                f"이제부터 같은 임상의 후속 변경도 알림이 옵니다."
            )

    return scanned, matched


# ─────────────────────────────────────────────
# 2. SEC EDGAR
# ─────────────────────────────────────────────
def run_sec(start_date: str, end_date: str) -> tuple[int, int]:
    url = "https://efts.sec.gov/LATEST/search-index"
    scanned = matched = 0
    seen_adsh = set()

    for q in SEC_QUERY_GROUPS:
        # forms는 콤마 구분 단일 파라미터 — 중복 키로 넘기면 500 발생
        params = {
            "q": q,
            "dateRange": "custom",
            "startdt": start_date,
            "enddt": end_date,
            "forms": ",".join(SEC_FORMS),
        }

        r = None
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, headers=UA, timeout=30)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                r = None
            time.sleep(2 * (attempt + 1))

        if r is None or r.status_code != 200:
            code = r.status_code if r is not None else "네트워크 오류"
            tg_send(f"🚨 SEC 응답 {code}: {q[:50]}...")
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
            root_forms = src.get("root_forms") or []
            form = src.get("form") or (root_forms[0] if root_forms else "?")
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
def _ctis_items(rss_text: str) -> list[tuple[str, str]]:
    """
    RSS에서 (EUCT 번호, 게시시각) 목록 추출.
    같은 임상의 새 업데이트는 게시시각이 달라 다시 잡힘.
    <item> 구조를 못 찾으면 EUCT 번호만으로 후퇴.
    """
    items = re.findall(r"<item\b.*?</item>", rss_text, flags=re.S)
    out = []
    if items:
        for it in items:
            m = re.search(r"EUCT=([\d-]+)", it)
            if not m:
                continue
            pd = re.search(r"<pubDate>(.*?)</pubDate>", it, flags=re.S)
            out.append((m.group(1), pd.group(1).strip() if pd else ""))
    else:
        out = [(e, "") for e in re.findall(r"EUCT=([\d-]+)", rss_text)]
    # (EUCT, 게시시각) 조합 기준 중복 제거, 순서 유지
    return list(dict.fromkeys(out))


def run_ctis() -> tuple[int, int]:
    rss_url = "https://euclinicaltrials.eu/ctis-public-api/rss/updates.rss"
    scanned = matched = 0

    r = requests.get(rss_url, params={"search_criteria": "{}"},
                     headers=CTIS_HEADERS, timeout=30)
    if r.status_code != 200:
        tg_send(f"🚨 CTIS RSS 응답 {r.status_code}")
        return 0, 0

    items = _ctis_items(r.text)[:60]

    for euct, pubdate in items:
        scanned += 1
        dedup_id = f"{euct}:{pubdate}" if pubdate else euct
        if was_seen("ctis", dedup_id):
            continue
        try:
            d = requests.get(
                f"https://euclinicaltrials.eu/ctis-public-api/retrieve/{euct}",
                headers=CTIS_HEADERS, timeout=20,
            )
            if d.status_code != 200:
                continue
            kw = match_korean(d.text)
            if not kw:
                continue

            # v3 키(EUCT 단독)로 이미 본 임상이면 '변경', 아니면 '신규'
            label = "업데이트" if was_seen("ctis", euct) else "새 공시"
            mark_seen("ctis", dedup_id)
            mark_seen("ctis", euct)

            try:
                j = d.json()
                title = str(j.get("shortTitle") or j.get("title") or euct)[:150]
            except Exception:
                title = euct

            alert(
                "🇪🇺", "CTIS (유럽)", title, kw,
                pubdate or datetime.utcnow().strftime("%Y-%m-%d"),
                f"https://euclinicaltrials.eu/search-for-clinical-trials/?lang=en&EUCT={euct}",
                f"EUCT 번호: {euct}",
                label=label,
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
    ap.add_argument("--quiet", action="store_true",
                    help="매칭 0건이면 요약도 보내지 않음")
    args = ap.parse_args()

    started = time.time()
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=args.hours)).strftime("%Y-%m-%d")
    # CT.gov 날짜는 미 동부시간 기준 + 예약 실행 누락 대비 → 하루 더 넉넉히 조회
    # (중복 제거가 NCT+날짜 기준이라 범위를 넓혀도 중복 알림은 없음)
    ct_cutoff = (now - timedelta(hours=args.hours) - timedelta(days=1)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    print(f"[BioWatch v4] 시작 {now.isoformat()} UTC / lookback {args.hours}h "
          f"(cutoff {cutoff}, CT cutoff {ct_cutoff}) / 키워드 {len(KOREAN_KEYWORDS)}개")
    results = {}
    warnings: list[str] = []

    for name, fn in [
        ("ClinicalTrials", lambda: run_clinicaltrials(ct_cutoff, warnings)),
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
    elapsed = time.time() - started
    kst = now + KST

    # 0건이어도 요약 발송 — 메시지가 아예 안 오면 그때만 고장
    if total > 0 or warnings or not args.quiet:
        lines = [
            f"📊 <b>BioWatch 스캔 결과</b> "
            f"({now.strftime('%m-%d %H:%M')} UTC / {kst.strftime('%H:%M')} KST)\n"
        ]
        for k, (s, m) in results.items():
            lines.append(f"• {k}: {s:,}건 스캔 → <b>{m}건</b> 알림")
        if total == 0:
            lines.append("\n신규 매칭 없음 (정상 동작)")
        for w in warnings:
            lines.append(f"⚠️ {w}")
        lines.append(f"\n⏱ 소요 {elapsed:.0f}초")
        tg_send("\n".join(lines))

    print(f"[BioWatch v4] 완료. 총 {total}건 알림. ({elapsed:.0f}초)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
