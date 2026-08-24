"""
의약품안전나라 (식약처) 크롤러
- 임상시험 승인 정보: https://nedrug.mfds.go.kr
- 의약품 품목허가 정보
- OpenAPI 키 없이 사용 가능한 공개 API 우선, 
  필요시 공공데이터포털(data.go.kr) API 활용
"""
import requests
from datetime import datetime, timedelta
from src.korean_biotech_filter import is_korean_entity
from src.cache import is_new
from src.telegram_notify import send_alert, send_error

# 공공데이터포털 API (환경변수로 키 관리)
import os
MFDS_API_KEY = os.environ.get("MFDS_API_KEY", "")

# 의약품안전나라 임상시험 정보 API (공공데이터포털 제공)
CLINICAL_APPROVAL_URL = "https://apis.data.go.kr/1471000/ClinicalTrialInfo/getClinicalTrialInfo"

# 의약품 품목허가 API
DRUG_APPROVAL_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService04/getDrugPrdtPrmsnDtlInq04"

# 의약품안전나라 직접 검색 (API 키 없이)
NEDRUG_BASE = "https://nedrug.mfds.go.kr"


def _fetch_clinical_approvals(date_from: str) -> list[dict]:
    """임상시험 승인 정보 조회"""
    if not MFDS_API_KEY:
        return _fetch_nedrug_clinical(date_from)

    try:
        params = {
            "serviceKey": MFDS_API_KEY,
            "pageNo": 1,
            "numOfRows": 100,
            "type": "json",
            "apprvDe": date_from.replace("-", ""),  # YYYYMMDD
        }
        resp = requests.get(CLINICAL_APPROVAL_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("body", {}).get("items", [])
        return items if isinstance(items, list) else []
    except Exception as e:
        send_error("mfds", f"임상시험 API 오류: {str(e)[:200]}")
        return _fetch_nedrug_clinical(date_from)


def _fetch_nedrug_clinical(date_from: str) -> list[dict]:
    """
    의약품안전나라 임상시험 검색 (공개 웹 API)
    API 키 없이 접근 가능한 엔드포인트
    """
    results = []
    try:
        # 의약품안전나라 임상시험 검색 API
        url = "https://nedrug.mfds.go.kr/pbp/CCBGA01/getItem"
        params = {
            "pageNo": 1,
            "limit": 100,
            "sortKey": "recentDate",
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        
        data = resp.json()
        for item in data.get("list", []):
            results.append({
                "id": item.get("apprvNo", ""),
                "title": item.get("prductNm", ""),
                "company": item.get("entrpsNm", ""),
                "approval_date": item.get("apprvDe", ""),
                "indication": item.get("efcyQesitm", ""),
                "source": "nedrug_clinical",
            })
    except Exception:
        pass
    
    return results


def _fetch_drug_approvals(date_from: str) -> list[dict]:
    """품목허가 신규 승인 조회"""
    if not MFDS_API_KEY:
        return _fetch_nedrug_drug(date_from)
    
    try:
        params = {
            "serviceKey": MFDS_API_KEY,
            "pageNo": 1,
            "numOfRows": 100,
            "type": "json",
            "permtDate": date_from.replace("-", ""),
        }
        resp = requests.get(DRUG_APPROVAL_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("body", {}).get("items", [])
        return items if isinstance(items, list) else []
    except Exception as e:
        send_error("mfds", f"품목허가 API 오류: {str(e)[:200]}")
        return _fetch_nedrug_drug(date_from)


def _fetch_nedrug_drug(date_from: str) -> list[dict]:
    """의약품안전나라 품목허가 검색 (공개 API)"""
    results = []
    try:
        url = "https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetail"
        params = {
            "pageNo": 1,
            "limit": 100,
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("list", []):
            results.append({
                "id": item.get("itemSeq", ""),
                "title": item.get("itemName", ""),
                "company": item.get("entpName", ""),
                "approval_date": item.get("permitDate", ""),
                "ingredient": item.get("ingr", ""),
                "indication": item.get("efcyQesitm", ""),
                "source": "nedrug_drug",
            })
    except Exception:
        pass
    return results


def _fetch_clinical_from_data_go_kr(date_from: str) -> list[dict]:
    """
    공공데이터포털 임상시험 현황 API
    https://www.data.go.kr/data/15103027/openapi.do
    """
    if not MFDS_API_KEY:
        return []
    
    results = []
    try:
        # 임상시험 현황 정보
        url = "https://apis.data.go.kr/1471000/ClincalExam/getClincalExamList"
        params = {
            "serviceKey": MFDS_API_KEY,
            "pageNo": "1",
            "numOfRows": "100",
            "type": "json",
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        
        body = data.get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if not isinstance(items, list):
            items = [items] if items else []
            
        for item in items:
            results.append({
                "id": item.get("apprvNo", item.get("irbNo", "")),
                "title": item.get("rearchTtl", item.get("title", "")),
                "company": item.get("sponsorNm", item.get("entrpsNm", "")),
                "approval_date": item.get("apprvDe", ""),
                "phase": item.get("clinTrlPhase", ""),
                "indication": item.get("icdNm", ""),
                "source": "data_go_kr_clinical",
            })
    except Exception as e:
        pass
    return results


def fetch_and_notify(lookback_hours: int = 1) -> int:
    """
    최근 N시간 이내 의약품안전나라 공시 중
    한국 기업 관련 항목 알림 (전체 텍스트 매칭)
    """
    date_from = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d")
    count = 0

    all_items = []
    all_items.extend(_fetch_clinical_approvals(date_from))
    all_items.extend(_fetch_drug_approvals(date_from))
    all_items.extend(_fetch_clinical_from_data_go_kr(date_from))

    for item in all_items:
        # 전체 텍스트 조합 후 매칭
        full_text = " ".join([
            str(item.get("title", "")),
            str(item.get("company", "")),
            str(item.get("indication", "")),
            str(item.get("ingredient", "")),
            str(item.get("phase", "")),
        ])
        
        matched, keyword = is_korean_entity(full_text)
        # 의약품안전나라는 기본적으로 국내 공시이므로
        # 매칭 안 돼도 회사명이 있으면 포함
        company = item.get("company", "")
        if not matched and company:
            matched, keyword = True, company

        if not matched:
            continue

        raw_id = str(item.get("id", "")) + item.get("source", "")
        if not raw_id or not is_new("mfds", raw_id):
            continue

        item_id = item.get("id", "")
        source = item.get("source", "")
        
        if "clinical" in source:
            url = f"https://nedrug.mfds.go.kr/pbp/CCBGA01/getItem?recvNo={item_id}"
            type_label = "임상시험 승인"
        else:
            url = f"https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetail?itemSeq={item_id}"
            type_label = "품목허가"

        alert_item = {
            "id": raw_id,
            "title": f"[{type_label}] {item.get('title', 'N/A')}",
            "matched_keyword": keyword or company,
            "date": item.get("approval_date", date_from),
            "url": url,
            "summary": (
                f"구분: {type_label}\n"
                f"업체명: {company}\n"
                f"적응증: {item.get('indication', 'N/A')}\n"
                f"임상 단계: {item.get('phase', 'N/A')}\n"
                f"승인일: {item.get('approval_date', 'N/A')}"
            ),
        }

        send_alert("mfds", alert_item)
        count += 1

    return count
