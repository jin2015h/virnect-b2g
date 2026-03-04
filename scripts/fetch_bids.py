"""
bizinfo.go.kr XR 공고 수집
URL: /web/lay1/bbs/S1T122C128/AS/74/list.do
"""
import json, time, re, os
from datetime import datetime
import requests

KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실',
    '혼합현실', '메타버스', '디지털트윈', '스마트글래스',
    '홀로그램', '실감콘텐츠', '실감기술', '가상훈련'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://www.bizinfo.go.kr/',
}

BASE_URL  = 'https://www.bizinfo.go.kr'
LIST_URL  = f'{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/list.do'

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    for a,b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'")]:
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text).strip()

def guess_category(title):
    t = title
    if any(k in t for k in ['군', '국방', '방위', '훈련', '전술']): return 'MR/군사'
    if any(k in t for k in ['안전', '산업안전', '재해', '사고']): return 'AI/안전'
    if any(k in t for k in ['물류', '창고', '피킹', '배송']): return 'AR/물류'
    if any(k in t for k in ['의료', '해부', '수술', '의과', '병원']): return 'VR/의료'
    if any(k in t for k in ['트윈', '디지털트윈']): return '디지털트윈'
    return 'AR/XR'

def parse_list_html(html, keyword):
    """bizinfo 목록 HTML에서 공고 추출"""
    results = []
    seen = set()

    # bizinfo HTML 구조: <td class="subject"><a href="...pblancId=PBLN_xxx">제목</a></td>
    # 여러 패턴 시도
    patterns = [
        # 패턴1: subject td 안의 링크
        re.compile(r'class=["\']subject["\'][^>]*>.*?href=["\'][^"\']*pblancId=(PBLN_\w+)[^"\']*["\'][^>]*>([^<]{3,200})', re.DOTALL),
        # 패턴2: 링크 직접
        re.compile(r'href=["\'][^"\']*pblancId=(PBLN_\w+)[^"\']*["\'][^>]*>\s*([^<\n]{5,200})\s*</a>', re.DOTALL),
        # 패턴3: view.do 링크
        re.compile(r'AS/74/view\.do\?pblancId=(PBLN_\w+)[^>]*>([^<]{5,150})'),
    ]

    for pat in patterns:
        for m in pat.finditer(html):
            pblanc_id = m.group(1)
            title = clean(m.group(2))
            if not title or len(title) < 4 or pblanc_id in seen:
                continue
            # 너무 짧거나 내비게이션 텍스트 제외
            if title in ['목록', '이전', '다음', '확인', '취소', '닫기']:
                continue
            seen.add(pblanc_id)

            # 키워드 관련성 체크 (단, 첫 번째 키워드 AR은 광범위하므로 완화)
            kw_match = any(k in title for k in KEYWORDS)

            detail_url = f'{BASE_URL}/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}'

            # 날짜 추출
            start = max(0, m.start() - 50)
            end = min(len(html), m.end() + 400)
            ctx = clean(html[start:end])
            dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)

            results.append({
                'id': f'BIZ-{pblanc_id}',
                'stage': '입찰공고',
                'title': title,
                'agency': '',
                'budget': '미정',
                'deadline': dates[1].replace('.','-') if len(dates) > 1 else (dates[0].replace('.','-') if dates else '-'),
                'postDate': dates[0].replace('.','-') if dates else datetime.now().strftime('%Y-%m-%d'),
                'contractType': '공모',
                'category': guess_category(title),
                'keywords': [k for k in KEYWORDS if k in title],
                'description': title,
                'requirements': [],
                'url': detail_url,
                'source': 'bizinfo',
                'kw_match': kw_match,
            })
        if results:
            break  # 첫 번째 패턴이 잡히면 사용

    return results

def fetch_keyword(session, keyword):
    # bizinfo 검색 파라미터 여러 조합 시도
    param_sets = [
        {'schKeyword': keyword, 'pageIndex': 1, 'pageUnit': 20},
        {'searchKeyword': keyword, 'pageIndex': 1, 'pageUnit': 20},
        {'keyword': keyword, 'pageIndex': 1},
        {'schText': keyword, 'pageIndex': 1},
    ]
    
    for params in param_sets:
        try:
            resp = session.get(LIST_URL, params=params, timeout=20)
            if resp.status_code == 200:
                results = parse_list_html(resp.text, keyword)
                if results:
                    print(f'     파라미터 {list(params.keys())[0]} → {len(results)}건')
                    return results
        except Exception as e:
            print(f'     오류: {e}')
    return []

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] bizinfo XR 공고 수집 시작')
    session = requests.Session()
    session.headers.update(HEADERS)

    # 기본 페이지 먼저 가져와서 쿠키 및 HTML 구조 확인
    try:
        resp0 = session.get(LIST_URL, timeout=20)
        print(f'기본 목록 응답: {resp0.status_code}, {len(resp0.text)}자')
        results0 = parse_list_html(resp0.text, '')
        print(f'기본 목록 파싱: {len(results0)}건')
    except Exception as e:
        print(f'기본 접속 오류: {e}')

    all_bids = []
    seen_ids = set()

    # 기본 목록 먼저 추가
    for b in results0:
        if b['id'] not in seen_ids:
            seen_ids.add(b['id'])
            all_bids.append(b)

    # 키워드별 검색
    for kw in KEYWORDS:
        print(f'  🔍 [{kw}]')
        bids = fetch_keyword(session, kw)
        added = 0
        for b in bids:
            if b['id'] not in seen_ids:
                seen_ids.add(b['id'])
                all_bids.append(b)
                added += 1
        if added > 0:
            print(f'  → +{added}건 신규 (누적 {len(all_bids)}건)')
        time.sleep(1.0)

    # kw_match 필드 제거
    for b in all_bids:
        b.pop('kw_match', None)

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
