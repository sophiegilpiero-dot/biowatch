"""
SEC EDGAR Full-Text Search API 크롤러
- EDGAR의 /efts/v1/search 엔드포인트 사용
- 한국 바이오/제약 기업명으로 전체 텍스트 검색
- 6-K, 20-F, SC 13G, 424B 등 주요 공시 유형 포함
"""
import requests
from datetime import datetime, timedelta
from src.korean_biotech_filter import KOREAN_COMPANIES, KOREAN_INSTITUTIONS
from src.cache import is_new
from src.telegram_notify import send_alert, send_error

BASE_URL = "https://efts.sec.gov/LATEST/search-index"
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"

# 실제 EDGAR Full-Text Search API
EDGAR_FTS_URL = "https://efts.sec.gov/LATEST/search-index"

# 주요 공시 유형
FORM_TYPES = ["6-K", "20-F", "F-1", "F-3", "SC 13G", "SC 13D", "424B4", "8-K", "10-K"]

# 검색할 한국 기업 핵심 키워드 (너무 일반적인 단어 제외)
SEARCH_KEYWORDS = [
    kw for kw in KOREAN_COMPANIES
    if len(kw) > 4 and not any(c in kw for c in ["약품", "제약", "바이오", "의료"])
]


def _search_edgar(query: str, date_from: str, date_to: str) -> list[dict]:
    """EDGAR Full-Text Search"""
    url = "https://efts.sec.gov/LATEST/search-index"
    
    # EDGAR의 공식 검색 API
    api_url = "https://efts.sec.gov/LATEST/search-index"
    
    # 올바른 EDGAR EFTS 엔드포인트
    search_url = "https://efts.sec.gov/LATEST/search-index"
    
    # EDGAR Full-Text Search API v1
    endpoint = "https://efts.sec.gov/LATEST/search-index"
    
    try:
        params = {
            "q": f'"{query}"',
            "dateRange": "custom",
            "startdt": date_from,
            "enddt": date_to,
            "forms": ",".join(FORM_TYPES),
        }
        
        # 정식 EDGAR 검색 API
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers={"User-Agent": "BioWatch research@biowatch.kr"},
            timeout=20,
        )
        
        # EDGAR Full Text Search
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": f'"{query}"',
                "dateRange": "custom", 
                "startdt": date_from,
                "enddt": date_to,
            },
            headers={"User-Agent": "BioWatch contact@example.com"},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("hits", {}).get("hits", [])
    except Exception:
        return []


def _search_edgar_official(query: str, date_from: str) -> list[dict]:
    """EDGAR Full-Text Search (공식 엔드포인트)"""
    try:
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": f'"{query}"',
                "dateRange": "custom",
                "startdt": date_from,
                "enddt": datetime.utcnow().strftime("%Y-%m-%d"),
                "forms": ",".join(FORM_TYPES),
            },
            headers={"User-Agent": "BioWatch biowatch@example.com"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("hits", {}).get("hits", [])
    except Exception:
        return []


def _real_edgar_search(query: str, date_from: str) -> list[dict]:
    """
    실제 EDGAR Full-Text Search API
    https://efts.sec.gov/LATEST/search-index?q="query"&dateRange=custom&startdt=...
    """
    try:
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": f'"{query}"',
                "dateRange": "custom",
                "startdt": date_from,
                "enddt": datetime.utcnow().strftime("%Y-%m-%d"),
            },
            headers={
                "User-Agent": "BioWatch Tracker biowatch@example.com",
                "Accept": "application/json",
            },
            timeout=20,
        )
        if resp.status_code == 200:
            return resp.json().get("hits", {}).get("hits", [])
        return []
    except Exception:
        return []


def fetch_and_notify(lookback_hours: int = 1) -> int:
    """
    최근 N시간 이내 EDGAR 공시 중 한국 기업 관련 항목 알림
    """
    date_from = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d")
    date_to = datetime.utcnow().strftime("%Y-%m-%d")

    seen_filings = set()
    count = 0

    # 주요 한국 기업들을 직접 검색 (전체 텍스트에서 언급 포함)
    search_terms = [
        # 영문 기업명 핵심
        "celltrion", "samsung bioepis", "samsung biologics",
        "hanmi pharma", "yuhan", "daewoong", "boryung",
        "cha biotech", "hugel", "medytox", "genexine",
        "alteogen", "helixmith", "kolon life science",
        "sk bioscience", "sk biopharma", "lotte biologics",
        "gc pharma", "green cross", "kangstem biotech",
        "bridge biotherapeutics", "tiumbio", "medpacto",
        "gi innovation", "hanall biopharma", "ildong",
        "dong-a st", "jw pharmaceutical", "chong kun dang",
        "korean biotech", "korea pharma",
    ]

    for term in search_terms:
        try:
            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q": f'"{term}"',
                    "dateRange": "custom",
                    "startdt": date_from,
                    "enddt": date_to,
                },
                headers={
                    "User-Agent": "BioWatch Tracker biowatch@example.com",
                    "Accept": "application/json",
                },
                timeout=20,
            )
            if resp.status_code != 200:
                continue

            hits = resp.json().get("hits", {}).get("hits", [])

            for hit in hits:
                src = hit.get("_source", {})
                filing_id = src.get("file_date", "") + src.get("entity_name", "") + src.get("file_num", "")

                if filing_id in seen_filings:
                    continue
                seen_filings.add(filing_id)

                raw_id = src.get("accession_no", filing_id)
                if not is_new("sec", raw_id):
                    continue

                accession = src.get("accession_no", "").replace("-", "")
                cik = src.get("entity_id", "")
                doc_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
                    if cik and accession
                    else "https://www.sec.gov/cgi-bin/browse-edgar"
                )

                item = {
                    "id": raw_id,
                    "title": f"[{src.get('form_type', 'N/A')}] {src.get('entity_name', 'N/A')}",
                    "matched_keyword": term,
                    "date": src.get("file_date", date_to),
                    "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={src.get('file_num', '')}&type={src.get('form_type', '')}&dateb=&owner=include&count=10",
                    "summary": (
                        f"공시유형: {src.get('form_type', 'N/A')}\n"
                        f"기업명: {src.get('entity_name', 'N/A')}\n"
                        f"접수일: {src.get('file_date', 'N/A')}\n"
                        f"감지 키워드: '{term}'\n\n"
                        f"{src.get('period_of_report', '')}"
                    ),
                }
                # URL을 EDGAR viewer로 개선
                if src.get("accession_no"):
                    item["url"] = f"https://www.sec.gov/Archives/edgar/data/{cik}/{src['accession_no'].replace('-','')}/{src['accession_no']}-index.htm"

                send_alert("sec", item)
                count += 1

        except Exception as e:
            send_error("sec", f"검색어 '{term}' 오류: {str(e)[:200]}")
            continue

    return count
