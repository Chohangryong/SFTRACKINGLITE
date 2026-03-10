# SF Express Tracking Dashboard 사용 가이드

## 1. 개요

이 시스템은 SF Express 운송장 조회기를 넘어서, 주문번호와 운송장번호를 연결하고 최신 배송 상태와 전체 이벤트 이력을 함께 관리하는 로컬 운영 대시보드다.

핵심 목적은 아래 4가지다.

- 업로드 파일에서 주문번호와 운송장번호를 추출한다.
- Order, Tracking, Order-Tracking 관계를 영속 저장한다.
- SF Express `EXP_RECE_SEARCH_ROUTES` 응답을 기반으로 최신 상태와 이벤트 이력을 분리 저장한다.
- 목록, 상세, 차트, 엑셀 다운로드 형태로 운영자가 바로 확인할 수 있게 한다.

## 2. 현재 구현 범위

현재 레포 기준으로 구현된 항목은 아래와 같다.

- FastAPI 백엔드
- SQLite 기반 데이터 저장
- CSV/XLSX/XLS 업로드
- 컬럼 자동 감지 및 매핑 확인
- 업로드 확정 시 Order / Tracking / 관계 저장
- SF API 키 저장 및 마스킹 조회
- SF 라우트 조회 결과의 이벤트 저장 및 최신 상태 계산
- 최신 상태 중심 대시보드 목록
- Tracking 상세 조회와 이벤트 타임라인
- 상태 분포 / 일자별 Delivered 차트
- Summary / Event 엑셀 다운로드
- 폴링 실행 이력 및 미매핑 상태 확인 화면
- PyInstaller / Inno Setup 패키징 자산

## 3. 폴더 구조

- `backend/`: API 서버, DB 모델, 서비스, 스케줄러, 테스트
- `frontend/`: React UI, 화면, API 클라이언트
- `packaging/`: Windows 배포 스크립트
- `data/`: 로컬 DB, 업로드 파일, export 산출물 저장 위치
- `docs/`: 사용 가이드와 운영 문서

## 4. 실행 방법

### 4.1 의존성 설치

프로젝트 루트에서 아래를 실행한다.

```bash
make install
```

직접 실행 시:

```bash
cd backend && python3 -m pip install -e ".[dev]"
cd ../frontend && npm install
```

### 4.2 개발 서버 실행

백엔드:

```bash
make run-backend
```

프론트엔드:

```bash
make run-frontend
```

기본 주소:

- 백엔드 API: `http://127.0.0.1:8000`
- 프론트엔드 개발 서버: `http://127.0.0.1:5173`

### 4.3 정적 빌드

```bash
make build
```

빌드 후 FastAPI가 `frontend/dist`를 정적 파일로 서빙한다.

### 4.4 테스트

```bash
make test
```

현재 포함된 테스트 범위:

- SF 서명 생성
- 엑셀 수식 주입 방지
- 업로드 확정 후 `NO_TRACKING` row 생성
- SF 응답 반영 후 `DELIVERED` 상태 및 이벤트 저장
- 설정 및 export API 기본 동작

## 5. 화면별 사용 방법

## 5.1 Dashboard

메인 화면에서 확인할 수 있는 내용:

- 전체 Order 수
- 전체 Tracking 수
- Tracking 없는 주문 수
- 진행 중 배송 수
- Delivered 수
- 예외 및 조회 실패 수

주요 사용 흐름:

- 검색창으로 주문번호 또는 운송장번호를 검색한다.
- `미종결 건 새로고침` 버튼으로 자동 폴링 대상 상태를 즉시 재조회한다.
- `Summary Export` 버튼으로 현재 summary 형식의 XLSX를 다운로드한다.
- 목록에서 Tracking Number가 있는 row를 클릭하면 상세 화면으로 이동한다.

## 5.2 Upload Wizard

업로드 화면의 처리 순서는 아래와 같다.

1. CSV/XLSX/XLS 파일을 업로드한다.
2. 시스템이 컬럼명을 보고 `order_number`, `tracking_number` 등의 후보를 자동 감지한다.
3. 운영자가 매핑을 확인하거나 수정한다.
4. Preview 테이블에서 샘플 row를 검토한다.
5. `확정 및 즉시 조회`를 누르면 DB 반영과 SF 조회가 함께 수행된다.

처리 규칙:

- `order_number`가 없으면 해당 row는 오류로 처리된다.
- `tracking_number`가 없으면 주문은 저장되지만 목록에서 `NO_TRACKING` 상태로 보인다.
- `tracking_number`가 있으면 `REGISTERED`로 생성 후 즉시 SF 조회를 시도한다.
- 같은 주문번호나 운송장번호가 다시 들어와도 중복 생성하지 않고 재사용한다.

## 5.3 Tracking Detail

상세 화면에서는 아래를 본다.

- 현재 상태 요약
- 마지막 이벤트 시각 / 위치 / 비고 / opcode
- 연결된 주문 목록
- 전체 이벤트 타임라인

이 화면은 최신 상태 확인보다 이력 분석에 초점을 둔다.

## 5.4 Settings

