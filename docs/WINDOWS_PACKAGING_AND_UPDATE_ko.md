# SF Express Tracking Lite Windows 패키징/업데이트 가이드

## 1. 배포 방식

- 배포 형식은 `PyInstaller onedir + Inno Setup 설치 프로그램` 기준이다.
- 설치 경로는 프로그램 파일만 가진다.
  - 예: `C:\Program Files\SFTrackingLite\`
- 사용자 데이터는 설치 경로가 아니라 AppData에 저장한다.
  - 예: `%LOCALAPPDATA%\SFTrackingLite\`

이 구조를 쓰는 이유:

- 설치 파일 업데이트 시 사용자 데이터가 유지된다.
- `Program Files` 권한 문제를 피할 수 있다.
- API Key, SQLite DB, 임시 다운로드 파일을 설치본에 섞지 않는다.

## 2. 포함/제외 원칙

설치본에 포함:

- `SFTrackingLite.exe`
- Python 런타임/라이브러리
- `frontend/dist`

설치본에 포함하지 않음:

- `data/app.db`
- `data/.cipher.key`
- `data/uploads/*`
- `data/lite_jobs/*`
- 테스트/로그/캐시 파일

즉, 설치본은 코드와 정적 자산만 가지고, 실제 운영 데이터는 첫 실행 후 AppData에 생성한다.

## 3. 빌드 절차

사전 준비:

- Node.js / npm
- Python build 환경
- `pyinstaller`
- `Inno Setup 6`

실행:

```powershell
cd packaging
.\build_windows.ps1
```

설치 프로그램 생성만 건너뛰려면:

```powershell
cd packaging
.\build_windows.ps1 -SkipInstaller
```

산출물:

- onedir 실행 폴더: `dist/SFTrackingLite/`
- 설치 파일: `build/SFTrackingLiteSetup.exe`

## 4. 첫 실행 동작

패키징된 앱은 `backend/launcher.py`를 시작점으로 사용한다.

동작:

1. 이미 `127.0.0.1:8000`에서 앱이 떠 있으면 브라우저만 연다.
2. 포트가 다른 프로그램에 점유되어 있으면 오류 메시지를 띄운다.
3. 아니면 로컬 서버를 실행한다.
4. `/api/health`가 응답하면 브라우저로 `/lite`를 연다.

## 5. 패치/업데이트 전략

현재 권장 전략은 `차등 패치`가 아니라 `전체 설치본 재배포`다.

이유:

- 앱 크기가 아주 큰 편은 아니다.
- 사용자 데이터가 AppData에 있어 재설치 시 데이터가 유지된다.
- 운영 리스크가 가장 낮다.

즉, 패치 배포는 아래처럼 처리한다.

1. 버전 올리기
2. 새 설치 파일 생성
3. 사용자에게 새 Setup.exe 배포
4. 같은 `AppId`로 덮어설치

이 방식이면:

- 실행 파일/프론트 리소스는 새 버전으로 교체
- API Key / DB / 임시결과는 AppData에 남음

## 6. 업데이트 시 꼭 지켜야 할 규칙

### 6-1. AppId 고정

Inno Setup의 `AppId`는 버전이 바뀌어도 유지해야 한다.

바뀌면:

- 업그레이드가 아니라 별도 앱으로 설치된다.

### 6-2. 사용자 데이터 경로 고정

`%LOCALAPPDATA%\SFTrackingLite\` 경로는 유지해야 한다.

바뀌면:

- 기존 API Key
- SQLite DB
- 임시 조회 결과

를 새 버전이 이어받지 못한다.

### 6-3. DB 스키마 변경은 신중히

현재 앱은 기본적으로 `create_all()` 중심이다.

즉:

- 새 테이블 추가
- nullable 컬럼 추가

같은 `가벼운 additive 변경`에는 비교적 안전하다.

반대로 아래는 위험하다.

- 기존 컬럼 타입 변경
- 컬럼 삭제/이름 변경
- 제약조건 강제 변경

이런 변경이 필요하면 배포 전에 별도 마이그레이션 경로를 넣어야 한다.

## 7. 패치 릴리스 체크리스트

1. `frontend` build
2. `PyInstaller onedir` build
3. 설치 파일 생성
4. 기존 버전이 설치된 PC에 덮어설치 테스트
5. 기존 API Key 유지 확인
6. 기존 DB 열림 확인
7. Lite 조회/다운로드 확인
8. 제거 후 재설치 동작 확인

## 8. 나중에 자동 업데이트가 필요하면

지금은 수동 설치본 교체가 가장 안전하다.

자동 업데이트가 필요해지면 그때 검토할 후보:

- WinSparkle
- 자체 업데이트 체크 API

하지만 현재 단계에서는 `전체 Setup.exe 재배포`가 가장 현실적이다.
