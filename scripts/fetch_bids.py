import json, time, re, os, requests
from datetime import datetime, timedelta

API_KEY  = 'fb382c284306f27f3c44e28cf6718dd7208691a64314f00df3dabf9008133b07'
API_BASE      = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService'
BFSPEC_BASE   = 'https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService'  # 사전규격정보서비스
DAYS          = 14  # 조회 범위 (일) — API 최대 허용 범위

XR_KEYWORDS = [
    # 핵심 XR
    'AR', 'VR', 'XR', 'MR', 'HMD',
    '증강현실', '가상현실', '혼합현실', '확장현실',
    '메타버스', '홀로그램', '실감콘텐츠', '실감기술',
    '몰입형', '공간컴퓨팅', '가상공간',

    # VIRNECT 제품 연관
    '스마트글래스', '스마트안경', '안경형', '웨어러블', '헤드셋',
    '디지털트윈', '디지털 트윈',
    '원격협업', '원격지원', '원격작업', '원격점검',
    '가상훈련', 'VR훈련', 'AR훈련',

    # 산업 안전 (VisionX)
    '스마트안전', '산업안전', '현장안전', '안전관제',
    '안전모니터링', '스마트헬멧', '작업자안전',

    # 스마트팩토리 / 제조
    '스마트팩토리', '스마트공장', '제조혁신', '스마트제조',
    '작업지시', '현장지원', '유지보수AR', '설비점검',

    # 공간인식 / 컴퓨터비전
    '컴퓨터비전', '비전AI', '영상인식', '영상분석',
    '공간인식', '3D시각화', '3D스캔', '포인트클라우드',
    '마커리스', '실내측위',

    # 건설 / 시설 (Twin/Track)
    'BIM', '스마트건설', '스마트시티', '시설관리',
    '건설현장', '디지털현장',

    # 교육 / 훈련 시뮬레이션
    '시뮬레이션', '가상시뮬레이션', '안전교육VR',
    '실감교육', '체험형교육', '몰입형교육',

    # 피지컬 AI / 지능형 시스템
    '피지컬AI', '피지컬 AI', 'Physical AI', 'PhysicalAI',
    '지능형로봇', '지능형시스템', '지능형제조', '자율제조',
    'AI로봇', 'AI검사시스템', 'AI기반',

    # 육안검사 / 검사 자동화
    '육안검사', '검사자동화', '자동화검사', '무인검사',
    '표면검사', '외관불량', '품질자동화', '인라인검사',
    '스마트검사', '검사솔루션',

    # 디지털트윈 확장
    '디지털트윈', '디지털 트윈', '가상공장', '가상플랜트',
    '공장디지털화', '제조디지털화', '디지털전환',
    'CPS', '사이버물리', '가상모델', '3D모델링',
    '실시간모니터링', '공정모니터링', '설비모니터링',
    '로봇', '협동로봇', '자율주행로봇', '서비스로봇', '산업용로봇',
    'AMR', 'AGV', '자율이동', '로봇시스템', '로봇플랫폼',
    '드론', '무인기', 'UAV',

    # 비전 검사 / 품질
    '비전검사', '외관검사', '불량검출', '결함검출', '품질검사',
    '머신비전', '자동검사', '비파괴검사', 'AOI',
    '딥러닝검사', 'AI검사', '이미지분석',

    # 시뮬레이션
    '시뮬레이션', '가상시뮬레이션', '디지털시뮬레이션',
    '물리시뮬레이션', '로봇시뮬레이션', '공정시뮬레이션',
    '가상환경', '가상테스트',

    # 에지AI / 플랫폼
    '엣지AI', '에지AI', 'AI플랫폼', 'AI솔루션',
]

def clean(v):
    if not v: return ''
    v = re.sub(r'<[^>]+>', '', str(v))
    for a,b in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' ')]:
        v = v.replace(a, b)
    return re.sub(r'\s+', ' ', v).strip()

