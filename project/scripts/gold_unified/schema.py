"""gold 통합 스키마: project/md/gold_unified_schema.md의 '10. 스키마 정의' 표를 읽어 스키마 객체로 만든다.

md 표가 스키마의 유일한 원본이다. 이 모듈은 표를 해석·검사만 하고 스키마 내용을 따로 갖지 않는다.

직접 실행하면 표 형식을 검사하고 schema_dictionary.csv(표의 자동 생성 사본)를 만든다.
  python project/scripts/gold_unified/schema.py
"""
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandas.api import types as ptypes

PROJECT = Path(__file__).resolve().parents[2]
SCHEMA_MD = PROJECT / "md/gold_unified_schema.md"
DICTIONARY_CSV = PROJECT / "data/model_datasets/unified/schema_dictionary.csv"

SECTION_TITLE = "## 10. 스키마 정의"
SOURCES = ["danawa", "zooplus", "petsathome", "petsmart"]
HEADER = ["속성명", "그룹", "타입", "단위", "설명", *SOURCES, "환산규칙"]
TYPES = {"문자열", "문자열(복수)", "범주", "범주(복수)", "불리언", "정수", "실수"}


class SchemaError(ValueError):
    """md 표 형식 오류 또는 데이터와 스키마의 불일치."""


@dataclass(frozen=True)
class Attribute:
    name: str
    group: str
    type: str
    unit: str
    description: str
    sources: dict  # {출처: 원본 컬럼 설명}, 해당 출처에 없으면 키가 없다
    rule: str

    @property
    def merge_kind(self):
        """출처 수로 판정한 병합 유형. 고정값·재계산으로 채우는 출처도 포함한다."""
        if self.name == "출처":
            return "파생"
        n = len(self.sources)
        return "전 출처 병합" if n == len(SOURCES) else "일부 출처 병합" if n >= 2 else "단일 출처"


def _cells(line):
    """md 표 한 줄을 칸으로 나눈다. '\\|'는 칸 구분이 아닌 문자 '|'다."""
    body = line.strip()
    if not (body.startswith("|") and body.endswith("|")):
        raise SchemaError(f"표 행이 '|'로 시작·종료하지 않음: {line!r}")
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", body[1:-1])]


def _table_lines(text):
    """SECTION_TITLE 절 안의 첫 번째 표 줄들을 돌려준다."""
    start = text.find(SECTION_TITLE)
    if start < 0:
        raise SchemaError(f"'{SECTION_TITLE}' 절을 찾을 수 없음: {SCHEMA_MD}")
    section = text[start + len(SECTION_TITLE):]
    next_section = re.search(r"^## ", section, re.M)
    lines = (section[:next_section.start()] if next_section else section).splitlines()
    table = []
    for line in lines:
        if line.lstrip().startswith("|"):
            table.append(line)
        elif table:  # 표가 끝난 뒤 다른 표가 나와도 무시한다
            break
    if len(table) < 3:
        raise SchemaError(f"'{SECTION_TITLE}' 절에 스키마 표가 없음")
    return table


def load_schema(path=SCHEMA_MD):
    """md 표를 읽어 Attribute 목록(표 순서 = 통합 데이터 컬럼 순서)을 돌려준다."""
    header, separator, *rows = _table_lines(Path(path).read_text(encoding="utf-8"))
    if _cells(header) != HEADER:
        raise SchemaError(f"표 머리글이 다름\n  기대: {HEADER}\n  실제: {_cells(header)}")
    if not all(re.fullmatch(r":?-+:?", c) for c in _cells(separator)):
        raise SchemaError("머리글 다음 줄이 구분선(|---|)이 아님")

    schema, errors = [], []
    for n, line in enumerate(rows, start=3):
        cells = _cells(line)
        if len(cells) != len(HEADER):
            errors.append(f"{n}번째 표 줄: 칸 수 {len(cells)} (기대 {len(HEADER)}) - 칸 안의 '|'를 '\\|'로 썼는지 확인")
            continue
        row = dict(zip(HEADER, cells))
        if not row["속성명"]:
            errors.append(f"{n}번째 표 줄: 속성명 없음")
        if row["타입"] not in TYPES:
            errors.append(f"{row['속성명']}: 알 수 없는 타입 '{row['타입']}' (허용: {', '.join(sorted(TYPES))})")
        sources = {s: row[s] for s in SOURCES if row[s]}
        if not sources:
            errors.append(f"{row['속성명']}: 원본 칸이 모두 비어 있음")
        schema.append(Attribute(row["속성명"], row["그룹"], row["타입"], row["단위"], row["설명"],
                                sources, row["환산규칙"]))
    names = [a.name for a in schema]
    errors += [f"속성명 중복: {name}" for name in sorted({x for x in names if names.count(x) > 1})]
    if errors:
        raise SchemaError("스키마 표 오류\n  " + "\n  ".join(errors))
    return schema


def validate_dataset(df, schema):
    """통합 데이터의 컬럼 이름·순서·타입이 스키마와 일치하는지 검사한다."""
    expected = [a.name for a in schema]
    errors = []
    if list(df.columns) != expected:
        missing = [c for c in expected if c not in df.columns]
        extra = [c for c in df.columns if c not in expected]
        errors.append(f"컬럼 불일치 - 누락: {missing}, 스키마에 없음: {extra}"
                      if missing or extra else "컬럼 순서가 스키마와 다름")
    checks = {"실수": ptypes.is_numeric_dtype, "정수": ptypes.is_numeric_dtype, "불리언": ptypes.is_bool_dtype}
    for a in schema:
        check = checks.get(a.type)
        if a.name in df.columns and check and df[a.name].notna().any() and not check(df[a.name]):
            errors.append(f"{a.name}: 스키마 타입 '{a.type}'인데 데이터 타입이 {df[a.name].dtype}")
    if errors:
        raise SchemaError("통합 데이터가 스키마와 다름\n  " + "\n  ".join(errors))


def write_dictionary(schema, path=DICTIONARY_CSV):
    """스키마 표의 사본에 병합유형을 더해 CSV로 저장한다 (엑셀 열람용, 직접 수정하지 않음)."""
    rows = [{"속성명": a.name, "그룹": a.group, "타입": a.type, "단위": a.unit, "설명": a.description,
             "병합유형": a.merge_kind, **{f"{s}_원본": a.sources.get(s, "") for s in SOURCES},
             "단위환산_규칙": a.rule} for a in schema]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    schema = load_schema()
    write_dictionary(schema)
    kinds = pd.Series([a.merge_kind for a in schema]).value_counts()
    print(f"스키마 OK: 속성 {len(schema)}개 ({SCHEMA_MD.name})")
    print(kinds.to_string())
    print(f"→ {DICTIONARY_CSV.relative_to(PROJECT)}")
