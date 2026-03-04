"""
나라장터(g2b.go.kr) + bizinfo 공고 수집
나라장터는 키워드 검색 정상 지원
"""
import json, time, re, os
from datetime import datetime, timedelta
import requests

XR_KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', '증강현실', '가상현실', '혼합현실',
    '메타버스', '디지털트윈', '스마트글래스', '홀로그램',
    '실감콘텐츠', '실감기술', '가상훈련', '원격협업',
    '웨어러블', '헤드셋', 'HMD',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}

BASE_G2B    = 'https://www.g2b.go.kr'
BASE_BIZ    = 'https://www.bizinfo.go.kr'

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    for a, b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'")]:
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

# ── 나라장터 검색 ────────────────────────────────────────────────────────
def fetch_g2b_keyword(session, keyword):
    """나라장터 입찰공고 키워드 검색 (공개 검색 API)"""
    results = []
    try:
        # 나라장터 검색 엔드포인트
        url = f'{BASE_G2B}/pbs/pba/bids/findBidPbancList'
        params = {
            'bidNm': keyword,
            'pageNo': 1,
            'numOfRows': 20,
        }
        resp = session.get(url, params=params, timeout=15)
        print(f'  G2B [{keyword}]: {resp.status_code}')

        if resp.status_code == 200:
            ct = resp.headers.get('Content-Type', '')
            if 'json' in ct:
                data = resp.json()
                items = data.get('data', {}).get('list', []) or data.get('items', []) or []
                for item in items:
                    title = clean(item.get('bidNm') or item.get('title') or '')
                    if not title: continue
                    bid_no = str(item.get('bidNo') or item.get('id') or abs(hash(title)) % 1000000)
                    results.append({
                        'id': f'G2B-{bid_no}',
                        'stage': '입찰공고',
                        'title': title,
                        'agency': clean(item.get('dminsttNm') or item.get('orgNm') or ''),
                        'budget': clean(item.get('presmptPrce') or '미정'),
                        'deadline': clean(item.get('bidClseDt') or '-'),
                        'postDate': clean(item.get('bidNtceDt') or datetime.now().strftime('%Y-%m-%d')),
                        'contractType': clean(item.get('cntrctMthdNm') or '입찰'),
                        'category': guess_category(title),
                        'keywords': [k for k in XR_KEYWORDS if k in title],
                        'description': title,
                        'requirements': [],
                        'url': f'{BASE_G2B}/pbs/pba/bids/viewBidPbanc?bidNo={bid_no}',
                        'source': 'g2b',
                    })
    except Exception as e:
        print(f'  G2B 오류: {e}')
    return results

def fetch_g2b_html(session, keyword):
    """나라장터 HTML 검색 폴백"""
    results = []
    try:
        url = f'{BASE_G2B}/pbs/pba/bids/findBidPbancList.do'
        params = {'bidNm': keyword, 'pageNo': 1, 'numOfRows': 20}
        resp = session.get(url, params=params, timeout=15)
        print(f'  G2B-HTML [{keyword}]: {resp.status_code}, {len(resp.text)}자')

        if resp.status_code == 200 and len(resp.text) > 500:
            # 공고번호 패턴 추출
            pat = re.compile(r'bidNo=(\d+-\d+)[^"\']*["\'][^>]*>\s*([^<]{5,150}?)\s*</a>', re.DOTALL)
            seen = set()
            for m in pat.finditer(resp.text):
                bid_no = m.group(1)
                title  = clean(m.group(2))
                if not title or bid_no in seen: continue
                seen.add(bid_no)
                results.append({
                    'id': f'G2B-{bid_no.replace("-","_")}',
                    'stage': '입찰공고', 'title': title, 'agency': '',
                    'budget': '미정', 'deadline': '-',
                    'postDate': datetime.now().strftime('%Y-%m-%d'),
                    'contractType': '입찰', 'category': guess_category(title),
                    'keywords': [k for k in XR_KEYWORDS if k in title],
                    'description': title, 'requirements': [],
                    'url': f'{BASE_G2B}/pbs/pba/bids/viewBidPbanc?bidNo={bid_no}',
                    'source': 'g2b',
                })
    except Exception as e:
        print(f'  G2B-HTML 오류: {e}')
    return results

# ── bizinfo 기본 목록 (최신 15건 XR 필터) ────────────────────────────────
def fetch_bizinfo_latest(session):
    """bizinfo 최신 공고 중 XR 관련 필터링"""
    results = []
    try:
        url = f'{BASE_BIZ}/web/lay1/bbs/S1T122C128/AS/74/list.do'
        resp = session.get(url, timeout=15)
        if resp.status_code != 200: return results

        pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>', re.DOTALL)
        seen = set()
        for m in pat.finditer(resp.text):
            pid   = m.group(1)
            title = clean(m.group(2))
            if not title or len(title) < 4 or pid in seen: continue
            if title in ['목록','이전','다음','확인','취소','닫기','스크랩']: continue
            seen.add(pid)
            ctx   = clean(resp.text[max(0,m.start()-50):min(len(resp.text),m.end()+300)])
            dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
            results.append({
                'id': f'BIZ-{pid}', 'stage': '입찰공고', 'title': title, 'agency': '',
                'budget': '미정',
                'deadline': dates[1].replace('.','-') if len(dates)>1 else '-',
                'postDate': dates[0].replace('.','-') if dates else datetime.now().strftime('%Y-%m-%d'),
                'contractType': '공모', 'category': guess_category(title),
                'keywords': [k for k in XR_KEYWORDS if k in title],
                'description': title, 'requirements': [],
                'url': f'{BASE_BIZ}/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
                'source': 'bizinfo',
            })
        print(f'  bizinfo 최신: {len(results)}건')
    except Exception as e:
        print(f'  bizinfo 오류: {e}')
    return results

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] XR 공고 수집 시작')
    session = requests.Session()
    session.headers.update(HEADERS)

    all_bids = []
    seen_ids = set()

    def add(bids):
        n = 0
        for b in bids:
            if b['id'] not in seen_ids:
                seen_ids.add(b['id'])
                all_bids.append(b)
                n += 1
        return n

    # 1. 나라장터 키워드 검색
    print('\n[1단계] 나라장터 키워드 검색')
    for kw in XR_KEYWORDS:
        bids = fetch_g2b_keyword(session, kw)
        if not bids:
            bids = fetch_g2b_html(session, kw)
        n = add(bids)
        if n: print(f'    +{n}건')
        time.sleep(0.5)

    # 2. bizinfo 최신 목록 (XR 필터 없이 전부 추가, 앱에서 필터)
    print('\n[2단계] bizinfo 최신 목록')
    bizinfo_all = fetch_bizinfo_latest(session)
    add(bizinfo_all)

    # 나라장터에서 못 잡은 경우 bizinfo 전체도 포함
    xr_bids = [b for b in all_bids if is_xr(b['title'])]

    # XR 0건이면 bizinfo 전체 포함 (수동 확인용)
    if not xr_bids and bizinfo_all:
        print('XR 키워드 미매칭 — bizinfo 전체 포함')
        xr_bids = bizinfo_all

    print(f'\n전체: {len(all_bids)}건, 최종: {len(xr_bids)}건')

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
    print(f'저장 완료: {len(xr_bids)}건')

if __name__ == '__main__':
    main()
