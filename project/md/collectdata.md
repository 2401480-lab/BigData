# 반려견 사료 데이터 수집·활용성 점검

작성일: 2026-11-02  
대상: `project/data`의 7개 CSV와 `md/data.md`의 데이터 사전

## 결론

손경빈 담당 데이터는 **정제 후 활용 가능**하다. 특히 `dog_food_nutrition_disclosed_lifeofepic_dry_2026-10-28.csv`(명견에픽)는 건식 사료의 조단백·조지방 비교 및 추천 후보 생성에 바로 쓸 수 있다. 다만 제품명 기준 중복, 브랜드 결측을 먼저 처리해야 한다. `dogpre_dog_food_nutrition_2026-10-28_idx1150-1269.csv`(강아지대통령)는 영양 컬럼이 더 풍부하지만 37건뿐인 페이지 구간 데이터이므로, 전체 크롤링을 완료하기 전에는 보조·검증 데이터로만 사용한다.

의료·처방·건강 효과를 단정하는 용도에는 어느 데이터도 단독으로 적합하지 않다. 보증성분은 다수가 “이상/이하” 경계값이며, 실제 성분 측정값이나 급여 결과가 아니기 때문이다.

## 분석 방법과 판정 기준

- CSV의 행 수·열 수·결측·정확한 행 중복·식별자 중복을 점검했다.
- 손경빈 영양 수치는 원문에서 첫 숫자를 추출해 요약했다. `이상`은 최소 보증치, `이하`는 최대 보증치이므로 평균·중앙값은 **표기 경계값의 요약**이지 실제 함량 평균이 아니다.
- “사용 가능”은 최소한 제품명 또는 URL, 분석 목적에 맞는 핵심 속성, 출처 URL을 보유한 경우로 정의했다. “빅데이터 활용 가능”은 규모뿐 아니라 표준화·갱신·결합·품질 관리 가능성까지 포함해 판단했다.

## 손경빈 데이터 통계

### 1. 명견에픽 — 건식 사료 영양 공개 데이터

파일: `data/dog_food_nutrition_disclosed_lifeofepic_dry_2026-10-28.csv`

| 항목 | 결과 |
| --- | ---: |
| 행 / 열 | 799 / 12 |
| 정확히 같은 행 | 0 |
| 제품명 고유값 | 766 |
| 제품명 중복 행 | 34 |
| 원본 URL 고유값 | 799 |
| 브랜드 고유값 | 131 |
| 브랜드 결측 | 147건 (18.4%) |
| 그 외 핵심 필드 결측 | 0건 (`source_site`, 제품명, 형태, 단백질·지방, 원료, URL) |
| 목록 페이지 수 | 40 |

| 지표(%) | 유효 건수 | 평균 | 표준편차 | Q1 | 중앙값 | Q3 | 범위 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 조단백질 | 799 | 25.12 | 8.72 | 22.0 | 25.0 | 28.0 | 0.9–57.0 |
| 조지방 | 799 | 12.93 | 6.59 | 9.0 | 12.0 | 16.0 | 0.1–42.0 |

판정: **조건부 사용 가능 (A-)**. URL은 모두 고유하므로 URL을 기본 키로 보존하고, 제품명·브랜드·영양표기 조합으로 중복 후보를 검토한다. 동일 제품 URL이 페이지 파라미터만 달리 반복된 사례가 있어 제품명만으로 집계하면 과대 계상될 수 있다. 브랜드 결측은 URL 또는 제품명에서 보완 가능한지 재수집한다. 0.9% 단백질·0.1% 지방 같은 극단값은 간식/보조식 혼입 또는 입력 오류 가능성을 별도 플래그로 검토한다.

### 2. 강아지대통령 — 건식 주식사료 영양 데이터

파일: `data/dogpre_dog_food_nutrition_2026-10-28_idx1150-1269.csv`

| 항목 | 결과 |
| --- | ---: |
| 행 / 열 | 37 / 15 |
| 정확히 같은 행 / 제품명·URL 중복 | 0 / 0 |
| 영양·원료·URL 결측 | 0건 |
| 수분 결측 | 1건 (2.7%) |
| 수집일 | 2026-10-28 (전 행 동일) |
| 범위 | kg 단위 건식 주식사료; 간식·영양제·껌 제외 |

