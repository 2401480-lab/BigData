# Gold 통합 스키마

작성일: 2026-11-02  
대상: `data/model_datasets/gold/`의 출처별 원본 4개  
생성 스크립트: `scripts/build_gold_unified.py`

## 1. 개요

다나와·Zooplus·Pets at Home·PetSmart 원본은 컬럼명 언어(한글/영어/혼용), 복수값 구분자, 불리언 표기, 단위가 모두 다르다. 이 문서는 네 파일을 **한글 속성명 77개의 단일 스키마**로 합친 규칙과, 그 과정에서 수행한 단위환산·보정을 설명한다.

| 산출물 | 경로 | 내용 |
| --- | --- | --- |
| 통합 데이터 | `data/model_datasets/unified/gold_unified.csv` | 8,454행 × 77열, 한 행 = 상품 1개 |
| 속성 사전 | `data/model_datasets/unified/schema_dictionary.csv` | 속성별 단위·설명·병합유형·출처별 원본 컬럼·환산 규칙·채움률 |
| 환산 로그 | `data/model_datasets/unified/unit_conversion_log.csv` | 값이 바뀌거나 NULL 처리된 2,025건의 원값·변환값·규칙 |

| 출처 | 입력 파일 | 행 수 |
| --- | --- | ---: |
| `zooplus` | `zooplus_dog_food.csv` | 3,551 |
| `danawa` | `danawa_.csv` (+ `Source/danawa_dogfood.csv`의 상품URL) | 2,470 |
| `petsathome` | `petsathome_dog_food.csv` | 1,595 |
| `petsmart` | `petsmart_dryfood_product.csv` (+ `unlabeled/petsmart_dryfood_sku.csv`의 SKU 가격·용량·URL) | 838 |

원본 파일은 수정하지 않는다. 통합 키는 `출처 + 상품ID`다.

## 2. 명명 규칙

| 규칙 | 예 |
| --- | --- |
| 속성명은 한글, 공백·`/` 없이 `_`로 연결 | `주 단백질원` → `주단백질원`, `단위가격_원/kg` → `kg당최저가` |
| 수치 속성은 이름 끝에 단위 | `조단백_pct`, `열량_kcal_kg`, `글루코사민_mg_kg`, `유산균_CFU_g` |
| 건물 기준은 `건물기준_` 접두어 | `dm_조단백`, `건물기준_조단백` → `건물기준_조단백_pct` |
| 불리언은 `~여부`, 값은 True/False/NULL | `처방식`, `is_dup`, `영양정보_있음` → `처방식여부`, `중복여부`, `영양정보보유여부` |
| 복수값 구분자는 `|` | 다나와 `소화·장건강, 피부·모질개선` → `소화·장건강|피부·모질개선` |
| 표준화한 범주에는 `_원문` 속성을 함께 둠 | `사료형태` + `사료형태_원문` |

## 3. 병합 가능했던 속성

### 3.1 전 출처 병합 (31개)

네 출처 모두 대응 컬럼이 있어 하나로 합쳤다. 괄호 안은 원본 컬럼이다.

| 속성 | 다나와 | Zooplus | Pets at Home | PetSmart |
| --- | --- | --- | --- | --- |
| `상품ID` | `pcode` | `product_id` | `product_id` | `web_style_id` |
| `상품명` | `상품명` | `name` | `name` | `name` |
| `상품URL` | 원본 `상품URL` | `url` | `url` | SKU 파일 `url` |
| `사료형태` | `제형` | `category`+`사료형태` | `category`+`food_format` | `food_type` |
| `생애주기` | `나이` | `생애주기` | `생애주기` | `life_stage` |
| `기능_원문` | `기능` | `기능` | `기능` | `hc_final` |
| `라벨출처` | 사이트분류 | 사이트분류 | 사이트분류 | `hc_source` |
| `조단백_pct` 외 6종 | `조단백` 등 | `조단백` 등 | `조단백` 등 | `crude_protein` 등 (회분은 `ash`) |
| `건물기준_*_pct` 7종 | 재계산 | 재계산 | 재계산 | 재계산 |
| `통화` | KRW (고정) | `currency` | `currency` | USD (고정) |
| `최저가` | `최저가` | `price_min` | `price_min` | `price_min` |
| `kg당최저가` | `단위가격_원/kg` | `price_per_kg_min` | `price_per_kg_min` | SKU로 계산 |
| `중량_kg_최소/최대` | `중량_kg` | `sizes` 파싱 | `sizes` 파싱 | `sizes` 파싱 |
| `평점`, `리뷰수` | `평점`, `리뷰수` | `rating`, `review_count` | 같음 | 같음 |

