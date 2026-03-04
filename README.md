# VIRNECT G2B Intelligence

나라장터 / bizinfo.go.kr XR 공고 자동 수집 + AI 수주 확률 분석 도구

## 구조

```
virnect-g2b/
├── index.html                        # 메인 앱 (GitHub Pages)
├── data/
│   └── bids.json                     # 수집된 공고 데이터 (Actions가 자동 갱신)
├── scripts/
│   └── fetch_bids.py                 # bizinfo.go.kr 크롤러
└── .github/workflows/
    └── fetch-bids.yml                # 매일 오전 10시 자동 실행
```

## 배포 방법 (5분)

### 1. GitHub 저장소 생성
```
GitHub → New repository → virnect-g2b → Public → Create
```

### 2. 파일 업로드
이 폴더의 모든 파일을 저장소에 올립니다.
(GitHub 웹에서 드래그&드롭 또는 git push)

### 3. GitHub Pages 활성화
```
Settings → Pages → Source: Deploy from a branch
Branch: main / (root) → Save
```

### 4. Actions 첫 실행
```
Actions 탭 → "Fetch XR Bids" → Run workflow
```

약 2분 후 `data/bids.json`이 채워지고,  
`https://{계정명}.github.io/virnect-g2b/` 에서 실행됩니다.

## Google API Key 발급

1. https://aistudio.google.com 접속
2. **Get API Key** → **Create API key**
3. 앱 상단 입력창에 붙여넣기 → 저장

## 동작 방식

```
GitHub Actions (매일 오전 10시)
    ↓ bizinfo.go.kr API 호출 (CORS 없음 — 서버 환경)
    ↓ XR 키워드 12개로 공고 수집
    ↓ data/bids.json 저장 → git commit & push
    
GitHub Pages (브라우저)
    ↓ data/bids.json 로드 (같은 도메인 — CORS 없음)
    ↓ Gemini AI로 수주 확률 분석
    ↓ 분석 결과 localStorage 저장
```
