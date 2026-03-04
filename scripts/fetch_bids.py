"""
bizinfo.go.kr XR 공고 수집 스크립트
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
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

def clean(text):
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def guess_category(title, desc=''):
    t = (title + ' ' + desc)
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
        # 방법 1: bizinfo JSON API
        url = 'https://www.bizinfo.go.kr/uss/ion/ptn/selectAnnouncementListjson.do'
        params = {'searchKeyword': keyword, 'pageUnit': 20, 'pageIndex': 1}
        resp = session.get(url, params=params, timeout=20)
        print(f'     API 응답: {resp.status_code}, Content-Type: {resp.headers.get("Content-Type","")}')

        if resp.status_code == 200:
            ct = resp.headers.get('Content-Type', '')
            if 'json' in ct:
                data = resp.json()
                items = (data.get('pblancList') or data.get('list') or
                         data.get('resultList') or data.get('data') or [])
                print(f'     JSON items: {len(items)}')
                for item in items:
                    title = clean(item.get('pblancNm') or item.get('title') or '')
                    if not title:
                        continue
                    pblanc_id = str(item.get('pblancId') or item.get('id') or abs(hash(title)) % 1000000)
                    results.append(make_bid(pblanc_id, title, item))
            else:
                # HTML 응답인 경우 파싱
                results = parse_html(resp.text, keyword)
    except Exception as e:
        print(f'     방법1 실패: {e}')

    # 방법 2: HTML 검색 페이지 직접 파싱
    if not results:
        try:
            url2 = f'https://www.bizinfo.go.kr/web/search/searchList.do'
            params2 = {'searchKeyword': keyword, 'pageIndex': 1}
            resp2 = session.get(url2, params=params2, timeout=20)
            print(f'     HTML 응답: {resp2.status_code}')
            if resp2.status_code == 200:
                results = parse_html(resp2.text, keyword)
        except Exception as e:
            print(f'     방법2 실패: {e}')

    return results

def make_bid(pblanc_id, title, item=None):
    item = item or {}
    agency  = clean(item.get('jrsdInsttNm') or item.get('insttNm') or '')
    budget  = clean(item.get('bsnsYrCnt') or item.get('budget') or '미정')
    if budget != '미정' and '원' not in budget:
        budget += '원'
    deadline  = clean(item.get('reqstDt') or item.get('closingDt') or '-')
    post_date = clean(item.get('pblancBgngDt') or item.get('startDt') or datetime.now().strftime('%Y-%m-%d'))
    desc = clean(item.get('pblancCn') or item.get('content') or title)[:300]
    url  = f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/pblancDetail.do?pblancId={pblanc_id}'
    return {
        'id': f'BIZ-{pblanc_id}',
        'stage': '입찰공고',
        'title': title,
        'agency': agency,
        'budget': budget,
        'deadline': deadline,
        'postDate': post_date,
        'contractType': clean(item.get('cntrctMthdNm') or '공모'),
        'category': guess_category(title, desc),
        'keywords': [k for k in KEYWORDS if k in title],
        'description': desc,
        'requirements': [],
        'url': url,
        'source': 'bizinfo',
    }

def parse_html(html, keyword):
    results = []
    # pblancId 포함 링크 추출
    pattern = re.compile(r'pblancId=(\d+)[^"\']*["\'][^>]*>\s*([^<]{5,100})')
    seen = set()
    for m in pattern.finditer(html):
        pblanc_id, title = m.group(1), clean(m.group(2))
        if not title or pblanc_id in seen:
            continue
        seen.add(pblanc_id)
        # 키워드 관련성 확인
        if not any(k in title for k in KEYWORDS):
            continue
        results.append(make_bid(pblanc_id, title))
        print(f'       HTML 파싱: {title[:30]}...')
    return results

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] bizinfo XR 공고 수집 시작')
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
        time.sleep(2)

    print(f'\n총 {len(all_bids)}건 수집')

    os.makedirs('data', exist_ok=True)

    # 0건이면 기존 데이터 유지
    if len(all_bids) == 0:
        print('⚠ 0건 수집 — bizinfo 접근 제한 가능성')
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