| 지표(%) | 유효 건수 | 평균 | 표준편차 | 중앙값 | 범위 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 조단백질 | 37 | 28.09 | 5.89 | 25.0 | 22.0–42.0 |
| 조지방 | 37 | 14.31 | 2.93 | 15.0 | 7.0–20.0 |
| 조섬유 | 37 | 4.71 | 1.90 | 4.0 | 2.3–8.0 |
| 조회분 | 37 | 8.05 | 1.41 | 8.0 | 5.6–10.0 |
| 칼슘 | 37 | 0.93 | 0.28 | 0.90 | 0.40–1.40 |
| 인 | 37 | 1.01 | 1.61 | 0.70 | 0.40–10.50 |
| 수분 | 36 | 10.40 | 0.88 | 10.0 | 9.0–12.0 |

판정: **조건부 사용 가능 (B, 보조 데이터)**. `인`의 평균과 표준편차는 한 건의 `10.5% 이상` 때문에 왜곡되어 있다. 해당 행은 제품 URL `https://dogpre.com/product/78925`이며 원문도 10.5%로 기록되어 있다. 조단백 28%, 조지방 11%, 칼슘 0.54%와 비교하면 1.05%의 소수점 누락 또는 원문 오기 가능성이 높지만, 근거 없이 수정하면 안 된다. 원본 페이지 확인 전까지 `phosphorus_pct >= 2`를 이상치 플래그로 제외한 분석을 병행한다. 또한 수치 필드는 `이상/이하` 문자를 포함한 문자열이므로 숫자값과 `bound_type`(min/max)을 분리해 저장한다.

## 프로젝트 전체 데이터의 활용 가능성

| 데이터셋 | 규모 (행×열) | 즉시 활용도 | 빅데이터 관점의 역할 | 주요 제약과 조치 |
| --- | ---: | --- | --- | --- |
| `danawa_dogfood.csv` | 2,470×13 | 조건부 가능 | 국내 가격·판매몰·평점·리뷰 수의 시계열 가격 모니터링 후보 | 판매몰수·평점·리뷰수 결측이 각각 37.3%, 인기순위 98.8% 결측. 수집일이 없어 추세 분석 불가 → 수집시각과 가격 스냅샷을 누적 |
| `dog_food_nutrition_disclosed_lifeofepic_dry_2026-10-28.csv` | 799×12 | 가능 | 국내 영양 기준 비교, 콘텐츠·추천 피처 | 제품명 중복 및 브랜드 18.4% 결측 → URL 중심 정규화 |
| `dogpre_dog_food_nutrition_2026-10-28_idx1150-1269.csv` | 37×15 | 보조로 가능 | 국내 건식 주식 영양 데이터의 정밀 검증·보강 | 일부 인덱스 구간, 경계값 문자열, 인 이상치 → 전체 수집 및 원문 검증 |
| `zooplus_dog_food.csv` | 3,551×59 | 조건부 가능 | 최대 규모의 상품·가격·리뷰·성분 다변량 분석, 해외 카탈로그 확장 | 희소 영양 열 다수, 사이트·통화 혼재, 중복 판정 열 활용 필요 → 핵심 공통 스키마만 우선 사용 |
| `petsathome_dog_food.csv` | 1,595×66 | 조건부 가능 | 영국 상품·가격·평점·원료 결합 분석 | 100% 빈 열 1개와 매우 희소한 미량 성분 열 → 빈 열 제거·성분 커버리지 기준 적용 |
| `purina_uk_dog_food.csv` | 119×51 | 보조로 가능 | 브랜드 단위 벤치마크·라벨 검증 | 규모가 작고 다수 미량성분 열이 97% 이상 결측 → 브랜드 분석에 한정 |
| `en.openpetfoodfacts.org.products.csv` | 약 15,136×210 (탭 구분) | 조건부 가능 | 가장 큰 외부 확장 풀: 성분·영양·국가·이미지 메타데이터 결합 | 71개 열이 전부 비어 있고 제품명 결측 약 19.7%. 탭 구분으로 읽어야 하며 스키마 축소·반려견 필터·라이선스 확인 필요 |

`en.openpetfoodfacts.org.products.csv`는 확장성은 크지만, 현재는 15,000여 행으로 전통적인 의미의 빅데이터(분산 처리 필요 수준)는 아니다. 이 프로젝트 전체도 약 2.4만 행 수준이라 단일 머신의 관계형 DB 또는 Parquet 기반 분석으로 충분하다. 여기서 “빅데이터 관점”의 핵심은 **다출처·다형식·반복 수집을 통한 누적 데이터 제품화**다.