이 외에 `사료형태_원문`, `생애주기_원문`, `품질플래그`가 전 출처 속성이다.

### 3.2 일부 출처 병합 (25개)

2~3개 출처에만 있는 속성이다. 없는 출처는 NULL이며, **NULL은 '해당 없음'이 아니라 '정보 없음'**이다.

| 속성 | 있는 출처 | 비고 |
| --- | --- | --- |
| `브랜드` | Zooplus, Pets at Home, PetSmart | 다나와는 `제조사`만 있어 병합하지 않음 (4.1 참고) |
| `견종크기` | Zooplus, Pets at Home, PetSmart | 다나와 `크기`는 알갱이 크기라 제외 (4.1 참고) |
| `알갱이크기` | 다나와, PetSmart | 다나와 `크기`, PetSmart `kibble_sizes` |
| `처방식여부` | 다나와, Pets at Home | |
| `맛`, `원재료`, `포장` | 2~3개 출처 | |
| `나트륨_pct` | Zooplus, Pets at Home | |
| `열량_kcal_kg`, `열량_원값` | Zooplus, Pets at Home, PetSmart | 다나와는 열량 정보 없음 |
| 미량성분 9종 | 2~3개 출처 | `타우린_pct`, `오메가3_pct`, `오메가6_pct`, `EPA_DHA합_pct`, `칼륨_pct`, `마그네슘_pct`, `탄수화물_pct`, `글루코사민_mg_kg`, `L카르니틴_mg_kg` |
| `최고가`, `판매옵션_원문` | Zooplus, Pets at Home, PetSmart | |
| `사이트`, `영양정보보유여부`, `중복여부` | Zooplus, Pets at Home | `중복여부`는 Zooplus `is_dup`, Pets at Home `in_zooplus` |

### 3.3 단일 출처 (20개)

정보 손실을 막기 위해 한 출처에만 있어도 보존했다.

- 다나와: `제조사`, `가공방식`, `사료여부`, `인증`, `표시태그`(무방부제·그레인프리 등 0/1 플래그 6개를 태그 목록으로 묶음), `주단백질원`, `주요기능성분`, `리뷰수_하한표기여부`, `등록연도`
- PetSmart: `영양표기기준`(보증성분 하한/상한), `리놀레산_pct`, `콘드로이틴_mg_kg`, `아연_mg_kg`, `셀레늄_mg_kg`, `비타민C_mg_kg`, `비타민A_IU_kg`, `비타민E_IU_kg`, `유산균_CFU_g`
- Zooplus: `전분_pct`, `염소_pct`

## 4. 병합 시 주의한 속성

### 4.1 이름은 비슷하지만 의미가 달라 분리한 속성

| 원본 | 오해하기 쉬운 대응 | 처리 |
| --- | --- | --- |
| 다나와 `크기` (`스몰(~8mm)`, `미디움(~13mm)`) | 견종크기 | **알갱이 크기**이므로 `알갱이크기`로 분리. 기존 `gold_candidates.csv`·`dog_food_merged.csv`에는 `breed_size`로 섞여 있었다. |
| 다나와 `제조사` (`한국마즈`) | 브랜드 (`로얄캐닌`) | `제조사`로 분리. 다나와 `브랜드`는 NULL |
| PetSmart `breed_size` 중 `Kibble`, `Crunchy` 등 23건 | 견종크기 | 식감 값이 잘못 들어간 것이므로 `견종크기_원문`에만 남기고 `견종크기`는 NULL |

### 4.2 값 표준화

범주 속성은 정규식 규칙으로 표준 코드로 바꾸고 원문을 `_원문` 속성에 보존했다.

| 속성 | 표준 코드 | 원문 예 |
| --- | --- | --- |
| `사료형태` | 건식·습식·반건조·동결건조·에어드라이·탈수건조·화식·냉동·토퍼·간식·액상·분말 | `Dry food`, `Kibble`, `Wet|Food Topper`, `건식` |
| `생애주기` | 퍼피·어덜트·시니어·전연령 | `Puppy/junior`, `All Life Stages`, `Adult dogs from 1 to 7 years old` |
| `견종크기` | 초소형·소형·중형·대형·초대형·전체 | `Extra small <4kg`, `Mini & Toy Breed`, `Small Breed` |

