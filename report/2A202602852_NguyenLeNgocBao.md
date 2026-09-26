# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin        | Nội dung                                                   |
| ---------------- | ---------------------------------------------------------- |
| Họ và tên        | Nguyễn Lê Ngọc Bảo                                         |
| MSSV             | 2A202602852                                                |
| Khóa/Lớp         | K4 — L3B                                                   |
| Tên nhóm         | Noob                                                       |
| Vai trò chính    | Data Foundation & Recovery (Ingestion, Cleaning, Repair)   |
| Repository       | https://github.com/thailuong1008-coder/K4-L3B-Day10-Noob-DataPipelineDataObservability |
| Ngày hoàn thành  | 2026-09-26                                                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Raw ingestion + fallback offline | `src/ingestion/crossref.py` — `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref REST API (`query`, `filter`, `rows=24`) hoặc snapshot `data/raw/crossref_response.json` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 `PaperRecord`) | Hoàn thành |
| Cleaning & pre-embed modeling | `src/ingestion/cleaning.py` — `build_clean_dataframe`, `build_embedding_text` | `list[PaperRecord]`, `run_date` | DataFrame 24 dòng, 16 cột (có `age_days`, `text_for_embedding`) → `data/clean/papers_clean.csv/.json` | Hoàn thành |
| Idempotent repair từ raw | `src/pipelines/corruption_flow.py` — `_rebuild_from_raw`, `repair_dataset` | `data/raw/crossref_records.json` (fallback `crossref_response.json`) | `data/clean/papers_clean_repaired.csv/.json` | Hoàn thành |

Phần của tôi là tầng dữ liệu nền: mọi module phía sau (ChromaDB index của Trường, GX quality gate + test set của Hiếu, orchestration của Lương) đều đọc schema do `cleaning.py` sinh ra, nên tôi phải giữ contract cột ổn định (`paper_id`, `title`, `summary`, `published`, `age_days`, `authors_joined`, `categories_joined`, `text_for_embedding`, …).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tách hàm `build_embedding_text` thành public để module corruption tái sử dụng | `src/ingestion/corruption.py` (Hiếu/Lương) | Dữ liệu bẩn được rebuild `text_for_embedding` đúng cùng format 5 phần như dữ liệu sạch |
| Viết test cho ingestion/cleaning/repair | `tests/test_pipeline.py` | `pytest tests` → 7 passed |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse payload Crossref, bóc thẻ JATS (`<jats:p>`), chuẩn hóa DOI/tác giả/ngày | `src/ingestion/crossref.py` | 24 `PaperRecord` sạch trong `crossref_records.json` | Lệnh CP0 → `Đã tải 24 bài báo` |
| Gọi API có retry (429/5xx, backoff 2^n) + fallback snapshot | `fetch_source_records`, `_request_crossref` | Pipeline không bị gián đoạn khi mất mạng / rate limit | Chạy mặc định (không có `REFRESH_SOURCE`) đọc snapshot; `git status` cho thấy 2 raw file không đổi |
| Clean: whitespace, parse ngày, `age_days`, dedup theo `paper_id`, `text_for_embedding` | `src/ingestion/cleaning.py` | `data/clean/papers_clean.csv/.json` 24 dòng | Lệnh CP1 → `Clean thành công 24 dòng` |
| Repair idempotent từ raw snapshot | `repair_dataset` trong `corruption_flow.py` | `papers_clean_repaired.*`, quality gate 9/9 PASS | `run_corruption_flow.py` in `idempotent_rerun_identical: True` |

Output cụ thể: bảng repair trong `data/reports/corruption_report.md` ghi `source: raw_records_json`, `rows: 24`, `idempotent_rerun_identical: PASS`, `quality_gate_after_repair: PASS`, và cả 4 metric của trạng thái Repaired quay về đúng Baseline (hit rate 1.0, token F1 1.0).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu Crossref thô không dùng trực tiếp để embed được: abstract chứa thẻ XML JATS, tên tác giả tách `given`/`family`, ngày xuất bản dạng `date-parts` có thể thiếu tháng/ngày, và có thể có bản ghi trùng hoặc thiếu abstract. Ngoài ra, khi dữ liệu downstream bị hỏng, pipeline cần một "điểm neo" (lineage anchor) để dựng lại dữ liệu sạch mà không phải gọi lại API.

### Cách triển khai

- **Parse:** duyệt `payload["message"]["items"]`; DOI được lower-case làm `paper_id`; abstract đi qua regex bỏ mọi thẻ `<...>` rồi `html.unescape` và gộp khoảng trắng. Ngày `published` lấy theo thứ tự ưu tiên `published → published-online → published-print → issued → created`, thiếu tháng/ngày thì mặc định 1. Bản ghi thiếu DOI, title, abstract hoặc ngày bị loại.
- **Fetch:** mặc định đọc snapshot nếu đã có (tái lập được, không tốn quota); chỉ gọi API khi `REFRESH_SOURCE=1` hoặc chưa có snapshot. Lỗi 429/5xx được retry 3 lần; hết retry thì fallback về snapshot. Raw JSON gốc được ghi nguyên vẹn, sau đó mới parse.
- **Clean:** chuẩn hóa text và list (bỏ phần tử rỗng/trùng), parse ngày bằng `pd.to_datetime(..., utc=True)`, `age_days = (run_date − published).days` (cả hai được normalize về 00:00 UTC), sinh `authors_joined`, `categories_joined`, `summary_chars`, và `text_for_embedding` 5 dòng `Title/Authors/Published/Categories/Summary`. Lọc dòng xấu, dedup theo `paper_id` giữ bản `updated` mới nhất, sort theo `published` giảm dần.
- **Repair:** không "vá" dữ liệu bẩn mà dựng lại từ raw bất biến bằng đúng hàm cleaning; chạy 2 lần và so sánh DataFrame để chứng minh idempotent.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref JSON (`message.items[]`) hoặc `crossref_records.json`; `run_date` (datetime UTC) |
| Output | `list[PaperRecord]`; DataFrame 16 cột: 11 cột gốc + `age_days`, `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding` |
| Module phụ thuộc | `core/config.py` (paths, query, filter), `core/utils.py` (`normalize_whitespace`, `read_json`, `write_json`) |
| Module sử dụng output | `retrieval/index.py`, `observability/quality.py`, `evaluation/testset.py`, `ingestion/corruption.py`, `pipelines/*` |
| Điều kiện lỗi cần xử lý | API 429/503/timeout; item thiếu abstract/DOI; `date-parts` thiếu tháng/ngày; bản ghi trùng `paper_id`; raw records rỗng/hỏng khi repair (fallback sang raw response) |

### Cách xác minh

```bash
cd src
../.venv/Scripts/python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
../.venv/Scripts/python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
cd ..
.venv/Scripts/python -m pytest -q tests
```

- **Kết quả mong đợi:** 24 bài báo; 24 dòng clean; test pass.
- **Kết quả thực tế:** `Đã tải 24 bài báo`, `Clean thành công 24 dòng`, `7 passed`.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json`, `data/clean/papers_clean.json`, `data/clean/papers_clean_repaired.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `fetch_source_records` có nên luôn gọi Crossref API mỗi lần chạy hay không.
- **Các phương án đã cân nhắc:** (1) luôn gọi API, chỉ dùng snapshot khi lỗi; (2) mặc định dùng snapshot đã có, chỉ gọi API khi bật `REFRESH_SOURCE=1` hoặc chưa có snapshot.
- **Phương án đã chọn:** (2).
- **Lý do:** Gọi API mỗi lần sẽ ghi đè snapshot bằng tập bài báo khác (Crossref trả kết quả thay đổi theo thời gian), làm test set và các metric Baseline/Corrupted/Repaired không còn so sánh được với nhau, đồng thời dễ dính rate limit. Chọn (2) đổi lại tính "mới" của dữ liệu lấy tính tái lập (reproducibility) — phù hợp với mục tiêu đo lường của lab. Config sẵn có cờ `REFRESH_SOURCE` nên không cần thêm tham số mới.
- **Bằng chứng quyết định phù hợp:** sau khi chạy, `git status` không ghi nhận thay đổi ở `data/raw/`; chạy lại `run_phase1.py` nhiều lần đều cho cùng 24 bản ghi và cùng baseline metrics.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ModuleNotFoundError: No module named 'pandas'` khi chạy lệnh kiểm tra bước cleaning.
- **Lệnh hoặc bước tái hiện:** chạy `python -c "import pandas"` bằng interpreter `python` mặc định của hệ thống.
- **Nguyên nhân gốc:** lệnh `python` trong terminal trỏ tới Python global, không phải `.venv` của project nơi đã cài dependencies từ `pyproject.toml`.
- **Cách xử lý:** chạy mọi lệnh bằng interpreter của venv (`.venv/Scripts/python`) hoặc kích hoạt venv trước; package được cài dạng editable nên `script/run_phase1.py` import được `pipelines`, `core`… mà không cần chỉnh `sys.path`.
- **Cách xác minh sau khi sửa:** `.venv/Scripts/python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"` in đúng `Môi trường sẵn sàng`.
- **Điều học được:** luôn xác định rõ interpreter đang dùng trước khi debug lỗi import; lỗi môi trường dễ bị nhầm thành lỗi code.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** API (hoặc snapshot) → raw JSON gốc được lưu nguyên vẹn → parse thành `PaperRecord` (`crossref_records.json`) → `build_clean_dataframe` chuẩn hóa và sinh `text_for_embedding` → quality gate GX + freshness → embed bằng `all-MiniLM-L6-v2` → nạp vào ChromaDB collection `papers-baseline` (24 docs, metadata gồm tác giả, ngày, categories, summary).
2. **Evaluation set:** 10 câu hỏi thuộc 4 nhóm (summary, authors, date, categories), mỗi câu có `ground_truth` và `ground_truth_doc_ids`. Retrieval hit = có ít nhất một doc id đúng trong top-k; answer quality đo bằng token F1 với ground truth và LLM judge (Gemini).
3. **Quality checks vs freshness:** quality checks (GX) kiểm tra tính đúng của từng bản ghi/bảng — số dòng, null, unique `paper_id`, độ dài title/summary; freshness đo độ cũ của cả tập dữ liệu — tỷ lệ bài có `age_days > 180` không được vượt 25%. Dữ liệu có thể hợp lệ về schema nhưng vẫn "cũ".
4. **Cùng test set:** nếu câu hỏi thay đổi thì chênh lệch metric có thể do câu hỏi dễ/khó hơn chứ không phải do dữ liệu; giữ nguyên test set giúp cô lập biến duy nhất là chất lượng dữ liệu.
5. **Repair thành công khi:** `repaired_quality_report.json` 9/9 PASS, `repaired_freshness_report.json` `is_fresh: true`, và `repaired_metrics.json` bằng `baseline_metrics.json` (hit rate 1.0, token F1 1.0, judge accuracy 1.0).

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | 2/10 câu mất doc đúng do bị drop (20% bài mới nhất) hoặc title bị cắt nên không còn khớp |
| `mean_token_f1` | 1.0000 | 0.8588 | 1.0000 | Giảm chủ yếu ở nhóm `summary` (F1 0.5294): 1 bài bị blank summary, 1 bài bị cắt title nên retrieval trượt |
| `judge_accuracy` | 1.0000 | 0.9000 | 1.0000 | LLM judge khoan dung hơn token F1 với câu trả lời lệch một phần |
| `mean_judge_score` | 5.0000 | 4.5000 | 5.0000 | Giảm nhẹ nhưng không báo lỗi — đúng kiểu silent failure |
| Quality checks | 9/9 PASS | 5/9 FAIL | 9/9 PASS | Bắt được unique `paper_id`, độ dài title, độ dài summary, `age_days` |
| Freshness status | FRESH (1/24 stale) | STALE (8/22 = 36%) | FRESH (1/24 stale) | Stale date đẩy tỷ lệ bài cũ vượt ngưỡng 25% |

### Kết luận từ số liệu

1. Blank summary + inject noise + truncate title + stale date + duplicate → GX FAIL 4/9 expectation và freshness chuyển STALE (36%) → token F1 giảm 0.1412, hit rate giảm 0.2, trong khi pipeline vẫn chạy exit code 0.
2. Rebuild từ `crossref_records.json` bằng cùng hàm cleaning → GX 9/9 PASS, freshness FRESH → cả 4 metric phục hồi đúng về mức baseline.

**Corruption ảnh hưởng rõ nhất:** nhóm câu hỏi `summary` (token F1 từ 1.0 xuống 0.5294). Câu trả lời lấy câu đầu của `summary`: bài `…1803` bị xóa rỗng summary nên câu trả lời rỗng; bài `…1805` bị cắt title còn 6 ký tự nên không tra đúng được bài và retrieval trượt. Ngược lại, `inject_noise` rơi vào 2 bài được hỏi về authors/date — các câu này đọc metadata chứ không đọc summary nên vẫn đúng, cho thấy mức độ ảnh hưởng phụ thuộc vào việc cột nào bị hỏng và câu hỏi dùng cột nào.

**Kết quả khác kỳ vọng:** tôi kỳ vọng stale date làm sai các câu hỏi `date`, nhưng F1 của nhóm `date` vẫn 1.0. Kiểm tra `corruption_log.json` thì các bài bị lùi ngày không trùng với 2 bài được hỏi về ngày trong test set — nghĩa là test set nhỏ (10 câu) không phủ hết các loại lỗi; freshness monitoring là tín hiệu duy nhất phát hiện được stale date trong lần chạy này.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Luôn lưu raw response nguyên vẹn trước khi biến đổi: nó là lineage anchor cho phép repair idempotent mà không phụ thuộc API ngoài.
2. Quality checks và freshness là hai lớp khác nhau; cần cả hai vì stale date lọt qua các check schema nhưng bị freshness bắt.
3. Dữ liệu bẩn không làm RAG agent crash mà chỉ làm câu trả lời kém đi — không có quality gate thì lỗi sẽ không ai thấy.

### Nếu có thêm thời gian

Mở rộng test set để mỗi loại corruption chắc chắn chạm ít nhất một câu hỏi (ví dụ sinh câu hỏi `date` cho các bài có `published` gần ngưỡng), rồi đo lại mức sụt F1 theo từng loại corruption riêng lẻ (chạy 6 lần, mỗi lần một lỗi) để định lượng tác động của từng lỗi.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Lê Ngọc Bảo
**Ngày xác nhận:** 2026-09-26