## 권장 활용 데이터와 우선순위

1. **1차 분석용:** 명견에픽 + 강아지대통령(이상치 플래그 적용) + 다나와. 국내 건식 사료의 영양·가격·리뷰 비교에 적합하다.
2. **확장 분석용:** Zooplus, Pets at Home. 공통 필드(브랜드, 제품명, 사료형태, 조단백, 조지방, 가격/kg, 통화, 평점, 리뷰수, 원료, URL)로 표준화하면 국가·유통채널별 비교가 가능하다.
3. **보조·검증용:** Purina UK와 Open Pet Food Facts. 전자는 브랜드 라벨 교차검증, 후자는 후보 상품·영양 속성 보강에 사용한다.
4. **현재 제외:** 전부 비어 있는 열, 95% 이상 결측인 미량성분 열, 수집일 없는 가격의 시계열 해석, 검증 전 `phosphorus_pct=10.5` 값.

## 빅데이터화·품질관리 제안

### 공통 스키마 — 기존안의 한계와 수정 원칙

기존안은 추천·가격 비교에 필요한 **핵심 요약 컬럼만** 제시한 것이어서, `data.md`에 있는 원본 속성(상세 영양소, 옵션, 카테고리 경로, 태그, 원문 라벨, 수집 범위)을 공통 스키마에서 누락시켰다. 그대로 구현하면 원본을 다시 확인할 때 정보 손실이 생기므로 적절하지 않다.

따라서 하나의 지나치게 넓은 상품 테이블이 아니라, 아래 6개 논리 테이블로 수정한다. 모든 출처에 없는 속성을 억지로 결측 컬럼으로 만들지 않고, 반복되는 성분·옵션·태그는 별도 행으로 저장한다. 원본 CSV와 원본 컬럼은 변경하지 않는다.

#### A. `product` — 상품 기본 정보

출처별 컬럼명은 아래 표준 컬럼으로 변환한다.

| 표준 컬럼명 | 의미 | 값/작성 규칙 |
| --- | --- | --- |
| `source` | 데이터를 수집한 사이트 또는 제공기관 | 예: `danawa`, `lifeofepic`, `dogpre`, `zooplus` |
| `collected_at` | 해당 레코드를 수집하거나 확인한 시각 | `YYYY-MM-DD` 또는 UTC 시각. 가격·평점은 반드시 수집시각을 기록 |
| `source_product_id` | 원본 사이트가 부여한 상품 식별자 | 사이트 내에서만 고유한 ID. 없으면 URL에서 안정적으로 추출한 값 사용 |
| `canonical_product_id` | 서로 다른 사이트의 동일 상품을 묶는 내부 표준 ID | 원본 ID를 덮어쓰지 않으며, 브랜드·제품명·용량·영양값 검토 후 부여 |
| `source_type` | 수집처의 성격 | 예: 가격비교, 판매몰, 사료정보 DB. `data.md`의 `source_type` 보존 |
| `brand` | 제조사 또는 사료 브랜드명 | 원문 표기를 보존하되 별도 정규화 테이블로 별칭을 통합 |
| `product_name` | 사이트에 표시된 상품명 | 원문 상품명. 비교용 정규화 이름은 별도 필드 또는 매핑 테이블에서 관리 |
| `country` | 판매·수집 시장 국가 또는 지역 | 예: `KR`, `UK`, `IE`; 제조국과 혼동하지 않음 |
| `category` | 사이트 분류를 정규화한 대표 상품군 | 예: 건식, 습식. 원본 카테고리 경로와 별도로 관리 |
| `food_type` | 사료의 형태·용도 분류 | 예: 건식, 습식, 간식, 처방식. 분석 대상이 주식 건식인지 판별하는 데 사용 |
| `food_format` | 물성·제조 형태 | 예: 키블, 캔, 파우치, 동결건조, 에어드라이, 소프트. 원본 `사료형태`·`food_format` 매핑 |
| `packaging_type` | 포장 형태 | 예: Bag, Tin, Pouch. 원본 `포장` 매핑 |
| `life_stage` | 권장 급여 생애주기 | 예: 퍼피, 어덜트, 시니어, 전연령 |
| `breed_size` | 권장 견종 크기 | 예: Small, Medium, Large. 복수값은 별도 `product_tag` 행으로 분해 가능 |
| `breed` | 특정 견종 대상 여부 | 예: French Bulldog. 원본 `견종` 매핑 |
| `url` | 상품 상세 페이지 URL | 원본 근거 및 재수집용 주소. URL 변경 가능성을 고려해 수집일과 함께 보관 |
| `quality_flags` | 데이터 품질 확인 결과 | 예: `duplicate_candidate`, `brand_missing`, `nutrition_outlier`, `price_missing`을 복수 기록 |

