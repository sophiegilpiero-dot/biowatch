import requests
from datetime import datetime
from src.korean_biotech_filter import is_korean_entity
from src.cache import is_new
from src.telegram_notify import send_alert, send_error

HEADERS = {
    "User-Agent": "BioWatch Tracker biowatch@example.com",
    "Accept": "application/json, text/xml, */*",
}

EUCTR_TERMS = [
    "celltrion", "samsung bioepis", "samsung biologics",
    "hanmi", "yuhan", "daewoong", "boryung",
    "hugel", "medytox", "genexine", "alteogen",
    "sk bioscience", "sk biopharma", "lotte biologics",
    "gc pharma", "green cross", "kangstem",
    "bridge biotherapeutics", "tiumbio", "medpacto",
    "gi innovation", "hanall", "ildong",
    "dong-a", "jw pharmaceutical", "chong kun dang",
    "seegene", "abl bio", "aprilbio",
    "kolon life science", "kolon tissue gene",
    "helixmith", "bioneer", "macrogen",
    "eubiologics", "toolgen", "theragen",
    "Korea", "Korean company",
]

EMA_TERMS = [
    "celltrion", "samsung bioepis", "hanmi", "yuhan",
    "daewoong", "hugel", "medytox", "sk biopharma",
    "lotte biologics", "gc pharma", "green cross",
    "korea", "korean",
]


def fetch_euctr_and_notify(lookback_hours: int = 2) -> int:
    count = 0
    seen = set()

    for term in EUCTR_TERMS:
        try:
            resp = requests.get(
                "https://www.clinicaltrialsregister.eu/ctr-search/rest/download/summary",
                params={"query": term, "format": "json", "pageSize": 100},
                headers=HEADERS,
                timeout=20,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            trials = data if isinstance(data, list) else data.get("results", [])

            for t in trials:
                trial_id = t.get("eudractNumber", t.get("id", ""))
                if not trial_id or trial_id in seen:
                    continue
                seen.add(trial_id)

                if not is_new("euctr", trial_id):
                    continue

                full_text = " ".join(str(v) for v in t.values())
                _, kw = is_korean_entity(full_text)

                send_alert("euctr", {
                    "id": trial_id,
                    "title": t.get("trialTitle", t.get("title", "N/A")),
                    "matched_keyword": kw or term,
                    "date": t.get("trialStartDate", datetime.utcnow().strftime("%Y-%m-%d")),
                    "url": f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{trial_id}/",
                    "summary": (
                        f"[{t.get('trialPhase', 'N/A')}] {t.get('medicalCondition', 'N/A')}\n"
                        f"스폰서: {t.get('sponsorName', 'N/A')}\n"
                        f"상태: {t.get('trialStatus', 'N/A')}\n"
                        f"국가: {t.get('countriesOfRecruitment', 'N/A')}"
                    ),
                })
                count += 1

        except Exception as e:
            send_error("euctr", f"'{term}' 오류: {str(e)[:200]}")

    return count


def fetch_ema_and_notify(lookback_hours: int = 2) -> int:
    count = 0
    seen = set()

    for term in EMA_TERMS:
        try:
            resp = requests.get(
                "https://medicines.europa.eu/api/medicines",
                params={"keyword": term, "page": 0, "pageSize": 20},
                headers=HEADERS,
                timeout=20,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            items = data.get("content", data.get("results", []))

            for item in items:
                item_id = str(item.get("id", item.get("productNumber", "")))
                if not item_id or item_id in seen:
                    continue
                seen.add(item_id)

                if not is_new("ema", item_id):
                    continue

                full_text = " ".join(str(v) for v in item.values())
                _, kw = is_korean_entity(full_text)

                send_alert("ema", {
                    "id": item_id,
                    "title": f"[EMA] {item.get('name', item.get('medicineName', 'N/A'))}",
                    "matched_keyword": kw or term,
                    "date": item.get("decisionDate", datetime.utcnow().strftime("%Y-%m-%d")),
                    "url": f"https://medicines.europa.eu/human-medicines/{item_id}",
                    "summary": (
                        f"적응증: {item.get('therapeuticArea', 'N/A')}\n"
                        f"활성성분: {item.get('activeSubstance', 'N/A')}\n"
                        f"상태: {item.get('authorisationStatus', 'N/A')}"
                    ),
                })
                count += 1

        except Exception:
            continue

    return count
