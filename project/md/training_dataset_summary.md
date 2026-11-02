# 기능 카테고리 학습 데이터셋 구성

작성일: 2026-11-02  
목적: 반려견 사료의 원료·영양성분·상품 정보를 입력으로 받아 건강 기능 카테고리를 예측하는 멀티라벨 분류 모델의 학습 데이터 구성을 정리한다.

## 생성 파일과 역할

| 구분 | 파일 | 행 수 | 역할 |
| --- | --- | ---: | --- |
| Gold | `data/model_datasets/gold/gold_candidates.csv` | 4,711 | 출처의 공식 기능 라벨 또는 PetSmart curated 라벨이 있는 주 학습 후보 |
| Gold 라벨 | `data/model_datasets/gold/labels_gold.csv` | 8,541 | 제1정규형으로 분해한 상품-표준카테고리 라벨 행 |
| Gold 라벨 근거 | `data/model_datasets/gold/label_evidence_gold.csv` | 8,580 | 원문 라벨에서 표준 카테고리로 변환한 근거 행 |
| 미매핑 라벨 | `data/model_datasets/gold/labels_gold_unmapped.csv` | 0 | 현재 카테고리 사전에 없는 원문 라벨 검토 목록 |
| Silver | `data/model_datasets/silver/silver_candidates.csv` | 261 | PetSmart 설명 텍스트에서 추출된 보조 학습 후보 |
| Unlabeled | `data/model_datasets/unlabeled/unlabeled_candidates.csv` | 6,336 | 기능 라벨이 없어 모델 완성 후 예측할 후보 |
| 범위 검토 | `data/model_datasets/unlabeled/openpetfoodfacts_scope_review.csv` | 15,136 | 반려견 식품 여부 판정 전의 Open Pet Food Facts 목록 |
| 카테고리 사전 | `data/model_datasets/카테고리딕셔너리.csv` | 81 | 원문 기능 라벨과 표준 카테고리의 매핑 규칙 |
| 매니페스트 | `data/model_datasets/dataset_manifest.csv` | 5 | 생성 파일의 행 수와 용도 |

원본 CSV는 변경·이동·삭제하지 않았다. 위 파일들은 학습 준비를 위한 역할별 복사본 또는 파생 후보 목록이다.

## Gold 데이터 구성

Gold는 라벨 신뢰도가 비교적 높은 후보다. 다만 최종 학습 전, 카테고리 사전으로 원문 라벨을 표준 카테고리로 변환하고 표본 검수를 수행해야 한다.

| 출처 | 라벨 근거 | 행 수 |
| --- | --- | ---: |
| 다나와 | 상품상세정보에서 파싱한 `기능` | 1,830 |
| Zooplus | 사이트 `기능` | 1,690 |
| Pets at Home | 사이트 `기능` | 670 |
| Purina UK | 사이트 `기능` | 42 |
| PetSmart | `hc_source=curated`의 `hc_final` | 479 |
| **합계** |  | **4,711** |

Gold 파일의 주요 컬럼은 `sample_id`, `group_id`, `source`, `product_id`, `brand`, `product_name`, 영양성분, 원료, `label_raw`, `label_source`, `label_confidence`, `quality_flags`다. 동일 상품의 변형·용량이 학습과 테스트에 나뉘지 않도록 `group_id`를 분할 기준으로 사용한다.

### 제1정규형 라벨 테이블

`labels_gold.csv`는 상품 한 개와 표준 카테고리 한 개를 한 행으로 저장한다. 따라서 하나의 상품이 소화와 피부 기능을 모두 가지면 두 행이 생성된다.

| 검증 항목 | 결과 |
| --- | ---: |
| Gold 상품 수 | 4,711 |
| 원문 라벨 매핑 근거 행 수 | 8,580 |
| 정규화 라벨 행 수 | 8,541 |
| 하나 이상의 표준 라벨을 가진 상품 | 4,711 |
| 1차 학습 카테고리 라벨 행 수 | 5,558 |
| 하나 이상의 1차 카테고리를 가진 상품 | 3,288 |
| 사전에 없는 원문 라벨 | 0 |

1차 학습 카테고리별 라벨 행 수는 `digestive` 1,731, `skin_coat` 1,382, `joint_bone` 952, `weight_management` 862, `dental_oral` 278, `renal` 190, `urinary` 163이다.

## Silver 데이터 구성

Silver는 PetSmart의 `hc_source=text` 261건이다. 상품 설명·기능 문구에서 자동으로 매핑된 라벨이므로 정답의 신뢰도가 Gold보다 낮다.

- Gold 데이터만으로 먼저 기준 모델을 학습한다.
- Silver는 성능이 안정된 뒤 보조 학습에만 사용한다.
- Silver의 라벨을 만든 `health_consideration`, `features_benefits` 텍스트를 그대로 모델 입력에 넣으면 라벨 누수가 발생할 수 있다.
- 최종 성능 평가는 Silver가 아닌 Gold 검수셋으로 한다.

## Unlabeled 데이터 구성

