"""
bizinfo.go.kr XR 공고 수집
- 여러 페이지 순회 후 로컬 키워드 필터링
- POST 방식으로 검색 시도
"""
import json, time, re, os
from datetime import datetime
import requests

XR_KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실', '혼합현실',
    '메타버스', '디지털트윈', '스마트글래스', '홀로그램',
    '실감콘텐츠', '실감기술', '가상훈련', '원격협업', '스마트팩토리',
    '웨어러블', '헤드셋', 'HMD', '3D스캔', '포인트클라우드'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://www.bizinfo.go.kr/',
}

BASE = 'https://www.bizinfo.go.kr'
LIST = f'{BASE}/web/lay1/bbs/S1T122C128/AS/74/list.do'
MAX_PAGES = 20

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    for a, b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'")]:
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text).strip()

def is_xr_related(title, desc=''):
    t = title + ' ' + desc
    return any(k in t for k in XR_KEYWORDS)

def guess_category(title):
    t = title
    if any(k in t for k in ['군', '국방', '방위', '훈련', '전술']): return 'MR/군사'
    if any(k in t for k in ['안전', '산업안전', '재해', '사고']): return 'AI/안전'
    if any(k in t for k in ['물류', '창고', '피킹', '배송']): return 'AR/물류'
    if any(k in t for k in ['의료', '해부', '수술', '병원']): return 'VR/의료'
    if any(k in t for k in ['트윈', '디지털트윈']): return '디지털트윈'
    return 'AR/XR'

def parse_page(html):
    items = []
    seen = set()
    pat = re.compile(
        r'href=["\'][^"\']*pblancId=(PBLN_\w+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>',
        re.DOTALL
    )
    for m in pat.finditer(html):
        pid = m.group(1)
        title = clean(m.group(2))
        if not title or len(title) < 4 or pid in seen:
            continue
        if title in ['목록', '이전', '다음', '확인', '취소', '닫기', '스크랩']:
            continue
        seen.add(pid)
        ctx = clean(html[max(0, m.start()-100):min(len(html), m.end()+400)])
        dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
        agency_m = re.search(r'소관[^:：]*[:：]\s*([^\s<,]{2,20})', ctx)
        agency = agency_m.group(1) if agency_m else ''
        items.append({
            'id': f'BIZ-{pid}', 'stage': '입찰공고', 'title': title, 'agency': agency,
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
    all_items = []
    seen_ids = set()
    xr_count = 0

    print(f'\n[1단계] 전체 목록 페이지 순회 (최대 {MAX_PAGES}페이지)')
    for page in range(1, MAX_PAGES + 1):
        try:
            resp = session.get(LIST, params={'pageIndex': page, 'pageUnit': 15}, timeout=20)
            if resp.status_code != 200:
                print(f'  페이지 {page}: {resp.status_code} 중단'); break
            items = parse_page(resp.text)
            if not items:
                print(f'  페이지 {page}: 항목 없음 중단'); break
            new_items = [i for i in items if i['id'] not in seen_ids]
            if not new_items:
                print(f'  페이지 {page}: 중복 중단'); break
            for i in new_items:
                seen_ids.add(i['id'])
                all_items.append(i)
                if is_xr_related(i['title']): xr_count += 1
            print(f'  페이지 {page}: {len(new_items)}건 (XR 누적: {xr_count}건)')
            time.sleep(0.8)
        except Exception as e:
            print(f'  페이지 {page} 오류: {e}'); break

    print(f'\n[2단계] POST 키워드 검색')
    for kw in ['증강현실', '가상현실', '디지털트윈', '메타버스']:
        try:
            resp = session.post(LIST, data={'searchKeyword': kw, 'pageIndex': 1, 'pageUnit': 20},
                headers={**HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'}, timeout=20)
            if resp.status_code == 200:
                items = parse_page(resp.text)
                new_items = [i for i in items if i['id'] not in seen_ids]
                for i in new_items:
                    seen_ids.add(i['id']); all_items.append(i)
                    if is_xr_related(i['title']): xr_count += 1
                if new_items: print(f'  POST [{kw}]: +{len(new_items)}건')
        except Exception as e:
            print(f'  POST [{kw}] 오류: {e}')
        time.sleep(0.8)

    xr_bids = [b for b in all_items if is_xr_related(b['title'], b['description'])]
    print(f'\n전체: {len(all_items)}건, XR: {len(xr_bids)}건')

    os.makedirs('data', exist_ok=True)
    if not xr_bids:
        print('⚠ XR 0건 — 기존 데이터 유지')
        if os.path.exists('data/bids.json'):
            with open('data/bids.json', encoding='utf-8') as f:
                existing = json.load(f)
            if existing.get('total', 0) > 0:
                existing['updatedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M') + ' (캐시)'
                with open('data/bids.json', 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                return

    output = {'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'), 'total': len(xr_bids), 'bids': xr_bids}
    with open('data/bids.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'✅ 저장 완료: {len(xr_bids)}건')

if __name__ == '__main__':
    main()
```

**④ 저장**
```
우상단 Commit changes 클릭 → Commit changes 클릭
```

**⑤ Actions 다시 실행**
```
Actions → Fetch XR Bids → Run workflow
