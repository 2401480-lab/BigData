# 반려견 사료 데이터 통합 규칙

작성일: 2026-11-02  
적용 대상: `project/data`의 원본 CSV와 이후 수집분  
목적: 출처별 상품 정보를 비교 가능한 분석 데이터로 통합하되, 원문·수집 범위·값의 의미를 잃지 않는다.

## 1. 핵심 원칙

1. **원본 불변**: 원본 CSV를 수정·덮어쓰기·삭제하지 않는다. 통합 결과는 별도 파일 또는 테이블로 생성한다.
2. **행 삭제 금지**: 중복·범위 밖·분석 대상 밖 행은 삭제하지 않는다. 각각 `record_status`와 `quality_flags`를 기록한 뒤 분석 뷰에서만 필요에 따라 제외한다.
3. **원문 우선**: 숫자로 파싱한 값과 원문 문자열을 함께 저장한다. 파싱 규칙이 바뀌어도 원문에서 다시 계산할 수 있어야 한다.
4. **출처 추적성**: 모든 통합 행은 출처 파일, 원본 행 번호, 원본 URL 또는 출처 상품 ID를 가진다.
5. **의미 보존**: `이상`, `이하`, `999+`, 통화, 단위, 영양 기준(현물/건물 기준/100g 기준)을 숫자만 남기고 지우지 않는다.
6. **불확실성 보존**: 정보 없음은 `NULL`로 두며 `False`, `0`, 빈 문자열과 혼동하지 않는다.

## 2. 입력 파일 등록 규칙

각 파일을 읽기 전에 `source_manifest`에 다음을 기록한다.

| 컬럼 | 의미 | 규칙 |
| --- | --- | --- |
| `source_file` | 실제 입력 파일명 | 디스크의 파일명과 정확히 같아야 함 |
| `source` | 수집 사이트 식별자 | 예: `danawa`, `lifeofepic`, `dogpre`, `zooplus`, `petsathome`, `purina_uk`, `openpetfoodfacts` |
| `file_format` | 파일 형식과 구분자 | Open Pet Food Facts는 확장자가 CSV여도 `tsv`로 기록 |
| `encoding` | 문자 인코딩 | 실제 판독에 쓴 인코딩 기록 |
| `row_count_raw` | 헤더를 제외한 원본 행 수 | 파싱 직후 산출 |
| `column_count_raw` | 원본 열 수 | 파싱 직후 산출 |
| `ingested_at` | 통합 실행 시각 | ISO 8601 형식 |
| `file_hash` | 파일 내용 해시 | 같은 이름의 다른 파일을 구분 |
| `schema_version` | 매핑 규칙 버전 | 규칙이 바뀌면 증가 |

파일을 읽을 때 열 수가 예상과 다르거나 인코딩 오류·잘린 행이 있으면 통합을 중단하고 오류 보고서를 만든다. 조용히 행을 건너뛰는 파서는 사용하지 않는다.

## 3. 산출물 구조와 역할

통합 결과를 하나의 32열 CSV만으로 끝내지 않는다.

| 산출물 | 행 단위 | 목적 |
| --- | --- | --- |
| `raw_record` | 원본 파일의 한 행 | 원문 전체와 파싱 결과를 보존하는 감사용 테이블 |
| `product_source` | 출처 사이트의 한 상품 | 사이트별 상품 기본 정보와 URL·상품 ID |
| `product_canonical` | 동일하다고 검증된 상품 묶음 | 출처 간 동일 상품 연결. 확정 전에는 생성하지 않아도 됨 |
| `nutrition_fact` | 상품·옵션·영양소 1개 | 영양소, 단위, 상·하한, 기준을 저장 |
| `product_variant` | 상품의 용량·맛·옵션 1개 | GTIN, 중량, 옵션 가격 연결 |
| `product_offer` | 수집 시점의 가격·평가 1개 | 가격·통화·판매몰·평점·리뷰의 시계열 보존 |
| `product_tag` | 상품의 태그 1개 | 생애주기, 견종크기, 기능, 특수식단 등 다중값 저장 |
| `merge_audit` | 원본 행의 통합 판정 1개 | 포함·제외·보류·중복 후보 및 사유 |
| `dog_food_analysis_view` | 분석에 쓸 상품 1개 | 32개 핵심 열을 제공하는 파생 뷰 |

`dog_food_analysis_view`는 편의를 위한 파생 결과다. 원본 보존형 정제 테이블을 대신하지 않는다.

## 4. 범위 포함·제외 규칙

### 4.1 범위 정의

기본 분석 범위는 **반려견용 식품**이다. 건식·습식·동결건조·냉동·간식·보조식은 모두 원본 보관 대상이며, 목적에 따라 분석 뷰에서 분리한다.