- PetSmart는 수집 범위가 `Dog > Food > Dry Food` 카테고리이므로, 형태 원문이 식감(`Crunchy` 등)뿐인 25건은 `건식`으로 두었다.
- Pets at Home `생애주기`는 자유 문장(644종)이라 나이 표현으로 분류했다. 예: `8+ weeks` → 퍼피, `12 months +` → 어덜트, `7+ years` → 시니어, `All dogs` → 전연령. 53건은 나이 정보가 없어 NULL이다(예: `Complementary Pet Food for Dogs.`). 근사 분류이므로 정밀 분석에는 `생애주기_원문`을 함께 확인한다.
- 기능 라벨은 원문만 통합했다. 표준 카테고리 매핑은 `카테고리딕셔너리.csv`로 별도 수행한다.

## 5. 단위환산이 필요했던 속성과 대처

환산 원칙:
1. 근거가 있는 환산만 적용하고, 값이 바뀐 행은 모두 `unit_conversion_log.csv`에 원값과 규칙을 남긴다.
2. 근거 없이 고칠 수 없는 값은 지우지 않고 **NULL + `품질플래그`**로 표시한다. 원값은 로그나 `_원값` 속성에 남는다.
3. 통화는 환산하지 않는다 (5.6 참고).

### 5.1 중량: g·lb·oz·묶음 → kg

| 출처 | 원문 | 대처 |
| --- | --- | --- |
| 다나와 | `중량_kg` 숫자 | 그대로 사용 |
| Zooplus, Pets at Home | `12kg|Economy Pack: 2 x 12kg`, `12 x 395g` | 옵션별로 파싱. g ÷ 1,000, `N x 용량`은 곱해서 총중량, `12kg + 2.4kg Free!`는 합산. 옵션 중 최소·최대를 `중량_kg_최소/최대`로 저장 |
| PetSmart | `4 Lb|10 Lb`, `oz` | **lb × 0.45359237**, **oz × 0.02835** (838건 로그) |

- Zooplus·Pets at Home에서 옵션 원문이 맛 이름뿐인 797건(`Chicken|Beef` 등)은 상품명의 용량(`6 x 800g`)으로 보충했다. 채움률: 다나와 97.3%, Zooplus 99.8%, Pets at Home 99.6%, PetSmart 100%.
- `ml` 표기는 비중을 몰라 kg으로 바꾸지 않았다.

### 5.2 kg당 가격

| 출처 | 원문 | 대처 |
| --- | --- | --- |
| 다나와 | 원본 `98원/10g` | 상류 단계에서 **×100**으로 원/kg 환산된 값(`단위가격_원/kg`)을 사용. 원본과 대조해 `원/10g` 2,375건 전부 일치를 확인. `원/10ml` 40건은 NULL |
| Zooplus, Pets at Home | `price_per_kg_min` | 그대로 사용 (통화/kg) |
| PetSmart | 없음 | SKU 파일에서 SKU별 `가격 ÷ (lb·oz → kg 중량)`을 구하고 상품별 최솟값을 사용 (838건) |

다나와 `최저가`는 묶음상품이면 **묶음 전체 가격**이고 `중량_kg`은 1개 단위다. 따라서 `최저가 ÷ 중량`으로 kg당 가격을 다시 계산하지 말고 `kg당최저가`를 쓴다 (약 11%가 불일치).

### 5.3 열량: kcal/g·kcal/100g·kJ·소수점 밀림 → kcal/kg

원본 `kcal_per_kg` 컬럼에 여러 단위가 섞여 있었다. 예: Zooplus `3.12`(kcal/g), `15570`(kJ/kg), Pets at Home `9196900`(소수점 오류).

