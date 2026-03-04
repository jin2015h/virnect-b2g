"""
나라장터 입찰공고 Open API + bizinfo 수집
"""
import json, time, re, os, requests
from datetime import datetime, timedelta

API_KEY  = 'fb382c284306f27f3c44e28cf6718dd7208691a64314f00df3dabf9008133b07'
API_BASE = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService'

XR_KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실', '혼합현실',
    '메타버스', '디지털트윈', '스마트글래스', '홀로그램',
    '실감콘텐츠', '실감기술', '가상훈련', '원격협업',
    '웨어러블', '헤드셋', 'HMD',
]

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    for a, b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' ')]:
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text).strip()

def is_xr(t): return any(k in t for k in XR_KEYWORDS)

def guess_category(title):
    if any(k in title for k in ['군', '국방', '방위', '훈련', '전술']): return 'MR/군사'
    if any(k in title for k in ['안전', '산업안전', '재해', '사고']): return 'AI/안전'
    if any(k in title for k in ['물류', '창고', '피킹', '배송']): return 'AR/물류'
    if any(k in title for k in ['의료', '해부', '수술', '병원']): return 'VR/의료'
    if any(k in title for k in ['트윈', '디지털트윈']): return '디지털트윈'
    return 'AR/XR'

def parse_items(items):
    results = []
    if isinstance(items, dict): items = items.get('item', [])
    if isinstance(items, dict): items = [items]
    if not items: return results
    for item in items:
        title = clean(item.get('bidNtceNm') or item.get('bidNm') or '')
        if not title: continue
        bid_no = str(item.get('bidNtceNo') or item.get('bidNo') or abs(hash(title)) % 1000000)
        budget = str(item.get('presmptPrce') or item.get('asignBdgtAmt') or '')
        if budget.isdigit() and int(budget) > 0:
            budget = f"{int(budget):,}원"
        else:
            budget = '미정'
        results.append({
            'id': f'G2B-{bid_no}', 'stage': '입찰공고',
            'title': title,
            'agency': clean(item.get('ntceInsttNm') or item.get('dminsttNm') or ''),
            'budget': budget,
            'deadline': clean(item.get('bidClseDt') or '-'),
            'postDate': clean(item.get('bidNtceDt') or item.get('rgstDt') or datetime.now().strftime('%Y-%m-%d')),
            'contractType': clean(item.get('cntrctMthdNm') or '입찰'),
            'category': guess_category(title),
            'keywords': [k for k in XR_KEYWORDS if k in title],
            'description': title, 'requirements': [],
            'url': f'https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoDtl.do?bidno={bid_no}',
            'source': 'g2b',
        })
    return results

def fetch_g2b(session, keyword):
    results = []
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=30)
    bgnDt = start_dt.strftime('%Y%m%d') + '0000'
    endDt = end_dt.strftime('%Y%m%d') + '2359'
    kw_enc = requests.utils.quote(keyword)

    ops = [
        'getBidPblancListInfoServcPPSSrch',
        'getBidPblancListInfoThngPPSSrch',
        'getBidPblancListInfoCnstwkPPSSrch',
    ]
    for op in ops:
        try:
            url = (f'{API_BASE}/{op}'
                   f'?ServiceKey={API_KEY}'
                   f'&numOfRows=20&pageNo=1&type=json'
                   f'&inqryDiv=1'
                   f'&bidNtceNm={kw_enc}'
                   f'&inqryBgnDt={bgnDt}&inqryEndDt={endDt}')
            label = op.replace('getBidPblancListInfo','').replace('PPSSrch','')
            resp = session.get(url, timeout=15)
            print(f'  [{keyword}]{label}: {resp.status_code}')
            if resp.status_code != 200: continue

            try:
                data = resp.json()
            except Exception:
                print(f'    JSON오류: {resp.text[:150]}')
                continue

            body  = data.get('response', {}).get('body', {})
            total = body.get('totalCount', 0)
            print(f'    totalCount: {total}')
            if total == 0:
                hdr = data.get('response', {}).get('header', {})
                print(f'    header: {hdr}')
                print(f'    raw응답: {resp.text[:400]}')
                continue

            parsed = parse_items(body.get('items', {}))
            print(f'    파싱: {len(parsed)}건')
            results.extend(parsed)
            if results: break
        except Exception as e:
            print(f'    오류: {e}')
    return results

def fetch_bizinfo_latest(session):
    results = []
    try:
        url = 'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do'
        resp = session.get(url, headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR'}, timeout=15)
        if resp.status_code != 200: return results
        pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>', re.DOTALL)
        seen = set()
        for m in pat.finditer(resp.text):
            pid = m.group(1); title = clean(m.group(2))
            if not title or len(title) < 4 or pid in seen: continue
            if title in ['목록','이전','다음','확인','취소','닫기','스크랩']: continue
            seen.add(pid)
            ctx = clean(resp.text[max(0,m.start()-50):min(len(resp.text),m.end()+300)])
            dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
            results.append({
                'id': f'BIZ-{pid}', 'stage': '입찰공고', 'title': title, 'agency': '',
                'budget': '미정',
                'deadline': dates[1].replace('.','-') if len(dates)>1 else '-',
                'postDate': dates[0].replace('.','-') if dates else datetime.now().strftime('%Y-%m-%d'),
                'contractType': '공모', 'category': guess_category(title),
                'keywords': [k for k in XR_KEYWORDS if k in title],
                'description': title, 'requirements': [],
                'url': f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
                'source': 'bizinfo',
            })
        print(f'  bizinfo: {len(results)}건')
    except Exception as e:
        print(f'  bizinfo 오류: {e}')
    return results

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] XR 공고 수집 시작')
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})

    all_bids = []; seen_ids = set()
    def add(bids):
        n = 0
        for b in bids:
            if b['id'] not in seen_ids:
                seen_ids.add(b['id']); all_bids.append(b); n += 1
        return n

    print('\n[1단계] 나라장터 Open API')
    for kw in XR_KEYWORDS:
        n = add(fetch_g2b(session, kw))
        if n: print(f'  +{n}건 (누적 {len(all_bids)}건)')
        time.sleep(0.3)

    print('\n[2단계] bizinfo 최신')
    add(fetch_bizinfo_latest(session))

    xr_bids = [b for b in all_bids if is_xr(b['title'])]
    if not xr_bids and all_bids: xr_bids = all_bids
    print(f'\n전체: {len(all_bids)}건, XR: {len(xr_bids)}건')

    os.makedirs('data', exist_ok=True)
    if not xr_bids:
        print('0건 — 기존 유지')
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
    print(f'✅ 저장 완료: {len(xr_bids)}건')

if __name__ == '__main__':
    main()