Unlabeled 6,336건은 기능 라벨이 비어 있어 학습 정답으로 사용하지 않는다.

- 명견에픽과 강아지대통령 데이터는 모델이 기능을 예측할 대상이다.
- 기존 출처에서 기능 태그가 없는 상품도 “기능 없음”이 아니라 “알 수 없음”으로 취급한다.
- Open Pet Food Facts는 15,136건 전체를 별도 범위 검토 파일로 두었다. 반려견 식품 판정 규칙을 적용한 뒤에만 추론 대상으로 편입한다.

## 표준 카테고리

### 1차 학습에 사용하는 건강 기능 카테고리

`primary_training=Y`인 매핑만 1차 모델의 정답으로 사용한다.

| 표준 카테고리 | 의미 | 대표 원문 라벨 |
| --- | --- | --- |
| `digestive` | 소화·위장 기능 | 소화기, 소화·장건강, Stomach & digestive care, Digestive Care, Gastrointestinal, Sensitive Stomach |
| `skin_coat` | 피부·피모·모질 기능 | 피부, 피부·피모·모질, Hair/fur/skin care, Skin & Coat, Sensitive Skin, Shiny Coat |
| `weight_management` | 체중 관리 기능 | 체중, Weight management, Weight Control |
| `joint_bone` | 관절·뼈·이동성 기능 | 관절, Joints & bone care, Hip & Joint, Mobility, Bone Development |
| `renal` | 신장 관리 기능 | 신장, Renal care |
| `dental_oral` | 치아·구강 기능 | 치아, Dental care & hygiene, Dental |
| `urinary` | 요로·비뇨 기능 | 비뇨기, Urinary care |

한 상품에 여러 기능이 있을 수 있다. 예를 들어 소화와 피부 라벨을 모두 가진 상품은 `digestive`와 `skin_coat` 두 개의 정답을 가진다. 따라서 이 문제는 단일 분류가 아닌 멀티라벨 분류다.

### 현재는 1차 학습에서 제외하는 건강 기능 카테고리

아래 카테고리는 라벨 수가 적어 추가 수집 또는 표본 검수 후 확장한다.

| 표준 카테고리 | 의미 | 대표 원문 라벨 | 제외 이유 |
| --- | --- | --- | --- |
| `immune` | 면역 지원 | Immune system, Immune Support | 희귀 라벨 |
| `heart` | 심장 건강 | Heart care, Cardiac | 희귀 라벨 |
| `liver` | 간 건강 | Liver care | 희귀 라벨 |
| `diabetes` | 당뇨 관리 | Diabetic | 희귀 라벨 |
| `brain_health` | 뇌·인지 건강 | Brain health, Brain Development | 희귀 라벨 |
| `vision` | 눈 건강 | Vision, Eye Care | 희귀 라벨 |

### 건강 기능과 분리하는 속성 태그

아래 값은 유용하지만 건강 기능 정답과 의미가 다르므로 별도 태그로 보관한다.

| 표준 태그 | 유형 | 대표 원문 라벨 | 처리 원칙 |
| --- | --- | --- | --- |
| `hypoallergenic` | 식이특성 | Hypoallergenic, 저알러지, Allergies | 건강 기능과 분리 |
| `sensitive` | 식이특성 | Sensitive | 대상 기능이 불명확하므로 분리 |
| `sterilised` | 대상특성 | Sterilised | 건강 기능과 분리 |
| `performance` | 대상특성 | Performance | 건강 기능과 분리 |
| `active_lifestyle` | 대상특성 | Active | 건강 기능과 분리 |
| `aging` | 대상특성 | Aging | 생애주기와 구분 |
| `general_health` | 포괄태그 | General Health | 개별 기능의 음성 라벨로 사용 금지 |
| `muscle_tone` | 보조기능 | Muscle Tone | 데이터 보강 후 별도 검토 |

## 라벨 변환 규칙

1. 원문 `label_raw`를 먼저 카테고리 사전에서 찾는다.
2. 사전의 `source`와 원문 출처가 일치하는 매핑만 적용한다.
3. `|`로 연결된 실제 복수 기능은 여러 라벨로 나눈다.
4. `Hair-, fur- & skin care`처럼 쉼표가 기능명 내부에 포함된 표현은 분리하지 않는다.
5. 사전에 없는 라벨은 삭제하지 않고 `unmapped_label`로 보관한다.
6. `primary_training=N`인 값은 1차 모델의 정답에서 제외하되 원문 태그는 보존한다.

## 다음 단계

1. Gold 파일의 `label_raw`를 `카테고리딕셔너리.csv`로 매핑한다.
2. 상품-표준카테고리 한 행 구조의 `labels.csv`를 만든다.
3. Gold 중 카테고리별 무작위 표본을 사람 검수해 테스트용 Gold셋을 확정한다.
4. `group_id` 단위로 학습·검증·테스트를 분할한다.
5. Gold만 사용한 기준 모델을 학습하고, Silver를 추가했을 때 성능 변화를 비교한다.
6. 검증된 모델만 Unlabeled 데이터에 적용한다.