설정 화면에서 관리 가능한 항목:

- SF API Key 추가
- 활성 키 전환
- API Key 테스트 요청
- 폴링 주기, 배치 크기, 지연 시간 설정
- 상태 매핑 목록 확인 및 재저장

보안 관련 동작:

- 저장 시 키 값은 암호화된다.
- 화면 조회 시에는 마스킹된 값만 노출된다.
- Windows에서는 DPAPI를 우선 사용하고, 비-Windows 개발 환경에서는 로컬 암호화 키를 사용한다.

## 5.5 Admin

운영 화면에서는 아래를 본다.

- 최근 폴링 실행 이력
- 성공/실패 건수
- 미매핑 상태 조합

미매핑 상태는 `UNKNOWN_OPCODE` 대응을 위한 운영 보조 데이터다.

## 6. 주요 특징

## 6.1 최신 상태와 이벤트 이력의 분리

`trackings` 테이블에는 최신 상태 요약만 저장하고, `tracking_events`에는 전체 라우트 이벤트를 저장한다. 이 구조 덕분에 목록 조회는 빠르게, 상세 추적은 풍부하게 처리할 수 있다.

## 6.2 Order 중심이 아니라 관계 중심 설계

핵심 row 단위는 단순 Tracking이 아니라 `Order-Tracking` 관계다. 따라서 같은 주문에 여러 운송장이 있거나, 동일 운송장을 여러 주문 문맥에서 볼 수 있는 구조를 유지한다.

## 6.3 재업로드 안전성

같은 파일을 다시 올릴 수 있고, 같은 주문번호나 운송장번호가 다시 등장해도 idempotent하게 처리한다. 운영자는 원본 업로드를 두려워하지 않고 반복 반영할 수 있다.

## 6.4 운영자 친화적 화면 구성

초기 구현은 아래 5개 화면으로 역할이 분리돼 있다.

- Dashboard: 최신 상태 중심
- Upload: 입력 파이프라인 중심
- Detail: 이벤트 이력 중심
- Settings: 외부 연동과 운영 설정 중심
- Admin: 폴링과 미매핑 상태 점검 중심

## 6.5 CSV/XLSX 다운로드 안전 처리

다운로드 시 셀 값이 `=`, `+`, `-`, `@` 로 시작하면 escape 처리한다. 엑셀 수식 주입을 막기 위한 최소 방어선이다.

## 6.6 공식 API 우선 구조

SF 연동은 `EXP_RECE_SEARCH_ROUTES`를 기준으로 작성되어 있고, 서명 규칙도 공식 문서 형식인 `Base64(MD5(msgData + timestamp + checkword))`를 따른다.

## 7. 데이터 모델 요약

핵심 테이블:

- `orders`
- `trackings`
- `order_trackings`
- `tracking_events`
- `upload_batches`

보조 테이블:

- `upload_errors`
- `column_mapping_presets`
- `api_keys`
- `status_mappings`
- `polling_runs`

데이터 관점에서 중요한 점:

- 목록은 `trackings`의 최신 상태를 사용한다.
- 상세는 `tracking_events`를 사용한다.
- Tracking 없는 주문도 synthetic row로 보여준다.

## 8. API 개요

주요 API 묶음은 아래와 같다.

- Upload: `/api/uploads`
- Tracking: `/api/trackings`
- Dashboard: `/api/dashboard`
- Export: `/api/export`
- Settings: `/api/settings`
- Admin: `/api/admin`
- Health: `/api/health`

대표 예시:

- `POST /api/uploads`
- `GET /api/uploads/{batch_id}/preview`
- `POST /api/uploads/{batch_id}/confirm`
- `GET /api/trackings`
- `GET /api/trackings/{tracking_number}`
- `GET /api/trackings/{tracking_number}/events`
- `POST /api/trackings/refresh-all`

## 9. 운영 팁

- 업로드 파일의 헤더명을 너무 제각각으로 쓰지 않는 편이 자동 감지 정확도가 높다.
- 상태 매핑이 부족하면 Admin 화면의 unmapped status를 보고 매핑 정책을 확장한다.
- `QUERY_FAILED`가 누적되면 Settings의 폴링 간격과 API 키 상태를 함께 점검한다.
- SF 응답 텍스트는 언어 설정의 영향을 받으므로, 운영 표시 용어는 내부 상태값 기준으로 보는 것이 안정적이다.

## 10. 현재 한계와 후속 작업 후보

현재 구현 기준의 제한 사항:

- `trackingType = 2` 주문번호 fallback 조회는 미구현
- 리드타임 차트 미구현
- 시스템 트레이 미구현
- Windows 실제 설치 검증은 별도 환경 필요
- 프론트 빌드는 동작하지만 Ant Design 번들이 커서 추가 코드 분할 여지가 있음
- 일부 Python 시간 처리에서 `datetime.utcnow()` deprecation warning이 남아 있음

후속 확장 후보:

- 상태 매핑 편집 UI 강화
- export preset 편집 화면 추가
- 차트 종류 확대
- 운영 로그 화면 강화
- Windows 런처 및 트레이 모드 추가
