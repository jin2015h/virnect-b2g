import json, time, re, os, requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY  = 'fb382c284306f27f3c44e28cf6718dd7208691a64314f00df3dabf9008133b07'
API_BASE      = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService'
BFSPEC_BASE   = 'https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService'  # 사전규격정보서비스
DAYS          = 14  # 조회 범위 (일) — API 최대 허용 범위

XR_KEYWORDS = [
    # 핵심 XR
    'AR', 'VR', 'XR', 'MR', 'HMD',
    '증강현실', '가상현실', '혼합현실', '확장현실',
    '메타버스', '홀로그램', '실감콘텐츠', '실감기술',
    '몰입형', '공간컴퓨팅',

    # VIRNECT 제품 연관
    '스마트글래스', '스마트안경', '웨어러블', '헤드셋',
    '디지털트윈',
    '원격협업', '원격지원', '원격점검',
    '가상훈련',

    # 산업 안전 (VisionX)
    '스마트안전', '산업안전', '안전관제', '스마트헬멧',

    # 스마트팩토리 / 제조
    '스마트팩토리', '스마트공장', '스마트제조',
    '작업지시', '설비점검',

    # 공간인식 / 컴퓨터비전
    '컴퓨터비전', '비전AI', '영상인식',
    '포인트클라우드', '실내측위',

    # 건설 / 시설
    'BIM', '스마트건설', '스마트시티',

    # 교육 / 훈련 시뮬레이션
    '시뮬레이션', '실감교육',

    # 피지컬 AI
    '피지컬AI', '피지컬 AI', 'Physical AI',
    '지능형로봇', '지능형제조', '자율제조',

    # 육안검사 / 검사 자동화
    '육안검사', '검사자동화', '표면검사', '머신비전', 'AOI',

    # 디지털트윈 확장
    '가상공장', '공장디지털화', '디지털전환',
    'CPS', '공정모니터링', '설비모니터링',

    # 로봇 / 자율이동
    '협동로봇', '자율주행로봇', '서비스로봇',
    'AMR', 'AGV', '드론', 'UAV',

    # 비전 검사 / 품질
    '비전검사', '외관검사', '불량검출', '결함검출', '품질검사',
    '비파괴검사', 'AI검사',

    # 로봇시뮬레이션
    '로봇시뮬레이션', '공정시뮬레이션', '가상환경',

    # 에지AI / 플랫폼
    '엣지AI', 'AI플랫폼',
]

