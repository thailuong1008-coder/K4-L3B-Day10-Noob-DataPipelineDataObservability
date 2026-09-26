# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin        | Nội dung |
| ---------------- | -------- |
| Khóa/Lớp         | K4 — L3B |
| Tên nhóm         | Noob |
| Repository       | https://github.com/thailuong1008-coder/K4-L3B-Day10-Noob-DataPipelineDataObservability |
| Ngày hoàn thành  | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Thái Lương | 2A202602932 | Trưởng nhóm / Pipeline Integrator | `src/core/`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `script/*.py` |
| 2 | Nguyễn Lê Ngọc Bảo | 2A202602852 | Data Foundation & Recovery | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `data/raw/`, repair từ raw snapshot |
| 3 | Nguyễn Xuân Trường | 2A202602761 | RAG & Vector Index | `src/retrieval/index.py`, `src/retrieval/embeddings.py`, `src/retrieval/agent.py`, `data/chroma/` |
| 4 | Cao Đức Hiếu | 2A202602701 | Observability & Evaluation | `src/observability/quality.py`, `src/observability/reporting.py`, `src/evaluation/testset.py`, `src/ingestion/corruption.py` |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành toàn bộ 7 khối của pipeline: ingestion Crossref có retry và fallback snapshot, cleaning sinh `text_for_embedding` và `age_days`, index ChromaDB với `all-MiniLM-L6-v2`, bộ test 10 câu hỏi thuộc 4 nhóm, quality gate Great Expectations 1.x (9 expectations) kèm Freshness SLA, bộ 6 corruption và repair tự động. Cả `script/run_phase1.py` và `script/run_corruption_flow.py` đều chạy exit code 0.

Baseline tạo ra raw artifacts (`data/raw/`), dữ liệu sạch 24 dòng (`data/clean/`), collection `papers-baseline` 24 docs, `data/eval/test_set.json`, `baseline_metrics.json` (hit rate 1.0, token F1 1.0, judge accuracy 1.0 với Gemini làm judge) và `phase1_report.md`.

Sau khi tiêm 6 loại lỗi, pipeline vẫn chạy bình thường nhưng hit rate giảm còn 0.8 và token F1 còn 0.8588 — hiện tượng silent failure. Ảnh hưởng rõ nhất là nhóm câu hỏi `summary` (token F1 0.5294) do blank summary và title bị cắt. Quality gate bắt được 4/9 expectation fail và freshness chuyển STALE (36% bài quá 180 ngày).

Repair dựng lại dữ liệu từ `data/raw/crossref_records.json`, được kích hoạt tự động khi quality gate fail, và phục hồi 100% cả 4 metric về mức baseline; chạy lại lần hai cho kết quả giống hệt (idempotent).