| 판단 | `record_status` | 처리 |
| --- | --- | --- |
| 반려견 식품으로 명확히 확인 | `included` | 분석 후보에 포함 |
| 반려견 여부가 불명확 | `review_required` | 원본 보관, 자동 집계에서는 제외 |
| 고양이·조류 등 비반려견 식품으로 명확 | `out_of_scope` | 원본 보관, 반려견 분석에서는 제외 |
| 상품명이 없거나 식별이 불가 | `incomplete` | 원본 보관, 별도 보완 대상 |

### 4.2 Open Pet Food Facts 판정

Open Pet Food Facts에는 다종 반려동물 식품이 섞여 있으므로 다음 우선순위를 적용한다.

1. `categories_tags` 또는 `main_category`에 신뢰 가능한 반려견 식품 태그가 있으면 `included`.
2. 고양이·조류·어류 등 배제 태그가 있고 반려견 태그가 없으면 `out_of_scope`.
3. 태그가 불완전하면 `categories_en`, `product_name`, URL, 원료 텍스트를 보조 근거로 삼되 `scope_reason`에 사용한 근거를 기록한다.
4. 근거가 충돌하거나 없으면 `review_required`로 둔다.

`scope_reason`에는 예를 들어 `categories_tags:en:dog-food`, `main_category:Dry dog food`, `excluded:en:cat-food`처럼 실제 판정 근거를 남긴다. 포함된 행·제외된 행·보류 행의 합은 해당 원본 파일의 행 수와 일치해야 한다.

## 5. 식별자와 중복 처리 규칙

### 5.1 식별자 우선순위

1. `source + source_product_id`
2. `source + url`
3. `GTIN`
4. `brand + 정규화한 product_name + 용량 + food_type`

`product_name`만으로 행을 삭제하거나 통합하지 않는다. 이름이 같아도 용량·맛·생애주기·판매국·성분표가 다를 수 있다.

### 5.2 중복 판정

| 상황 | 처리 |
| --- | --- |
| 같은 출처 ID와 같은 URL | `exact_duplicate` 후보. 원본 행은 모두 보존하고 대표행 선택 규칙을 기록 |
| 같은 GTIN, 브랜드·용량도 일치 | `same_variant_candidate` |
| 이름만 같고 영양·원료·URL이 다름 | `conflict_candidate`; 절대 자동 삭제하지 않음 |
| URL이 페이지 파라미터만 다름 | URL 정규화 후 후보화하되 원본 URL 유지 |
| 출처 간 이름이 유사 | `cross_source_candidate`; 사람이 검토하거나 높은 신뢰도 규칙이 있을 때만 canonical ID 부여 |

명견에픽처럼 같은 상품명인데 영양값·원료·URL이 달라지는 사례는 수집 오류 또는 충돌 후보로 격리한다. 34행을 1행으로 축소하지 않는다.

### 5.3 필수 감사 필드

| 컬럼 | 의미 |
| --- | --- |
| `source_row_id` | `source_file:원본행번호` 형식의 불변 키 |
| `duplicate_group_id` | 중복 후보군 식별자 |
| `duplicate_status` | `not_checked`, `exact_duplicate`, `candidate`, `confirmed_same`, `conflict` |
| `canonical_match_confidence` | 출처 간 동일 상품 연결 신뢰도 |
| `canonical_match_method` | GTIN, URL, 수동 검토 등 판정 방식 |

## 6. 컬럼 매핑 규칙

### 6.1 공통 핵심 컬럼

| 분석 뷰 컬럼 | 우선 원본 컬럼 | 규칙 |
| --- | --- | --- |
| `source` | 수집 파일·사이트명 | 코드값으로 표준화, 원문 사이트명은 보존 |
| `region` | `site`, `countries`, 수집처 | 판매시장과 제조국을 혼합하지 않음. ISO 국가 코드는 별도 `market_country_code`에 저장 |
| `currency` | `currency` | ISO 4217만 허용. 미확인 값은 NULL |
| `product_id` | `product_id`, `pcode`, `code`, URL ID | 원본 값을 문자열로 보존. 숫자로 캐스팅 금지 |
| `brand` | `brand`, `brands` | 원문과 정규화 브랜드를 분리 |
| `product_name` | `name`, `product_name`, 상품명 | 원문명 보존. 정규화명은 별도 컬럼 |
| `food_type` | `category`, `food_method`, `food_format` | 건식·습식·간식·보조식·냉동·동결건조를 별도 코드로 매핑; 복합값은 태그로 분리 |
| `life_stage` | `생애주기` 등 | `|` 복수값은 `product_tag`로 분리하고 원문도 보존 |
| `breed_size` | `견종크기` | 복수값은 태그 행으로 분리 |
| `function` | `기능`, `health_condition`, `special_needs` | 건강기능과 질병·처방 정보를 하나의 불명확 문자열로 합치지 않음 |
| `prescription` | 처방식 태그·분류 | `true`, `false`, `unknown`의 3상태 사용 |
| `ingredients` | `ingredients`, `ingredients_full`, `main_ingredients` | 축약본과 전체 원문을 별도 보존 |
| `url` | `url`, `source_url`, 상품URL | 원문 URL 유지, 별도 `normalized_url` 생성 가능 |

