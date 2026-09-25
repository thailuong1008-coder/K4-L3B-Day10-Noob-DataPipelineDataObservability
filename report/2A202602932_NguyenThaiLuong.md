# Báo Cáo Cá Nhân — Thành Viên 1: Trưởng Nhóm & Pipeline Integrator

> Mẫu báo cáo cá nhân dành cho Thành viên 1 theo chuẩn quy định tại `report/individual_report.md`. Hãy cập nhật lại Họ tên và MSSV trước khi nộp.

---

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| **Họ và tên** | Nguyễn Thái Lương |
| **MSSV** |2A202602932 |
| **Khóa / Lớp** | K4 - Lớp B (Ca Sáng) |
| **Tên nhóm** | Noob |
| **Vai trò chính** | Trưởng nhóm & Pipeline Integrator |
| **Repository** | `https://github.com/[org]/K4-L3B-DAY10-[TenNhom]-DataPipelineDataObservability` |
| **Ngày hoàn thành** | 2026-09-26 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu chính (Ownership)

| Module / Deliverable | File / Hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Cấu hình & Quản lý môi trường** | `src/core/config.py`, `.env` | File `.env.example`, biến môi trường | Object `Settings`, `Paths` chuẩn hóa | Hoàn thành |
| **Baseline Pipeline (Phase 1)** | `src/pipelines/phase1.py` (`run_phase1_pipeline`) | Raw records từ Ingestion, Clean DataFrame | End-to-end baseline flow, console logging, artifacts | Hoàn thành |
| **Corruption Flow & Phục hồi** | `src/pipelines/corruption_flow.py` (`run_corruption_flow`) | Clean DF, Baseline metrics, Raw snapshot | Bảng đối chiếu 3 trạng thái, so sánh đa chiều | Hoàn thành |
| **Entrypoints thực thi** | `script/run_phase1.py`, `script/run_corruption_flow.py` | CLI execution | Mã trả về `exit code 0`, điều phối | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên / Module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| **Quản trị Git & Phân nhánh** | Toàn bộ 4 thành viên | Thiết lập branch riêng (`feat/*`), chặn leak `.env` và `.venv` qua `.gitignore`. |
| **Thiết kế Contract / Interfaces** | Thành viên 2 (Data), 3 (Vector), 4 (Observability) | Thống nhất cấu trúc hàm, kiểu dữ liệu trả về giữa các module để tích hợp không lỗi. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File / Hàm liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Cấu hình dự án an toàn | `src/core/config.py`, `.env` | Nạp đúng đường dẫn tuyệt đối động, mock/gemini fallback | `python -c "from core.config import load_settings; s=load_settings(); print(s.paths.project_dir)"` |
| Orchestration Pha 1 | `src/pipelines/phase1.py` | 10 bước thực thi tuần tự có timestamp và log chi tiết | `python script/run_phase1.py` |
| Orchestration Luồng 3 trạng thái | `src/pipelines/corruption_flow.py` | 8 giai đoạn: Baseline $\to$ Corrupt $\to$ Evaluate $\to$ Repair $\to$ Bảng so sánh | `python script/run_corruption_flow.py` |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Một hệ thống RAG trong môi trường thực tế không thể chạy các đoạn mã rời rạc. Cần có một kiến trúc điều phối (Pipeline Orchestrator) quản lý toàn bộ vòng đời dữ liệu: từ thu thập, làm sạch, lập chỉ mục vector, kiểm định chất lượng, đánh giá định lượng đến phục hồi dữ liệu khi xảy ra sự cố.

### Cách triển khai
1. **Kiến trúc Interface-driven / Contract-driven:**
   - Xây dựng 2 hàm điều phối cấp cao `run_phase1_pipeline()` và `run_corruption_flow()`.
   - Mỗi bước được thiết kế độc lập, có cơ chế bắt lỗi `NotImplementedError` để thông báo rõ ràng cho từng thành viên module nào chưa hoàn tất.
2. **Quản lý trạng thái đa tầng (State Management):**
   - Cô lập rõ ràng 3 không gian dữ liệu: Baseline (sạch), Corrupted (bị tiêm lỗi), và Repaired (phục hồi).
   - Đảm bảo tính Idempotency: Có thể chạy lại pipeline nhiều lần mà không bị lỗi ghi đè rác hoặc trùng lặp dữ liệu vector.
3. **Hiển thị trực quan (Visual Feedback):**
   - Tích hợp hàm in bảng đối chiếu ASCII trực tiếp trên Terminal để phục vụ Live Demo (CP6) trực quan cho Giảng viên xem.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi khởi chạy lần đầu trên máy trạm hoặc môi trường CI, nếu chưa có `GOOGLE_API_KEY`, pipeline sẽ crash ngay lập tức ở bước khởi tạo LLM.
- **Phương án cân nhắc:**
  1. *Phương án A:* Bắt buộc người dùng phải điền API key ngay từ đầu, nếu thiếu thì abort chương trình.
  2. *Phương án B:* Thiết lập `LLM_PROVIDER=mock` làm mặc định an toàn trong `.env`, đồng thời hỗ trợ chuyển đổi linh hoạt sang `gemini` khi người dùng nhập key.
- **Phương án đã chọn:** Phương án B.
- **Lý do:** Giúp toàn bộ nhóm có thể kiểm thử toàn bộ luồng data pipeline, data quality gate, và chroma indexing hoàn toàn offline mà không bị phụ thuộc vào quota API hoặc chi phí.

---

## 6. Hiểu biết về luồng End-to-End

1. **Dữ liệu đi từ Crossref đến Vector Index như thế nào?**
   - API Crossref trả về JSON metadata thô $\to$ Lưu vào `crossref_response.json` (Lineage) $\to$ Parse thành list `PaperRecord` $\to$ Module `cleaning.py` loại bỏ tag rác, tính `age_days`, tạo `text_for_embedding` $\to$ Model `all-MiniLM-L6-v2` chuyển đổi text thành vector 384 chiều $\to$ Nạp vào collection ChromaDB.
2. **Vì sao phải dùng cùng một Test Set cho cả 3 trạng thái?**
   - Để đảm bảo tính nhất quán khoa học (Controlled Experiment). Nếu thay đổi bộ câu hỏi giữa Baseline và Corrupted, ta không thể biết sự sụt giảm hiệu năng là do dữ liệu bẩn hay do câu hỏi khó hơn.
3. **Thế nào là một Idempotent Repair thành công?**
   - Khi dữ liệu bẩn bị loại bỏ hoàn toàn, dữ liệu được tái tạo từ nguồn snapshot gốc đáng tin cậy (`crossref_records.json`), chỉ số Hit Rate & Token F1 phục hồi tương đương Baseline, và Quality Gate của GX 1.x trả về `success=True`.
