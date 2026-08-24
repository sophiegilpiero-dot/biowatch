"""
ClinicalTrials.gov API v2 크롤러
- 전체 텍스트에서 한국 기업/기관명 매칭
"""
import json
import requests
from datetime import datetime, timedelta
from src.korean_biotech_filter import is_korean_entity
from src.cache import is_new
from src.telegram_notify import send_alert, send_error

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def _parse_study(study: dict) -> dict:
    ps = study.get("protocolSection", {})
    id_mod = ps.get("identificationModule", {})
    sponsor_mod = ps.get("sponsorCollaboratorsModule", {})
    status_mod = ps.get("statusModule", {})
    desc_mod = ps.get("descriptionModule", {})
    cond_mod = ps.get("conditionsModule", {})

    nct_id = id_mod.get("nctId", "")
    title = id_mod.get("briefTitle", "")
    sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "")
    status = status_mod.get("overallStatus", "")
    phase = ps.get("designModule", {}).get("phases", [])
    conditions = ", ".join(cond_mod.get("conditions", []))
    summary = desc_mod.get("briefSummary", "")
    start_date = status_mod.get("startDateStruct", {}).get("date", "")

    return {
        "id": nct_id,
        "title": title,
        "sponsor": sponsor,
        "status": status,
        "phase": ", ".join(phase) if phase else "N/A",
        "conditions": conditions,
        "summary": summary[:500],
        "date": start_date or datetime.utcnow().strftime("%Y-%m-%d"),
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
    }


def fetch_and_notify(lookback_hours: int = 2) -> int:
    # 날짜만 사용 (시간 포함하면 400 오류)
    since = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d")

    params = {
        "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{since},MAX]",
        "pageSize": 100,
        "format": "json",
    }

    count = 0
    next_page_token = None

    while True:
        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            send_error("clinicaltrials", str(e))
            break

        studies = data.get("studies", [])

        for study in studies:
            # 연구 전체 JSON을 텍스트로 변환해 매칭 (누락 필드 없게)
            full_text = json.dumps(study, ensure_ascii=False)
            matched, keyword = is_korean_entity(full_text)

            if not matched:
                continue

            parsed = _parse_study(study)

            if not parsed["id"] or not is_new("clinicaltrials", parsed["id"]):
                continue

            parsed["matched_keyword"] = keyword
            parsed["summary"] = (
                f"[{parsed['phase']}] {parsed['conditions']}\n"
                f"스폰서: {parsed['sponsor']} | 상태: {parsed['status']}\n\n"
                f"{parsed['summary']}"
            )

            send_alert("clinicaltrials", parsed)
            count += 1

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return count
