# Báo cáo cá nhân — Cao Đức Hiếu

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Cao Đức Hiếu |
| MSSV | 2A202602701 |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | Noob |
| Vai trò chính | Data Observability & Benchmark Evaluation |
| Repository | https://github.com/thailuong1008-coder/K4-L3B-Day10-Noob-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Data Quality Gate | `src/observability/quality.py` — `run_data_quality_checks()` | Cleaned DataFrame và `Settings` | Báo cáo GX cho baseline, corrupted và repaired | Hoàn thành |
| Freshness SLA | `evaluate_freshness_sla()`, `build_freshness_report()` | Cột `age_days`, `published` | Freshness status, stale ratio và khoảng ngày xuất bản | Hoàn thành |
| Benchmark test set | `src/evaluation/testset.py` — `build_test_set()` | Cleaned DataFrame | `data/eval/test_set.json` gồm 10 câu hỏi | Hoàn thành |
| Báo cáo kết quả | `src/observability/reporting.py` | Metrics, quality và freshness reports | `phase1_report.md`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Kiểm tra template câu hỏi và câu trả lời | RAG/QA module | Bốn dạng câu hỏi `summary`, `authors`, `date`, `categories` trả về đúng ground truth |
| Kiểm thử tích hợp | Pipeline Integrator | Xác minh quality gate thay đổi `PASS → FAIL → PASS` qua ba trạng thái |
| Phân tích kết quả corruption | Corruption & Repair flow | Đối chiếu Hit Rate, Token F1, LLM Judge và Freshness SLA |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Thiết lập GX 1.x Ephemeral Context | `run_data_quality_checks()` | Sáu phép kiểm tra từ bốn loại expectation bắt buộc | `baseline_quality_report.json` có `success: true` |
| Giám sát freshness | `evaluate_freshness_sla()` | Cảnh báo khi tỷ lệ dòng cũ vượt 25% | Corrupted đạt 33,33% và trả về `is_fresh: false` |
| Sinh benchmark | `build_test_set()` | 10 câu hỏi: 3 summary, 3 authors, 2 date, 2 categories | `data/eval/test_set.json` |
| Xuất báo cáo ba trạng thái | `generate_corruption_report()` | Bảng Baseline/Corrupted/Repaired và mức thay đổi | `data/reports/corruption_report.md` |

Output tiêu biểu của phần việc là quality gate phát hiện dữ liệu corrupted dù pipeline vẫn có thể trả lời. Baseline và repaired đều PASS, trong khi corrupted FAIL do summary rỗng, DOI trùng và Freshness SLA vượt ngưỡng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

RAG có thể tiếp tục trả lời khi dữ liệu đầu vào đã mất bản ghi, bị rỗng, trùng lặp hoặc quá cũ. Đây là hiện tượng silent failure: hệ thống không crash nhưng độ chính xác suy giảm. Phần observability cần tạo tín hiệu định lượng để phát hiện trạng thái này và phần evaluation cần dùng cùng một benchmark để đo tác động công bằng.

### Cách triển khai

Quality gate dùng Great Expectations 1.x với Ephemeral Context và Pandas Data Source. DataFrame được đưa vào whole-dataframe batch, sau đó kiểm tra số dòng từ 5 đến 5000; `paper_id`, `title`, `text_for_embedding` không null; `paper_id` duy nhất; và `summary` dài tối thiểu 30 ký tự.

Freshness SLA chuyển `age_days` sang dạng số, đếm số dòng có tuổi lớn hơn 180 ngày và tính `stale_ratio`. Dữ liệu chỉ được xem là fresh khi có dữ liệu hợp lệ và tỷ lệ stale không vượt 25%.

Benchmark lấy 10 tài liệu hoàn chỉnh, không trùng DOI. Các loại câu hỏi được phân bổ gần đều thành 3 summary, 3 authors, 2 date và 2 categories. Câu summary dùng câu đầu tiên làm ground truth; mỗi câu giữ DOI trong `ground_truth_doc_ids` để đo retrieval hit.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | DataFrame sạch có `paper_id`, `title`, `summary`, `authors`, `categories`, `published`, `age_days`, `text_for_embedding` |
| Output | Dictionary quality có `success`; freshness report; test set JSON; báo cáo Markdown |
| Module phụ thuộc | `core.config`, `core.utils`, Pandas, Great Expectations 1.x |
| Module sử dụng output | `pipelines.phase1`, `pipelines.corruption_flow`, `evaluation.metrics` |
| Điều kiện lỗi cần xử lý | Thiếu cột, null, DOI trùng, summary ngắn, ngày không hợp lệ, thiếu đủ 10 tài liệu benchmark |

### Cách xác minh

