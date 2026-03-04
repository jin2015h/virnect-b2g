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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://www.bizinfo.go.kr/',
}

BASE = 'https://www.bizinfo.go.kr'

def clean(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    for a, b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'"),('&quot;','"')]:
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text).strip()

def is_xr(title):
    return any(k in title for k in XR_KEYWORDS)

def guess_category(title):
    if any(k in title for k in ['군', '국방', '방위', '훈련', '전술']): return 'MR/군사'
    if any(k in title for k in ['안전', '산업안전', '재해', '사고']): return 'AI/안전'
    if any(k in title for k in ['물류', '창고', '피킹', '배송']): return 'AR/물류'
    if any(k in title for k in ['의료', '해부', '수술', '병원']): return 'VR/의료'
    if any(k in title for k in ['트윈', '디지털트윈']): return '디지털트윈'
    return 'AR/XR'

def make_bid(pid, title, agency='', post_date='', deadline=''):
    if not post_date: post_date = datetime.now().strftime('%Y-%m-%d')
    return {
        'id': f'BIZ-{pid}', 'stage': '입찰공고', 'title': title, 'agency': agency,
        'budget': '미정', 'deadline': deadline or '-', 'postDate': post_date,
        'contractType': '공모', 'category': guess_category(title),
        'keywords': [k for k in XR_KEYWORDS if k in title],
        'description': title, 'requirements': [],
        'url': f'{BASE}/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
        'source': 'bizinfo',
    }

def fetch_rss(session, keyword):
    """RSS 피드로 키워드 검색"""
    results = []
    urls = [
        f'{BASE}/uss/rss/bizinfoRss.do?searchKeyword={requests.utils.quote(keyword)}',
        f'{BASE}/uss/rss/bizinfoRss.do?schKeyword={requests.utils.quote(keyword)}',
    ]
    for url in urls:
        try:
            resp = session.get(url, timeout=15)
            print(f'  RSS [{keyword}]: {resp.status_code}')
            if resp.status_code != 200: continue
            xml = resp.text
            # RSS item 파싱
            items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
            print(f'  RSS items: {len(items)}개')
            for item in items:
                title = clean(re.search(r'<title>(.*?)</title>', item, re.DOTALL).group(1) if re.search(r'<title>', item) else '')
                link  = clean(re.search(r'<link>(.*?)</link>', item, re.DOTALL).group(1) if re.search(r'<link>', item) else '')
                date  = clean(re.search(r'<pubDate>(.*?)</pubDate>', item, re.DOTALL).group(1) if re.search(r'<pubDate>', item) else '')
                if not title: continue
                pid_m = re.search(r'pblancId=([\w_]+)', link)
                pid = pid_m.group(1) if pid_m else str(abs(hash(title)) % 1000000)
                results.append(make_bid(pid, title, post_date=date[:10] if date else ''))
            if results: break
        except Exception as e:
            print(f'  RSS 오류: {e}')
    return results

def fetch_post_search(session, keyword):
    """POST 방식 키워드 검색"""
    results = []
    list_url = f'{BASE}/web/lay1/bbs/S1T122C128/AS/74/list.do'
    
    # 여러 파라미터 조합 시도
    param_sets = [
        {'schKeyword': keyword, 'pageIndex': 1, 'pageUnit': 20},
        {'searchNm': keyword, 'pageIndex': 1, 'pageUnit': 20},
        {'pblancNm': keyword, 'pageIndex': 1, 'pageUnit': 20},
        {'schText': keyword, 'pageIndex': 1, 'pageUnit': 20},
    ]
    
    for params in param_sets:
        try:
            resp = session.post(list_url, data=params,
                headers={**HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15)
            if resp.status_code != 200: continue
            
            # 패턴2로 추출
            pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>', re.DOTALL)
            seen = set()
            for m in pat.finditer(resp.text):
                pid = m.group(1)
                title = clean(m.group(2))
                if not title or len(title) < 4 or pid in seen: continue
                if title in ['목록','이전','다음','확인','취소','닫기','스크랩']: continue
                seen.add(pid)
                ctx = clean(resp.text[max(0,m.start()-50):min(len(resp.text),m.end()+300)])
                dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
                results.append(make_bid(pid, title,
                    post_date=dates[0].replace('.','-') if dates else '',
                    deadline=dates[1].replace('.','-') if len(dates)>1 else ''))
            
            if results:
                pname = list(params.keys())[0]
                print(f'  POST {pname}=[{keyword}]: {len(results)}건')
                break
        except Exception as e:
            print(f'  POST 오류: {e}')
    return results

def fetch_default_page(session):
    """기본 목록에서 패턴2로 추출"""
    list_url = f'{BASE}/web/lay1/bbs/S1T122C128/AS/74/list.do'
    resp = session.get(list_url, timeout=15)
    results = []
    seen = set()
    pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>', re.DOTALL)
    for m in pat.finditer(resp.text):
        pid = m.group(1)
        title = clean(m.group(2))
        if not title or len(title) < 4 or pid in seen: continue
        if title in ['목록','이전','다음','확인','취소','닫기','스크랩']: continue
        seen.add(pid)
        ctx = clean(resp.text[max(0,m.start()-50):min(len(resp.text),m.end()+300)])
        dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
        results.append(make_bid(pid, title,
            post_date=dates[0].replace('.','-') if dates else '',
            deadline=dates[1].replace('.','-') if len(dates)>1 else ''))
    print(f'기본 목록: {len(results)}건')
    return results

def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] bizinfo XR 공고 수집 시작')
    session = requests.Session()
    session.headers.update(HEADERS)

    all_bids = []
    seen_ids = set()

    def add(bids):
        for b in bids:
            if b['id'] not in seen_ids:
                seen_ids.add(b['id'])
                all_bids.append(b)

    # 1. RSS 피드로 키워드 검색
    print('\n[1단계] RSS 키워드 검색')
    for kw in XR_KEYWORDS:
        bids = fetch_rss(session, kw)
        add(bids)
        time.sleep(0.5)

    # 2. POST 키워드 검색
    print('\n[2단계] POST 키워드 검색')
    for kw in ['증강현실', '가상현실', '디지털트윈', '메타버스', 'XR', 'AR', 'VR']:
        bids = fetch_post_search(session, kw)
        add(bids)
        time.sleep(0.8)

    # 3. 기본 목록 (최신 15건)
    print('\n[3단계] 기본 목록')
    add(fetch_default_page(session))

    xr_bids = [b for b in all_bids if is_xr(b['title'])]
    print(f'\n전체: {len(all_bids)}건, XR: {len(xr_bids)}건')

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