# g2b API 검색용: 결과가 많은 핵심 키워드만 (나머지는 is_xr 필터로 걸림)
G2B_KEYWORDS = [
    'AR', 'VR', 'XR', 'MR', 'HMD',
    '증강현실', '가상현실', '혼합현실', '확장현실',
    '메타버스', '홀로그램', '실감콘텐츠',
    '디지털트윈', 'BIM',
    '스마트팩토리', '스마트공장',
    '시뮬레이션', '로봇시뮬레이션',
    '머신비전', '비전검사', '육안검사',
    '스마트안전', '협동로봇', 'AMR', 'AGV', '드론',
    '피지컬AI', '컴퓨터비전', 'AI검사',
    '스마트글래스', '원격협업', '공정모니터링',
    # AI 솔루션/플랫폼
    '인공지능', 'AI플랫폼', 'AI솔루션', '엣지AI',
    '영상인식', '영상분석', '비전AI', '딥러닝',
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
    # ── 명확히 무관한 사업 제외 ──────────────────────────
    EXCLUDE = [
        # 이벤트·행사 운영 (기술 납품 아님)
        '행사 위탁', '행사위탁', '행사 운영', '행사운영', '행사 기획', '박람회 운영',
        '박람회 위탁', '축제', '공연', '전시 운영', '홍보 대행', '홍보대행',
        # 드론 서비스 (촬영·방제·택배 등 하드웨어 운용)
        '드론 방제', '드론방제', '드론 촬영', '드론촬영', '드론 배송', '드론배송',
        '드론 순찰', '드론순찰', '드론 항공감시', '항공감시', '드론 대행',
        # 스포츠·게임 콘텐츠 운영
        '슈퍼리그', '스포츠 리그', '스포츠리그', 'e스포츠', '게임 대회', '게임대회',
        # 단순 구매·임차 (기술 납품 아님)
        '임차', '임대', '리스', '차량 구입', '장비 구입',
        # 조사·연구 (소프트웨어 개발 아님)
        '실태조사', '이용자보호', '인식조사', '설문조사',
        # 시설·청소·관리 용역
        '청소', '시설 관리', '시설관리', '건물 관리', '경비',
    ]
    if any(ex in t for ex in EXCLUDE):
        return False

    for k in _EN_KW:
        if _re.search(r'(?<![A-Za-z])' + k + r'(?![A-Za-z])', t):
            return True
    return any(k in t for k in _KO_KW)

def category(title):
    t = title

    # ── XR/AR ────────────────────────────────────────────
    if any(k in t for k in ['증강현실','AR글래스','AR고글','스마트글래스','스마트안경',
                             '홀로그램','HMD','헤드마운트','혼합현실','공간컴퓨팅']): return 'XR/AR'
    if any(k in t for k in ['가상현실','VR']): return 'XR/AR'
    if _re.search(r'(?<![A-Za-z])(?:AR|XR|MR)(?![A-Za-z])', t): return 'XR/AR'

    # ── 로봇 ─────────────────────────────────────────────
    if any(k in t for k in ['협동로봇','자율주행로봇','서비스로봇','지능형로봇',
                             '로봇시스템','로봇솔루션','로봇구축']): return '로봇'
    if _re.search(r'(?<![A-Za-z])(?:AMR|AGV)(?![A-Za-z])', t): return '로봇'
    if any(k in t for k in ['드론','UAV']) and not any(k in t for k in [
        '드론 방제','드론방제','드론 촬영','드론촬영','드론 배송','드론배송',
        '드론 순찰','항공감시','드론 대행','드론 행사','드론박람회']): return '로봇'

    # ── AI ───────────────────────────────────────────────
    if any(k in t for k in ['육안검사','검사자동화','표면검사','외관불량','인라인검사',
                             '비전검사','외관검사','불량검출','결함검출','품질검사',
                             '머신비전','AOI','비파괴']): return 'AI'
    if any(k in t for k in ['스마트안전','안전관제','스마트헬멧','산업안전',
                             '안전모니터링']): return 'AI'
    if any(k in t for k in ['피지컬AI','피지컬 AI','Physical AI','PhysicalAI',
                             '지능형제조','자율제조']): return 'AI'
    if any(k in t for k in ['AI플랫폼','AI 플랫폼','엣지AI','엣지 AI','컴퓨터비전',
                             '비전AI','영상인식','영상분석','AI솔루션','AI시스템',
                             '인공지능','머신러닝','딥러닝']): return 'AI'

    # ── 디지털트윈 ────────────────────────────────────────
    if any(k in t for k in ['디지털트윈','디지털 트윈','BIM','가상공장','가상플랜트',
                             '공장디지털화','CPS','사이버물리','공정모니터링',
                             '설비모니터링']): return '디지털트윈'

    # ── 스마트팩토리 ──────────────────────────────────────
    if any(k in t for k in ['스마트팩토리','스마트공장','스마트제조','작업지시',
                             '설비점검','유지보수','공정관리']): return '스마트팩토리'

    # ── 시뮬레이션 ────────────────────────────────────────
    if any(k in t for k in ['시뮬레이션','가상시뮬레이션','로봇시뮬레이션',
                             '공정시뮬레이션','가상환경','가상훈련','교육훈련',
                             '훈련','체험','실감교육']): return '시뮬레이션'

    # ── fallback ─────────────────────────────────────────
    return '기타'

_NOW = datetime.now()

def _is_past(deadline_str):
    """마감일이 현재 시각보다 이전이면 True"""
    if not deadline_str or deadline_str == '-': return False
    try:
        return datetime.fromisoformat(deadline_str[:16].replace(' ', 'T')) < _NOW
    except Exception:
        return False

def parse_items(items):
    if isinstance(items, dict): items = items.get('item', [])
    if isinstance(items, dict): items = [items]
    out = []
    for item in (items or []):
        title = clean(item.get('bidNtceNm') or '')
        if not title: continue

        # ── 마감된 공고 즉시 제외 ──────────────────────────
        deadline_raw = clean(item.get('bidClseDt') or '-')
        if _is_past(deadline_raw):
            continue

        no     = str(item.get('bidNtceNo')  or abs(hash(title)) % 1000000)
        ord_no = str(item.get('bidNtceOrd') or '00')
        amt    = str(item.get('presmptPrce') or '')
        budget = f"{int(amt):,}원" if amt.isdigit() and int(amt) > 0 else '미정'

        detail_url = (f"https://www.g2b.go.kr:8101/ep/tbid/tbidFwd.do"
                      f"?bidNtceNo={no}&bidNtceOrd={ord_no}&re=Y")
        spec_url  = clean(item.get('ntceSpecDocUrl') or '')
        draft_url = clean(item.get('drftDocUrl')     or '')
        rgst_dt   = clean(item.get('bidNtceDt')      or datetime.now().strftime('%Y-%m-%d'))

        # 개찰 정보
        open_dt   = clean(item.get('opengDt')   or '')
        open_plce = clean(item.get('opengPlce') or '')

        # 담당자
        contact_nm  = clean(item.get('ntceInsttOfclNm')    or '')
        contact_tel = clean(item.get('ntceInsttOfclTelNo') or '')
        contact     = f"{contact_nm} {contact_tel}".strip() if contact_nm or contact_tel else ''

        # 참가자격 & 계약방식
        qual        = clean(item.get('bidQlfctRgstDt')     or item.get('bidPrtcptQlfctYn') or '')
        bsns_div    = clean(item.get('ntceSttsCd')         or '')

        out.append({
            'id':           f'G2B-{no}',
            'bidNo':        no,
            'bidOrd':       ord_no,
            'stage':        '입찰공고',
            'title':        title,
            'agency':       clean(item.get('ntceInsttNm')   or ''),
            'demandAgency': clean(item.get('dmndInsttNm')   or ''),
            'budget':       budget,
            'deadline':     clean(item.get('bidClseDt')     or '-'),
            'openDate':     open_dt,
            'openPlace':    open_plce,
            'postDate':     rgst_dt[:10],
            'contractType': clean(item.get('cntrctMthdNm') or '입찰'),
            'category':     category(title),
            'keywords':     ([k for k in XR_KEYWORDS if _re.search(r'(?<![A-Za-z])'+k+r'(?![A-Za-z])', title) if k in _EN_KW] +
                             [k for k in _KO_KW if k in title]),
            'description':  clean(item.get('bidPurpsNm')   or title),
            'requirements': [],
            'url':          detail_url,
            'specUrl':      spec_url,
            'draftUrl':     draft_url,
            'files':        [],          # fetch_bid_detail 에서 채워짐
            'contact':      contact,
            'qual':         qual,
            'source':       'g2b',
        })
    return out


def parse_prespec_items(items, keyword):
    """사전규격 응답 파싱 (g2b와 필드명 다름)"""
    if isinstance(items, dict): items = items.get('item', [])
    if isinstance(items, dict): items = [items]
    out = []
    for item in (items or []):
        # 사전규격은 prdctNm(품명) 또는 bfSpecNm 이 사업명
        title = clean(item.get('prdctNm') or item.get('bfSpecNm') or '')
        if not title or len(title) < 3: continue
        no       = str(item.get('bfSpecRgstnNo') or abs(hash(title)) % 1000000)
        amt      = str(item.get('asignBdgtAmt')  or '')
        budget   = f"{int(amt):,}원" if amt.isdigit() and int(amt) > 0 else '미정'
        deadline = clean(item.get('opninRcptnEndDt') or item.get('rlOpninRcptnEndDt') or '-')

        # ── 마감된 사전규격 즉시 제외 ──────────────────────
        if _is_past(deadline):
            continue
        post_dt  = clean(item.get('rcptDt') or item.get('rgstDt') or datetime.now().strftime('%Y-%m-%d'))
        detail_url = f"https://www.g2b.go.kr:8101/ep/tbid/tbidSpec.do?bfSpecRgstnNo={no}"
        out.append({
            'id':           f'SPEC-{no}',
            'stage':        '사전규격',
            'title':        title,
            'agency':       clean(item.get('ntceInsttNm') or ''),
            'demandAgency': clean(item.get('dmndInsttNm') or ''),
            'budget':       budget,
            'deadline':     deadline,
            'postDate':     post_dt[:10] if post_dt else '-',
            'contractType': '공고예정',
            'category':     category(title),
            'keywords':     [keyword],
            'description':  clean(item.get('bfSpecCn') or title),
            'requirements': [],
            'url':          detail_url,
            'specUrl':      '',
            'draftUrl':     '',
            'contact':      clean(item.get('ntceInsttOfclTelNo') or ''),
            'source':       'g2b',
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
               f'&numOfRows=30&pageNo=1&type=json'
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




def fetch_bid_detail(session, bid):
    """나라장터 공고 첨부파일 + 상세정보 수집
    
    3가지 방법을 순서대로 시도:
    1) 공공데이터포털 첨부파일 전용 API  (getBidPblancFileInfo*)
    2) 나라장터 내부 XHR API             (tbidFwd / conFile JSON)
    3) 상세 HTML 파싱 (fallback)
    """
    files  = []
    extra  = {}
    no     = bid.get('bidNo',  bid['id'].replace('G2B-','').replace('SPEC-',''))
    ord_no = bid.get('bidOrd', '00')
    seen_u = set()

    ext_icon = {'hwp':'📝','pdf':'📕','xlsx':'📊','xls':'📊',
                'docx':'📄','doc':'📄','zip':'🗜️','pptx':'📊','ppt':'📊',
                'hwpx':'📝'}

    doc_type_label = {
        '공고서': '📢 공고서', '공고서(원본)': '📢 공고서(원본)',
        '공고서(변환본)': '📢 공고서(PDF)', '과업지시서': '📋 과업지시서',
        '제안요청서': '📋 제안요청서', '규격서': '📋 규격서',
        '설계서': '📐 설계서', '기타': '📎 기타', '청렴': '📎 청렴서류',
    }

    def make_file_entry(name, url, doc_type=''):
        if url in seen_u: return None
        seen_u.add(url)
        # 아이콘: 문서구분 우선, 없으면 확장자
        label = doc_type_label.get(doc_type, '')
        if not label:
            ext = re.search(r'\.(\w{2,5})(?:[?&#]|$)', url)
            icon = ext_icon.get(ext.group(1).lower(), '📎') if ext else '📎'
            label = f'{icon} {name}' if name else f'{icon} 파일'
        else:
            label = f'{label}: {name}' if name else label
        return {'name': label.strip(), 'url': url, 'docType': doc_type}

    # ── 방법 1: 공공데이터포털 첨부파일 전용 API ───────────────
    # getBidPblancFileInfoServc / Thng / Cnstwk
    FILE_API = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService'
    for op in ['Servc', 'Thng', 'Cnstwk']:
        try:
            url = (f'{FILE_API}/getBidPblancFileInfo{op}'
                   f'?ServiceKey={API_KEY}&type=json'
                   f'&bidNtceNo={no}&bidNtceOrd={ord_no}')
            r = session.get(url, timeout=10)
            if r.status_code != 200: continue
            resp = r.json().get('response', {})
            code = resp.get('header', {}).get('resultCode', '')
            if code not in ('00', '0'): continue
            raw_items = resp.get('body', {}).get('items', {})
            if isinstance(raw_items, dict): raw_items = raw_items.get('item', [])
            if isinstance(raw_items, dict): raw_items = [raw_items]
            for fi in (raw_items or []):
                fname   = clean(fi.get('atchFileNm')   or fi.get('fileNm') or '')
                furl    = clean(fi.get('atchFileUrl')   or fi.get('fileUrl') or '')
                fid     = clean(fi.get('atchFileId')    or '')
                fsn     = clean(fi.get('fileSn')        or '0')
                doc_tp  = clean(fi.get('docClsfcNm')    or fi.get('fileDstnctNm') or '')
                fsize   = clean(fi.get('atchFileSz')    or '')
                # 직접 URL 없으면 fileDown 패턴으로 조합
                if not furl and fid:
                    furl = (f'https://www.g2b.go.kr:8101/ep/common/conFile/fileDown.do'
                            f'?atchFileId={fid}&fileSn={fsn}')
                if not furl: continue
                if furl.startswith('/'): furl = 'https://www.g2b.go.kr' + furl
                entry = make_file_entry(fname, furl, doc_tp)
                if entry:
                    if fsize: entry['size'] = fsize
                    files.append(entry)
            if files: break  # 한 op에서 성공하면 중단
        except Exception:
            pass

    # ── 방법 2: 나라장터 내부 파일목록 XHR API ──────────────────
    if not files:
        for xhr_url, data in [
            # 패턴 A: tbidFwd 계열 JSON
            (f'https://www.g2b.go.kr:8101/ep/tbid/tbidFileList.do',
             {'bidNtceNo': no, 'bidNtceOrd': ord_no}),
            # 패턴 B: conFile JSON API
            (f'https://www.g2b.go.kr:8101/ep/common/conFile/getConFileList.do',
             {'bidNtceNo': no, 'bidNtceOrd': ord_no, 'menuNo': '02001'}),
        ]:
            try:
                r = session.post(xhr_url, data=data, headers={
                    'User-Agent':  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer':     'https://www.g2b.go.kr/',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                }, timeout=10)
                if r.status_code != 200: continue
                ct = r.headers.get('Content-Type', '')
                if 'json' in ct:
                    rows = r.json()
                    if isinstance(rows, dict): rows = rows.get('list') or rows.get('fileList') or []
                    for fi in (rows or []):
                        fid   = clean(str(fi.get('atchFileId') or ''))
                        fsn   = clean(str(fi.get('fileSn')     or '0'))
                        fname = clean(fi.get('atchFileNm') or fi.get('fileNm') or '')
                        doc_tp= clean(fi.get('fileDstnctNm') or fi.get('docClsfcNm') or '')
                        fsize = clean(str(fi.get('atchFileSz') or ''))
                        furl  = (clean(fi.get('fileUrl') or '') or
                                 f'https://www.g2b.go.kr:8101/ep/common/conFile/fileDown.do?atchFileId={fid}&fileSn={fsn}')
                        entry = make_file_entry(fname, furl, doc_tp)
                        if entry:
                            if fsize: entry['size'] = fsize
                            files.append(entry)
                elif 'html' in ct:
                    # HTML 테이블 파싱
                    for m in re.finditer(r"fileDown\.do\?[^'\"<>]*atchFileId=([\w]+)[^'\"<>]*fileSn=(\d+)", r.text):
                        furl = f'https://www.g2b.go.kr:8101/ep/common/conFile/fileDown.do?atchFileId={m.group(1)}&fileSn={m.group(2)}'
                        ctx  = r.text[max(0,m.start()-200):m.end()+50]
                        fname_m = re.search(r'>([^<]{2,80}\.(?:hwp|pdf|xlsx?|docx?|zip|pptx?))<', ctx, re.I)
                        fname   = clean(fname_m.group(1)) if fname_m else ''
                        entry   = make_file_entry(fname, furl)
                        if entry: files.append(entry)
                if files: break
            except Exception:
                pass

    # ── 방법 3: 단건 API에서 specUrl / drftUrl ───────────────────
    if not files:
        try:
            api_url = (f'http://apis.data.go.kr/1230000/ad/BidPublicInfoService'
                       f'/getBidPblancListInfoServc'
                       f'?ServiceKey={API_KEY}&type=json'
                       f'&bidNtceNo={no}&bidNtceOrd={ord_no}')
            r = session.get(api_url, timeout=10)
            if r.status_code == 200:
                raw  = r.json().get('response',{}).get('body',{}).get('items',{})
                item = raw.get('item',{}) if isinstance(raw,dict) else (raw[0] if raw else {})
                if isinstance(item, list): item = item[0] if item else {}
                for key, label in [('ntceSpecDocUrl','📋 규격서'), ('drftDocUrl','📄 서류')]:
                    v = clean(item.get(key) or '')
                    if v:
                        entry = make_file_entry(label, v, '')
                        if entry: files.append(entry)
                nm  = clean(item.get('ntceInsttOfclNm')    or '')
                tel = clean(item.get('ntceInsttOfclTelNo') or '')
                if nm or tel: extra.setdefault('contact', f'{nm} {tel}'.strip())
        except Exception:
            pass

    # ── 담당자/자격 보완: 상세 URL HTML ─────────────────────────
    try:
        r = session.get(bid.get('url',''), headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.g2b.go.kr/',
        }, timeout=12)
        if r.status_code == 200:
            html = r.text
            # HTML에 파일 링크가 있으면 추가
            for m in re.finditer(
                r'fileDown\.do\?[^\'\"<>\s]*atchFileId=([\w]+)[^\'\"<>\s]*fileSn=(\d+)', html):
                furl = (f'https://www.g2b.go.kr:8101/ep/common/conFile/fileDown.do'
                        f'?atchFileId={m.group(1)}&fileSn={m.group(2)}')
                ctx  = html[max(0,m.start()-300):m.end()+100]
                nm_m = re.search(r'>([^<]{2,80}\.(?:hwp|pdf|xlsx?|docx?|zip|pptx?|hwpx))<', ctx, re.I)
                nm   = clean(nm_m.group(1)) if nm_m else ''
                dt_m = re.search(r'<td[^>]*>\s*([가-힣\w\s()]{2,20}?)\s*</td>\s*<td[^>]*>[^<]*'+
                                  re.escape(nm[:10] if nm else ''), ctx)
                doc_tp = clean(dt_m.group(1)) if dt_m else ''
                entry = make_file_entry(nm, furl, doc_tp)
                if entry: files.append(entry)
            # 담당자
            if not extra.get('contact'):
                m = re.search(r'([가-힣]{2,5})\s*(?:담당)?[^\n<]{0,10}(0\d{1,2}[-\s]\d{3,4}[-\s]\d{4})', html)
                if m: extra['contact'] = f"{m.group(1)} {m.group(2)}"
                else:
                    m2 = re.search(r'(0\d{1,2}[-\s]\d{3,4}[-\s]\d{4})', html)
                    if m2: extra['contact'] = m2.group(1)
            # 입찰참가자격
            m = re.search(r'(?:입찰참가자격|참가자격)[^:：\n]{0,10}[:：]\s*([^<\n]{5,300})', html)
            if m: extra.setdefault('qual', clean(m.group(1)))
    except Exception:
        pass

    return files, extra

def fetch_bizinfo_keyword(session, keyword):
    """bizinfo 정부지원사업 수집 — RSS API → HTML 스크래핑 순서로 시도"""
    out = []
    seen = set()

    # ── 방법 1: RSS/JSON API ──────────────────────────────
    try:
        r = session.get('https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do', params={
            'crtfcKey': 'OPEN_API_KEY', 'dataType': 'json',
            'searchKeyword': keyword, 'pageUnit': 20, 'pageIndex': 1,
        }, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/xml'}, timeout=12)
        if r.status_code == 200:
            data = r.json()
            items = (data.get('jsonArray') or data.get('items') or data.get('resultList') or [])
            for item in items:
                title = clean(item.get('pblancNm') or item.get('title') or '')
                pid   = str(item.get('pblancId') or item.get('id') or '')
                if not title or not pid or pid in seen or not is_xr(title): continue
                seen.add(pid)
                out.append({
                    'id': f'BIZ-{pid}', 'stage': '지원사업', 'title': title,
                    'agency':       clean(item.get('jrsdInsttNm') or ''),
                    'demandAgency': '',
                    'budget':       clean(item.get('totPbancBdgt') or '미정'),
                    'deadline':     clean(item.get('reqstEndDt') or '-').replace('.', '-'),
                    'postDate':     clean(item.get('pblancBgngDt') or datetime.now().strftime('%Y-%m-%d')).replace('.', '-'),
                    'contractType': '공모/지원', 'category': category(title),
                    'keywords':     [k for k in XR_KEYWORDS if k in title],
                    'description':  clean(item.get('bsnsSumryCn') or title),
                    'requirements': [], 'specUrl': '', 'draftUrl': '', 'contact': '',
                    'url': f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
                    'source': 'bizinfo',
                })
    except Exception:
        pass
    if out: return out

    # ── 방법 2: HTML 스크래핑 ────────────────────────────
    for page_url, params in [
        ('https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do',
         {'schKeyword': keyword, 'schCondition': 'title', 'pageIndex': 1}),
    ]:
        try:
            r = session.get(page_url, params=params, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'ko-KR,ko;q=0.9',
                'Referer': 'https://www.bizinfo.go.kr/',
            }, timeout=15)
            if r.status_code != 200: continue
            html = r.text
            # pblancId 추출 후 주변 텍스트에서 제목 수집
            for m in re.finditer(r'pblancId=([\w\-]+)', html):
                pid = m.group(1).strip()
                if not pid or pid in seen: continue
                ctx = html[max(0, m.start()-30):m.end()+800]
                candidates = [clean(c) for c in re.findall(r'>([^<]{5,200})<', ctx)]
                title = max((c for c in candidates if len(c) > 5
                             and c not in ['목록','이전','다음','확인','취소','닫기','스크랩','검색','공고명','접수마감']),
                            key=len, default='')
                if not title or not is_xr(title): continue
                seen.add(pid)
                dates = re.findall(r'(\d{4}[.\-]\d{2}[.\-]\d{2})', ctx)
                bm = re.search(r'([\d,]+)\s*원', ctx)
                out.append({
                    'id': f'BIZ-{pid}', 'stage': '지원사업', 'title': title,
                    'agency': '', 'demandAgency': '',
                    'budget': bm.group(0) if bm else '미정',
                    'deadline': dates[1].replace('.', '-') if len(dates) > 1 else '-',
                    'postDate': dates[0].replace('.', '-') if dates else datetime.now().strftime('%Y-%m-%d'),
                    'contractType': '공모/지원', 'category': category(title),
                    'keywords': [k for k in XR_KEYWORDS if k in title],
                    'description': title, 'requirements': [],
                    'specUrl': '', 'draftUrl': '', 'contact': '',
                    'url': f'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}',
                    'source': 'bizinfo',
                })
        except Exception as e:
            print(f'    bizinfo[{keyword}] HTML오류: {e}')
    return out

def score_bid(b):
    """정렬 점수: 높을수록 위로 (마감 임박 + 핵심 XR 키워드)"""
    score = 0
    # 1) 마감 임박 (7일 이내 +40, 14일 이내 +20)
    try:
        dl = b.get('deadline', '-')
        if dl and dl != '-':
            dl_clean = dl[:10].replace('/', '-').replace('.', '-')
            days_left = (datetime.strptime(dl_clean, '%Y-%m-%d') - datetime.now()).days
            if   days_left <= 3:  score += 50
            elif days_left <= 7:  score += 40
            elif days_left <= 14: score += 20
    except: pass
    # 2) 핵심 XR 키워드 직접 매칭 (+30)
    title = b.get('title', '')
    core  = ['AR', 'VR', 'XR', 'MR', 'HMD', '증강현실', '가상현실', '혼합현실', '메타버스',
             '스마트글래스', '디지털트윈', '원격협업', '스마트안전', '피지컬AI']
    if any(k in title for k in core): score += 30
    # 3) 사전규격은 선제 대응 가치 (+15)
    if b.get('stage') == '사전규격': score += 15
    # 4) 예산 규모 (+10 for 억 이상)
    budget = b.get('budget', '')
    try:
        amt = int(budget.replace(',','').replace('원',''))
        if amt >= 100_000_000: score += 10
        if amt >= 500_000_000: score += 10
    except: pass
    return score


def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] XR 공고 수집 (최근 {DAYS}일)')

    # ── keywords.json 오버라이드 ───────────────────────────
    global G2B_KEYWORDS, XR_KEYWORDS
    kw_path = 'data/keywords.json'
    if os.path.exists(kw_path):
        try:
            kw = json.load(open(kw_path, encoding='utf-8'))
            if kw.get('g2b') and isinstance(kw['g2b'], list):
                G2B_KEYWORDS = kw['g2b']
                print(f'  ✅ keywords.json 로드: G2B={len(G2B_KEYWORDS)}개')
            if kw.get('xr') and isinstance(kw['xr'], list):
                XR_KEYWORDS = kw['xr']
                print(f'  ✅ keywords.json 로드: XR={len(XR_KEYWORDS)}개')
        except Exception as e:
            print(f'  ⚠️  keywords.json 로드 실패: {e}')

    sess = requests.Session()
    sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                         'Accept': 'application/json, text/html'})

    all_bids, seen = [], set()
    lock_seen = __import__('threading').Lock()
    save_lock  = __import__('threading').Lock()
    last_saved = [0]  # 마지막 저장 시점의 건수

    os.makedirs('data', exist_ok=True)

    def save_partial(stage_label, status='running'):
        """단계별 중간 결과를 bids.json에 저장 — HTML 폴링으로 실시간 표시"""
        with save_lock:
            xr_now = sorted(
                [b for b in all_bids if is_xr(b['title'])],
                key=score_bid, reverse=True
            )
            payload = {
                'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status':    status,       # 'running' | 'done'
                'stage':     stage_label,  # 진행 단계 메시지
                'total':     len(xr_now),
                'bids':      xr_now,
            }
            json.dump(payload, open('data/bids.json', 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            last_saved[0] = len(all_bids)

    def add(bids):
        n = 0
        with lock_seen:
            for b in bids:
                if b['id'] not in seen:
                    seen.add(b['id']); all_bids.append(b); n += 1
        # 3건 이상 쌓이면 중간 저장
        if n and (len(all_bids) - last_saved[0]) >= 3:
            save_partial('① 나라장터 수집 중...')
        return n

    # 수집 시작 알림
    save_partial('⏳ 수집 시작...', status='running')

    now   = datetime.now()
    start = now - timedelta(days=DAYS)
    bgn   = start.strftime('%Y%m%d') + '0000'
    end   = now.strftime('%Y%m%d')   + '2359'

    # ── 1단계: 나라장터 입찰공고 ─────────────────────────
    print(f'\n[1단계] 나라장터 API (병렬, {len(G2B_KEYWORDS)}개 키워드)')
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_g2b, sess, kw): kw for kw in G2B_KEYWORDS}
        for f in as_completed(futs):
            try:
                n = add(f.result())
                if n: print(f'  +{n}건 [{futs[f]}] (누적 {len(all_bids)}건)')
            except Exception as e:
                print(f'  ⚠️  [{futs[f]}] {e}')
    print(f'  → {len(all_bids)}건 ({time.time()-t0:.1f}초)')
    save_partial(f'② 사전규격 수집 중... (나라장터 {len(all_bids)}건 완료)')

    # ── 1.5단계: 사전규격 ────────────────────────────────
    print(f'\n[1.5단계] 사전규격 API (병렬, {len(G2B_KEYWORDS)}개 키워드)')
    t0 = time.time()
    ps_count = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_prespec, kw, bgn, end): kw for kw in G2B_KEYWORDS}
        for f in as_completed(futs):
            try:
                res = f.result()
                if res:
                    n = add(res); ps_count += n
            except Exception as e:
                print(f'  ⚠️  사전규격[{futs[f]}] {e}')
    print(f'  → 사전규격 {ps_count}건 ({time.time()-t0:.1f}초)')
    save_partial(f'③ bizinfo 수집 중... (총 {len(all_bids)}건)')

    # ── 2단계: bizinfo ───────────────────────────────────
    print(f'\n[2단계] bizinfo 검색 (병렬, {len(XR_KEYWORDS)}개 키워드)')
    t0 = time.time()
    bizinfo_all, biz_seen = [], set()
    biz_lock = __import__('threading').Lock()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_bizinfo_keyword, sess, kw): kw for kw in XR_KEYWORDS}
        for f in as_completed(futs):
            try:
                bids = f.result()
                with biz_lock:
                    new = [b for b in bids if b['id'] not in biz_seen]
                    for b in new: biz_seen.add(b['id'])
                    bizinfo_all.extend(new)
            except Exception: pass
    print(f'  → bizinfo {len(bizinfo_all)}건 ({time.time()-t0:.1f}초)')

    title_to_biz_url = {b['title']: b['url'] for b in bizinfo_all}
    for b in all_bids:
        if b['source'] == 'g2b':
            matched = title_to_biz_url.get(b['title'])
            if matched: b['url'] = matched
    add(bizinfo_all)
    save_partial(f'④ 첨부파일 수집 중... (총 {len(all_bids)}건)')

    # ── 3단계: 상세 스크래핑 ────────────────────────────
    g2b_bids = [b for b in all_bids if b['source'] == 'g2b' and b['stage'] == '입찰공고']
    print(f'\n[3단계] 공고 상세 스크래핑 ({len(g2b_bids)}건)')
    t0 = time.time()
    detail_lock = __import__('threading').Lock()
    done = [0]

    def enrich(bid):
        files, extra = fetch_bid_detail(sess, bid)
        with detail_lock:
            if files: bid['files'] = files
            for k, v in extra.items():
                if v and not bid.get(k): bid[k] = v
            done[0] += 1
            if done[0] % 5 == 0:
                print(f'  상세 {done[0]}/{len(g2b_bids)}건...')
                save_partial(f'④ 첨부파일 수집 중... ({done[0]}/{len(g2b_bids)}건)')

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(enrich, g2b_bids))
    print(f'  → 완료 ({time.time()-t0:.1f}초)')

    # ── 최종 저장 ────────────────────────────────────────
    xr = [b for b in all_bids if is_xr(b['title'])]
    if not xr and all_bids: xr = all_bids
    xr.sort(key=score_bid, reverse=True)
    print(f'\n전체: {len(all_bids)}건, XR: {len(xr)}건')

    if not xr:
        if os.path.exists('data/bids.json'):
            cached = json.load(open('data/bids.json', encoding='utf-8'))
            if cached.get('total', 0) > 0:
                cached['updatedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                cached['status'] = 'done'
                cached['stage']  = '완료 (캐시)'
                json.dump(cached, open('data/bids.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
                print('0건 — 기존 캐시 유지'); return

    out = {
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'status':    'done',
        'stage':     f'✅ 완료 — {len(xr)}건',
        'total':     len(xr),
        'bids':      xr,
    }
    json.dump(out, open('data/bids.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 저장: {len(xr)}건')

if __name__ == '__main__':
    main()
