"""
bizinfo.go.kr XR 공고 수집 스크립트
GitHub Actions에서 실행 → data/bids.json 저장
"""
import json, time, re, os
from datetime import datetime
import requests

# XR 관련 검색 키워드
KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실',
    '혼합현실', '메타버스', '디지털트윈', '스마트글래스',
    '홀로그램', '실감콘텐츠'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/javascript, */*',
    'Referer': 'https://www.bizinfo.go.kr/',
}

def guess_category(title, desc=''):
    t = (title + ' ' + desc).lower()
    if any(k in t for k in ['군', '국방', '방위', '훈련', '전술']): return 'MR/군사'
    if any(k in t for k in ['안전', '산업안전', '재해', '사고']): return 'AI/안전'
    if any(k in t for k in ['물류', '창고', '피킹', '배송']): return 'AR/물류'
    if any(k in t for k in ['의료', '해부', '수술', '의과', '병원']): return 'VR/의료'
    if any(k in t for k in ['트윈', 'twin', '시뮬레이']): return '디지털트윈'
    if any(k in t for k in ['ar', '증강현실', '원격']): return 'AR/XR'
    return '기타XR'

def guess_stage(item):
    status = item.get('pblancSttusNm', '') or item.get('sttusNm', '')
    if '접수' in status: return '요청접수'
    if '규격' in status: return '사전규격'
    if '공고' in status or '입찰' in status: return '입찰공고'
    if '개찰' in status or '결과' in status: return '개찰결과'
    if '계약' in status: return '계약현황'
    return '입찰공고'

def clean(text):
    if not text: return ''
    return re.sub(r'<[^>]+>', '', str(text)).strip()

def fetch_keyword(keyword):
    results = []
    try:
        # bizinfo.go.kr OpenAPI JSON 엔드포인트
        url = 'https://www.bizinfo.go.kr/uss/ion/ptn/selectAnnouncementListjson.do'
        params = {
            'searchKeyword': keyword,
            'pageUnit': 20,
            'pageIndex': 1,
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        items = (data.get('pblancList')
                 or data.get('list')
                 or data.get('resultList')
                 or [])

        for item in items:
            title = clean(item.get('pblancNm') or item.get('pblancTitle') or '')
            if not title:
                continue

            bid_id = str(item.get('pblancId') or item.get('id') or '')
            agency = clean(item.get('jrsdInsttNm') or item.get('insttNm') or '')
            budget = clean(item.get('bsnsYrCnt') or item.get('budget') or '미정')
            deadline = clean(item.get('reqstDt') or item.get('closingDt') or '-')
            post_date = clean(item.get('pblancBgngDt') or item.get('startDt') or '-')
            desc = clean(item.get('pblancCn') or item.get('content') or '')
            contract_type = clean(item.get('cntrctMthdNm') or '공모')

            # 상세 페이지 URL
            if bid_id:
                detail_url = f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/pblancDetail.do?pblancId={bid_id}'
            else:
                detail_url = f'https://www.bizinfo.go.kr/web/search/searchList.do?searchKeyword={requests.utils.quote(title)}'

            kw_tags = [k for k in KEYWORDS if k in title or k in desc]

            results.append({
                'id': f'BIZ-{bid_id}' if bid_id else f'BIZ-{hash(title) & 0xFFFF:04x}',
                'stage': guess_stage(item),
                'title': title,
                'agency': agency,
                'budget': budget if '원' in budget else budget + '원' if budget != '미정' else '미정',
                'deadline': deadline,
                'postDate': post_date,
                'contractType': contract_type,
                'category': guess_category(title, desc),
                'keywords': kw_tags or [keyword],
                'description': desc[:300] + ('...' if len(desc) > 300 else ''),
                'requirements': [],
                'url': detail_url,
                'source': 'bizinfo',
            })
    except Exception as e:
        print(f'  ⚠ [{keyword}] 실패: {e}')
    return results

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] bizinfo XR 공고 수집 시작')
    all_bids = []
    seen_ids = set()

    for kw in KEYWORDS:
        print(f'  🔍 키워드: {kw}')
        bids = fetch_keyword(kw)
        for b in bids:
            if b['id'] not in seen_ids:
                seen_ids.add(b['id'])
                all_bids.append(b)
        print(f'     → {len(bids)}건 (누적 {len(all_bids)}건)')
        time.sleep(1.0)  # 서버 부하 방지

    # 저장
    os.makedirs('data', exist_ok=True)
    output = {
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total': len(all_bids),
        'bids': all_bids,
    }
    with open('data/bids.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'✅ 완료: {len(all_bids)}건 → data/bids.json')

if __name__ == '__main__':
    main()