대처 방법:
1. 500~6,000 kcal/kg 범위 안의 값은 그대로 둔다.
2. 범위 밖 값은 **성분 기반 추정 열량**과 비교한다. NRC 수정 Atwater 계수(단백질 3.5, 지방 8.5, 탄수화물 3.5 kcal/g)를 쓰고, 탄수화물은 `100 − 단백질 − 지방 − 섬유 − 회분 − 수분`이다.
3. 후보 배수(×1,000 kcal/g, ×10 kcal/100g, ÷4.184 kJ/kg, ×10÷4.184 kJ/100g, ×100·÷10·÷100·÷10,000 소수점 밀림)를 적용한 값 중 추정치의 ±35% 안에서 가장 가까운 것을 채택한다.
4. 범위 밖이어도 추정치와 맞으면 그대로 둔다. 수분 90% 이상인 액상·토퍼(예: 60 kcal/kg)가 여기에 해당한다.
5. 맞는 배수가 없으면 NULL로 둔다.

| 결과 | 건수 | 예 |
| --- | ---: | --- |
| kcal/g → ×1,000 | 23 | `3.12` → 3,120 |
| kcal/100g → ×10 | 5 | `89` (수분 80%) → 890 |
| kJ/kg → ÷4.184 | 2 | `15570` → 3,721 |
| kJ/100g → ×10÷4.184 | 1 | `133` (수분 93%) → 318 |
| 소수점 밀림 | 6 | `9196900` → 920, `11.7` → 1,170 |
| 보정 불가 → NULL | 1 | `38980` |

보정한 37건에는 `열량_단위보정`, NULL 처리한 1건에는 `열량_보정불가` 플래그를 붙였다. 보정 전 값은 `열량_원값`에 남아 있다.

### 5.4 미량성분: % ↔ mg/kg, ppm, CFU

| 속성 | 문제 | 대처 |
| --- | --- | --- |
| `글루코사민_mg_kg`, `L카르니틴_mg_kg` | Zooplus는 %(`0.05`), PetSmart는 mg/kg(`600`) | 표준 단위를 mg/kg로 정하고 Zooplus 값 × 10,000 (1% = 10,000 mg/kg). 14건 |
| `타우린_pct` | Zooplus % 컬럼에 mg/kg 값(`1000`~`2680`)이 섞임 | 100 초과 값은 mg/kg로 보고 ÷ 10,000 (12건). 1~100 사이 값(`1.7%` 등)은 근거가 없어 유지하고 `타우린>1%` 플래그 |
| ppm (PetSmart) | 글루코사민·콘드로이틴·비타민C·L카르니틴에 `ppm`과 `mg/kg` 혼재, 대소문자 차이(`MG/KG`) | ppm = mg/kg이므로 수치는 그대로 두고 단위만 통일 |
| `유산균_CFU_g` | `CFU/lb` 112건, `CFU/g` 13건 | CFU/lb ÷ 453.59 → CFU/g. 단위가 없는 74건은 값(`600`, `80` 등)으로 단위를 추정할 수 없어 NULL + `유산균_CFU_g_단위없음` |
| 호환되지 않는 단위 1건씩 | 비타민A `%`, 비타민E `mg/kg`, 글루코사민 `IU/kg`, 오메가6 `IU/kg` | NULL + `*_단위오류`. 비타민E의 mg↔IU 환산은 천연/합성 형태에 따라 계수가 달라 적용하지 않음 |
| 단위 없는 PetSmart 값 | 주요 영양소 등 소수 행 | 해당 성분의 단위가 하나뿐이면(`%`, `mg/kg`) 그 단위로 가정하고 로그에 기록 |
| `EPA_DHA합_pct` | Pets at Home은 합계, PetSmart는 EPA·DHA 별도 | PetSmart는 둘 다 있을 때만 합산 |

### 5.5 건물 기준 (단위가 아닌 기준 통일)

- 원본마다 건물 기준 제공 여부가 달랐다. 다나와는 조단백·조지방만, Zooplus·Pets at Home은 `dm_*` 7종을 제공하고, PetSmart는 제공하지 않는다.
- 모든 출처에서 같은 식으로 재계산했다: **건물기준값 = 현물값 ÷ (1 − 수분/100)**.
- 원본 제공값과 재계산값을 대조한 결과 다나와 1,147건, Zooplus 1,684건이 모두 일치했다.
- 다나와 `영양_DM표기=1`인 10건은 현물값 없이 건물 기준값만 있어 원본값을 그대로 쓴다.
- 건식(수분 약 10%)과 습식(약 80%)을 비교할 때는 `건물기준_*_pct`를 사용한다.

### 5.6 통화: 환산하지 않음

