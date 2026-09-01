# MotiCon Studio

원본 사진이나 직접 그린 캐릭터 한 장을 정리된 마스터 이미지로 만들고, 실생활에서 사용할 수 있는 24개 이모티콘 세트를 기획·생성·검수·내보내는 로컬 우선 웹앱입니다.

> 현재 단계: 1인용 로컬 MVP. 생성 결과의 플랫폼 승인이나 수익을 보장하지 않습니다.

## 구현된 기능

- JPG 업로드, EXIF 제거, 배경 분리와 입력 품질 검사
- 원본 색감·깨끗한 흰색·피치·민트·라일락·버터 마스터 생성
- 마스터 캐릭터와 색상 분위기 잠금
- Gemini 기반 24개 문구·감정·동작 기획과 로컬 폴백
- Gemini 이미지 모델 기반 24개 감정·행동 키프레임 생성
- 항목별 5개 원화 프레임 분리와 무손실 애니메이션 WebP 합성
- 순차 생성, 현재 항목 후 정지, 완료분 저장과 이어 만들기
- 샘플 승인, 개별 편집, 결과 다운로드와 ZIP 생성
- 유료 모델 자동 전환과 자동 결제를 차단하는 무료 우선 정책
- 반응형 제작 스튜디오와 홈 모션 갤러리

## 기술 구성

| 영역 | 기술 |
| --- | --- |
| 프런트엔드 | React, Vite, Lucide React |
| 백엔드 | Cloudflare Worker(공개), FastAPI·SQLite(로컬) |
| 이미지 처리 | Pillow, NumPy |
| AI | Cloudflare Workers AI FLUX.2 Klein 4B(공개), Gemini 선택 사용(로컬) |
| 영상/내보내기 | Pillow animated WebP, FFmpeg 선택 사용 |
| 저장 | 로컬 `data/` 프로젝트 폴더와 SQLite |

## Cloudflare 배포 구조

- `moticon`: GitHub `main`과 연결되는 React/Vite Cloudflare Worker Static Assets 프런트엔드
- `moticon` Worker가 정적 프런트와 `/api`를 함께 제공하며 Workers AI와 KV를 바인딩
- 로컬 개발에서는 기존 FastAPI·SQLite를 계속 사용
- `VITE_API_BASE_URL`이 비어 있으면 동일 출처 `/api`를 사용하고, 별도 Worker 배포 후 API 주소를 지정
- `wrangler.jsonc`가 `dist` 정적 파일과 SPA 경로 fallback을 관리하므로 Pages 전용 `_redirects` 파일은 사용하지 않음

## 실행 방법

### 1. 요구 사항