#### B. `nutrition_fact` — 모든 영양성분 (기존의 넓은 영양 컬럼 대체)

`data.md`에는 조단백·조지방뿐 아니라 조섬유, 조회분, 수분, 칼슘, 인, 나트륨, 타우린, 오메가3·6, 마그네슘, 칼륨, 탄수화물, 전분, 카르니틴, 염소, 글루코사민, 열량, 건물 기준 성분이 정의되어 있다. 이를 상품 테이블의 일부 컬럼으로만 남기면 나머지 성분을 잃으므로, 아래와 같이 성분 1개당 1행으로 저장한다.

| 표준 컬럼명 | 의미 | 값/작성 규칙 |
| --- | --- | --- |
| `nutrition_fact_id` | 영양성분 레코드 식별자 | 내부 키 |
| `canonical_product_id` / `source_product_id` | 해당 성분이 속한 상품 | 상품 기본 정보와 연결하는 키 |
| `variant_name` | 성분표가 적용되는 맛·용량·옵션 | 원본 `constituents_variant`, `sizes`와 연결; 공통 성분이면 빈값 가능 |
| `nutrient_name` | 정규화한 영양소명 | 예: `crude_protein`, `crude_fat`, `calcium`, `taurine`, `energy` |
| `value` | 수치 값 | 숫자만 저장. 결측은 0이 아닌 NULL |
| `unit` | 수치 단위 | `%`, `kcal/kg`, `mg/kg`, `IU/kg` 등 원문 기준 단위 |
| `bound_type` | 수치의 의미 | `min`(이상), `max`(이하), `exact`, `unknown` |
| `basis` | 영양성분 산출 기준 | `as_fed`, `dry_matter`, `per_kg`, `per_100g`, `unknown`. `dm_` 컬럼은 `dry_matter` |
| `raw_label` | 사이트에 기재된 원문 표기 | 예: `조단백 25% 이상`; 변환 검증과 재파싱에 사용 |
| `source_column` | 원본 CSV의 컬럼명 | 예: `조단백`, `crude_protein_pct`, `dm_조단백` |

분석 편의상 `protein_min_pct`, `fat_min_pct`, `fiber_max_pct`, `ash_max_pct`, `moisture_max_pct`, `calcium_min_pct`, `phosphorus_min_pct`, `kcal_per_kg`는 이 테이블에서 만든 **파생 뷰**로 제공할 수 있다. 이들은 원본의 유일한 저장 위치가 아니다.

#### C. `product_offer` — 가격·판매·평가 스냅샷

| 표준 컬럼명 | 의미 | `data.md` 및 실제 데이터와의 대응 |
| --- | --- | --- |
| `offer_id` | 가격·평가 스냅샷 식별자 | 내부 키 |
| `source_product_id` | 판매 정보가 속한 원본 상품 | `product`와 연결 |
| `variant_name` | 가격이 적용되는 용량·옵션 | `sizes`, 변형 상품명 |
| `price_min`, `price_max` | 옵션 중 최저·최고 판매가 | Zooplus/Pets at Home의 동명 컬럼 |
| `price_per_kg_min` | kg당 최저 가격 | 통화/kg 기준. 비교에는 우선 사용 |
| `currency` | 가격 통화 | ISO 4217 (`KRW`, `GBP`, `EUR`) |
| `seller_count` | 판매몰 수 | 다나와 `판매몰수` |
| `rating` | 사이트 평점 | 만점 체계는 `rating_scale`에 함께 기록 |
| `rating_scale` | 평점의 최대 점수 | 원문에 없으면 NULL; 사이트 기본값을 임의로 가정하지 않음 |
| `review_count` | 리뷰 수 | 원본 `리뷰수` 또는 `review_count` |
| `popularity_rank` | 수집 당시 인기순위 | 다나와 `인기순위`; 대부분 결측일 수 있음 |
| `listed_month` | 상품 등록월 | 다나와 `등록월`; 날짜 형식 표준화 필요 |
| `observed_at` | 가격·평점 관측 시각 | `collected_at`과 분리 가능. 시계열 분석의 필수값 |