Giới hạn còn lại: test set chỉ 10 câu nên không phủ hết mọi corruption (stale date không chạm câu hỏi `date` nào), và Ragas chưa được bật.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (hoặc snapshot data/raw/crossref_response.json khi mất mạng / 429)
    -> raw response + raw records (data/raw/)
    -> cleaning và data modeling (data/clean/papers_clean.*)
    -> GX 1.x quality gate + Freshness SLA (data/quality/)
    -> embedding MiniLM + ChromaDB collection papers-baseline
    -> evaluation baseline trên test set 10 câu (data/results/baseline_*)
    -> phase1_report.md
    -> corruption 6 loại (corruption_log.json)
    -> quality gate FAIL -> re-index papers-corrupted và re-evaluate
    -> auto-repair từ raw records (idempotent) -> quality gate PASS
    -> re-index papers-repaired và re-evaluate
    -> corruption_report.md (Baseline vs Corrupted vs Repaired)
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` hoặc snapshot | Retry 429/5xx (3 lần, backoff 2^n), fallback snapshot, parse + bóc thẻ JATS | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Nguyễn Lê Ngọc Bảo |
| Cleaning | `list[PaperRecord]`, `run_date` | Chuẩn hóa whitespace/list, parse ngày, `age_days`, dedup `paper_id`, `text_for_embedding` | `data/clean/papers_clean.csv/.json` | Nguyễn Lê Ngọc Bảo |
| Embedding/index | Clean DataFrame | `all-MiniLM-L6-v2` (normalize), ChromaDB cosine, 3 collection tách biệt | `data/chroma/`, `data/embeddings/*.json` | Nguyễn Xuân Trường |
| Evaluation | Clean DataFrame, index | Test set 10 câu / 4 nhóm; hit rate, token F1, LLM judge | `data/eval/test_set.json`, `data/results/*_metrics.json` | Cao Đức Hiếu |
| Observability | Clean/corrupted/repaired DataFrame | GX 1.x ephemeral context, 9 expectations, Freshness SLA 180 ngày / 25% | `data/quality/*.json` | Cao Đức Hiếu |
| Corruption/repair | Clean DataFrame, raw records | 6 corruption (seed 42); repair = rebuild từ raw + kiểm tra idempotent | `data/results/corruption_log.json`, `data/clean/papers_clean_{corrupted,repaired}.*` | Cao Đức Hiếu (corruption), Nguyễn Lê Ngọc Bảo (repair) |
| Orchestration | Settings, toàn bộ module | Thứ tự chạy phase 1 → corruption → auto-repair → report | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Nguyễn Thái Lương |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-3.5-flash-lite` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 (`max_results=24`) |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; tối đa 25% bài stale |
| Random seed, nếu có | 42 (corruption) |

### Lệnh cài đặt

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Tạo `.env` từ `.env.example` và điền `GOOGLE_API_KEY` (không commit `.env`).

### Lệnh chạy

```bash
.venv/Scripts/python script/run_phase1.py
.venv/Scripts/python script/run_corruption_flow.py
.venv/Scripts/python -m pytest -q tests
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công (exit 0) | 2026-09-26 11:40 (GMT+7) | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công (exit 0) | 2026-09-26 11:42 (GMT+7) | `data/results/{corrupted,repaired}_metrics.json`, `data/reports/corruption_report.md` |
| Pytest | 7 passed | 2026-09-26 | `tests/test_pipeline.py` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `https://api.crossref.org/works` (snapshot offline `data/raw/crossref_response.json`) |
| Query/filter | `query="agentic retrieval augmented generation large language model"`, `filter=from-pub-date:<hôm nay − 180 ngày>,has-abstract:true`, `rows=24`, sort `published desc` |
| Thời điểm lấy dữ liệu | Snapshot offline có sẵn trong repo; mặc định pipeline không gọi lại API (bật `REFRESH_SOURCE=1` để refresh) |
| Số record nhận được | 24 items → 24 `PaperRecord` hợp lệ |
| Cơ chế retry/backoff | Retry tối đa 3 lần cho 429/500/502/503/504 và lỗi mạng, chờ 2s → 4s; hết retry thì fallback snapshot |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | str | Có | DOI (lower-case), khóa duy nhất | Thiếu → loại record; trùng → giữ bản `updated` mới nhất |
| `title` | str | Có | Tiêu đề bài báo | Thiếu → loại record; chuẩn hóa whitespace |
| `summary` | str | Có | Abstract đã bỏ thẻ JATS/HTML | Thiếu/rỗng → loại record |
| `authors` | list[str] | Không | `given + family` từng tác giả | Bỏ phần tử rỗng/trùng; list rỗng vẫn giữ |
| `categories` | list[str] | Không | `subject` của Crossref | Bỏ phần tử rỗng/trùng |
| `primary_category` | str | Không | Category đầu tiên | Rỗng → lấy `categories[0]` |
| `published` | str `YYYY-MM-DD` | Có | Ngày xuất bản | Fallback `published-online → published-print → issued → created`; thiếu tháng/ngày → 1; không parse được → loại |
| `updated` | str `YYYY-MM-DD` | Không | Ngày cập nhật | Thiếu → dùng `published` |
| `age_days` | int | Có (clean) | Số ngày từ `published` đến `run_date` | Tính lại mỗi lần chạy |
| `authors_joined`, `categories_joined` | str | Có (clean) | List nối bằng `", "` | Rỗng nếu list rỗng |
| `summary_chars` | int | Có (clean) | Độ dài summary | — |
| `text_for_embedding` | str | Có (clean) | Văn bản 5 phần dùng để embed | Luôn sinh từ các cột đã clean |

### Quy tắc cleaning

| Quy tắc | Quality dimension liên quan | Số record bị tác động | Cách xác minh |
| --- | --- | ---: | --- |
| Bóc thẻ JATS/HTML và decode entity trong abstract | Validity | 24 (mọi abstract đều bọc `<jats:p>`) | So sánh `crossref_response.json` với `crossref_records.json` |
| Loại record thiếu DOI/title/abstract/ngày | Completeness | 0 | 24 items → 24 records |
| Khử trùng lặp theo `paper_id` | Uniqueness | 0 trên snapshot (test: nhân đôi 48 → 24) | GX `expect_column_values_to_be_unique` PASS; `test_clean_dataframe_schema_and_dedup` |
| Chuẩn hóa ngày về `YYYY-MM-DD` UTC | Consistency | 24 | Cột `published` trong `papers_clean.csv` |

`text_for_embedding` gồm 5 dòng `Title / Authors / Published / Categories / Summary` để vector mang đủ tín hiệu cho cả 4 nhóm câu hỏi. Document ID trong ChromaDB là `<paper_id>::<vị trí>` (để các dòng trùng lặp khi corrupt vẫn nạp được), còn metadata `paper_id` (DOI) dùng để đối chiếu ground truth. `age_days = (run_date − published).days`, cả hai được normalize về 00:00 UTC.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| Các `question_type` | `summary` (3), `authors` (3), `date` (2), `categories` (2) |
| Ground-truth document ID | DOI của bài được chọn; bài được chọn cách đều theo thứ tự `paper_id` (deterministic) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection | ChromaDB persistent `data/chroma/`, cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | Gemini `gemini-3.5-flash-lite` (LLM judge + agent demo) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha256 `be7dc96d57c9…`) |

Test set được sinh một lần ở phase 1 và chỉ được đọc lại ở corruption flow. Nếu câu hỏi thay đổi giữa các trạng thái thì chênh lệch metric có thể đến từ độ khó câu hỏi; giữ cố định giúp biến duy nhất là chất lượng dữ liệu.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | 24 items / 24 records |
| Cleaned dataset | `data/clean/` | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/` | Có | 3 manifest, `persist_path` tương đối |
| Evaluation set | `data/eval/` | Có | 10 câu |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | Kèm `baseline_answers.json` |
| Quality/freshness | `data/quality/` | Có | baseline/corrupted/repaired quality + freshness |
| Baseline report | `data/reports/phase1_report.md` | Có | Sinh tự động |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 10/10 câu có doc đúng trong top-4 |
| `mean_token_f1` | 1.0000 | Câu trả lời trích đúng trường metadata/câu đầu summary |
| `judge_accuracy` | 1.0000 | Gemini đánh giá 10/10 câu đúng |
| `mean_judge_score` | 5.0000 | Điểm tối đa trên thang 1–5 |
| Ragas, nếu có | N/A | Chưa bật (`RUN_RAGAS=1`) để tiết kiệm thời gian/quota |

Metric baseline tối đa vì câu hỏi chứa nguyên tiêu đề bài báo và QA tra cứu chính xác theo title trước khi search vector — baseline đóng vai trò mốc tham chiếu hơn là thước đo độ khó retrieval.

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `ExpectTableRowCountToBeBetween` | Completeness | 19–24 dòng | PASS (24) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` (`paper_id`, `title`, `summary`, `text_for_embedding`) | Completeness | 0 null | PASS (0) | như trên |
| `ExpectColumnValuesToBeUnique` (`paper_id`) | Uniqueness | 0 trùng | PASS (0) | như trên |
| `ExpectColumnValueLengthsToBeBetween` (`title`) | Validity | ≥ 8 ký tự | PASS (0 vi phạm) | như trên |
| `ExpectColumnValueLengthsToBeBetween` (`summary`) | Validity | 50–5000 ký tự | PASS (0 vi phạm) | như trên |
| `ExpectColumnValuesToBeBetween` (`age_days`) | Timeliness | 0–180, `mostly=0.75` | PASS (1 vi phạm, 4.2%) | như trên |

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | Clean dataset (cột `published` / `age_days`) — `data/quality/freshness_report.json` |
| Timestamp mới nhất | 2026-07-22 (cũ nhất 2026-03-28) |
| Ngưỡng freshness | 180 ngày; stale ratio ≤ 25% |
| Trạng thái baseline | Fresh |
| Lý do | 1/24 bài (4.17%) quá 180 ngày, dưới ngưỡng 25% |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | ---: | --- | --- | --- |
| `drop_latest_records` | Xóa 20% bài có `published` mới nhất | 5 | Row count giảm | 24 → 19 (+3 dup = 22), vẫn trong ngưỡng 19–24; 1 câu `authors` mất doc đúng | Rebuild từ raw |
| `blank_summary` | Summary = `""` | 3 | Summary length FAIL | Góp phần vào 3 vi phạm độ dài summary; 1 câu `summary` trả lời rỗng | Rebuild từ raw |
| `inject_noise` | Chèn token rác + đảo ngược từ trong summary | 3 | Có thể lọt qua GX | Lọt qua GX (độ dài vẫn hợp lệ); rơi vào câu `authors`/`date` nên không đổi F1 | Rebuild từ raw |
| `truncate_title` | Cắt title còn 6 ký tự | 3 | Title length FAIL | 4 vi phạm (tính cả dòng duplicate); 1 câu `summary` retrieval trượt | Rebuild từ raw |
| `stale_date` | Lùi `published` 1095 ngày, cộng `age_days` | 6 | `age_days` FAIL, freshness STALE | 8/22 bài stale (36%) → FAIL + STALE | Rebuild từ raw |
| `duplicate_rows` | Nhân bản 3 dòng | 3 | Unique `paper_id` FAIL | 6 giá trị trùng → FAIL | Rebuild từ raw (dedup) |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đủ 6 loại, số dòng và danh sách `paper_id` bị tác động, seed 42, số dòng vào/ra (24 → 22), và ví dụ title trước/sau khi cắt.

Repair không sửa từng ô trong dữ liệu bẩn mà dựng lại dataset từ lineage anchor bất biến `data/raw/crossref_records.json` (fallback `crossref_response.json`) bằng đúng hàm `build_clean_dataframe`. Repair được kích hoạt tự động khi quality gate hoặc freshness fail, sau đó phải qua lại quality gate (nếu fail thì pipeline dừng với lỗi). Pipeline chạy rebuild hai lần và so sánh DataFrame: `idempotent_rerun_identical: True`.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | −0.2000 | 100% | 2 câu mất doc đúng: bài bị drop và bài bị cắt title |
| `mean_token_f1` | 1.0000 | 0.8588 | 1.0000 | −0.1412 | 100% | Nhóm `summary` giảm còn 0.5294; 3 nhóm còn lại giữ 1.0 |
| `judge_accuracy` | 1.0000 | 0.9000 | 1.0000 | −0.1000 | 100% | Judge khoan dung hơn token F1 |
| `mean_judge_score` | 5.0000 | 4.5000 | 5.0000 | −0.5000 | 100% | Giảm nhẹ, không có lỗi runtime nào |
| Quality checks pass/fail | 9/9 PASS | 5/9 FAIL | 9/9 PASS | −4 checks | 100% | Fail: unique `paper_id`, độ dài title, độ dài summary, `age_days` |
| Freshness status | FRESH (4.2%) | STALE (36.4%) | FRESH (4.2%) | +32.2 điểm % stale | 100% | Vượt ngưỡng 25% do `stale_date` |

1. `blank_summary` + `truncate_title` → GX fail độ dài summary (3) và title (4) → token F1 nhóm `summary` giảm từ 1.0 xuống 0.5294 và hit rate giảm 0.1; tương tự `drop_latest_records` làm mất doc của 1 câu `authors` → hit rate giảm thêm 0.1. Pipeline vẫn exit 0 — chỉ quality gate phát hiện được.
2. Auto-repair rebuild từ raw records → GX 9/9 PASS, freshness FRESH (4.2%) → cả 4 metric trở về đúng baseline (`repaired_metrics.json` trùng `baseline_metrics.json`).

Kết quả khác kỳ vọng: `stale_date` không làm giảm metric nào vì 6 bài bị lùi ngày không trùng 2 bài được hỏi về ngày (đối chiếu `corruption_log.json` với `test_set.json`), và `inject_noise` rơi vào câu hỏi `authors`/`date` vốn không đọc summary. Hai lỗi này chỉ được phát hiện qua freshness (stale date) hoặc hoàn toàn không bị phát hiện (noise lọt qua GX vì độ dài vẫn hợp lệ).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi chuyển từ judge dự phòng sang Gemini thật, agent demo trả về câu trả lời dạng list các block `{'type': 'text', 'text': ..., 'extras': {'signature': ...}}` thay vì chuỗi, làm `agent_demo_answers.json` chứa dữ liệu thô khó đọc. Trước đó, key được đặt dưới tên `gemini_API_Key` nên `build_llm` báo thiếu `GOOGLE_API_KEY` và toàn bộ judge chạy ở chế độ fallback heuristic.
- **Nguyên nhân:** `core/config.py` chỉ đọc `GOOGLE_API_KEY`; và model Gemini 3.x trả `AIMessage.content` dạng list content blocks (text + thought signature), trong khi `run_agent_question` giả định content là `str`.
- **Cách xử lý:** Đổi tên biến trong `.env` thành `GOOGLE_API_KEY`; sửa `run_agent_question` trong `src/retrieval/agent.py` để nối các block `text` thành chuỗi.
- **Cách xác minh:** Chạy lại `script/run_phase1.py` → `[phase1] agent demo: ok`; `data/results/*_answers.json` có 0 judge dùng fallback; `agent_demo_answers.json` chứa câu trả lời dạng văn bản.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Test set chỉ 10 câu, câu hỏi chứa nguyên title | Baseline đạt tối đa; một số corruption (stale date, noise) không chạm câu hỏi nào | Thêm câu hỏi paraphrase không chứa title và đảm bảo mỗi loại corruption chạm ≥ 1 câu; đo lại theo từng loại corruption riêng lẻ |
| `inject_noise` lọt qua quality gate | Summary rác vẫn được embed mà không có cảnh báo | Thêm expectation về tỷ lệ ký tự không phải chữ / token rác (`ExpectColumnValuesToNotMatchRegex`), kiểm chứng bằng `corrupted_quality_report.json` |
| Ragas chưa chạy | Thiếu faithfulness/context precision | Chạy với `RUN_RAGAS=1` và so sánh 3 trạng thái |
| Snapshot offline cố định | Freshness sẽ tự chuyển STALE khi thời gian trôi qua | Lên lịch refresh với `REFRESH_SOURCE=1` và theo dõi `freshness_report.json` theo thời gian |

## 13. Checklist trước khi nộp

- [ ] Thông tin nhóm và repository chính xác.
- [ ] Phân công khớp với module, artifact và kết quả thực tế.
- [ ] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [ ] Baseline, corrupted và repaired dùng cùng evaluation set.
- [ ] Bảng metrics khớp với các file trong `data/results/`.
- [ ] Quality/freshness conclusions khớp với `data/quality/`.
- [ ] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [ ] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
