# Patreon Gmail Member Exporter

Patreon 가입 알림 메일만 Gmail에서 읽어서 CSV/XLSX 표로 뽑는 도구입니다.

## 동작 방식

1. Gmail API에서 `no-reply@info.patreon.com` 가입 후보 메일을 검색합니다.
2. 제목과 본문에 `새로 가입했습니다`, `회원으로 가입했습니다`, `joined as`, `new member`가 있는지 다시 확인합니다.
3. 이름, 이메일, 통화, 금액을 추출합니다.
4. `통화+금액` 매핑으로 먼저 티어를 확정합니다.
5. 매핑에 없으면 Frankfurter 환율 API로 USD 환산 후 가장 가까운 티어를 추정합니다.
6. 환율 조회가 실패하면 `config.json`의 보조 환율값을 씁니다.

기본 티어는 `2.99`, `4.99`, `9.99`, `29.99` USD이고, `config.json`에서 수정할 수 있습니다.

## Gmail API 만들기

Google 공식 Python quickstart 기준 절차입니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 새 프로젝트를 만들거나 기존 프로젝트를 선택합니다.
2. [Gmail API 사용 설정](https://console.cloud.google.com/flows/enableapi?apiid=gmail.googleapis.com)을 엽니다.
3. Google Auth Platform 또는 OAuth 동의 화면을 설정합니다.
   - 개인 Gmail이면 보통 `External`로 만들고, 게시 상태는 `Testing`으로 둔 뒤 본인 Gmail을 테스트 사용자에 추가합니다.
   - Workspace 조직 내부용이면 `Internal`을 쓸 수 있습니다.
4. OAuth 클라이언트를 만듭니다.
   - Application type: `Desktop app`
   - 생성 후 JSON을 다운로드합니다.
5. 다운로드한 파일을 이 폴더에 `credentials.json` 이름으로 둡니다.

공식 문서:

- [Gmail API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [users.messages.list reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- [users.messages.get reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)

## 설치

```powershell
cd C:\SR6\patreon_mail_exporter
python -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

`config.json`은 처음 실행할 때 없으면 자동 생성되지만, 미리 복사해 수정해도 됩니다.

## 실행

바탕화면의 `Patreon Gmail Exporter` 바로가기를 실행하면 프로그램 창이 열립니다.

창에서 할 수 있는 일:

- `다크 모드` 토글
- 상단 기간 드롭다운으로 `지난 24시간`, `지난 30일`, `지난 6개월`, `지난 12개월`, `전체`, `사용자 지정` 필터링
- Patreon 스타일의 어두운 대시보드에서 각진 탭, 카드, 테이블로 데이터 확인
- `요약` 탭에서 티어별 현황 확인
- `기간별` 탭에서 전체, 멤버십 등급, 청구 주기, 결제 상태, 유료로 전환하는 경로 기준의 막대 그래프 확인
- `기간별` 탭에서 매일/매주/매월 집계 전환
- `목록` 탭에서 신규 회원, 멤버십 등급, 청구 주기, 결제 상태, 유료 전환 경로를 포함한 표 확인
- `Patreon API` 탭에서 Patreon의 현재 멤버 상태/티어/결제 상태 가져오기
- `Gmail에서 새로 불러오기`로 메일 재조회

명령줄로 파일만 뽑으려면:

```powershell
cd C:\SR6\patreon_mail_exporter
python .\export_patreon_members.py --after 2026/01/01 --xlsx .\output\patreon_members.xlsx --html .\output\patreon_members_report.html
```

처음 실행하면 브라우저가 열리고 Gmail 접근 승인을 요구합니다. 승인이 끝나면 `token.json`이 생성되어 다음 실행부터는 다시 로그인하지 않습니다.

기간을 제한하려면:

```powershell
python .\export_patreon_members.py --after 2026/04/01 --before 2026/06/01
```

환율 API를 쓰지 않고 매핑과 보조 환율만 쓰려면:

```powershell
python .\export_patreon_members.py --exchange-mode off
```

## 결과 컬럼

- `received_at`: 수신 시각
- `member_name`: 후원자 이름
- `member_email`: 후원자 이메일
- `tier`: 1, 2, 3, 4 또는 빈칸
- `tier_usd`: 기준 USD 티어 가격
- `original_amount`: 메일 원문 금액
- `currency`, `amount`: 통화와 숫자 금액
- `usd_estimate`: 환율 기반 USD 추정값
- `match_method`: `local_price_map`, `frankfurter`, `fallback-config`, `missing-rate`
- `confidence`: `high`, `medium`, `low`, `needs_review`

## 화면 리포트

`--html .\output\patreon_members_report.html` 옵션을 주면 티어별 막대 차트와 회원 표가 들어간 HTML 리포트가 생성됩니다.

## Patreon API 연동

`Patreon API` 탭에서 `Patreon 키 설정`을 누르고 다음 값을 저장하면 Patreon에서 현재 멤버 데이터를 가져올 수 있습니다.

- Client ID
- Client Secret
- Access Token
- Refresh Token

이 값들은 `patreon_credentials.json`에 저장되며 `.gitignore`에 포함되어 있습니다. Client Secret과 토큰은 비밀번호처럼 취급하고 공개하지 마세요. 이미 공개된 토큰은 Patreon 개발자 페이지에서 폐기하거나 새로 발급하는 것이 안전합니다.

Patreon API 결과는 `output\patreon_api_members.csv`에 저장됩니다.

## 티어 매핑 수정

Patreon 지역가가 확인되면 `config.json`의 `local_price_map`에 추가하세요.

```json
"GBP": {
  "2.50": 1,
  "4.50": 2,
  "9.00": 3,
  "27.00": 4
}
```

정확한 지역 가격은 직접 확인되는 대로 매핑에 넣는 방식이 가장 안정적입니다. 매핑에 없는 통화나 금액은 환율 기반으로 추정하고, 애매하면 `needs_review`로 남깁니다.

## API 없이 테스트하기

Gmail에서 메일 원본을 `.eml`로 저장한 뒤 폴더에 모아두면 API 없이 파서만 테스트할 수 있습니다.

```powershell
python .\export_patreon_members.py --eml-dir .\samples --exchange-mode off
```