### 6.2 출처 특화 필드 보존

다음은 32개 분석 뷰에 없어도 `raw_record` 또는 확장 테이블에 반드시 보존한다.

- 다나와: 수집정렬, 페이지, 인기순위, 상품상세정보 원문, 단위가격, 판매몰수, 등록월
- 명견에픽: `source_type`, 단백질·지방 원문 라벨, `list_page`
- 강아지대통령: `collection_scope`, `nutrition_label_raw`, `collected_at`
- Zooplus·Pets at Home·Purina: 상세 설명, 특장점, 첨가물, 성분표 원문, 변형 수, GTIN, 용량, 포장, 견종, 카테고리 경로, 원료·알레르기·특수식단 태그, 건물 기준 영양성분
- Open Pet Food Facts: 생성·수정 이력, 국가·제조·구매 장소, 패키징, 알레르겐·혼입 가능 물질, 이미지, Nutri-Score·NOVA·환경 점수, 품질 상태, 모든 `*_100g` 성분

## 7. 문자열 파싱 규칙

### 7.1 공통 원칙

파싱 결과는 아래 6개를 항상 함께 저장한다.

| 컬럼 | 예: `28.0% 이상` | 예: `999+` |
| --- | --- | --- |
| `raw_value` | `28.0% 이상` | `999+` |
| `parsed_value` | `28.0` | `999` |
| `unit` | `%` | `count` |
| `bound_type` | `min` | `lower_bound` |
| `parse_status` | `parsed` | `parsed` |
| `parse_rule_version` | 적용 규칙 버전 | 적용 규칙 버전 |

파싱할 수 없으면 `parsed_value`는 NULL이고, `parse_status`는 `unparsed` 또는 `ambiguous`다. 원문을 삭제하거나 0으로 바꾸지 않는다.

### 7.2 영양성분

- `이상`, `at least`, `min` → `bound_type=min`
- `이하`, `up to`, `max` → `bound_type=max`
- 표기 없이 숫자와 단위만 있음 → `bound_type=exact`가 아니라 `unknown`을 기본값으로 한다. 출처 명세가 보증성분임을 명시할 때만 `exact` 또는 해당 기준을 사용한다.
- `%`, `g/100g`, `mg/kg`, `IU/kg`, `kcal/100g`, `kcal/kg`, `kJ/100g`를 단위별로 보존한다.
- `g/100g`는 질량비 기준 `%`와 수치상 같을 수 있지만, 변환 여부와 근거를 기록한다.
- `dm_` 접두어는 `basis=dry_matter`로 기록한다. 현물 기준 수치와 같은 열에 덮어쓰지 않는다.

### 7.3 가격·리뷰

- `원/10g`은 `price_per_kg = 원/10g × 100`으로 환산하고, `price_unit_raw`와 환산 규칙을 남긴다.
- 가격 범위는 `price_min`, `price_max` 모두 보존한다.
- `999+` 리뷰는 `review_count=999`, `review_count_bound=lower_bound`로 저장한다.
- 통화가 다른 가격은 환율 기준일·환율 소스를 기록하지 않는 한 같은 수치로 비교·평균 내지 않는다.

## 8. 영양성분·단위 검증 규칙

### 8.1 검증 방식

검증 실패 시 값을 바로 비우지 않는다. `quality_flags`에 사유를 추가하고 `parsed_value`·`raw_value`를 모두 보존한다. 분석 뷰에서만 `usable_value`를 NULL로 처리할 수 있다.

| 검사 | 예시 | 처리 |
| --- | --- | --- |
| 음수 검사 | 지방 -1% | `negative_value` |
| 물리 범위 검사 | 수분 7600% | `out_of_physical_range` |
| 단위 오류 검사 | kcal/100g를 kcal/kg처럼 사용 | `unit_or_scale_conflict` |
| 소수점 누락 후보 | 칼슘 30%, 인 24% | `decimal_shift_candidate` |
| 성분 합계 검사 | 단백질+지방+수분+회분+섬유가 과도 | `composition_sum_conflict` |
| 출처 내 복수값 충돌 | kJ와 kcal 환산값 불일치 | `cross_field_conflict` |
| 상품 형태 불일치 | 습식인데 수분 0%, 건식인데 수분 95% | `food_type_nutrition_conflict` |

### 8.2 참고 범위

