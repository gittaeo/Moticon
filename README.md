# MotiCon Studio

원본 사진이나 직접 그린 캐릭터 한 장을 정리된 마스터 이미지로 만들고, 실생활에서 사용할 수 있는 24개 이모티콘 세트를 기획·생성·검수·내보내는 로컬 우선 웹앱입니다.

> 현재 단계: 1인용 로컬 MVP. 생성 결과의 플랫폼 승인이나 수익을 보장하지 않습니다.

## 구현된 기능

- JPG 업로드, EXIF 제거, 배경 분리와 입력 품질 검사
- 원본 색감·깨끗한 흰색·피치·민트·라일락·버터 마스터 생성
- 마스터 캐릭터와 색상 분위기 잠금
- Gemini 기반 24개 문구·감정·동작 기획과 로컬 폴백
- Gemini 이미지 모델 기반 정적 PNG 세트 생성
- 5개 키프레임 시트 분리와 애니메이션 WebP 합성
- 샘플 승인, 개별 편집, 결과 다운로드와 ZIP 생성
- 유료 모델 자동 전환과 자동 결제를 차단하는 무료 우선 정책
- 반응형 제작 스튜디오와 홈 모션 갤러리

## 기술 구성

| 영역 | 기술 |
| --- | --- |
| 프런트엔드 | React, Vite, Lucide React |
| 백엔드 | FastAPI, SQLite |
| 이미지 처리 | Pillow, NumPy |
| AI | Google Gemini API 무료 할당량 우선 |
| 영상/내보내기 | Pillow animated WebP, FFmpeg 선택 사용 |
| 저장 | 로컬 `data/` 프로젝트 폴더와 SQLite |

## 실행 방법

### 1. 요구 사항

- Node.js 20 이상
- npm
- [uv](https://docs.astral.sh/uv/) 또는 Python 3.11 이상

### 2. 설치

```powershell
npm.cmd install
Copy-Item .env.example .env
```

### 3. API 키 설정

Google AI Studio 키는 `.env`의 `GEMINI_API_KEY`에 설정합니다. 카카오 REST API 키는 다음 명령으로 화면에 노출하지 않고 저장할 수 있습니다.

```powershell
npm.cmd run key:kakao
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
5. 대표 키프레임 모션 생성과 승인
6. 나머지 세트 생성 및 개별 수정
7. PNG·WebP·ZIP 다운로드

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
```

## 라이선스

별도 라이선스가 추가되기 전까지 모든 권리는 프로젝트 소유자에게 있습니다.
