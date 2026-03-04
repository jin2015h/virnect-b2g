import json, time, re, os
from datetime import datetime
import requests

XR_KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실', '혼합현실',
    '메타버스', '디지털트윈', '스마트글래스', '홀로그램',
    '실감콘텐츠', '실감기술', '가상훈련', '원격협업',
    '웨어러블', '헤드셋', 'HMD',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://www.bizinfo.go.kr/',
}

BASE = 'https://www.bizinfo.go.kr'
LIST = f'{BASE}/web/lay1/bbs/S1T122C128/AS/74/list.do'

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    for a, b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'")]:
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text).strip()

def is_xr_related(title):
    return any(k in title for k in XR_KEYWORDS)

def guess_category(title):
    if any(k in title for k in ['군', '국방', '방위', '훈련', '전술']): return 'MR/군사'
    if any(k in title for k in ['안전', '산업안전', '재해', '사고']): return 'AI/안전'
    if any(k in title for k in ['물류', '창고', '피킹', '배송']): return 'AR/물류'
    if any(k in title for k in ['의료', '해부', '수술', '병원']): return 'VR/의료'
    if any(k in title for k in ['트윈', '디지털트윈']): return '디지털트윈'
    return 'AR/XR'

def parse_page(html):
    items = []
    seen = set()

    # HTML 구조 디버깅 - pblancId 패턴 확인
    pblanc_ids = re.findall(r'pblancId=(\w+)', html)
    print(f'    pblancId 패턴 수: {len(pblanc_ids)}, 샘플: {pblanc_ids[:3]}')

    # 링크 텍스트 패턴들 시도
    patterns = [
        re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*<[^>]*>\s*([^<]{4,150})', re.DOTALL),
        re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,150})', re.DOTALL),
        re.compile(r'(PBLN_[\w]+).*?<[^>]+>\s*([가-힣a-zA-Z0-9\s\(\)\[\]\/\-\_\.]{5,100})\s*<', re.DOTALL),
    ]

    for pi, pat in enumerate(patterns):
        matches = pat.findall(html)
        print(f'    패턴{pi+1} 매치: {len(matches)}개')
        if matches:
            print(f'    샘플: {matches[0]}')

    # 실제 추출 시도
    pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,150}?)\s*</a>', re.DOTALL)
    for m in pat.finditer(html):
        pid = m.group(1)
        title = clean(m.group(2))
        if not title or len(title) < 4 or pid in seen:
            continue
        if title in ['목록', '이전', '다음', '확인', '취소', '닫기', '스크랩', '상세보기']:
            continue
        seen.add(pid)
        ctx = clean(html[max(0,m.start()-100):min(len(html),m.end()+400)])
        dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
        items.append({
            'id': f'BIZ-{pid}', 'stage': '입찰공고', 'title': title, 'agency': '',
            'budget': '미정',
            'deadline': dates[1].replace('.','-') if len(dates)>1 else (dates[0].replace('.','-') if dates else '-'),
            'postDate': dates[0].replace('.','-') if dates else datetime.now().strftime('%Y-%m-%d'),
            'contractType': '공모', 'category': guess_category(title),
            'keywords': [k for k in XR_KEYWORDS if k in title],
            'description': title, 'requirements': [],
            'url': f'{BASE}/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
            'source': 'bizinfo',
        })
    return items

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] bizinfo XR 공고 수집 시작')
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1페이지 가져와서 HTML 구조 확인
    resp = session.get(LIST, params={'pageIndex': 1}, timeout=20)
    print(f'응답: {resp.status_code}, 길이: {len(resp.text)}자')

    # HTML 일부 출력 (pblancId 주변)
    html = resp.text
    idx = html.find('pblancId')
    if idx >= 0:
        print(f'\n=== pblancId 주변 HTML (200자) ===')
        print(repr(html[idx:idx+200]))
        print('===')
    else:
        print('pblancId 없음! HTML 앞부분 500자:')
        print(repr(html[:500]))

    all_items = []
    seen_ids = set()

    print(f'\n[1단계] 페이지 순회')
    for page in range(1, 21):
        resp = session.get(LIST, params={'pageIndex': page}, timeout=20)
        if resp.status_code != 200:
            break
        items = parse_page(resp.text)
        new_items = [i for i in items if i['id'] not in seen_ids]
        if not new_items:
            print(f'  페이지 {page}: 신규 없음, 중단')
            break
        for i in new_items:
            seen_ids.add(i['id'])
            all_items.append(i)
        xr = [i for i in new_items if is_xr_related(i['title'])]
        print(f'  페이지 {page}: {len(new_items)}건 (XR {len(xr)}건)')
        time.sleep(0.8)

    xr_bids = [b for b in all_items if is_xr_related(b['title'])]
    print(f'\n전체: {len(all_items)}건, XR: {len(xr_bids)}건')

    os.makedirs('data', exist_ok=True)
    if not xr_bids:
        print('XR 0건 - 기존 유지')
        if os.path.exists('data/bids.json'):
            with open('data/bids.json', encoding='utf-8') as f:
                ex = json.load(f)
            if ex.get('total', 0) > 0:
                ex['updatedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M') + ' (캐시)'
                with open('data/bids.json', 'w', encoding='utf-8') as f:
                    json.dump(ex, f, ensure_ascii=False, indent=2)
                return

    out = {'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'), 'total': len(xr_bids), 'bids': xr_bids}
    with open('data/bids.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'저장 완료: {len(xr_bids)}건')

if __name__ == '__main__':
    main()