import re as _re
# 영문 단독 키워드는 단어경계로 매칭, 한글은 포함 여부로 매칭
_EN_KW = {'AR', 'VR', 'XR', 'MR', 'HMD', 'BIM', 'AMR', 'AGV', 'UAV', 'AOI'}
_KO_KW = set(XR_KEYWORDS) - _EN_KW | {'디지털 트윈'}

def is_xr(t):
    for k in _EN_KW:
        if _re.search(r'(?<![A-Za-z])' + k + r'(?![A-Za-z])', t):
            return True
    return any(k in t for k in _KO_KW)

def category(title):
    if any(k in title for k in ['군','국방','방위','전술','함정']): return 'MR/군사'
    if any(k in title for k in ['안전','재해','사고','소방','구조','안전모','헬멧']): return 'AI/안전'
    if any(k in title for k in ['물류','창고','배송','피킹']): return 'AR/물류'
    if any(k in title for k in ['의료','수술','병원','해부','재활']): return 'VR/의료'
    if any(k in title for k in ['트윈','디지털트윈','디지털 트윈','BIM','시설관리']): return '디지털트윈'
    if any(k in title for k in ['스마트팩토리','스마트공장','제조','작업지시','설비점검','유지보수']): return '스마트팩토리'
    if any(k in title for k in ['건설','스마트건설','현장','스마트시티']): return '스마트건설'
    if any(k in title for k in ['교육','훈련','시뮬레이션','체험','학습']): return 'XR/교육훈련'
    if any(k in title for k in ['피지컬AI','피지컬 AI','Physical AI','PhysicalAI','지능형로봇','지능형제조','자율제조']): return '피지컬AI'
    if any(k in title for k in ['육안검사','검사자동화','표면검사','외관불량','인라인검사','스마트검사','무인검사']): return 'AI/비전검사'
    if any(k in title for k in ['가상공장','가상플랜트','공장디지털화','제조디지털화','디지털전환','CPS','사이버물리','공정모니터링','설비모니터링']): return '디지털트윈'
    if any(k in title for k in ['비전검사','외관검사','불량검출','결함검출','품질검사','머신비전','AOI','비파괴']): return 'AI/비전검사'
    if any(k in title for k in ['시뮬레이션','가상시뮬레이션','로봇시뮬레이션','공정시뮬레이션','가상환경']): return 'XR/시뮬레이션'
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
            'keywords':     [k for k in XR_KEYWORDS if _re.search(r'(?<![A-Za-z])'+k+r'(?![A-Za-z])', title) if k in _EN_KW] +
                            [k for k in _KO_KW if k in title],
            'description':  title, 'requirements': [],
            'url': f'https://www.g2b.go.kr:8101/ep/tbid/tbidList.do?bidNm={no}&searchDtType=1&radOrgan=1&regYn=Y&bidSearchType=1&searchType=1',
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

def fetch_prespec(keyword, bgn, end):
    """사전규격정보서비스 — 입찰공고 전 단계 (공공데이터포털 별도 신청 필요)
    서비스: 조달청_나라장터 사전규격정보서비스 (data.go.kr ID: 15129437)
    오퍼레이션:
      - getBfSpecListInfoServc  (용역)
      - getBfSpecListInfoThng   (물품)
      - getBfSpecListInfoCnstwk (공사)
    """
    out = []
    ops = [('Servc','용역'), ('Thng','물품'), ('Cnstwk','공사')]
    for op, op_nm in ops:
        try:
            url = (f'{BFSPEC_BASE}/getHrcspSsstndrdInfo{op}'
                   f'?ServiceKey={API_KEY}'
                   f'&numOfRows=10&pageNo=1&type=json'
                   f'&inqryBgnDt={bgn}&inqryEndDt={end}'
                   f'&bidNtceNm={requests.utils.quote(keyword)}')
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                continue
            body = r.json().get('response', {})
            hdr  = body.get('header', {})
            code = hdr.get('resultCode', '')
            if code not in ('00', '0'):
                # 미등록 서비스인 경우 조용히 스킵
                if code in ('99', '22', '30'):
                    return []  # 이 키로 미등록 — 더 이상 시도 안 함
                continue
            items = body.get('body', {}).get('items', {})
            parsed = parse_items(items)
            for b in parsed:
                b['stage'] = '사전규격'
                b['contractType'] = b.get('contractType', '공모 예정')
            out.extend(parsed)
        except Exception:
            pass
    return out


