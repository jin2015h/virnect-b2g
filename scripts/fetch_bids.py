import json, time, re, os, requests
from datetime import datetime, timedelta

API_KEY  = 'fb382c284306f27f3c44e28cf6718dd7208691a64314f00df3dabf9008133b07'
API_BASE = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService'
DAYS     = 3   # 조회 범위 (일) — 매일 자동실행 기준 3일이면 충분

XR_KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실', '혼합현실',
    '메타버스', '디지털트윈', '스마트글래스', '홀로그램',
    '실감콘텐츠', '실감기술', '가상훈련', '원격협업',
    '웨어러블', '헤드셋', 'HMD',
]

def clean(v):
    if not v: return ''
    v = re.sub(r'<[^>]+>', '', str(v))
    for a,b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' ')]:
        v = v.replace(a, b)
    return re.sub(r'\s+', ' ', v).strip()

def is_xr(t): return any(k in t for k in XR_KEYWORDS)

def category(title):
    if any(k in title for k in ['군','국방','방위']): return 'MR/군사'
    if any(k in title for k in ['안전','재해','사고']): return 'AI/안전'
    if any(k in title for k in ['물류','창고','배송']): return 'AR/물류'
    if any(k in title for k in ['의료','수술','병원']): return 'VR/의료'
    if any(k in title for k in ['트윈','디지털트윈']):  return '디지털트윈'
    return 'AR/XR'

def parse_items(items):
    if isinstance(items, dict): items = items.get('item', [])
    if isinstance(items, dict): items = [items]
    out = []
    for item in (items or []):
        title = clean(item.get('bidNtceNm') or '')
        if not title: continue
        no  = str(item.get('bidNtceNo') or abs(hash(title)) % 1000000)
        amt = str(item.get('presmptPrce') or '')
        budget = f"{int(amt):,}원" if amt.isdigit() and int(amt) > 0 else '미정'
        out.append({
            'id': f'G2B-{no}', 'stage': '입찰공고', 'title': title,
            'agency':       clean(item.get('ntceInsttNm') or ''),
            'budget':       budget,
            'deadline':     clean(item.get('bidClseDt') or '-'),
            'postDate':     clean(item.get('bidNtceDt') or datetime.now().strftime('%Y-%m-%d')),
            'contractType': clean(item.get('cntrctMthdNm') or '입찰'),
            'category':     category(title),
            'keywords':     [k for k in XR_KEYWORDS if k in title],
            'description':  title, 'requirements': [],
            'url': f'https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoDtl.do?bidno={no}',
            'source': 'g2b',
        })
    return out

def fetch_g2b(session, keyword):
    now   = datetime.now()
    start = now - timedelta(days=DAYS)
    bgn   = start.strftime('%Y%m%d') + '0000'
    end   = now.strftime('%Y%m%d')   + '2359'
    kw    = requests.utils.quote(keyword)
    ops   = ['ServcPPSSrch', 'ThngPPSSrch', 'CnstwkPPSSrch']

    for op in ops:
        url = (f'{API_BASE}/getBidPblancListInfo{op}'
               f'?ServiceKey={API_KEY}'
               f'&numOfRows=10&pageNo=1&type=json'
               f'&inqryDiv=1'
               f'&inqryBgnDt={bgn}&inqryEndDt={end}'
               f'&bidNtceNm={kw}')
        try:
            r = session.get(url, timeout=15)
            label = op.replace('PPSSrch','')
            print(f'  [{keyword}]{label}: {r.status_code}')
            if r.status_code != 200: continue

            data  = r.json()
            # 에러 응답 처리
            if 'nkoneps.com.response.ResponseError' in data:
                msg = data['nkoneps.com.response.ResponseError']['header']['resultMsg']
                print(f'    API에러: {msg}')
                continue

            body  = data.get('response', {}).get('body', {})
            total = body.get('totalCount', 0)
            print(f'    totalCount: {total}')
            if not total: continue

            parsed = parse_items(body.get('items', {}))
            print(f'    파싱: {len(parsed)}건')
            if parsed: return parsed
        except Exception as e:
            print(f'    오류: {e}')
    return []

def fetch_bizinfo(session):
    out = []
    try:
        r = session.get('https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do',
                        headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR'}, timeout=15)
        if r.status_code != 200: return out
        pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>', re.DOTALL)
        seen = set()
        for m in pat.finditer(r.text):
            pid, title = m.group(1), clean(m.group(2))
            if not title or len(title) < 4 or pid in seen: continue
            if title in ['목록','이전','다음','확인','취소','닫기','스크랩']: continue
            seen.add(pid)
            ctx   = r.text[max(0,m.start()-50):m.end()+300]
            dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
            out.append({
                'id': f'BIZ-{pid}', 'stage': '입찰공고', 'title': title, 'agency': '',
                'budget': '미정',
                'deadline': dates[1].replace('.','-') if len(dates)>1 else '-',
                'postDate': dates[0].replace('.','-') if dates else datetime.now().strftime('%Y-%m-%d'),
                'contractType': '공모', 'category': category(title),
                'keywords': [k for k in XR_KEYWORDS if k in title],
                'description': title, 'requirements': [],
                'url': f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
                'source': 'bizinfo',
            })
        print(f'  bizinfo: {len(out)}건')
    except Exception as e:
        print(f'  bizinfo 오류: {e}')
    return out

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] XR 공고 수집 (최근 {DAYS}일)')
    sess = requests.Session()
    sess.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json'})

    all_bids, seen = [], set()
    def add(bids):
        n = 0
        for b in bids:
            if b['id'] not in seen:
                seen.add(b['id']); all_bids.append(b); n += 1
        return n

    print('\n[1단계] 나라장터 API')
    for kw in XR_KEYWORDS:
        n = add(fetch_g2b(sess, kw))
        if n: print(f'  +{n}건 (누적 {len(all_bids)}건)')
        time.sleep(0.3)

    print('\n[2단계] bizinfo')
    add(fetch_bizinfo(sess))

    xr = [b for b in all_bids if is_xr(b['title'])]
    if not xr and all_bids: xr = all_bids
    print(f'\n전체: {len(all_bids)}건, XR: {len(xr)}건')

    os.makedirs('data', exist_ok=True)
    if not xr:
        if os.path.exists('data/bids.json'):
            ex = json.load(open('data/bids.json', encoding='utf-8'))
            if ex.get('total', 0) > 0:
                ex['updatedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M') + ' (캐시)'
                json.dump(ex, open('data/bids.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
                print('0건 — 기존 캐시 유지')
                return
    out = {'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'), 'total': len(xr), 'bids': xr}
    json.dump(out, open('data/bids.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 저장: {len(xr)}건')

if __name__ == '__main__':
    main()
