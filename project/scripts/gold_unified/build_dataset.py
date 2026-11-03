"""gold 폴더의 출처별 원본 4개(다나와·Zooplus·Pets at Home·PetSmart)를 한글 통합 스키마로 변환한다.

산출물 (data/model_datasets/unified/):
  - gold_unified.csv          통합 데이터 (한 행 = 상품 1개)
  - schema_dictionary.csv     속성 사전 (속성별 단위, 출처별 원본 컬럼, 병합 유형, 환산 규칙)
  - unit_conversion_log.csv   값이 바뀌거나 무효 처리된 환산 내역 (행 단위)

원칙: 원본 파일은 수정하지 않는다. 환산은 근거 규칙을 로그로 남기고, 근거 없이 고칠 수 없는 값은
삭제하지 않고 NULL + 품질플래그로 표시한다 (project/md/data_integration_rules.md).

실행: python project/scripts/build_gold_unified.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
GOLD = PROJECT / "data/model_datasets/gold"
PETSMART_SKU = PROJECT / "data/model_datasets/unlabeled/petsmart_dryfood_sku.csv"
DANAWA_RAW = PROJECT / "data/Source/danawa_dogfood.csv"  # danawa_.csv에 없는 상품URL 복원용
OUT = PROJECT / "data/model_datasets/unified"

LB_TO_KG = 0.45359237
OZ_TO_KG = 0.028349523125
G_PER_LB = 453.59237
KJ_PER_KCAL = 4.184
PCT_TO_MG_KG = 10_000  # 1% = 10 g/kg = 10,000 mg/kg

# ---------------------------------------------------------------------------
# 통합 스키마 정의: (속성명, 그룹, 타입, 단위, 설명, {출처: 원본 컬럼}, 환산 규칙)
# 병합 유형은 원본 컬럼이 있는 출처 수로 자동 판정한다.
# ---------------------------------------------------------------------------
SOURCES = ["danawa", "zooplus", "petsathome", "petsmart"]
SCHEMA = [
    ("출처", "식별", "문자열", "", "데이터 출처 코드", {s: "(파일 단위로 부여)" for s in SOURCES}, ""),
    ("사이트", "식별", "문자열", "", "판매 사이트 국가 구분", {"zooplus": "site", "petsathome": "site"}, ""),
    ("상품ID", "식별", "문자열", "", "출처 내 상품 식별자 (출처+상품ID가 통합 키)",
     {"danawa": "pcode", "zooplus": "product_id", "petsathome": "product_id", "petsmart": "web_style_id"}, ""),
    ("상품명", "식별", "문자열", "", "사이트에 표시된 상품명 원문",
     {"danawa": "상품명", "zooplus": "name", "petsathome": "name", "petsmart": "name"}, ""),
    ("브랜드", "식별", "문자열", "", "사료 브랜드",
     {"zooplus": "brand", "petsathome": "brand", "petsmart": "brand"}, ""),
    ("제조사", "식별", "문자열", "", "제조·수입사 (브랜드와 다름)", {"danawa": "제조사"}, ""),
    ("상품URL", "식별", "문자열", "", "상품 상세 페이지 URL",
     {"danawa": "Source/danawa_dogfood.csv 상품URL (pcode로 결합)", "zooplus": "url", "petsathome": "url",
      "petsmart": "petsmart_dryfood_sku.csv url (첫 SKU)"}, ""),
    ("사료형태", "분류", "범주(복수)", "", "표준 코드: 건식·습식·반건조·동결건조·에어드라이·화식·냉동·토퍼·간식·액상·분말",
     {"danawa": "제형", "zooplus": "category + 사료형태", "petsathome": "category + food_format", "petsmart": "food_type"}, ""),
    ("사료형태_원문", "분류", "문자열", "", "표준화 전 사료형태 원문",
     {"danawa": "제형", "zooplus": "사료형태", "petsathome": "food_format", "petsmart": "food_type"}, ""),
    ("가공방식", "분류", "문자열", "", "동결건조·화식·에어드라이 등 가공 방식", {"danawa": "가공방식"}, ""),
    ("사료여부", "분류", "불리언", "", "주식 사료 여부 (False = 액상·분말 보조식 등)", {"danawa": "사료여부"}, ""),
    ("생애주기", "분류", "범주(복수)", "", "표준 코드: 퍼피·어덜트·시니어·전연령",
     {"danawa": "나이", "zooplus": "생애주기", "petsathome": "생애주기", "petsmart": "life_stage (없으면 life_stages)"}, ""),
    ("생애주기_원문", "분류", "문자열", "", "표준화 전 생애주기 원문",
     {"danawa": "나이", "zooplus": "생애주기", "petsathome": "생애주기", "petsmart": "life_stage"}, ""),
    ("견종크기", "분류", "범주(복수)", "", "표준 코드: 초소형·소형·중형·대형·초대형·전체",
     {"zooplus": "견종크기", "petsathome": "견종크기", "petsmart": "breed_size"}, ""),
    ("견종크기_원문", "분류", "문자열", "", "표준화 전 견종크기 원문",
     {"zooplus": "견종크기", "petsathome": "견종크기", "petsmart": "breed_size"}, ""),
    ("알갱이크기", "분류", "문자열", "", "사료 알갱이(키블) 크기", {"danawa": "크기", "petsmart": "kibble_sizes"}, ""),
    ("기능_원문", "라벨", "문자열(복수)", "", "출처의 건강 기능 라벨 원문 (카테고리딕셔너리로 표준화 예정)",
     {"danawa": "기능", "zooplus": "기능", "petsathome": "기능", "petsmart": "hc_final"}, ""),
    ("라벨출처", "라벨", "범주", "", "기능 라벨의 근거: 사이트분류 / 큐레이션 / 텍스트추출",
     {"danawa": "(고정: 사이트분류)", "zooplus": "(고정: 사이트분류)", "petsathome": "(고정: 사이트분류)", "petsmart": "hc_source"}, ""),
    ("처방식여부", "분류", "불리언", "", "처방식 표시 여부", {"danawa": "처방식여부", "petsathome": "처방식"}, ""),
    ("맛", "분류", "문자열(복수)", "", "맛·주요 풍미", {"zooplus": "맛", "petsathome": "맛", "petsmart": "flavor"}, ""),
    ("포장", "분류", "문자열", "", "포장 형태", {"danawa": "포장", "zooplus": "포장", "petsathome": "포장"}, ""),
    ("인증", "분류", "문자열(복수)", "", "AAFCO·HACCP 등 인증 표시", {"danawa": "인증"}, ""),
    ("표시태그", "분류", "문자열(복수)", "", "무방부제·그레인프리 등 상품 표시 태그 (값이 1인 플래그만 나열)",
     {"danawa": "무방부제여부·무합성보존제여부·GMOFree여부·가수분해여부·그레인프리여부·무색소여부"}, ""),
    ("원재료", "원료", "문자열", "", "원재료 원문",
     {"zooplus": "ingredients", "petsathome": "ingredients", "petsmart": "ingredients"}, ""),
    ("주단백질원", "원료", "문자열(복수)", "", "주 단백질원 요약", {"danawa": "주 단백질원"}, ""),
    ("주요기능성분", "원료", "문자열(복수)", "", "L-카르니틴 등 강조 성분", {"danawa": "주요성분"}, ""),
]
NUTRIENT_PCT = [  # (표준명, 다나와/zooplus/pah 컬럼, petsmart 컬럼)
    ("조단백", "조단백", "crude_protein"),
    ("조지방", "조지방", "crude_fat"),
    ("조섬유", "조섬유", "crude_fiber"),
    ("조회분", "조회분", "ash"),
    ("수분", "수분", "moisture"),
    ("칼슘", "칼슘", "calcium"),
    ("인", "인", "phosphorus"),
    ("나트륨", "나트륨", "sodium"),
]
for name, kr, en in NUTRIENT_PCT:
    cols = {"danawa": kr, "zooplus": kr, "petsathome": kr, "petsmart": en}
    if name == "나트륨":
        cols = {"zooplus": kr, "petsathome": kr}
    rule = "petsmart: 단위 없는 행은 %로 간주(로그)" if "petsmart" in cols else ""
    SCHEMA.append((f"{name}_pct", "영양(현물)", "실수", "%", f"{name} 함량, 현물(as-fed) 기준", cols, rule))
SCHEMA.append(("영양표기기준", "영양(현물)", "문자열", "", "보증성분의 하한/상한 표기 (예: 조단백:하한|조섬유:상한)",
               {"petsmart": "*_minmax"}, "min→하한, max→상한"))
for name, kr, _ in NUTRIENT_PCT:
    cols = {"danawa": f"건물기준_{kr}" if kr in ("조단백", "조지방") else "(재계산)",
            "zooplus": f"dm_{kr}", "petsathome": f"dm_{kr}", "petsmart": "(재계산)"}
    if name == "수분":
        continue
    SCHEMA.append((f"건물기준_{name}_pct", "영양(건물)", "실수", "%", f"{name} 함량, 건물(dry matter) 기준", cols,
                   "현물값 ÷ (1 − 수분/100) 로 전 출처 재계산. 현물값이 없고 원본 건물기준만 있으면 원본값 사용"))
SCHEMA += [
    ("열량_kcal_kg", "열량", "실수", "kcal/kg", "대사에너지(ME), 현물 기준",
     {"zooplus": "kcal_per_kg", "petsathome": "kcal_per_kg", "petsmart": "kcal_per_kg"},
     "범위(500~6,000) 밖 값은 성분 추정 열량과 비교해 kcal/g·kcal/100g·kJ·소수점 밀림 중 맞는 배수로 보정, 불가하면 NULL"),
    ("열량_원값", "열량", "실수", "원문 단위", "보정 전 원본 열량 값",
     {"zooplus": "kcal_per_kg", "petsathome": "kcal_per_kg", "petsmart": "kcal_per_kg"}, ""),
    ("타우린_pct", "미량성분", "실수", "%", "타우린", {"zooplus": "타우린", "petsmart": "taurine"},
     "zooplus: 100 초과 값은 mg/kg로 보고 ÷10,000"),
    ("오메가3_pct", "미량성분", "실수", "%", "오메가3 지방산",
     {"zooplus": "오메가3", "petsathome": "오메가3", "petsmart": "omega3"}, ""),
    ("오메가6_pct", "미량성분", "실수", "%", "오메가6 지방산",
     {"zooplus": "오메가6", "petsathome": "오메가6", "petsmart": "omega6"}, "petsmart: IU/kg 표기 1건은 단위오류로 NULL"),
    ("EPA_DHA합_pct", "미량성분", "실수", "%", "EPA+DHA 합계",
     {"petsathome": "EPA_DHA", "petsmart": "epa + dha"}, "petsmart: EPA와 DHA가 모두 있을 때만 합산"),
    ("리놀레산_pct", "미량성분", "실수", "%", "리놀레산", {"petsmart": "linoleic_acid"}, ""),
    ("칼륨_pct", "미량성분", "실수", "%", "칼륨", {"zooplus": "칼륨", "petsathome": "칼륨"}, ""),
    ("마그네슘_pct", "미량성분", "실수", "%", "마그네슘", {"zooplus": "마그네슘", "petsathome": "마그네슘"}, ""),
    ("탄수화물_pct", "미량성분", "실수", "%", "탄수화물", {"zooplus": "탄수화물", "petsathome": "탄수화물"}, ""),
    ("전분_pct", "미량성분", "실수", "%", "전분", {"zooplus": "전분"}, ""),
    ("염소_pct", "미량성분", "실수", "%", "염소", {"zooplus": "염소"}, ""),
    ("글루코사민_mg_kg", "미량성분", "실수", "mg/kg", "글루코사민", {"zooplus": "글루코사민", "petsmart": "glucosamine"},
     "zooplus % ×10,000 / petsmart ppm=mg/kg / IU/kg는 단위오류로 NULL"),
    ("콘드로이틴_mg_kg", "미량성분", "실수", "mg/kg", "콘드로이틴", {"petsmart": "chondroitin"}, "ppm=mg/kg"),
    ("L카르니틴_mg_kg", "미량성분", "실수", "mg/kg", "L-카르니틴", {"zooplus": "카르니틴", "petsmart": "l_carnitine"},
     "zooplus % ×10,000 / petsmart ppm=mg/kg"),
    ("아연_mg_kg", "미량성분", "실수", "mg/kg", "아연", {"petsmart": "zinc"}, ""),
    ("셀레늄_mg_kg", "미량성분", "실수", "mg/kg", "셀레늄", {"petsmart": "selenium"}, ""),
    ("비타민C_mg_kg", "미량성분", "실수", "mg/kg", "비타민 C", {"petsmart": "vitamin_c"}, "ppm=mg/kg"),
    ("비타민A_IU_kg", "미량성분", "실수", "IU/kg", "비타민 A", {"petsmart": "vitamin_a"}, "% 표기 1건은 단위오류로 NULL"),
    ("비타민E_IU_kg", "미량성분", "실수", "IU/kg", "비타민 E", {"petsmart": "vitamin_e"},
     "mg/kg 표기 1건은 형태(천연/합성)를 몰라 IU 환산 불가 → NULL"),
    ("유산균_CFU_g", "미량성분", "실수", "CFU/g", "유산균 수", {"petsmart": "probiotics_cfu"},
     "CFU/lb ÷ 453.59 → CFU/g, 단위 없는 행은 NULL"),
    ("통화", "가격", "범주", "ISO 4217", "가격 통화",
     {"danawa": "(고정: KRW)", "zooplus": "currency", "petsathome": "currency", "petsmart": "(고정: USD)"}, ""),
    ("최저가", "가격", "실수", "통화", "옵션 중 최저 판매가 (다나와는 묶음상품이면 묶음 전체 가격)",
     {"danawa": "최저가", "zooplus": "price_min", "petsathome": "price_min", "petsmart": "price_min"}, ""),
    ("최고가", "가격", "실수", "통화", "옵션 중 최고 판매가",
     {"zooplus": "price_max", "petsathome": "price_max", "petsmart": "price_max"}, ""),
    ("kg당최저가", "가격", "실수", "통화/kg", "kg당 최저 가격",
     {"danawa": "단위가격_원/kg", "zooplus": "price_per_kg_min", "petsathome": "price_per_kg_min",
      "petsmart": "(계산) SKU 가격 ÷ SKU 중량"},
     "다나와: 원문 원/10g ×100 (상류 단계에서 환산됨, 원/10ml 40건은 NULL) / petsmart: SKU별 lb·oz→kg 후 가격÷중량의 최솟값"),
    ("중량_kg_최소", "가격", "실수", "kg", "판매 옵션 중 최소 총중량",
     {"danawa": "중량_kg", "zooplus": "sizes", "petsathome": "sizes", "petsmart": "sizes"},
     "g ÷1,000, lb ×0.4536, oz ×0.02835, 'N x 용량'은 곱해서 총중량, '+ 증정'은 합산"),
    ("중량_kg_최대", "가격", "실수", "kg", "판매 옵션 중 최대 총중량",
     {"danawa": "중량_kg", "zooplus": "sizes", "petsathome": "sizes", "petsmart": "sizes"}, "중량_kg_최소와 같음"),
    ("판매옵션_원문", "가격", "문자열", "", "용량·옵션 원문",
     {"zooplus": "sizes", "petsathome": "sizes", "petsmart": "sizes"}, ""),
    ("평점", "리뷰", "실수", "5점 만점", "사이트 평점",
     {"danawa": "평점", "zooplus": "rating", "petsathome": "rating", "petsmart": "rating"}, ""),
    ("리뷰수", "리뷰", "정수", "건", "리뷰 수",
     {"danawa": "리뷰수", "zooplus": "review_count", "petsathome": "review_count", "petsmart": "review_count"}, ""),
    ("리뷰수_하한표기여부", "리뷰", "불리언", "", "True면 원문이 '999+' (실제 리뷰수는 그 이상)", {"danawa": "리뷰수_999이상"}, ""),
    ("등록연도", "리뷰", "정수", "", "사이트 등록 연도", {"danawa": "등록연도"}, ""),
    ("영양정보보유여부", "품질", "불리언", "", "영양성분 정보 보유 여부",
     {"zooplus": "영양정보_있음", "petsathome": "영양정보_있음"}, ""),
    ("중복여부", "품질", "불리언", "", "출처가 표시한 중복 여부 (zooplus: 사이트 내 중복, petsathome: zooplus에도 있음)",
     {"zooplus": "is_dup", "petsathome": "in_zooplus"}, ""),
    ("품질플래그", "품질", "문자열(복수)", "", "범위 검사·환산 결과 플래그 + 원본 이상값 표시(원본: 접두어)",
     {"danawa": "(검사 결과)", "zooplus": "(검사 결과)", "petsathome": "(검사 결과) + 이상값", "petsmart": "(검사 결과)"},
     "data_integration_rules.md 8.2 검토 범위 적용"),
]
COLUMNS = [s[0] for s in SCHEMA]

# ---------------------------------------------------------------------------
# 공통 도우미
# ---------------------------------------------------------------------------
LOG = []


def log(df, mask, attr, before, after, rule):
    """값이 바뀌거나 무효 처리된 행을 환산 로그에 남긴다. rule은 문자열 또는 행별 Series."""
    for i in df.index[mask]:
        LOG.append({"출처": df.at[i, "출처"], "상품ID": df.at[i, "상품ID"], "속성": attr,
                    "원값": before[i], "변환값": after[i],
                    "규칙": rule[i] if isinstance(rule, pd.Series) else rule})


def add_flag(df, mask, flag):
    df.loc[mask, "품질플래그"] = df.loc[mask, "품질플래그"].fillna("").map(lambda s: f"{s}|{flag}" if s else flag)


def multi(s, sep):
    """복수값 구분자를 '|'로 통일하고 공백·중복을 정리한다."""
    def one(v):
        if pd.isna(v):
            return np.nan
        items = list(dict.fromkeys(t.strip() for t in str(v).split(sep) if t.strip()))
        return "|".join(items) if items else np.nan
    return s.map(one)


def to_bool(s, true_values=(1, True, "Yes", "yes")):
    return s.map(lambda v: pd.NA if pd.isna(v) else v in true_values).astype("boolean")


FOOD_TYPE_RULES = [  # (정규식, 표준 코드) - 위에서부터 검사
    (r"동결|freeze", "동결건조"), (r"에어드라이|air.?dr", "에어드라이"), (r"dehydrat", "탈수건조"),
    (r"화식|fresh|cooked", "화식"),
    (r"냉동|frozen", "냉동"), (r"topper|토퍼", "토퍼"), (r"snack|treat|간식", "간식"),
    (r"반건조|semi", "반건조"), (r"습식|wet|can|pouch|tray", "습식"), (r"건식|dry|kibble", "건식"),
    (r"액상|liquid|broth", "액상"), (r"분말|powder", "분말"),
]
LIFE_STAGE_RULES = [
    (r"전연령|all\s*(life\s*)?stages?|all\s*ages|^all$", "전연령"), (r"퍼피|puppy|puppies|junior", "퍼피"),
    (r"어덜트|adult", "어덜트"), (r"시니어|senior|mature|aging|ageing|7\+", "시니어"),
    # petsathome 자유 문장의 나이 표현 ("All dogs from 8 weeks", "Dogs aged 1+ years", "8+ years")
    (r"\ball dogs\b", "전연령"),
    (r"\d+\s*\+?\s*weeks|\b([1-9]|1[01])\s*\+?\s*months?", "퍼피"),
    (r"\b(1[2-9]|[2-9]\d)\s*months|\b[1-6]\s*(\+|-|to)?\s*\d*\s*(yrs|years)", "어덜트"),
    (r"\b([7-9]|1\d)\s*\+\s*(yrs|years)", "시니어"),
]
BREED_SIZE_RULES = [
    (r"extra\s*small|x-?small|mini|toy", "초소형"), (r"extra\s*large|x-?large|giant", "초대형"),
    (r"small", "소형"), (r"medium", "중형"), (r"large", "대형"), (r"^all|all\s*breed", "전체"),
]


def categorize(s, rules, split=None):
    """원문에서 규칙에 맞는 표준 코드를 모두 찾아 '|'로 잇는다. split이 있으면 토큰별로 첫 규칙만 적용."""
    def one(v):
        if pd.isna(v):
            return np.nan
        text = str(v).lower()
        if split:
            found = []
            for tok in re.split(split, text):
                for pat, code in rules:
                    if re.search(pat, tok.strip()):
                        found.append(code)
                        break
        else:
            found = [code for pat, code in rules if re.search(pat, text)]
        found = list(dict.fromkeys(found))
        return "|".join(found) if found else np.nan
    return s.map(one)


WEIGHT_RE = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|lbs?|oz)\b", re.I)
UNIT_TO_KG = {"kg": 1.0, "g": 0.001, "lb": LB_TO_KG, "lbs": LB_TO_KG, "oz": OZ_TO_KG}


def option_kg(text):
    """옵션 하나의 총중량(kg). '2 x 12kg' → 24, '12kg + 2.4kg Free!' → 14.4"""
    hits = WEIGHT_RE.findall(str(text))
    if not hits:
        return np.nan
    return sum((int(n) if n else 1) * float(w.replace(",", ".")) * UNIT_TO_KG[u.lower()] for n, w, u in hits)


def sizes_kg(s):
    kg = s.map(lambda v: [x for x in (option_kg(o) for o in str(v).split("|")) if not np.isnan(x)] if pd.notna(v) else [])
    return kg.map(lambda l: min(l) if l else np.nan), kg.map(lambda l: max(l) if l else np.nan)


def read(path):
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def blank(df_src, source):
    out = pd.DataFrame(index=df_src.index, columns=COLUMNS, dtype=object)
    out["출처"] = source
    return out


def copy_nutrients(out, src, petsmart=False):
    for name, kr, en in NUTRIENT_PCT:
        col = en if petsmart else kr
        if col in src:
            out[f"{name}_pct"] = pd.to_numeric(src[col], errors="coerce")
    for col in ["건물기준_조단백", "건물기준_조지방"] + [f"dm_{kr}" for _, kr, _ in NUTRIENT_PCT]:
        if col in src:
            out[col.replace("dm_", "건물기준_") + "_pct"] = src[col]  # 원본 건물기준값: 재계산 시 보조로만 사용


# ---------------------------------------------------------------------------
# 출처별 변환
# ---------------------------------------------------------------------------
def load_danawa():
    src = read(GOLD / "danawa_.csv")
    raw = read(DANAWA_RAW)[["pcode", "상품URL"]]
    src = src.merge(raw, on="pcode", how="left")
    out = blank(src, "danawa")
    out["상품ID"] = src["pcode"].astype(str)
    out["상품명"] = src["상품명"]
    out["제조사"] = src["제조사"]
    out["상품URL"] = src["상품URL"]
    out["사료형태_원문"] = src["제형"]
    out["사료형태"] = categorize(src["제형"].fillna("") + " " + src["가공방식"].fillna(""), FOOD_TYPE_RULES)
    out["가공방식"] = src["가공방식"]
    out["사료여부"] = to_bool(src["사료여부"])
    out["생애주기_원문"] = src["나이"]
    out["생애주기"] = categorize(src["나이"], LIFE_STAGE_RULES)
    out["알갱이크기"] = multi(src["크기"], ",")
    out["기능_원문"] = multi(src["기능"], ",")
    out["라벨출처"] = np.where(src["기능"].notna(), "사이트분류", None)
    out["처방식여부"] = to_bool(src["처방식여부"])
    out["포장"] = src["포장"]
    out["인증"] = multi(src["인증"], ",")
    tag_cols = {"무방부제여부": "무방부제", "무합성보존제여부": "무합성보존제", "GMOFree여부": "GMO Free",
                "가수분해여부": "가수분해", "그레인프리여부": "그레인프리", "무색소여부": "무색소"}
    out["표시태그"] = src[list(tag_cols)].apply(
        lambda r: "|".join(t for c, t in tag_cols.items() if r[c] == 1) or np.nan, axis=1)
    out["주단백질원"] = multi(src["주 단백질원"], ",")
    out["주요기능성분"] = multi(src["주요성분"], ",")
    copy_nutrients(out, src)
    out["통화"] = "KRW"
    out["최저가"] = src["최저가"]
    out["kg당최저가"] = src["단위가격_원/kg"]
    out["중량_kg_최소"] = out["중량_kg_최대"] = src["중량_kg"]
    out["평점"] = src["평점"]
    out["리뷰수"] = src["리뷰수"]
    out["리뷰수_하한표기여부"] = to_bool(src["리뷰수_999이상"])
    out["등록연도"] = src["등록연도"]
    return out


def load_eu(path, source):
    """zooplus·petsathome: 같은 수집기 출력이라 컬럼 구성이 거의 같다."""
    src = read(path)
    out = blank(src, source)
    out["사이트"] = src["site"]
    out["상품ID"] = src["product_id"].astype(str)
    out["상품명"] = src["name"]
    out["브랜드"] = src["brand"]
    out["상품URL"] = src["url"]
    fmt = "사료형태" if source == "zooplus" else "food_format"
    out["사료형태_원문"] = src[fmt]
    out["사료형태"] = categorize(src["category"].fillna("") + "|" + src[fmt].fillna(""), FOOD_TYPE_RULES)
    out["생애주기_원문"] = src["생애주기"]
    out["생애주기"] = categorize(src["생애주기"], LIFE_STAGE_RULES)
    out["견종크기_원문"] = src["견종크기"]
    out["견종크기"] = categorize(src["견종크기"], BREED_SIZE_RULES, split=r"\|")
    out["기능_원문"] = multi(src["기능"], "|")
    out["라벨출처"] = np.where(src["기능"].notna(), "사이트분류", None)
    if "처방식" in src:
        out["처방식여부"] = to_bool(src["처방식"])
    out["맛"] = multi(src["맛"], "|")
    out["포장"] = src["포장"]
    out["원재료"] = src["ingredients"]
    copy_nutrients(out, src)
    out["열량_원값"] = src["kcal_per_kg"]
    for kr, std in [("오메가3", "오메가3_pct"), ("오메가6", "오메가6_pct"), ("칼륨", "칼륨_pct"),
                    ("마그네슘", "마그네슘_pct"), ("탄수화물", "탄수화물_pct"), ("전분", "전분_pct"),
                    ("염소", "염소_pct"), ("EPA_DHA", "EPA_DHA합_pct"), ("타우린", "타우린_pct")]:
        if kr in src:
            out[std] = src[kr]
    for kr, std in [("글루코사민", "글루코사민_mg_kg"), ("카르니틴", "L카르니틴_mg_kg")]:
        if kr in src:  # zooplus는 %로 수집 → mg/kg
            m = src[kr].notna()
            out[std] = src[kr] * PCT_TO_MG_KG
            log(out, m, std, src[kr].astype(str) + " %", out[std], "% × 10,000 → mg/kg")
    if "타우린" in src:  # % 컬럼에 mg/kg 값이 섞임 (1,000~2,680)
        m = src["타우린"] > 100
        after = src["타우린"] / PCT_TO_MG_KG
        log(out, m, "타우린_pct", src["타우린"].astype(str), after, "100 초과 값은 mg/kg로 판단 → ÷10,000 → %")
        out.loc[m, "타우린_pct"] = after[m]
    out["통화"] = src["currency"]
    out["최저가"] = src["price_min"]
    out["최고가"] = src["price_max"]
    out["kg당최저가"] = src["price_per_kg_min"]
    out["판매옵션_원문"] = src["sizes"]
    out["중량_kg_최소"], out["중량_kg_최대"] = sizes_kg(src["sizes"])
    # 옵션 원문이 맛 이름뿐이면 상품명의 용량 표기(예: '6 x 800g')로 보충
    from_name = src["name"].map(option_kg)
    out["중량_kg_최소"] = out["중량_kg_최소"].fillna(from_name)
    out["중량_kg_최대"] = out["중량_kg_최대"].fillna(from_name)
    out["평점"] = src["rating"]
    out["리뷰수"] = src["review_count"]
    out["영양정보보유여부"] = to_bool(src["영양정보_있음"])
    out["중복여부"] = to_bool(src["is_dup" if source == "zooplus" else "in_zooplus"])
    if "이상값" in src:
        out["품질플래그"] = src["이상값"].map(lambda v: "|".join(f"원본:{t}" for t in str(v).split("|")) if pd.notna(v) else np.nan)
    return out


# petsmart 미량성분: 표준명 → (원본 컬럼, {소문자 단위: 배수 또는 None(=단위오류 NULL)}, 단위 없을 때 가정 단위)
PETSMART_MICRO = {
    "타우린_pct": ("taurine", {"%": 1}, "%"),
    "오메가3_pct": ("omega3", {"%": 1}, "%"),
    "오메가6_pct": ("omega6", {"%": 1, "iu/kg": None}, "%"),
    "리놀레산_pct": ("linoleic_acid", {"%": 1}, "%"),
    "글루코사민_mg_kg": ("glucosamine", {"mg/kg": 1, "ppm": 1, "iu/kg": None}, "mg/kg"),
    "콘드로이틴_mg_kg": ("chondroitin", {"mg/kg": 1, "ppm": 1}, "mg/kg"),
    "L카르니틴_mg_kg": ("l_carnitine", {"mg/kg": 1, "ppm": 1}, "mg/kg"),
    "아연_mg_kg": ("zinc", {"mg/kg": 1}, "mg/kg"),
    "셀레늄_mg_kg": ("selenium", {"mg/kg": 1}, "mg/kg"),
    "비타민C_mg_kg": ("vitamin_c", {"mg/kg": 1, "ppm": 1}, "mg/kg"),
    "비타민A_IU_kg": ("vitamin_a", {"iu/kg": 1, "%": None}, "iu/kg"),
    "비타민E_IU_kg": ("vitamin_e", {"iu/kg": 1, "mg/kg": None}, "iu/kg"),
    "유산균_CFU_g": ("probiotics_cfu", {"cfu/g": 1, "cfu/lb": 1 / G_PER_LB}, None),
}


def convert_petsmart_unit(out, src, std, col, factors, assume):
    val, unit = src[col], src[f"{col}_unit"].str.strip().str.lower()
    unit_filled = unit.fillna(assume) if assume else unit
    factor = unit_filled.map(lambda u: factors.get(u, None) if pd.notna(u) else None)
    result = val * pd.to_numeric(factor, errors="coerce")
    has = val.notna()
    no_unit = has & unit.isna()
    if assume:
        log(out, no_unit & result.notna(), std, val.astype(str) + " (단위 없음)", result, f"단위 없음 → {assume} 가정")
    else:
        log(out, no_unit, std, val.astype(str) + " (단위 없음)", result, "단위 없음 → 배수가 커서 추정 불가, NULL")
        add_flag(out, no_unit, f"{std}_단위없음")
    changed = has & unit.notna() & factor.map(lambda f: pd.notna(f) and f != 1)
    log(out, changed, std, val.astype(str) + " " + unit, result, unit + " → 표준 단위 환산")
    bad = has & unit.notna() & factor.isna()
    log(out, bad, std, val.astype(str) + " " + unit, result, "표준 단위와 호환되지 않는 단위 → 단위오류, NULL")
    add_flag(out, bad, f"{std}_단위오류")
    out[std] = result


def load_petsmart():
    src = read(GOLD / "petsmart_dryfood_product.csv")
    sku = read(PETSMART_SKU)
    out = blank(src, "petsmart")
    out["상품ID"] = src["web_style_id"].astype(str)
    out["상품명"] = src["name"]
    out["브랜드"] = src["brand"]
    first_url = sku.drop_duplicates("web_style_id").set_index("web_style_id")["url"]
    out["상품URL"] = src["web_style_id"].map(first_url)
    out["사료형태_원문"] = src["food_type"]
    # 수집 범위가 'Dog > Food > Dry Food' 카테고리라 형태 원문이 식감(Crunchy 등)뿐이면 건식으로 본다
    out["사료형태"] = categorize(src["food_type"], FOOD_TYPE_RULES).fillna("건식")
    life = src["life_stage"].fillna(src["life_stages"])
    out["생애주기_원문"] = life
    out["생애주기"] = categorize(life, LIFE_STAGE_RULES)
    out["견종크기_원문"] = src["breed_size"]
    out["견종크기"] = categorize(src["breed_size"], BREED_SIZE_RULES, split=r"[|,]")
    out["알갱이크기"] = src["kibble_sizes"]
    out["기능_원문"] = multi(src["hc_final"], "|")
    out["라벨출처"] = src["hc_source"].map({"curated": "큐레이션", "text": "텍스트추출"})
    out["맛"] = src["flavor"]
    out["원재료"] = src["ingredients"]

    for name, _, en in NUTRIENT_PCT:  # 주요 영양소는 모두 % → 단위 없는 행만 % 가정
        if en in src:
            convert_petsmart_unit(out, src, f"{name}_pct", en, {"%": 1}, "%")
    bounds = {"min": "하한", "max": "상한"}
    out["영양표기기준"] = src.apply(lambda r: "|".join(
        f"{name}:{bounds[r[f'{en}_minmax']]}" for name, _, en in NUTRIENT_PCT
        if f"{en}_minmax" in src and r[f"{en}_minmax"] in bounds) or np.nan, axis=1)
    for std, (col, factors, assume) in PETSMART_MICRO.items():
        convert_petsmart_unit(out, src, std, col, factors, assume)
    both = src["epa"].notna() & src["dha"].notna()
    out["EPA_DHA합_pct"] = (src["epa"] + src["dha"]).where(both)
    out["열량_원값"] = src["kcal_per_kg"]

    out["통화"] = "USD"
    out["최저가"] = src["price_min"]
    out["최고가"] = src["price_max"]
    out["판매옵션_원문"] = src["sizes"]
    out["중량_kg_최소"], out["중량_kg_최대"] = sizes_kg(src["sizes"])
    imperial = src["sizes"].str.contains(r"(?i)\b(?:lb|lbs|oz)\b", na=False)
    log(out, imperial, "중량_kg", src["sizes"],
        out["중량_kg_최소"].round(3).astype(str) + " ~ " + out["중량_kg_최대"].round(3).astype(str),
        "lb × 0.45359, oz × 0.02835 → kg")
    sku["kg"] = sku["size"].map(option_kg)
    sku["per_kg"] = sku["price"] / sku["kg"]
    per_kg = sku.groupby("web_style_id")["per_kg"].min()
    out["kg당최저가"] = src["web_style_id"].map(per_kg)
    log(out, out["kg당최저가"].notna(), "kg당최저가", pd.Series("SKU 가격/lb·oz", index=out.index),
        out["kg당최저가"].round(2), "SKU별 가격 ÷ (lb·oz→kg 중량)의 최솟값")
    out["평점"] = src["rating"]
    out["리뷰수"] = src["review_count"]
    return out


# ---------------------------------------------------------------------------
# 출처 공통 후처리: 건물기준 재계산, 열량 보정, 범위 검사
# ---------------------------------------------------------------------------
KCAL_RANGE = (500, 6000)
KCAL_TOLERANCE = 0.35  # 성분 추정 열량 대비 ±35% 이내면 일치로 본다
KCAL_FACTORS = [  # (배수, 규칙) - 단위 혼동이 소수점 밀림보다 우선
    (1000, "kcal/g로 판단 → ×1,000"), (10, "kcal/100g로 판단 → ×10"),
    (1 / KJ_PER_KCAL, "kJ/kg로 판단 → ÷4.184"), (10 / KJ_PER_KCAL, "kJ/100g로 판단 → ×10÷4.184"),
    (100, "소수점 밀림 추정 → ×100"), (0.1, "소수점 밀림 추정 → ÷10"),
    (0.01, "소수점 밀림 추정 → ÷100"), (0.0001, "소수점 밀림 추정 → ÷10,000"),
]


def estimated_kcal(df):
    """NRC 수정 Atwater 계수(단백질 3.5, 지방 8.5, 탄수화물 3.5 kcal/g)로 추정한 kcal/kg.
    수분이 없으면 사료형태로 가정(건식 10%, 습식 78%), 조섬유·조회분이 없으면 형태별 대표값을 쓴다."""
    wet = df["사료형태"].fillna("").str.contains("습식")
    moist = df["수분_pct"].fillna(pd.Series(np.where(wet, 78.0, 10.0), index=df.index))
    is_wet = moist >= 50
    fiber = df["조섬유_pct"].fillna(pd.Series(np.where(is_wet, 0.5, 3.0), index=df.index))
    ash = df["조회분_pct"].fillna(pd.Series(np.where(is_wet, 2.0, 7.0), index=df.index))
    p, f = df["조단백_pct"], df["조지방_pct"]
    nfe = (100 - p - f - fiber - ash - moist).clip(lower=0)
    return 10 * (3.5 * p + 8.5 * f + 3.5 * nfe)


def fix_kcal(df):
    raw = pd.to_numeric(df["열량_원값"], errors="coerce")
    est = estimated_kcal(df)
    result, rules = raw.copy(), pd.Series(None, index=df.index, dtype=object)
    for i in df.index[raw.notna()]:
        v, e = raw[i], est[i]
        close = (lambda x: abs(x / e - 1) <= KCAL_TOLERANCE) if pd.notna(e) and e > 0 else None
        if KCAL_RANGE[0] <= v <= KCAL_RANGE[1] or (close and close(v)):
            continue  # 정상 범위이거나, 저열량 액상·토퍼처럼 범위 밖이어도 성분 추정치와 맞으면 유지
        if close:
            cands = [(abs(v * k / e - 1), k, r) for k, r in KCAL_FACTORS if close(v * k)]
            if cands:
                _, k, r = min(cands)
                result[i], rules[i] = v * k, r
                continue
        elif v < 10 and KCAL_RANGE[0] <= v * 1000 <= KCAL_RANGE[1]:
            result[i], rules[i] = v * 1000, "kcal/g로 판단(성분 없음, 범위 기준) → ×1,000"
            continue
        result[i], rules[i] = np.nan, "보정 배수를 찾지 못함 → NULL"
    m = rules.notna()
    log(df, m, "열량_kcal_kg", raw, result.round(1), rules)
    add_flag(df, m & result.notna(), "열량_단위보정")
    add_flag(df, m & result.isna(), "열량_보정불가")
    df["열량_kcal_kg"] = result


def dry_matter(df):
    moist = df["수분_pct"]
    valid = moist.notna() & (moist < 100)
    for name, _, _ in NUTRIENT_PCT:
        if name == "수분":
            continue
        col = f"건물기준_{name}_pct"
        source_dm = pd.to_numeric(df[col], errors="coerce")  # 원본 제공값 (재계산값과 일치 확인됨)
        calc = (df[f"{name}_pct"] / (1 - moist / 100)).where(valid).round(2)
        df[col] = calc.fillna(source_dm)


RANGE_CHECKS = [("조단백_pct", 70), ("조지방_pct", 50), ("조섬유_pct", 20), ("조회분_pct", 20), ("수분_pct", 95),
                ("칼슘_pct", 5), ("인_pct", 3), ("나트륨_pct", 2), ("타우린_pct", 1), ("오메가3_pct", 10)]


def range_flags(df):
    for col, upper in RANGE_CHECKS:
        add_flag(df, df[col] > upper, f"{col.removesuffix('_pct')}>{upper}%")
        add_flag(df, df[col] < 0, f"{col.removesuffix('_pct')}<0")
    total = df[["조단백_pct", "조지방_pct", "조섬유_pct", "조회분_pct", "수분_pct"]].sum(axis=1, min_count=5)
    add_flag(df, total > 105, "성분합>105%")
    dry_but_wet = df["사료형태"].eq("건식") & (df["수분_pct"] > 40)
    wet_but_dry = df["사료형태"].eq("습식") & (df["수분_pct"] < 40)
    add_flag(df, dry_but_wet | wet_but_dry, "사료형태_수분불일치")


def write_dictionary(df):
    rows = []
    for name, group, typ, unit, desc, cols, rule in SCHEMA:
        n = sum(s in cols for s in SOURCES)  # 고정값·재계산으로 채우는 출처도 포함
        kind = ("파생" if name == "출처" else "전 출처 병합" if n == 4 else
                "일부 출처 병합" if n >= 2 else "단일 출처")
        rows.append({"속성명": name, "그룹": group, "타입": typ, "단위": unit, "설명": desc, "병합유형": kind,
                     **{f"{s}_원본": cols.get(s, "") for s in SOURCES},
                     "단위환산_규칙": rule, "채움률_%": round(df[name].notna().mean() * 100, 1)})
    pd.DataFrame(rows).to_csv(OUT / "schema_dictionary.csv", index=False, encoding="utf-8-sig")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.concat([load_danawa(), load_eu(GOLD / "zooplus_dog_food.csv", "zooplus"),
                    load_eu(GOLD / "petsathome_dog_food.csv", "petsathome"), load_petsmart()], ignore_index=True)
    dry_matter(df)
    fix_kcal(df)
    range_flags(df)
    df = df[COLUMNS]
    for col in ["처방식여부", "사료여부", "리뷰수_하한표기여부", "영양정보보유여부", "중복여부"]:
        df[col] = df[col].astype("boolean")
    df.to_csv(OUT / "gold_unified.csv", index=False, encoding="utf-8-sig")
    write_dictionary(df)
    log_df = pd.DataFrame(LOG)
    log_df.to_csv(OUT / "unit_conversion_log.csv", index=False, encoding="utf-8-sig")

    print(f"통합: {df.shape[0]:,}행 × {df.shape[1]}열")
    print(df["출처"].value_counts().to_string())
    print("\n[환산 로그] 속성·규칙별 건수")
    print(log_df.groupby(["속성", "규칙"]).size().to_string())
    print("\n[품질플래그] 상위")
    print(df["품질플래그"].str.split("|").explode().value_counts().head(25).to_string())


if __name__ == "__main__":
    main()