- Node.js 20 이상
- npm
- [uv](https://docs.astral.sh/uv/) 또는 Python 3.11 이상

### 2. 설치

```powershell
npm.cmd install
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

### 3. API 키 설정

Google AI Studio 키는 `.env`의 `GEMINI_API_KEY`에 설정합니다. 카카오 REST API 키는 다음 명령으로 화면에 노출하지 않고 저장할 수 있습니다.

```powershell
npm.cmd run key:kakao
```

Cloudflare Workers AI는 Dashboard의 **AI → Workers AI → Use REST API**에서 Account ID와 `Workers AI Read/Edit` 권한 토큰을 복사한 뒤 다음 명령으로 연결합니다. 토큰은 터미널 화면에 표시되지 않으며, 이미지 생성 없이 인증만 확인합니다.

```powershell
npm.cmd run key:cloudflare
```

`.env`는 Git에 포함되지 않습니다. 유료 사용 방지 설정은 다음 값을 유지하세요.

```dotenv
FREE_ONLY=true
ALLOW_PAID_MODELS=false
PROJECT_PAID_BUDGET_KRW=0
```

### 4. 개발 서버 실행

터미널 1:

```powershell
npm.cmd run backend
```

터미널 2:

```powershell
npm.cmd run dev
```

브라우저에서 [http://127.0.0.1:5173](http://127.0.0.1:5173)을 엽니다. API 문서는 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)에서 확인할 수 있습니다.

## 제작 흐름

1. 원본 사진 업로드 및 사용 권리 확인
2. 배경·스캔 질감 정리와 마스터 색상 선택
3. 마스터 정체성 잠금
4. 문구·감정·동작 24개 구성
5. 24개 항목을 순차 생성하고 진행 상황 확인
6. 필요한 항목만 개별 수정
7. WebP 개별 다운로드 또는 전체 ZIP 다운로드

## 안전과 권리

- 본인이 사용 권리를 가진 사진과 그림만 업로드해야 합니다.
- `.env`, API 키, 업로드 원본, 생성 결과와 로컬 DB는 저장소에 커밋하지 않습니다.
- 카카오톡·OGQ 등 외부 플랫폼의 심사와 상업 이용 정책을 별도로 확인해야 합니다.
- 타인의 이모티콘을 크롤링해 원본 파일로 저장하거나 AI 학습 데이터로 재사용하지 않습니다.

## 문서

- [문서 안내](docs/README.md)
- [무료 우선 MVP PRD](docs/PRD_FREE_FIRST_MVP.md)
- [초기 복원 PRD](docs/PRD_ORIGINAL_RECONSTRUCTED.md)
- [날짜별 변경 이력](CHANGELOG.md)

## 주요 명령

```powershell
npm.cmd run dev        # Vite 개발 서버
npm.cmd run backend    # FastAPI 서버와 Python 의존성 실행
npm.cmd run build      # 프로덕션 프런트엔드 빌드
npm.cmd run key:kakao  # 카카오 REST API 키 안전 저장
npm.cmd run key:cloudflare # Workers AI Account ID·Token 검증 및 안전 저장
```

## 라이선스

별도 라이선스가 추가되기 전까지 모든 권리는 프로젝트 소유자에게 있습니다.

## 변경 이력

### 2026-09-01

- 웹페이지에서 FastAPI 백엔드를 통해 Gemini 이미지 모델을 직접 호출하는 웹 네이티브 생성 흐름으로 전환
- Codex에서 미리 제작한 시드 이미지를 24개 세트의 생성 완료 항목에서 제외
- 마스터 이미지를 기준으로 24개 감정·행동 항목을 순차 생성하는 기능 추가
- 항목마다 5개 키프레임을 생성하고 무손실 애니메이션 WebP로 합성하도록 구현
- 생성 중지, 완료 항목 저장, 이어 만들기 및 전체 ZIP 내보내기 지원
- Gemini API 키를 제작 페이지에서 연결하고 상태를 확인할 수 있는 UI 추가
- Gemini 키 연결 시 원격 모델 목록을 기다리지 않고 즉시 로컬 저장하며, UI 타임아웃과 버튼 상태 복구를 보장하도록 개선
- Cloudflare Workers AI Account ID·Token을 숨김 입력하고 인증한 뒤 무료 FLUX.2 Klein 4B 설정으로 저장하는 터미널 명령 추가
- Cloudflare Workers 자동 배포를 위한 Static Assets SPA 라우팅과 `VITE_API_BASE_URL` 기반 프런트/API 분리 구조 추가
- Workers 배포에서 무한 순환을 일으키던 Pages 전용 `_redirects`를 제거하고 `wrangler.jsonc`의 `single-page-application` fallback으로 교체
- 공개 Worker에 프로젝트 생성, 이미지 업로드, 마스터 잠금, 24개 실생활 장면 기획, 개별 AI 원화 생성 API 추가
- Workers AI·KV를 브라우저 키 노출 없이 바인딩하고 업로드 이미지를 AI 입력 제한에 맞춰 500px 이하 PNG로 안전 변환
- 계정에서 R2가 활성화되지 않은 상태에서도 배포되도록 초기 공개판의 이미지 저장소를 KV로 통합
- 24개 생성 슬롯을 독립 저장해 연속 생성 중 상태 유실을 방지하고, 완료된 PNG와 권리·모델 manifest를 ZIP으로 내려받는 API 추가
- 공개 Workers AI 종단간 테스트에서 24개 원화 생성, 24/24 상태 조회, PNG ZIP 다운로드를 확인하고 안전 필터 자동 재시도 적용
- 공개 홈의 로컬 전용 이미지 경로를 배포 자산으로 교체하고 Kakao 이미지 검색 API용 최신 이모티콘 참고 영역 연결
- 무료 모델만 사용하고 유료 모델 전환·자동 결제를 차단하는 정책 적용
- 카카오 트렌드 메타데이터를 기획 프롬프트에 참고 신호로 반영하되 외부 이모티콘 원본은 복제하지 않도록 제한
- 최종 제품 목표를 자연어 요구에 따라 표정·자세·동작·문구와 개별 프레임을 다시 수정할 수 있는 대화형 생성 스튜디오로 확정

### 2026-08-31

- MotiCon Studio 로컬 MVP와 반응형 제작 UI 구축
- 사진 업로드, 배경 정리, 선화 보정 및 마스터 색상 선택 기능 구현
- Gemini 기반 24개 문구·감정·동작 기획 기능 추가
- 5프레임 `안녕!` 웨이브 모션의 캐릭터 일관성 및 미리보기 캐시 문제 개선
- 일별 카카오 이모티콘 트렌드 참고 데이터 기능 추가
- README, PRD와 프로젝트 문서 구조 정리 및 GitHub 저장소 최초 공개
