# BioWatch 🧪📋💊

한국 바이오/제약 기업 관련 공시를 실시간 추적해 텔레그램으로 알리는 시스템.

## 추적 소스
| 소스 | 내용 |
|------|------|
| 🧪 ClinicalTrials.gov | 임상시험 등록/업데이트 (전체 텍스트에서 한국 기업명 매칭) |
| 📋 SEC EDGAR | 6-K, 20-F, 8-K 등 공시에 한국 기업 언급 포함 |
| 💊 의약품안전나라 | 임상시험 승인, 품목허가 신규 정보 |

## 설정 방법

### 1단계 — 텔레그램 봇 만들기

1. 텔레그램에서 `@BotFather` 검색
2. `/newbot` 명령 → 봇 이름 설정
3. 발급된 **Bot Token** 복사
4. 본인 채팅창에서 `@userinfobot` 검색 → 본인 **Chat ID** 확인

### 2단계 — GitHub 저장소 생성 & 코드 업로드

```bash
git init
git add .
git commit -m "BioWatch 초기 설정"
git remote add origin https://github.com/[YOUR_ID]/biowatch.git
git push -u origin main
```

### 3단계 — GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 |
|-------------|-----|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 받은 토큰 |
| `TELEGRAM_CHAT_ID` | 본인 Chat ID (숫자) |
| `MFDS_API_KEY` | 공공데이터포털 API 키 (선택, 없어도 동작) |

### 4단계 — 의약품안전나라 API 키 발급 (선택)

더 많은 데이터를 받으려면:
1. https://www.data.go.kr 접속
2. "임상시험" 검색 → "임상시험 현황 정보" API 신청 (무료)
3. 발급된 키를 `MFDS_API_KEY` Secret에 등록

### 5단계 — 실행 확인

- GitHub Actions 탭 → **BioWatch** 워크플로우 확인
- **Run workflow** 버튼으로 수동 테스트
- 30분마다 자동 실행됨

## 알림 예시

```
🧪 [ClinicalTrials.gov] 새 공시 감지

📅 날짜: 2024-01-15
🏢 감지 키워드: celltrion
📌 제목: A Phase 3 Study of CT-P17 in Patients with RA

📝 요약:
[PHASE3] Rheumatoid Arthritis
스폰서: Celltrion | 상태: RECRUITING

🔗 원문 보기
```

## 기업 키워드 추가

`src/korean_biotech_filter.py`의 `KOREAN_COMPANIES` 리스트에 추가:

```python
KOREAN_COMPANIES = [
    ...
    "추가할 기업명 영문",  # 새 기업
]
```

## 로컬 테스트

```bash
pip install -r requirements.txt

# 텔레그램 없이 콘솔 출력으로 테스트
python main.py

# 텔레그램 발송 포함 테스트
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python main.py
```
