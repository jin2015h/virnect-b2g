"""
bizinfo.go.kr XR 공고 수집 스크립트
올바른 URL: /web/lay1/bbs/S1T122C128/AS/74/list.do
"""
import json, time, re, os
from datetime import datetime
import requests

KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실',
    '혼합현실', '메타버스', '디지털트윈', '스마트글래스',
    '홀로그램', '실감콘텐츠'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://www.bizinfo.go.kr/',
}

BASE_URL = 'https://www.bizinfo.go.kr'
LIST_URL = f'{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/list.do'

def clean(text):
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def guess_category(title, desc=''):
    t = title + ' ' + desc
    if any(k in t for k in ['군', '국방', '방위', '훈련', '전술']):
        return 'MR/군사'
    if any(k in t for k in ['안전', '산업안전', '재해', '사고예방']):
        return 'AI/안전'
    if any(k in t for k in ['물류', '창고', '피킹', '배송']):
        return 'AR/물류'
    if any(k in t for k in ['의료', '해부', '수술', '의과', '병원']):
        return 'VR/의료'
    if any(k in t for k in ['트윈', '디지털트윈']):
        return '디지털트윈'
    return 'AR/XR'

def fetch_keyword(keyword):
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        params = {
            'searchKeyword': keyword,
            'pageIndex': 1,
            'pageUnit': 20,
        }
        resp = session.get(LIST_URL, params=params, timeout=20)
        print(f'     목록 응답: {resp.status_code}')

        if resp.status_code != 200:
            return results

        html = resp.text

        # pblancId 패턴으로 공고 추출
        # URL 예: /web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId=PBLN_000000000103358
        pattern = re.compile(
            r'pblancId=(PBLN_\w+)[^"\']*["\'][^>]*>\s*<[^>]+>\s*([^<]{5,150})',
            re.DOTALL
        )

        seen = set()
        for m in pattern.finditer(html):
            pblanc_id = m.group(1)
            title = clean(m.group(2))
            if not title or pblanc_id in seen or len(title) < 5:
                continue
            seen.add(pblanc_id)

            detail_url = f'{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}'

            # 날짜 추출 (공고 주변 컨텍스트)
            start = max(0, m.start() - 100)
            end = min(len(html), m.end() + 300)
            ctx = clean(html[start:end])
            dates = re.findall(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2})', ctx)

            results.append({
                'id': f'BIZ-{pblanc_id}',
                'stage': '입찰공고',
                'title': title,
                'agency': '',
                'budget': '미정',
                'deadline': dates[1] if len(dates) > 1 else (dates[0] if dates else '-'),
                'postDate': dates[0] if dates else datetime.now().strftime('%Y-%m-%d'),
                'contractType': '공모',
                'category': guess_category(title),
                'keywords': [k for k in KEYWORDS if k in title],
                'description': title,
                'requirements': [],
                'url': detail_url,
                'source': 'bizinfo',
            })

        # 패턴 안 잡히면 넓은 범위로 시도
        if not results:
            pattern2 = re.compile(r'pblancId=(PBLN_\w+)')
            ids = set(pattern2.findall(html))
            print(f'     pblancId 발견: {len(ids)}개')
            # 타이틀 별도 추출
            title_pattern = re.compile(r'class="[^"]*title[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{5,150})', re.DOTALL)
            titles = [clean(t) for t in title_pattern.findall(html) if clean(t)]
            for i, (pid, ttl) in enumerate(zip(sorted(ids), titles)):
                detail_url = f'{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}'
                results.append({
                    'id': f'BIZ-{pid}',
                    'stage': '입찰공고',
                    'title': ttl,
                    'agency': '',
                    'budget': '미정',
                    'deadline': '-',
                    'postDate': datetime.now().strftime('%Y-%m-%d'),
                    'contractType': '공모',
                    'category': guess_category(ttl),
                    'keywords': [k for k in KEYWORDS if k in ttl],
                    'description': ttl,
                    'requirements': [],
                    'url': detail_url,
                    'source': 'bizinfo',
                })

    except Exception as e:
        print(f'     오류: {e}')

    return results


def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] bizinfo XR 공고 수집 시작')
    print(f'대상 URL: {LIST_URL}')

    # 연결 테스트
    try:
        test = requests.get(BASE_URL, headers=HEADERS, timeout=10)
        print(f'bizinfo 접속 테스트: {test.status_code}')
    except Exception as e:
        print(f'bizinfo 접속 실패: {e}')

    all_bids = []
    seen_ids = set()

    for kw in KEYWORDS:
        print(f'  🔍 [{kw}]')
        bids = fetch_keyword(kw)
        added = 0
        for b in bids:
            if b['id'] not in seen_ids:
                seen_ids.add(b['id'])
                all_bids.append(b)
                added += 1
        print(f'  → +{added}건 (누적 {len(all_bids)}건)')
        time.sleep(1.5)

    print(f'\n총 {len(all_bids)}건 수집')

    os.makedirs('data', exist_ok=True)

    if len(all_bids) == 0:
        print('⚠ 0건 — 기존 데이터 유지')
        if os.path.exists('data/bids.json'):
            with open('data/bids.json', encoding='utf-8') as f:
                existing = json.load(f)
            if existing.get('total', 0) > 0:
                existing['updatedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M') + ' (캐시)'
                with open('data/bids.json', 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                print('기존 데이터 유지')
                return

    output = {
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total': len(all_bids),
        'bids': all_bids,
    }
    with open('data/bids.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'✅ data/bids.json 저장 완료')

if __name__ == '__main__':
    main()
