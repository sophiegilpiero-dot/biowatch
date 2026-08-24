"""
ClinicalTrials.gov API v2 크롤러
- 전체 텍스트에서 한국 기업/기관명 매칭
- 스폰서, 공동연구자, 기관, 상태, 적응증 등 모든 필드 검색
"""
import requests
from datetime import datetime, timedelta
from src.korean_biotech_filter import is_korean_entity
from src.cache import is_new
from src.telegram_notify import send_alert, send_error

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

# 검사할 필드 (전체 텍스트 커버)
FIELDS_TO_CONCAT = [
    "protocolSection.identificationModule.briefTitle",
    "protocolSection.identificationModule.officialTitle",
    "protocolSection.identificationModule.organization.fullName",
    "protocolSection.sponsorCollaboratorsModule.leadSponsor.name",
    "protocolSection.sponsorCollaboratorsModule.collaborators",
    "protocolSection.descriptionModule.briefSummary",
    "protocolSection.descriptionModule.detailedDescription",
    "protocolSection.conditionsModule.conditions",
    "protocolSection.conditionsModule.keywords",
    "protocolSection.contactsLocationsModule.locations",
    "protocolSection.contactsLocationsModule.centralContacts",
    "protocolSection.armsInterventionsModule.interventions",
]


def _safe_get(d: dict, dotted_key: str) -> str:
    """중첩 dict에서 점 표기법으로 값 추출"""
    keys = dotted_key.split(".")
    val = d
    for k in keys:
        if not isinstance(val, dict):
            return ""
        val = val.get(k, "")
    if isinstance(val, list):
        return " ".join(str(i) for i in val)
    return str(val) if val else ""


def _extract_full_text(study: dict) -> str:
    """연구 전체 텍스트 추출"""
    parts = []
    for field in FIELDS_TO_CONCAT:
        parts.append(_safe_get(study, field))
    # JSON 전체를 문자열로도 추가 (놓치는 필드 없게)
    import json
    parts.append(json.dumps(study, ensure_ascii=False))
    return " ".join(parts)


def _parse_study(study: dict) -> dict:
    """API 응답에서 필요한 정보 추출"""
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


def fetch_and_notify(lookback_hours: int = 1) -> int:
    """
    최근 lookback_hours 시간 이내에 업데이트된 연구 중
    한국 관련 항목을 찾아 텔레그램 알림 발송
    Returns: 발송 건수
    """
        since = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime(
        "%Y-%m-%d"
    )

    params = {
        "filter.lastUpdatePostDate.gte": since,
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
            full_text = _extract_full_text(study)
            matched, keyword = is_korean_entity(full_text)

            if not matched:
                continue

            parsed = _parse_study(study)

            if not is_new("clinicaltrials", parsed["id"]):
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