#### D. `product_content` — 원료·설명·분류 원문

| 표준 컬럼명 | 의미 | 대응 원본 속성 |
| --- | --- | --- |
| `ingredients_raw` | 원재료·구성 전체 원문 | `ingredients_full`, `ingredients`, `main_ingredients` |
| `additives_raw` | 첨가물 원문 | `additives` |
| `constituents_raw` | 분석성분표 원문 또는 JSON | `constituents_raw`, `nutrition_label_raw` |
| `description` | 상품 상세 설명 | `description` |
| `features` | 판매 문구·상품 특장점 | `features`, `highlights`, `product_benefits` |
| `breadcrumb` | 사이트 탐색·카테고리 경로 | `breadcrumb`, `category_groups` |
| `main_protein` | 주 단백질원 또는 맛 | `main_protein`, `맛`, `주 단백질원` |
| `not_suitable_for` | 급여 비권장 대상 | `not_suitable_for` |
| `nutrition_label_raw` | 보증성분 라벨 전체 원문 | 강아지대통령 `nutrition_label_raw` |

#### E. `product_variant` — 용량·바코드·변형 상품

| 표준 컬럼명 | 의미 | 대응 원본 속성 |
| --- | --- | --- |
| `variant_id` | 옵션/변형 상품 식별자 | 내부 키 |
| `source_product_id` | 상위 상품 | `product`와 연결 |
| `variant_name` | 옵션명 또는 용량 표기 | `sizes`, `constituents_variant` |
| `quantity_raw` | 판매 단위 원문 | Open Pet Food Facts `quantity`, `product_quantity` 등 원문 보존 |
| `weight_value`, `weight_unit` | 파싱된 중량과 단위 | 예: `12`, `kg`; 원문 표기도 보존 |
| `serving_size_raw`, `serving_quantity` | 1회 제공량 원문과 파싱 수치 | `serving_size`, `serving_quantity`; 상품 중량과 구분 |
| `gtin` | GTIN·바코드 | `gtin`; 복수값은 행으로 분리 |
| `n_variants` | 사이트가 제공한 변형 수 | `n_variants` |
| `n_constituent_options` | 성분표 옵션 수 | `n_constituent_options` |

#### F. `product_alias`, `product_identifier` — 상품명·식별코드 확장

| 표준 컬럼명 | 의미 | 대응 원본 속성 |
| --- | --- | --- |
| `product_alias.alias_type` | 상품명 변형의 종류 | `display_name`, `abbreviated_name`, `generic_name` |
| `product_alias.alias_text` | 해당 이름 원문 | `product_name`, `abbreviated_product_name`, `generic_name`, 판매몰 상품명 |
| `product_identifier.id_type` | GTIN 외 식별코드 종류 | `source_code`, `pcode`, `emb_code`, `packaging_code` |
| `product_identifier.id_value` | 식별코드 원문 | Open Pet Food Facts `code`, `emb_codes`, 다나와 `pcode` 등 |
| `product_identifier.geo_hint` | 코드에 연결된 지리 정보 | `first_packaging_code_geo`; 원문 그대로 보존 |

#### G. `product_tag`, `product_attribute`, `source_record` — 분류·확장 속성·원문 보존