아래는 자동 삭제 기준이 아니라 검토 플래그 기준이다. 동결건조·보조식·처방식은 일반 사료와 다른 값이 가능하다.

| 항목 | 검토 권장 범위 | 추가 조건 |
| --- | --- | --- |
| 조단백 | 0–70% | 동결건조는 상단 예외 가능 |
| 조지방 | 0–50% | 50% 초과 시 단위·소수점 확인 |
| 조섬유 | 0–20% | 20% 초과 시 원문 확인 |
| 조회분 | 0–20% | 20% 초과 시 원문 확인 |
| 수분 | 0–95% | 95% 초과 시 액상·수프 여부 확인 |
| 칼슘 | 0–5% | 5% 초과 시 단위·소수점 확인 |
| 인 | 0–3% | 3% 초과 시 단위·소수점 확인 |
| 나트륨 | 0–2% | 2% 초과 시 단위 확인 |
| 열량 | 0–10,000 kcal/kg | 10,000 초과 시 100g·kJ·소수점 변환 검증 |

## 9. Boolean·결측값 규칙

| 유형 | 허용값 | 금지 사항 |
| --- | --- | --- |
| Boolean | `true`, `false`, `NULL` | 정보가 없는데 `false`를 넣지 않음 |
| 숫자 | 숫자, `NULL` | 결측을 0으로 변환하지 않음 |
| 분류 | 표준 코드, 원문, `NULL` | `Unknown`을 실제 분류값처럼 사용하지 않음 |
| 복수값 | 별도 행 또는 배열 | 구분자 문자열만 남기고 의미를 잃지 않음 |

`is_treat`, `prescription`, `is_dup`, `has_nutrition`은 특히 `unknown` 상태가 필요하다. `is_dup`은 원본 사이트의 중복 플래그인지, 이번 통합 과정의 중복 판정인지 분리해 저장한다.

## 10. 실행 순서

1. 입력 파일을 매니페스트에 등록하고 행 수·열 수·해시를 검증한다.
2. 각 원본 행을 `raw_record`에 무변형으로 적재한다.
3. 출처별 매핑을 적용해 `product_source`, `nutrition_fact`, `product_variant`, `product_offer`, `product_tag`를 만든다.
4. 범위·단위·파싱 검사를 적용해 플래그를 기록한다.
5. 범위 판정으로 `merge_audit`에 포함·제외·보류 사유를 기록한다.
6. 중복 후보를 만든다. 자동 삭제하지 않는다.
7. 필요한 경우에만 검증된 후보에 canonical ID를 부여한다.
8. `included`이고 치명적 품질 플래그가 없는 행을 기준으로 `dog_food_analysis_view`를 생성한다.
9. 원본 대비 행 수·식별자·주요 수치의 검증 보고서를 생성한다.

## 11. 필수 검증 항목

통합 실행은 아래 조건이 모두 충족될 때만 완료로 판정한다.

| 검증 | 통과 기준 |
| --- | --- |
| 행 수 조정 | 파일별 `included + out_of_scope + review_required + incomplete`가 원본 행 수와 같음 |
| 원본 추적 | 모든 통합 행에 `source_file`, `source_row_number`, `source_row_id` 존재 |
| 식별자 | `source + source_product_id` 또는 URL 중 하나 존재 |
| 중복 | 삭제 수가 0이거나, 삭제 대신 대표행·원본행 연결표가 존재 |
| 파싱 | 숫자로 바뀐 값에 `raw_value`, 단위, 파싱 상태 존재 |
| 단위 | kcal/kg, kcal/100g, kJ/100g, %, mg/kg를 혼합하지 않음 |
| 범위 | 검토 범위 밖 값은 누락이 아니라 품질 플래그로 집계됨 |
| 통화 | 서로 다른 통화의 가격을 환율 정보 없이 합산·평균하지 않음 |
| 분석 뷰 | 32개 핵심 열은 파생 결과이며, 원문 보존 테이블과 연결 가능 |

## 12. 이번 데이터에 대한 즉시 조치 목록

1. 현재 `dog_food_merged.csv`를 최종 정제본이 아니라 분석용 임시 뷰로 지정한다.
2. 명견에픽에서 제거된 33행을 복원하고 `conflict_candidate`로 표시한다.
3. Open Pet Food Facts의 15,136행 전체에 범위 판정과 사유를 다시 기록한다.
4. 다나와 `단위가격` 2,416건을 원문 보존 후 kg 단가로 환산한다.
5. 다나와 리뷰 `999+` 96건에 하한 표기를 복원한다.
6. kcal/kg, 칼슘·인, 조섬유·조회분의 이상값을 삭제하지 말고 재파싱·단위 검증 대상으로 표시한다.
7. `source_file`을 실제 입력 파일명으로 정정하고 파일 해시를 기록한다.
