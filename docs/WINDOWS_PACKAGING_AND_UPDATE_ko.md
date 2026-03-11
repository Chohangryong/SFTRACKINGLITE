# SF Express Tracking Lite Windows 패키징/업데이트 가이드

## 1. 배포 방식

- 배포 형식은 `PyInstaller onedir + Inno Setup 설치 프로그램` 기준이다.
- 설치 경로는 현재 사용자 기준 프로그램 폴더를 사용한다.
  - 예: `%LOCALAPPDATA%\Programs\SFTrackingLite\`
- 사용자 데이터는 실행 파일과 분리해서 별도 AppData 경로에 저장한다.
  - 예: `%LOCALAPPDATA%\SFTrackingLite\`

이 구조를 쓰는 이유:

- 일반 사용자도 관리자 권한 없이 설치할 수 있다.
- 설치 파일 교체와 사용자 데이터 보존을 분리할 수 있다.
- API Key, SQLite DB, 임시 조회 결과를 설치본에 포함하지 않을 수 있다.

## 2. 설치본 포함/제외 기준

설치본에 포함:

- `SFTrackingLite.exe`
- Python 런타임/필수 라이브러리
- `frontend/dist`

설치본에 포함하지 않음:

- `data/app.db`
- `data/.cipher.key`
- `data/uploads/*`
- `data/lite_jobs/*`
- 테스트 로그/캐시 파일

즉 설치본은 코드와 정적 자산만 포함하고, 실제 운영 데이터는 첫 실행 후 AppData에 생성한다.

## 3. 빌드 순서

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

1. 이미 `127.0.0.1:8000`에서 앱이 실행 중이면 브라우저만 연다.
2. 포트가 다른 프로그램에 의해 사용 중이면 오류 메시지를 보여준다.
3. 아니면 로컬 서버를 실행한다.
4. `/api/health`가 정상 응답하면 브라우저에서 `/lite`를 연다.

## 5. 업데이트/패치 전략

현재 권장 전략은 `차등 패치`가 아니라 `전체 설치본 재배포`다.

이유:

- 앱 크기가 아주 큰 편이 아니다.
- 사용자 데이터가 AppData에 있어서 재설치해도 데이터가 유지된다.
- 운영 복잡도를 낮출 수 있다.

즉 배포 절차는 아래와 같다.

1. 버전 올리기
2. 새 설치 파일 생성
3. 사용자에게 새 `SFTrackingLiteSetup.exe` 배포
4. 같은 `AppId`로 덮어설치

이 방식이면:

- 실행 파일/프런트 자산은 새 버전으로 교체
- API Key / DB / 임시 결과는 AppData에 유지

## 6. 업데이트 시 지켜야 할 규칙

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

를 다음 버전에서 이어받지 못한다.

### 6-3. DB 스키마 변경 주의

현재 앱은 기본적으로 `create_all()` 중심이다.

즉,

- 새 테이블 추가
- nullable 컬럼 추가

같은 additive 변경은 비교적 안전하다.

반대로 아래는 위험하다.

- 기존 컬럼 타입 변경
- 컬럼 삭제/이름 변경
- 제약조건 강제 변경

이런 변경이 필요하면 배포 전에 별도 마이그레이션 경로를 넣어야 한다.

## 7. 릴리스 체크리스트

1. `frontend` build
2. `PyInstaller onedir` build
3. 설치 파일 생성
4. 기존 버전 설치 PC에서 덮어설치 테스트
5. 기존 API Key 유지 확인
6. 기존 DB 유지 확인
7. Lite 조회/다운로드 확인
8. 제거 후 재설치 동작 확인

## 8. 자동 업데이트가 필요해질 때

지금은 수동 설치본 교체가 가장 안전하다.

자동 업데이트가 필요해지면 그때 검토할 후보:

- WinSparkle
- 자체 업데이트 체크 API

하지만 현재 단계에서는 `전체 Setup.exe 재배포`가 가장 현실적이다.
