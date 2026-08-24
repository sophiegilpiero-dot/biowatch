"""
BioWatch 메인 실행 스크립트
GitHub Actions에서 30분마다 실행
"""
import sys
import traceback
from datetime import datetime
from src.crawl_clinicaltrials import fetch_and_notify as ct_fetch
from src.crawl_sec import fetch_and_notify as sec_fetch
from src.crawl_mfds import fetch_and_notify as mfds_fetch
from src.telegram_notify import send_summary, send_error

# 30분 주기이므로 lookback을 1.5시간으로 설정 (겹침 여유분 포함)
# 중복 제거는 cache.py가 담당하므로 중복 알림 없음
LOOKBACK_HOURS = 2


def main():
    print(f"[BioWatch] 시작: {datetime.utcnow().isoformat()} UTC")
    counts = {}

    # 1. ClinicalTrials.gov
    try:
        print("[1/3] ClinicalTrials.gov 스캔 중...")
        counts["clinicaltrials"] = ct_fetch(LOOKBACK_HOURS)
        print(f"  → {counts['clinicaltrials']}건 신규")
    except Exception as e:
        send_error("clinicaltrials", traceback.format_exc()[:500])
        counts["clinicaltrials"] = 0

    # 2. SEC EDGAR
    try:
        print("[2/3] SEC EDGAR 스캔 중...")
        counts["sec"] = sec_fetch(LOOKBACK_HOURS)
        print(f"  → {counts['sec']}건 신규")
    except Exception as e:
        send_error("sec", traceback.format_exc()[:500])
        counts["sec"] = 0

    # 3. 의약품안전나라
    try:
        print("[3/3] 의약품안전나라 스캔 중...")
        counts["mfds"] = mfds_fetch(LOOKBACK_HOURS)
        print(f"  → {counts['mfds']}건 신규")
    except Exception as e:
        send_error("mfds", traceback.format_exc()[:500])
        counts["mfds"] = 0

    # 요약 발송 (신규 건 있을 때만)
    send_summary(counts)

    total = sum(counts.values())
    print(f"[BioWatch] 완료. 총 {total}건 알림 발송.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