def fetch_bizinfo_keyword(session, keyword):
    """bizinfo 키워드 검색 — 정부지원사업 포함"""
    out = []
    try:
        # bizinfo는 GET 파라미터로 검색 지원
        url = 'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do'
        r = session.get(url, params={'schKeyword': keyword, 'schCondition': 'title', 'pageIndex': 1},
                        headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR',
                                 'Referer':'https://www.bizinfo.go.kr/'}, timeout=15)
        if r.status_code != 200: return out
        pat = re.compile(r'pblancId=([\w_]+)[^"\']*["\'][^>]*>\s*([^<]{4,200}?)\s*</a>', re.DOTALL)
        seen = set()
        for m in pat.finditer(r.text):
            pid, title = m.group(1), clean(m.group(2))
            if not title or len(title) < 4 or pid in seen: continue
            if title in ['목록','이전','다음','확인','취소','닫기','스크랩','검색']: continue
            # 실제로 키워드가 제목에 포함된 것만
            if not is_xr(title): continue
            seen.add(pid)
            ctx   = r.text[max(0,m.start()-50):m.end()+300]
            dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
            out.append({
                'id': f'BIZ-{pid}', 'stage': '지원사업', 'title': title, 'agency': '',
                'budget': '미정',
                'deadline': dates[1].replace('.','-') if len(dates)>1 else '-',
                'postDate': dates[0].replace('.','-') if dates else datetime.now().strftime('%Y-%m-%d'),
                'contractType': '공모/지원', 'category': category(title),
                'keywords': [k for k in XR_KEYWORDS if k in title],
                'description': title, 'requirements': [],
                'url': f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
                'source': 'bizinfo',
            })
    except Exception as e:
        print(f'    bizinfo[{keyword}] 오류: {e}')
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

    print('\n[1.5단계] 사전규격 API')
    prespec_ok = True
    for kw in XR_KEYWORDS[:5]:  # 첫 5개 키워드로 서비스 가용 여부 확인
        ps = fetch_prespec(kw, bgn, end)
        if ps is None:  # 미등록 서비스
            print('  ⚠️  사전규격 API 미등록 — data.go.kr에서 별도 신청 필요')
            print('     https://www.data.go.kr/data/15129437/openapi.do')
            prespec_ok = False
            break
        if ps:
            n = add(ps)
            print(f'  [{kw}]: {n}건')

    if prespec_ok:
        for kw in XR_KEYWORDS[5:]:
            ps = fetch_prespec(kw, bgn, end)
            if ps:
                n = add(ps)
                if n: print(f'  [{kw}]: {n}건')
            time.sleep(0.2)


    bizinfo_all = []
    biz_seen_ids = set()
    for kw in XR_KEYWORDS:
        bids = fetch_bizinfo_keyword(sess, kw)
        new = [b for b in bids if b['id'] not in biz_seen_ids]
        for b in new: biz_seen_ids.add(b['id'])
        if new:
            print(f'  [{kw}]: {len(new)}건')
        bizinfo_all.extend(new)
        time.sleep(0.3)

    # bizinfo pblancId → URL 매핑 (g2b 결과 URL 보완용)
    title_to_biz_url = {b['title']: b['url'] for b in bizinfo_all}

    # g2b 결과에 bizinfo URL 덮어쓰기
    for b in all_bids:
        if b['source'] == 'g2b':
            matched = title_to_biz_url.get(b['title'])
            if matched:
                b['url'] = matched

    # bizinfo 공고 추가
    n = add(bizinfo_all)
    print(f'  bizinfo 합계: {n}건 추가')

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
