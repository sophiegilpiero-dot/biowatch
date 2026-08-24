"""
BioWatch 메인 실행 스크립트
GitHub Actions에서 30분마다 실행

사용법:
  python main.py              # 기본 (2시간 lookback)
  python main.py --hours 48   # 최근 48시간 수동 스캔
"""
import sys
import argparse
import traceback
from datetime import datetime
from src.crawl_clinicaltrials import fetch_and_notify as ct_fetch
from src.crawl_sec import fetch_and_notify as sec_fetch
from src.crawl_mfds import fetch_and_notify as mfds_fetch
from src.crawl_europe import fetch_euctr_and_notify, fetch_ema_and_notify
from src.telegram_notify import send_summary, send_error

DEFAULT_LOOKBACK_HOURS = 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=DEFAULT_LOOKBACK_HOURS,
                        help="몇 시간 이전부터 스캔할지 (기본: 2)")
    args = parser.parse_args()
    lookback = args.hours

    print(f"[BioWatch] 시작: {datetime.utcnow().isoformat()} UTC")
    print(f"[BioWatch] Lookback: {lookback}시간")
    counts = {}

    # 1. ClinicalTrials.gov
    try:
        print("[1/5] ClinicalTrials.gov 스캔 중...")
        counts["clinicaltrials"] = ct_fetch(lookback)
        print(f"  → {counts['clinicaltrials']}건 신규")
    except Exception:
        send_error("clinicaltrials", traceback.format_exc()[:500])
        counts["clinicaltrials"] = 0

    # 2. SEC EDGAR
    try:
        print("[2/5] SEC EDGAR 스캔 중...")
        counts["sec"] = sec_fetch(lookback)
        print(f"  → {counts['sec']}건 신규")
    except Exception:
        send_error("sec", traceback.format_exc()[:500])
        counts["sec"] = 0

    # 3. 의약품안전나라
    try:
        print("[3/5] 의약품안전나라 스캔 중...")
        counts["mfds"] = mfds_fetch(lookback)
        print(f"  → {counts['mfds']}건 신규")
    except Exception:
        send_error("mfds", traceback.format_exc()[:500])
        counts["mfds"] = 0

    # 4. EUCTR (유럽 임상시험)
    try:
        print("[4/5] EUCTR 스캔 중...")
        counts["euctr"] = fetch_euctr_and_notify(lookback)
        print(f"  → {counts['euctr']}건 신규")
    except Exception:
        send_error("euctr", traceback.format_exc()[:500])
        counts["euctr"] = 0

    # 5. EMA (유럽 의약품청)
    try:
        print("[5/5] EMA 스캔 중...")
        counts["ema"] = fetch_ema_and_notify(lookback)
        print(f"  → {counts['ema']}건 신규")
    except Exception:
        send_error("ema", traceback.format_exc()[:500])
        counts["ema"] = 0

    # 요약 발송 (신규 건 있을 때만)
    send_summary(counts)

    total = sum(counts.values())
    print(f"[BioWatch] 완료. 총 {total}건 알림 발송.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
