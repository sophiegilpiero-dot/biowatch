"""
한국 바이오/제약 기업 자동 감지 필터
- 기업명 키워드 매칭
- 한국 도메인/주소 패턴
- 한국 병원/기관 공동 스폰서 감지
"""

# 주요 한국 바이오/제약 기업 (영문명)
KOREAN_COMPANIES = [
    # 대형 제약
    "celltrion", "samsung bioepis", "samsung biologics", "lg chem", "lg화학",
    "yuhan", "유한양행", "hanmi", "한미약품", "daewoong", "대웅제약",
    "boryung", "보령제약", "ildong", "일동제약", "chong kun dang", "종근당",
    "dongwha", "동화약품", "taejoon", "태준제약", "hana pharm", "하나제약",
    "kuhnil", "국일제약", "alvogen korea", "신풍제약", "shinpoong",
    "huons", "휴온스", "pharmbio korea", "jw pharmaceutical", "jw중외제약",
    "dong-a", "동아에스티", "dong-a st", "dongah",
    "meiji seika korea", "pfizer korea", "ahn-gook", "안국약품",

    # 바이오텍
    "medytox", "메디톡스", "hugel", "휴젤", "bioneer", "바이오니아",
    "macrogen", "마크로젠", "helixmith", "헬릭스미스", "viromed",
    "kolon life science", "코오롱생명과학", "inventis", "인벤티스",
    "genexine", "제넥신", "bti genic", "크리스탈지노믹스", "crystalgenomics",
    "alteogen", "알테오젠", "InventisBio", "abclonal",
    "onsero", "온세로", "kainos medicine", "카이노스메드",
    "ildong bioscience", "일동바이오사이언스",
    "chongkundang", "한올바이오파마", "hanall biopharma",
    "boryung biopharma", "보령바이오파마",
    "gI innovation", "지아이이노베이션",
    "agenus korea", "녹십자", "gc pharma", "green cross",
    "sk bioscience", "sk바이오사이언스",
    "sk biopharmaceuticals", "sk바이오팜",
    "sk biopharma", "sk life science",
    "yuhan corporation",
    "ildong", "일동",
    "hugel", "휴젤",
    "cellid", "셀리드",
    "inventisbio", "inventis bio",
    "olipass", "올리패스",
    "pharos ibio", "파로스아이바이오",
    "inventage", "인벤티지랩",
    "abion", "에이비온",
    "y-biologics", "와이바이오로직스",
    "bridge biotherapeutics", "브릿지바이오테라퓨틱스",
    "inventisbio",
    "ildong",
    "tiumbio", "티움바이오",
    "medpacto", "메드팩토",
    "onconova", "온코노바",
    "acetaminophen",
    "inventis",
    "obi pharma",
    "cha biotech", "차바이오텍", "cha medical",
    "cha vaccine", "차백신",
    "aribio", "아리바이오",
    "celltrion healthcare",
    "hugel", 
    "binex", "바이넥스",
    "samjin", "삼진제약",
    "kwangdong", "광동제약",
    "korean red ginseng", "korea ginseng",
    "hyundai pharma", "현대약품",
    "bio pharma", "biopharmaceutical",
    "inventis bio",
    "shin poong",
    "cosmax bio", "코스맥스바이오",
    "cj healthcare", "cj바이오사이언스", "cj bioscience",
    "lotte biologics", "롯데바이오로직스",
    "samsung bioepis",
    "boryung", 
    "medy-tox",
    "abclon", "에이비클론",
    "alteogen",
    "inventage lab",
    "ildong",
    "vaxcell-bio", "백셀",
    "curigin", "큐리진",
    "genosco",
    "oncobiologics",
    "inventisbio",
    "kangstem biotech", "강스템바이오텍",
    "naturalendo tech",
    "reyon pharmaceutical", "레이온파마",
    "scancell",
    "inventis",
    "boeringer",
]

# 한국 기관/병원 (공동 스폰서로 등장하는 경우)
KOREAN_INSTITUTIONS = [
    "seoul national university", "서울대",
    "samsung medical center", "삼성서울병원",
    "asan medical center", "서울아산병원",
    "severance hospital", "세브란스",
    "yonsei university", "연세대",
    "korea university", "고려대",
    "sungkyunkwan university", "성균관대",
    "ajou university", "아주대",
    "catholic university of korea", "가톨릭대",
    "national cancer center korea", "국립암센터",
    "korea fda", "mfds", "식품의약품안전처",
    "health insurance review", "건강보험심사평가원",
    "korea centers for disease", "질병관리청",
    "seoul st. mary", "서울성모병원",
    "bundang", "분당서울대병원",
    "anam hospital",
    "korea institute", "한국과학기술",
    "kaist",
    "postech",
    "snu hospital",
    "chonnam national", "전남대",
    "pusan national", "부산대",
    "keimyung", "계명대",
    "gachon university", "가천대",
    "inha university", "인하대",
]

# 국가 코드
KOREA_COUNTRY_CODES = [
    "korea", "republic of korea", "south korea", "kr", "kor",
    "seoul", "busan", "incheon", "daegu", "gwangju", "daejeon", "ulsan",
    "gyeonggi", "경기", "서울", "부산",
]


def normalize(text: str) -> str:
    return text.lower().strip()


def is_korean_entity(text: str) -> tuple[bool, str]:
    """
    텍스트에서 한국 기업/기관 여부 판별
    Returns: (is_korean, matched_keyword)
    """
    if not text:
        return False, ""
    
    normalized = normalize(text)
    
    for kw in KOREAN_COMPANIES:
        if normalize(kw) in normalized:
            return True, kw
    
    for kw in KOREAN_INSTITUTIONS:
        if normalize(kw) in normalized:
            return True, kw
    
    for kw in KOREA_COUNTRY_CODES:
        if normalize(kw) in normalized:
            return True, kw
    
    return False, ""


def filter_results(items: list[dict], fields_to_check: list[str]) -> list[dict]:
    """
    결과 리스트에서 한국 관련 항목만 필터링
    items: 결과 딕셔너리 리스트
    fields_to_check: 검사할 필드명 리스트
    """
    filtered = []
    for item in items:
        for field in fields_to_check:
            value = item.get(field, "") or ""
            if isinstance(value, list):
                value = " ".join(str(v) for v in value)
            matched, keyword = is_korean_entity(str(value))
            if matched:
                item["_matched_keyword"] = keyword
                item["_matched_field"] = field
                filtered.append(item)
                break
    return filtered
