"""gold_unified.csv에서 학습 입력에 쓸 9개 속성만 떼어 project/result/에 저장한다.

학습카테고리가 없는 상품(정답 없음), 중복 상품, 이상치 상품, 사료형태가 복수값(예: 건식|동결건조)인 상품은 뺀다.
중복 상품은 두 가지다.
- 출처가 표시한 중복: 중복여부=True (Zooplus 사이트 내 중복, Zooplus에도 있는 Pets at Home 상품)
- 용량만 다른 같은 상품: 다나와·PetSmart는 중복 표시가 없어서, 같은 출처 안에서 상품명의 용량 표기
  (1.5kg, 400g, 130ml 등)를 뺀 이름이 같으면 같은 상품으로 보고 첫 행만 남긴다.
이상치는 물리적으로 불가능한 값이다.
- 건물기준 조단백·조지방·조섬유·조회분의 합이 100%를 넘음 (고형분의 일부이므로 100%를 넘을 수 없다)
- 사료형태와 수분이 맞지 않음 (품질플래그 사료형태_수분불일치: 건식인데 수분 > 40%, 습식인데 수분 < 40%)

실행: python project/scripts/gold_unified/export_training_input.py (build_dataset.py 실행 뒤)
"""
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "data/model_datasets/unified/gold_unified.csv"
OUT = PROJECT / "result/gold_training_input.csv"
DM_COLUMNS = ["건물기준_조단백_pct", "건물기준_조지방_pct", "건물기준_조섬유_pct", "건물기준_조회분_pct"]
COLUMNS = ["출처", "상품ID", "상품명", *DM_COLUMNS, "사료형태", "학습카테고리"]
# 용량·수량 표기: "1.5kg", "(400g)", "130ml", "2.26 kg x 2개" 등
SIZE = r"\s*\(?\d+(?:\.\d+)?\s*(?:kg|g|ml|m|lb|lbs|oz)\b\)?(?:\s*[xX×*]\s*\d+\s*(?:개|팩|ea)?)?"


def base_name(names):
    """상품명에서 용량 표기를 빼고 소문자·공백을 정리한다 (용량 변형을 같은 상품으로 묶는 키)."""
    return names.str.lower().str.replace(SIZE, "", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()


def is_outlier(df):
    dm_sum_over = df[DM_COLUMNS].sum(axis=1, min_count=1) > 100
    form_moisture = df["품질플래그"].fillna("").str.contains("사료형태_수분불일치", regex=False)
    return dm_sum_over | form_moisture


def main():
    gold = pd.read_csv(SOURCE, encoding="utf-8-sig", dtype={"상품ID": str}, low_memory=False)
    n0 = len(gold)
    gold = gold[gold["학습카테고리"].notna()]
    n1 = len(gold)
    gold = gold[gold["중복여부"] != True]
    n2 = len(gold)
    gold = gold[~gold.assign(기본명=base_name(gold["상품명"])).duplicated(["출처", "기본명"])]
    n3 = len(gold)
    gold = gold[~is_outlier(gold)]
    n4 = len(gold)
    gold = gold[~gold["사료형태"].str.contains("|", regex=False, na=False)]
    print(f"Gold {n0:,}행 → 학습카테고리 없음 {n0 - n1:,}행, 출처 표시 중복 {n1 - n2:,}행, "
          f"용량 변형 중복 {n2 - n3:,}행, 이상치 {n3 - n4:,}행, 사료형태 복수값 {n4 - len(gold):,}행 제외")
    gold = gold[COLUMNS]
    if gold.duplicated(["출처", "상품ID"]).any():
        raise ValueError("출처 + 상품ID가 중복된다")
    OUT.parent.mkdir(exist_ok=True)
    gold.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{len(gold):,}행 × {gold.shape[1]}열 → {OUT.relative_to(PROJECT)}")
    print(gold.isna().sum().rename("결측").to_string())


if __name__ == "__main__":
    main()
