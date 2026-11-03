"""gold 폴더의 출처별 원본 4개(다나와·Zooplus·Pets at Home·PetSmart)를 통합 스키마에 맞춰 하나로 합친다.

스키마는 schema.py가 project/md/gold_unified_schema.md의 '10. 스키마 정의' 표에서 읽는다.
이 파일은 원본 컬럼을 스키마 속성에 채우는 변환 규칙만 갖고, 저장 전에 결과가 스키마와 맞는지 검사한다.

산출물 (data/model_datasets/unified/):
  - gold_unified.csv          통합 데이터 (한 행 = 상품 1개)
  - schema_dictionary.csv     스키마 표의 자동 생성 사본 (schema.py)
  - unit_conversion_log.csv   값이 바뀌거나 무효 처리된 환산 내역 (행 단위)

원칙: 원본 파일은 수정하지 않는다. 환산은 근거 규칙을 로그로 남기고, 근거 없이 고칠 수 없는 값은
삭제하지 않고 NULL + 품질플래그로 표시한다 (project/md/data_integration_rules.md).

실행: python project/scripts/gold_unified/build_dataset.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from schema import load_schema, validate_dataset, write_dictionary

PROJECT = Path(__file__).resolve().parents[2]
GOLD = PROJECT / "data/model_datasets/gold"
PETSMART_SKU = PROJECT / "data/model_datasets/unlabeled/petsmart_dryfood_sku.csv"
DANAWA_RAW = PROJECT / "data/Source/danawa_dogfood.csv"  # danawa_.csv에 없는 상품URL 복원용
CATEGORY_DICT = PROJECT / "data/model_datasets/기능카테고리사전.csv"  # 기능_원문 → 표준 카테고리
OUT = PROJECT / "data/model_datasets/unified"

LB_TO_KG = 0.45359237
OZ_TO_KG = 0.028349523125
G_PER_LB = 453.59237
KJ_PER_KCAL = 4.184
PCT_TO_MG_KG = 10_000  # 1% = 10 g/kg = 10,000 mg/kg

# 통합 스키마(속성명·순서·타입)는 schema.py가 md 표에서 읽는다. 여기서는 정의하지 않는다.
SCHEMA = load_schema()
COLUMNS = [a.name for a in SCHEMA]

NUTRIENT_PCT = [  # 변환 코드용 영양소 원본 컬럼 대응: (표준명, 다나와/zooplus/pah 컬럼, petsmart 컬럼)
    ("조단백", "조단백", "crude_protein"),
    ("조지방", "조지방", "crude_fat"),
    ("조섬유", "조섬유", "crude_fiber"),
    ("조회분", "조회분", "ash"),
    ("수분", "수분", "moisture"),
    ("칼슘", "칼슘", "calcium"),
    ("인", "인", "phosphorus"),
    ("나트륨", "나트륨", "sodium"),
]

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


DRY_SUBTYPES = ["동결건조", "에어드라이", "탈수건조"]  # 수분 추정용 하위 형태 (이 순서로 판정, 없으면 일반 건식)


def form_group(value):
    """사료형태 복수값을 건식·습식·반건조·미상으로 묶는다 (그룹별 수분 중앙값: 건식 5~18%, 반건조 25%, 습식 72~95%)."""
    if pd.isna(value):
        return "미상"
    codes = set(value.split("|"))
    if codes & {"습식", "화식", "냉동"}:
        return "습식"
    if "반건조" in codes and "건식" not in codes:
        return "반건조"
    if codes & {"건식", *DRY_SUBTYPES}:
        return "건식"
    return "습식" if "토퍼" in codes else "미상"


def dry_subtype(value):
    codes = set(str(value).split("|"))
    return next((s for s in DRY_SUBTYPES if s in codes), "건식")


def dry_matter(df):
    """건물기준 = 현물값 ÷ (1 − 수분/100). 수분이 없는 건식은 하위 형태별 실측 수분 중앙값으로 추정한다.

    건식 수분은 중앙값 10%, 사분위 10~12%로 좁고 건강기능 카테고리별 차이가 없어(EDA 4-4절) 추정 오차가 작다.
    습식은 수분 범위가 넓어 추정하지 않는다. 추정 수분은 수분_pct에도 채우고, 추정 여부는 수분추정여부로 표시한다
    (실측값만 쓰려면 수분추정여부=False인 행만 쓴다). 돌려주는 값은 하위 형태별 추정 수분(중앙값)이다.
    """
    df["형태대분류"] = df["사료형태"].map(form_group)
    dry = df["형태대분류"].eq("건식")
    subtype = df["사료형태"].map(dry_subtype).where(dry)
    measured = df["수분_pct"].where(df["수분_pct"] < 100)
    medians = measured[dry].groupby(subtype[dry]).median()
    raw_cols = [f"{name}_pct" for name, _, _ in NUTRIENT_PCT if name != "수분"]
    impute = dry & df["수분_pct"].isna() & df[raw_cols].notna().any(axis=1)
    estimate = subtype.map(medians).where(impute)
    moist = measured.fillna(estimate)
    df["수분_pct"] = df["수분_pct"].fillna(estimate)
    df["수분추정여부"] = impute
    for name, _, _ in NUTRIENT_PCT:
        if name == "수분":
            continue
        col = f"건물기준_{name}_pct"
        source_dm = pd.to_numeric(df[col], errors="coerce")  # 원본 제공값 (재계산값과 일치 확인됨)
        calc = (df[f"{name}_pct"] / (1 - moist / 100)).round(2)
        df[col] = calc.fillna(source_dm)
    return medians


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


def add_function_categories(df):
    """기능_원문을 기능카테고리사전.csv로 표준 카테고리에 매핑한다.

    기능카테고리: 건강기능(health_function) 카테고리 전체, 학습카테고리: 그중 학습채택=adopted만.
    한 원문 라벨이 여러 카테고리에 대응할 수 있고(예: 신장·요로건강 → renal, urinary),
    카테고리 표기 순서는 사전의 행 순서를 따른다. 사전에 없는 원문 라벨은 품질플래그로 표시한다.
    """
    dic = read(CATEGORY_DICT)
    order = {c: i for i, c in enumerate(dict.fromkeys(dic["카테고리"]))}
    health = dic[dic["유형"] == "health_function"]
    to_categories = health.groupby(["출처", "원문라벨"])["카테고리"].agg(list).to_dict()
    adopted = set(dic.loc[dic["학습채택"] == "adopted", "카테고리"])
    known = set(zip(dic["출처"], dic["원문라벨"]))

    def one(source, raw):
        if pd.isna(raw):
            return np.nan, np.nan, False
        keys = [(source, label.strip()) for label in raw.split("|")]
        found = sorted({c for k in keys for c in to_categories.get(k, [])}, key=order.get)
        train = [c for c in found if c in adopted]
        return "|".join(found) or np.nan, "|".join(train) or np.nan, any(k not in known for k in keys)

    result = [one(s, r) for s, r in zip(df["출처"], df["기능_원문"])]
    df["기능카테고리"] = [r[0] for r in result]
    df["학습카테고리"] = [r[1] for r in result]
    add_flag(df, pd.Series([r[2] for r in result], index=df.index), "기능라벨_사전없음")


def apply_types(df):
    """스키마 타입에 맞춰 dtype을 정한다 (불리언 → True/False/NULL, 정수 → 결측 허용 정수, 실수 → 숫자)."""
    for a in SCHEMA:
        if a.type == "불리언":
            df[a.name] = df[a.name].astype("boolean")
        elif a.type == "정수":
            df[a.name] = pd.to_numeric(df[a.name], errors="coerce").astype("Int64")
        elif a.type == "실수":
            df[a.name] = pd.to_numeric(df[a.name], errors="coerce")
    return df


GOLD_LABEL_SOURCES = ("사이트분류", "큐레이션")  # PetSmart 텍스트추출 라벨은 silver


def select_gold(df):
    """기능 라벨이 사이트 공식 분류 또는 PetSmart 큐레이션인 행만 남긴다 (training_dataset_summary.md의 Gold 기준)."""
    return df[df["기능_원문"].notna() & df["라벨출처"].isin(GOLD_LABEL_SOURCES)].reset_index(drop=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.concat([load_danawa(), load_eu(GOLD / "zooplus_dog_food.csv", "zooplus"),
                    load_eu(GOLD / "petsathome_dog_food.csv", "petsathome"), load_petsmart()], ignore_index=True)
    moisture_medians = dry_matter(df)
    fix_kcal(df)
    range_flags(df)
    add_function_categories(df)
    df = apply_types(df[COLUMNS].copy())
    gold = select_gold(df)
    for data in (df, gold):
        validate_dataset(data, SCHEMA)
    df.to_csv(OUT / "unified_all.csv", index=False, encoding="utf-8-sig")
    gold.to_csv(OUT / "gold_unified.csv", index=False, encoding="utf-8-sig")
    write_dictionary(SCHEMA, OUT / "schema_dictionary.csv")
    log_df = pd.DataFrame(LOG)
    log_df.to_csv(OUT / "unit_conversion_log.csv", index=False, encoding="utf-8-sig")

    print(f"전체 통합: {df.shape[0]:,}행 × {df.shape[1]}열 → unified_all.csv")
    print(f"Gold: {gold.shape[0]:,}행 × {gold.shape[1]}열 → gold_unified.csv")
    print(pd.DataFrame({"전체": df["출처"].value_counts(), "gold": gold["출처"].value_counts()}).to_string())
    print(f"\n[건식 수분 추정] {df['수분추정여부'].sum():,}행 (gold {gold['수분추정여부'].sum():,}행), "
          f"하위 형태별 추정 수분(%): {moisture_medians.to_dict()}")
    print("\n[환산 로그] 속성·규칙별 건수")
    print(log_df.groupby(["속성", "규칙"]).size().to_string())
    print("\n[품질플래그] 상위")
    print(df["품질플래그"].str.split("|").explode().value_counts().head(25).to_string())


if __name__ == "__main__":
    main()
