# 🚀 GitHub Actions 설정 가이드

배민외식업광장 슬롯 모니터링을 GitHub Actions에서 자동으로 실행하는 방법입니다.

---

## 📋 필요한 것

1. **GitHub 계정** (무료)
2. **Google Cloud 프로젝트** (무료)
3. **Google Sheets** (무료)

---

## 🔧 설정 단계

### 1단계: GitHub 저장소 생성

1. [GitHub](https://github.com) 접속
2. 우측 상단 **+** → **New repository**
3. Repository name: `baemmin-monitor`
4. **Private** 선택 (보안을 위해)
5. **Create repository** 클릭

---

### 2단계: 파일 업로드

GitHub 저장소에 다음 파일들을 업로드:

```
baemmin-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml     ← 워크플로우 파일
├── main.py                 ← 메인 스크립트
├── sheets_manager.py       ← Sheets 연동
├── requirements.txt        ← 의존성 목록
└── README.md               ← 이 파일
```

**업로드 방법:**
1. 저장소 페이지에서 **Add file** → **Upload files**
2. 모든 파일 드래그 앤 드롭
3. **Commit changes** 클릭

> ⚠️ `.github/workflows/` 폴더 구조를 정확히 유지해야 합니다!

---

### 3단계: Google Sheets API 설정

#### 3-1. Google Cloud Console 설정

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성:
   - 프로젝트 이름: `baemmin-monitor`
   - **만들기** 클릭
3. 프로젝트 선택 후 진행

#### 3-2. API 활성화

1. 좌측 메뉴 → **API 및 서비스** → **라이브러리**
2. 검색: `Google Sheets API`
3. **사용 설정** 클릭
4. 검색: `Google Drive API`
5. **사용 설정** 클릭

#### 3-3. 서비스 계정 생성

1. **API 및 서비스** → **사용자 인증 정보**
2. **사용자 인증 정보 만들기** → **서비스 계정**
3. 서비스 계정 이름: `baemmin-monitor`
4. **만들고 계속하기** 클릭
5. 역할: `편집자` 선택
6. **완료** 클릭

#### 3-4. JSON 키 다운로드

1. 생성된 서비스 계정 클릭
2. **키** 탭 → **키 추가** → **새 키 만들기**
3. **JSON** 선택 → **만들기**
4. `credentials.json` 파일 자동 다운로드됨

> 📌 이 파일 내용을 GitHub Secrets에 저장합니다!

---

### 4단계: Google Sheets 준비

1. [Google Sheets](https://sheets.google.com) 에서 새 스프레드시트 생성
2. 이름: `배민 모니터링 로그`
3. 스프레드시트 ID 확인:
   - URL: `https://docs.google.com/spreadsheets/d/`**여기가_ID**`/edit`
   - 예: `1abc123def456ghi789jkl`
4. **공유** 버튼 클릭
5. 서비스 계정 이메일 추가:
   - `baemmin-monitor@프로젝트ID.iam.gserviceaccount.com`
   - 권한: **편집자**
   - **공유** 클릭

---

### 5단계: GitHub Secrets 설정

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭

#### Secret 1: GOOGLE_CREDENTIALS
- Name: `GOOGLE_CREDENTIALS`
- Secret: `credentials.json` 파일 내용 전체 복사/붙여넣기

```json
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  ...
}
```

#### Secret 2: SPREADSHEET_ID
- Name: `SPREADSHEET_ID`
- Secret: 스프레드시트 ID (예: `1abc123def456ghi789jkl`)

#### Secret 3: TARGET_URL (선택사항)
- Name: `TARGET_URL`
- Secret: 모니터링할 URL (기본값: 배민사장님광장)

---

### 6단계: 실행 확인

#### 자동 실행
- 매일 오전 10시 (한국시간) 자동 실행
- cron: `0 1 * * *` (UTC 01:00 = KST 10:00)

#### 수동 실행 (테스트)
1. GitHub 저장소 → **Actions** 탭
2. **배민외식업광장 슬롯 모니터링** 클릭
3. **Run workflow** → **Run workflow** 클릭
4. 실행 로그 확인

---

## 📊 결과 확인

### Google Sheets
매 실행마다 새로운 행이 추가됩니다:

| 날짜 | 시간 | 상태 | 슬롯수 | 링크수 | 깨진링크 | ... |
|------|------|------|--------|--------|----------|-----|
| 2026-02-05 | 10:00:00 | success | 15 | 45 | 0 | ... |

### GitHub Actions Artifacts
- **screenshots**: 페이지 스크린샷 (7일 보관)
- **logs**: 실행 로그 (30일 보관)

---

## ⚙️ 커스터마이징

### 실행 시간 변경

`.github/workflows/monitor.yml` 파일에서:

```yaml
schedule:
  # 매일 오전 9시 (한국시간)
  - cron: '0 0 * * *'
  
  # 매일 오전 10시 (한국시간) - 기본값
  - cron: '0 1 * * *'
  
  # 매일 오후 2시 (한국시간)
  - cron: '0 5 * * *'
  
  # 평일만 (월-금)
  - cron: '0 1 * * 1-5'
  
  # 하루 2번 (오전 10시, 오후 6시)
  - cron: '0 1,9 * * *'
```

### 모니터링 URL 변경

1. GitHub Settings → Secrets에서 `TARGET_URL` 수정
2. 또는 `main.py`의 `Config.TARGET_URL` 수정

### 슬롯 선택자 수정

`main.py`의 `Config.SLOT_SELECTORS`를 실제 사이트 구조에 맞게 수정:

```python
SLOT_SELECTORS = {
    'main_banner': '.your-banner-class',
    'content_cards': '.your-card-class',
    # ...
}
```

---

## 🔧 문제 해결

### 워크플로우가 실행되지 않음
1. `.github/workflows/monitor.yml` 경로 확인
2. Actions 탭에서 워크플로우 활성화 확인
3. Repository Settings → Actions → General → "Allow all actions" 확인

### Google Sheets 오류
1. `GOOGLE_CREDENTIALS` Secret이 올바른 JSON인지 확인
2. 서비스 계정에 스프레드시트 편집 권한 부여 확인
3. `SPREADSHEET_ID`가 정확한지 확인

### 페이지 로드 실패
1. `TARGET_URL`이 유효한지 확인
2. 사이트가 봇 차단을 하는지 확인
3. Actions 로그에서 상세 오류 확인

### 스크린샷이 검은 화면
- 페이지 로드 시간 부족 → `time.sleep()` 증가
- JavaScript 렌더링 필요 → 대기 시간 증가

---

## 💡 팁

### 비용
- **GitHub Actions**: 월 2,000분 무료 (하루 1회 실행 시 약 3분 × 30일 = 90분/월)
- **Google Sheets API**: 무료 (일 500요청 이하)
- **총 비용: 무료! 🎉**

### 알림 추가 (선택사항)

#### Slack 알림
```yaml
- name: Slack 알림
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook: ${{ secrets.SLACK_WEBHOOK }}
```

#### 이메일 알림
```yaml
- name: 이메일 알림
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.gmail.com
    # ...
```

---

## 📞 지원

문제가 있으면:
1. GitHub Issues에 문의
2. Actions 실행 로그 확인
3. Claude에게 다시 물어보기! 😊

---

**Happy Monitoring! 🚀**