```powershell
python -m unittest discover -s tests -v
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline PASS, corrupted FAIL, repaired PASS; báo cáo có đủ ba cột so sánh.
- **Kết quả thực tế:** 13 tests đạt; Hit Rate `100% → 50% → 100%`; Token F1 `1.0000 → 0.7788 → 1.0000`.
- **Artifact/log:** `data/quality/`, `data/eval/test_set.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần xác định quality gate tổng thể có nên PASS khi các expectation GX đạt nhưng dữ liệu đã quá cũ hay không.
- **Các phương án đã cân nhắc:** Tách freshness thành cảnh báo độc lập; hoặc kết hợp freshness với kết quả GX thành trạng thái chung.
- **Phương án đã chọn:** `success = gx_success and freshness["is_fresh"]`.
- **Lý do:** Dữ liệu đúng schema nhưng lỗi thời vẫn có thể làm RAG trả lời sai. Một gate thống nhất giúp pipeline và báo cáo không bỏ sót rủi ro freshness.
- **Bằng chứng quyết định phù hợp:** Dữ liệu corrupted có stale ratio 33,33%, vượt ngưỡng 25%, nên gate FAIL; repaired còn 4,17% và gate PASS.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `NotImplementedError("Student task: implement quality checks.")` khi pipeline gọi quality gate.
- **Lệnh hoặc bước tái hiện:** Chạy `python script/run_phase1.py` trên scaffold ban đầu.
- **Nguyên nhân gốc:** `run_data_quality_checks()` và `build_freshness_report()` mới chỉ có pseudo-code, chưa có triển khai GX 1.x và chưa ghi artifact.
- **Cách xử lý:** Tạo Ephemeral Context, khai báo Pandas batch, chạy các expectations, bổ sung freshness SLA và ghi báo cáo JSON.
- **Cách xác minh sau khi sửa:** Bộ kiểm thử quality kiểm tra dữ liệu hợp lệ, null, duplicate, summary ngắn, thiếu cột và ranh giới freshness 25%; tất cả đều đạt.
- **Điều học được:** Kiểm tra schema và nội dung chưa đủ; freshness cần được đo riêng và kết hợp vào quyết định cuối của gate.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả về JSON gốc, pipeline lưu raw snapshot và bóc tách thành `PaperRecord`. Cleaning chuẩn hóa nội dung, tính `age_days`, khử trùng DOI và tạo `text_for_embedding`. MiniLM biến văn bản thành vector rồi ChromaDB lưu vector cùng metadata.
2. Evaluation set chứa câu hỏi, ground truth và DOI đúng. DOI được so với các document ID truy xuất để tính Hit Rate; câu trả lời được so với ground truth để tính Token F1 và LLM Judge.
3. Quality checks kiểm tra số lượng, null, uniqueness và độ dài nội dung. Freshness monitoring đo tuổi dữ liệu và tỷ lệ bài quá 180 ngày. Một dataset có thể đúng schema nhưng vẫn không fresh.
4. Dùng cùng test set giúp thay đổi metric phản ánh sự thay đổi của dữ liệu, không phải do đổi câu hỏi hoặc ground truth giữa các lần chạy.
5. Repair thành công khi dữ liệu được dựng lại từ raw snapshot, quality và freshness quay lại PASS, đồng thời Hit Rate và Token F1 trở lại mức baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 100% | 50% | 100% | Việc bỏ các bài mới nhất làm mất trực tiếp tài liệu ground truth |
| `mean_token_f1` | 1.0000 | 0.7788 | 1.0000 | Dữ liệu lỗi làm giảm mức trùng khớp nội dung câu trả lời |
| `judge_accuracy` | 100% | 80% | 100% | OpenRouter Judge phát hiện một phần câu trả lời corrupted không còn đúng |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | Chất lượng trung bình giảm dù pipeline vẫn trả lời được |
| Quality checks | PASS | FAIL | PASS | Null/summary ngắn và DOI trùng được GX phát hiện |
| Freshness status | PASS (4,17%) | FAIL (33,33%) | PASS (4,17%) | Corruption vượt ngưỡng stale 25%; repair khôi phục tỷ lệ ban đầu |

### Kết luận từ số liệu

1. Drop latest, blank summary, duplicate và stale date → quality/freshness chuyển từ PASS sang FAIL → Hit Rate giảm 50 điểm phần trăm và Token F1 giảm 0,2212.
2. Dựng lại cleaned dataset từ raw snapshot → quality/freshness trở lại PASS → Hit Rate và Token F1 phục hồi hoàn toàn về baseline.

Drop latest records ảnh hưởng rõ nhất tới retrieval vì 5 trong 10 tài liệu ground truth của benchmark không còn trong corrupted index, khiến Hit Rate giảm trực tiếp xuống 50%.

Kết quả đáng chú ý là Token F1 vẫn còn 0,7788 và Judge Accuracy còn 80% dù quality gate FAIL. Điều này cho thấy silent failure có thể bị che khuất nếu chỉ nhìn vào việc hệ thống có trả về câu trả lời hay không. Việc đối chiếu artifact và metric xác nhận đây là ảnh hưởng thực của dữ liệu bị làm bẩn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot là điểm neo lineage giúp repair có thể lặp lại mà không phụ thuộc API ngoài.
2. Data observability cần kết hợp kiểm tra cấu trúc, nội dung và freshness thay vì chỉ kiểm tra schema.
3. Chất lượng dữ liệu tác động trực tiếp tới retrieval và câu trả lời RAG, kể cả khi ứng dụng không phát sinh exception.

### Nếu có thêm thời gian

Tôi sẽ bổ sung GitHub Actions chạy tests và một dashboard hiển thị quality status, stale ratio và biến động metric theo từng lần chạy. Hiệu quả có thể đo bằng coverage, thời gian phát hiện lỗi và khả năng quan sát xu hướng suy giảm trước khi triển khai.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Cao Đức Hiếu

**Ngày xác nhận:** 2026-09-26
