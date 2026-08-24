"""
텔레그램 봇 알림 발송 모듈
"""
import os
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

EMOJI = {
    "clinicaltrials": "🧪",
    "sec": "📋",
    "mfds": "💊",
    "euctr": "🇪🇺",
    "ema": "🏥",
    "error": "🚨",
    "summary": "📊",
}

SOURCE_LABEL = {
    "clinicaltrials": "ClinicalTrials.gov",
    "sec": "SEC EDGAR",
    "mfds": "의약품안전나라",
    "euctr": "EUCTR (유럽 임상시험)",
    "ema": "EMA (유럽 의약품청)",
}


def _send(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[텔레그램] 환경변수 미설정 — 콘솔 출력으로 대체:")
        print(text)
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[텔레그램 발송 실패] {e}")
        return False


def send_alert(source: str, item: dict) -> bool:
    emoji = EMOJI.get(source, "📌")
    label = SOURCE_LABEL.get(source, source.upper())
    
    date_str = item.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    keyword = item.get("matched_keyword", "")
    
    lines = [
        f"{emoji} <b>[{label}] 새 공시 감지</b>",
        f"",
        f"📅 <b>날짜:</b> {date_str}",
        f"🏢 <b>감지 키워드:</b> {keyword}",
        f"📌 <b>제목:</b> {item.get('title', 'N/A')}",
        f"",
        f"📝 <b>요약:</b>",
        f"{item.get('summary', '요약 없음')[:400]}",
        f"",
        f"🔗 <a href=\"{item.get('url', '#')}\">원문 보기</a>",
    ]
    
    return _send("\n".join(lines))


def send_summary(counts: dict) -> bool:
    total = sum(counts.values())
    if total == 0:
        return True

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"📊 <b>BioWatch 스캔 완료</b> ({now})",
        f"",
    ]
    for source, count in counts.items():
        emoji = EMOJI.get(source, "📌")
        label = SOURCE_LABEL.get(source, source)
        lines.append(f"{emoji} {label}: <b>{count}건</b> 신규")
    
    lines += ["", f"총 <b>{total}건</b> 알림 발송됨"]
    return _send("\n".join(lines))


def send_error(source: str, error_msg: str) -> bool:
    text = (
        f"🚨 <b>[BioWatch 오류]</b>\n"
        f"소스: {source}\n"
        f"오류: {error_msg[:300]}"
    )
    return _send(text)