| 표준 컬럼명 | 의미 | 값/작성 규칙 |
| --- | --- | --- |
| `product_tag.product_id` | 태그가 붙는 상품 | 상품과 연결 |
| `product_tag.tag_type` | 태그의 분류 | `pet_type`, `diet`, `health_condition`, `certification`, `allergen_free`, `processing_method`, `texture`, `packaging`, `ingredient_claim` 등 |
| `product_tag.tag_value` | 태그 값 | 예: `강아지 전용`, `그레인프리`, `가수분해`, `신장 관리`, `GMO Free`, `퍼피` |
| `product_tag.source_column` | 태그를 만든 원본 컬럼 | `기능`, `특수식단`, `free_from`, `recipe_type`, `health_condition`, `인증`, `알레르기 예방` 등 |
| `product_attribute.attribute_name` | 태그가 아닌 출처 확장 속성의 이름 | 예: `nutriscore_grade`, `nova_group`, `completeness`, `unique_scans_n` |
| `product_attribute.value_text` | 문자열·코드·불리언 값 | 예: 등급, 소유자, 상태, 원산지 텍스트. 원문 문자열 보존 |
| `product_attribute.value_number` | 수치형 확장 속성 | 예: 환경점수, 완성도, 스캔 수, 탄소발자국. 단위는 `unit`에 기록 |
| `product_attribute.unit` | 확장 수치의 단위 | 예: `g`, `kg`, `%`, `score`, `unknown` |
| `product_attribute.language` | 값의 언어 또는 로캘 | 다국어 `*_en`, 국가별 라벨·카테고리의 구분에 사용 |
| `product_attribute.source_column` | 값을 만든 원본 열 | 재매핑·검증을 위한 원본 열 이름 |
| `source_record.source_file` | 원본 파일명 | 어떤 CSV에서 왔는지 추적 |
| `source_record.source_row_number` | 원본 행 번호 | 재현 가능한 검증·오류 수정용 |
| `source_record.raw_payload` | 원본 행 전체 | JSON 등 변경 없는 형태로 보존 |
| `source_record.list_page` | 수집한 목록 페이지 | 명견에픽 `list_page` 및 수집 범위 검증용 |
| `source_record.collection_scope` | 수집·선별 기준 | 강아지대통령 `collection_scope` 보존 |

`data.md`의 최민서 태그(강아지 전용, 건식·습식, 퍼피·어덜트·시니어, 입자 크기, 가수분해, 그레인프리, GMO/보존제/색소 무첨가, 처방식, 건강 기능 등)는 컬럼을 계속 늘리는 대신 `product_tag`에 저장한다. 복수값을 `|`로 보관한 생애주기·견종크기·맛·GTIN도 동일하게 한 값당 한 행으로 분해한다. 이렇게 해야 다중 조건 검색과 태그별 집계가 가능하며 값이 사라지지 않는다.

#### H. `product_geography`, `product_allergen`, `product_image` — Open Pet Food Facts 확장 정보

Open Pet Food Facts에는 다른 CSV에 없는 대규모 메타데이터가 있다. 이것을 단순 `raw_payload`에만 묻어두면 국가별·알레르겐별·이미지 보유 여부 분석이 불가능하므로 아래 테이블을 추가한다.

| 표준 컬럼명 | 의미 | 대응 원본 속성 |
| --- | --- | --- |
| `product_geography.geo_type` | 장소 정보의 종류 | `origins`, `manufacturing_places`, `purchase_places`, `stores`, `countries`, `cities` |
| `product_geography.geo_name` | 원문 장소·국가명 | `*_en`, 태그, 원문명을 함께 보존 |
| `product_allergen.kind` | 알레르겐 구분 | `allergen` 또는 `trace` |
| `product_allergen.name` | 알레르겐·혼입 가능 물질 | `allergens`, `traces`, `*_tags`, `*_en` |
| `product_image.image_type` | 이미지 종류 | `front`, `ingredients`, `nutrition` |
| `product_image.image_url` | 원본 이미지 URL | 일반·small URL 모두 행으로 보존 |
| `product_image.size_type` | 이미지 크기 구분 | `full`, `small` |

#### I. `source_event` — 생성·수정·검증 이력

| 표준 컬럼명 | 의미 | 대응 원본 속성 |
| --- | --- | --- |
| `source_event.event_type` | 원본 이력 이벤트 | `created`, `last_modified`, `last_updated`, `last_image` |
| `source_event.event_at` | 이벤트 시각 | `*_datetime` 우선, 없으면 Unix timestamp `*_t` 변환 |
| `source_event.actor` | 이벤트 수행자 | `creator`, `last_modified_by`, `owner` |
| `source_event.quality_state` | 출처가 제공한 품질·완성도 상태 | `states`, `data_quality_errors_tags`, `completeness`, `no_nutrition_data` |

#### J. `product_measurement` — 영양소 외 수치 측정값

`nutrition_fact`는 영양성분 전용이다. Open Pet Food Facts의 `ph`, `glycemic-index`, `water-hardness`, `carbon-footprint`, `cocoa`, `fruits-vegetables-legumes`, `collagen-meat-protein-ratio` 같은 값까지 영양소로 오해해 넣지 않도록 별도 테이블에 저장한다.