- `통화` 속성에 KRW(다나와), EUR·GBP(Zooplus), GBP(Pets at Home), USD(PetSmart)를 기록했다.
- 다나와와 PetSmart는 원본에 통화 컬럼이 없어 판매 시장 기준으로 고정값을 넣었다.
- 가격·kg당가격은 원래 통화 그대로다. [데이터 통합 규칙](data_integration_rules.md) 7.3에 따라 환율 기준일과 출처가 정해지기 전에는 환산하지 않는다.
- 출처 간 가격을 비교하려면 환율표(통화, 환율, 기준일, 출처)를 정한 뒤 별도 컬럼으로 추가한다.

### 5.7 보증성분의 하한/상한

PetSmart `*_minmax`(`min`, `max`)는 `영양표기기준` 속성에 `조단백:하한|조섬유:상한` 형태로 보존했다. 다른 출처는 원본에 하한/상한 정보가 없어 NULL이다.

## 6. 품질 플래그

`품질플래그`는 환산 결과와 [데이터 통합 규칙](data_integration_rules.md) 8.2의 검토 범위를 적용한 결과다. 174행에 1개 이상 붙었다. 행을 삭제하지 않으므로, 분석 시 필요에 따라 제외한다.

| 플래그 | 건수 | 의미 |
| --- | ---: | --- |
| `유산균_CFU_g_단위없음` | 74 | 5.4 참고 |
| `열량_단위보정` / `열량_보정불가` | 37 / 1 | 5.3 참고 |
| `성분합>105%` | 19 | 단백질+지방+섬유+회분+수분 합계 초과 |
| `오메가3>10%`, `조섬유>20%`, `조단백>70%`, `조회분>20%`, `조지방>50%`, `인>3%`, `칼슘>5%`, `나트륨>2%`, `수분>95%`, `타우린>1%` | 2~11 | 검토 범위 초과 |
| `사료형태_수분불일치` | 7 | 건식인데 수분 40% 초과, 또는 습식인데 40% 미만 |
| `*_단위오류` | 4 | 5.4 참고 |
| `원본:…` | 39 | Pets at Home 원본 `이상값` 컬럼의 표시를 보존 |

## 7. 통합 스키마에 넣지 않은 원본 컬럼

아래 컬럼은 통합 스키마에서 제외했지만 원본 파일에 그대로 남아 있다. 필요하면 `출처 + 상품ID`로 다시 결합한다.

- 공통 원문: `description`, `features`, `breadcrumb`, `constituents_raw`, `calorie_raw`, `additives`, `ingredients_full`, `gtin`, `n_variants`
- Zooplus: `특수식단`(100% 결측), `견종`, `constituents_variant`, `n_constituent_options`
- Pets at Home: `사이트분류`, `page_type`, `pet`, `not_suitable_for`, `recipe_type`, `health_condition`(100% 결측), `product_benefits`, `free_from`, `food_texture`, `hypoallergenic_flag`, `category_groups`, `search_keywords`, `multi_value`
- PetSmart: `master_id`(`web_style_id`와 동일), `category`, `species`, `nutritional_benefits`, `health_consideration`, `hc_text_mapped`, `hc_curated`, `caloric_content`, `guaranteed_analysis`, `features_benefits`, `food_category`, `nutritional_options`, `series`, `skus`, `*_unit`(환산에 사용)

## 8. 남은 과제

1. 다나와 `브랜드`: 상품명에서 추출하려면 브랜드 사전이 필요하다 (예: `한국마즈 로얄캐닌 …` → 로얄캐닌).
2. 통화 환산: 환율 기준일과 출처를 정한다.
3. 기능 라벨 표준화: `기능_원문`을 `카테고리딕셔너리.csv`로 매핑한다.
4. 품질 플래그가 붙은 174행은 원문을 검수한다. 특히 `오메가3>10%` 11건과 `타우린>1%` 5건은 원문 자체가 % 표기라서 자동 보정하지 않았다.
5. PetSmart는 `라벨출처`가 큐레이션인 479건만 기존 gold 기준에 해당한다. 텍스트추출 261건과 라벨 없음 98건도 통합 파일에 포함되어 있으므로 학습 시 `라벨출처`로 거른다.

## 9. 실행

```bash
python project/scripts/build_gold_unified.py
```

`netflix` conda 환경(pandas)에서 실행한다. 실행하면 `unified/` 폴더의 산출물 3개를 다시 생성하고, 출처별 행 수, 환산 규칙별 건수, 품질 플래그 상위 목록을 출력한다.