| 표준 컬럼명 | 의미 | 작성 규칙 |
| --- | --- | --- |
| `measurement_name` | 측정값 이름 | 원본 열명에서 정규화. 예: `ph`, `carbon_footprint`, `glycemic_index` |
| `value` | 측정 수치 | 숫자만 저장 |
| `unit` | 측정 단위 | 원본 메타데이터 또는 명세 기준. 불명확하면 `unknown` |
| `basis` | 산출 기준 | 예: `per_100g`, `product`, `unknown` |
| `source_column` | 원본 열명 | 예: `ph_100g`, `carbon-footprint_100g` |

#### K. `source_taxonomy` — 외부 분류체계와 점수

| 표준 컬럼명 | 의미 | 대응 원본 속성 |
| --- | --- | --- |
| `taxonomy_type` | 분류체계 종류 | `category`, `label`, `packaging`, `food_group`, `pnns_group`, `nutrient_level`, `popularity` |
| `taxonomy_value` | 원문 분류 값 | `categories`, `labels`, `packaging_tags`, `food_groups`, `pnns_groups_1/2`, `popularity_tags` 등 |
| `score_type` | 상품 점수·등급 종류 | `nutriscore`, `nova`, `environmental_score` |
| `score_value` | 점수 또는 등급 | `nutriscore_score/grade`, `nova_group`, `environmental_score_score/grade` |

#### 전체 헤더 대조 결과

실제 CSV의 물리적 헤더는 426개이고, 중복 헤더명을 합치면 326개다. 이번 수정 전에는 Open Pet Food Facts의 비영양 메타데이터(생성·수정 이력, 이미지, 장소·유통, 알레르겐, 별칭·식별코드, 품질·환경·분류 점수)가 독립 테이블에 매핑되지 않았다. 이번에 F–K를 추가해 분석 가능한 형태로 매핑했다.

그래도 출처별 신규 열이나 해석이 불명확한 열이 생길 수 있으므로, **모든 원본 열은** `source_record.raw_payload`에 열 이름과 값을 그대로 기록한다. 이 필드가 426개 물리 헤더 전체의 최종 보존 장치다. 단, Open Pet Food Facts 파일은 쉼표 CSV가 아니라 탭 구분 형식이므로 `TSV`로 읽어야 열이 합쳐져 손실되는 일을 막을 수 있다.

#### 매핑 시 반드시 남길 원본 속성

다음 속성은 활용 빈도가 낮거나 출처 특화라 하더라도 삭제하지 않고 `source_record.raw_payload` 및 위 확장 테이블에 보존한다: `site`, `pcode`, `page`, `product_range`, `page_type`, `pet`, `recipe_type`, `free_from`, `food_texture`, `search_keywords`, `calorie_raw`, `multi_value`, `is_treat`, `hypoallergenic_flag`, `is_dup`, `영양정보_있음`, 다나와 `상품상세정보`와 `단위가격`. 이 원칙이 있어야 새 분석 요구가 생겨도 원본 CSV를 다시 수집하지 않고 재매핑할 수 있다.

### 처리 순서

1. URL·사이트별 상품 ID로 원본을 보존하고, 제품명·브랜드·용량·영양값을 이용해 `canonical_product_id` 후보를 만든다.
2. `% 이상/이하`를 숫자와 상·하한 의미로 분리한다. 결측은 0으로 바꾸지 않는다.
3. 유효 범위 검사(예: 인 0–2%, 수분 0–100%)와 중복 후보 검토를 `quality_flags`에 기록한다.
4. 가격·평점·리뷰에는 `collected_at`을 필수화하고, 통화 환산에는 환율 기준일을 별도 저장한다.
5. 원본 CSV는 변경하지 않고, 정제본은 Parquet와 분석용 테이블로 버전·수집일 파티션을 나눈다.

### 분석으로 만들 수 있는 가치

- 가격/kg, 영양 범위, 원료·알레르기 키워드, 평점·리뷰 수를 함께 사용하는 사료 탐색·비교 서비스
- 국내/해외 유통채널별 동일·유사 제품의 가격 및 영양 포지셔닝 분석
- 수집 시계열이 충분히 쌓인 뒤의 가격 변동·품절·신제품 탐지
- 원료 텍스트 기반 성분 태그 추출과 영양 프로필 군집화

이 분석은 상품 정보의 비교·탐색을 위한 것이며, 개별 반려견의 건강 상태를 위한 급여 처방은 수의사 판단과 별도 영양 기준이 필요하다.
