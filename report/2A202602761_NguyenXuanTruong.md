# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                             |
| --------------- | ------------------------------------ |
| Họ và tên       | Nguyễn Xuân Trường                   |
| MSSV            | 2A202601761                          |
| Khóa/Lớp        | K4                                   |
| Tên nhóm        | Noob                                 |
| Vai trò chính   | Member 3 — RAG & Vector Index        |
| Repository      | [Điền đường dẫn repository của nhóm] |
| Ngày hoàn thành | 2026-09-26                           |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                               | File/hàm phụ trách                                                                           | Input nhận vào                                                                    | Output bàn giao                                                                | Trạng thái |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------- |
| Vector embedding và vector index                 | `src/retrieval/embeddings.py`, `src/retrieval/index.py`                                      | Dataset đã xử lý, trường `text_for_embedding`, embedding model `all-MiniLM-L6-v2` | ChromaDB collections: `papers-baseline`, `papers-corrupted`, `papers-repaired` | Hoàn thành |
| Retrieval evaluation và corruption/repaired flow | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `src/ingestion/corruption.py` | Evaluation set, các collection và dataset baseline/corrupted/repaired             | Retrieval metrics, answer artifacts và comparison report                       | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                               | Thành viên/module được hỗ trợ     | Kết quả                                                                   |
| --------------------------------------- | --------------------------------- | ------------------------------------------------------------------------- |
| Tích hợp và kiểm tra pipeline retrieval | Các module pipeline/evaluation    | Xác minh baseline, corrupted và repaired sử dụng cùng evaluation flow     |
| Kiểm tra demo RAG/Vector                | `src/retrieval/qa.py` và ChromaDB | Chạy được câu hỏi → retrieval → answer → sources mà không cần LLM API key |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                         | File/hàm/artifact liên quan                     | Kết quả bàn giao                                                           | Cách xác minh                             |
| --------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------- |
| Xây dựng embedding bằng MiniLM                | `src/retrieval/embeddings.py`                   | Embedding bằng `sentence-transformers/all-MiniLM-L6-v2`                    | Chạy retrieval và model load thành công   |
| Xây dựng local vector index bằng ChromaDB     | `src/retrieval/index.py`                        | Collections `papers-baseline`, `papers-corrupted`, `papers-repaired`       | Search/lookup trả về document và metadata |
| Chạy baseline retrieval evaluation            | `src/pipelines/phase1.py`                       | `data/results/baseline_metrics.json`, `data/results/baseline_answers.json` | Phase 1 pipeline                          |
| Tạo corrupted dataset và đánh giá             | `src/ingestion/corruption.py`                   | `data/results/corruption_log.json`, `data/results/corrupted_metrics.json`  | Corruption flow                           |
| Repair và so sánh baseline/corrupted/repaired | `src/pipelines/corruption_flow.py`              | `data/results/repaired_metrics.json`, `data/reports/corruption_report.md`  | Chạy corruption flow                      |
| Demo RAG/vector                               | `src/retrieval/qa.py`, `src/retrieval/index.py` | Top-4 sources và answer từ baseline collection                             | Python CLI demo                           |

Một output cụ thể của phần việc là comparison report:

`data/reports/corruption_report.md`

Report ghi nhận:

* Baseline retrieval hit rate: `1.0`
* Corrupted retrieval hit rate: `0.6`
* Repaired retrieval hit rate: `1.0`

Ngoài ra, demo retrieval trả về 4 nguồn từ collection `papers-baseline`, chứng minh vector search hoạt động trên dữ liệu thực tế của lab.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần RAG & Vector Index cần biến dữ liệu scholarly papers đã được xử lý thành một vector index để hệ thống có thể tìm các tài liệu liên quan đến câu hỏi. Sau đó retrieval phải được đánh giá trên cùng một evaluation set trước và sau khi dữ liệu bị corruption và repair.

### Cách triển khai

Dữ liệu được chuyển thành trường `text_for_embedding` và được encode bằng `sentence-transformers/all-MiniLM-L6-v2`.

Embedding được chuẩn hóa và đưa vào ChromaDB với cosine distance. Mỗi document được lưu cùng document content và metadata như title, publication information và các trường phục vụ QA.

`LocalEmbeddingIndex` hỗ trợ:

* build collection từ DataFrame;
* tạo embedding cho documents;
* lưu documents, embeddings và metadata vào ChromaDB;
* semantic search theo query;
* exact lookup theo title.

Ba collection được sử dụng tương ứng với ba trạng thái dữ liệu:

* `papers-baseline`
* `papers-corrupted`
* `papers-repaired`

Để tránh lỗi duplicate ID khi corrupted data tạo duplicate rows, ChromaDB ID của bản ghi trùng được thêm suffix như `__duplicate_1`, trong khi metadata gốc vẫn được giữ.

### Input, output và contract

| Thành phần              | Mô tả                                                                                                |
| ----------------------- | ---------------------------------------------------------------------------------------------------- |
| Input                   | Dataset papers có `paper_id`, metadata và `text_for_embedding`; evaluation questions                 |
| Output                  | ChromaDB vector collections, retrieved documents, answer và retrieval metrics                        |
| Module phụ thuộc        | `core.config`, `retrieval.embeddings`, ChromaDB, sentence-transformers                               |
| Module sử dụng output   | `retrieval.qa`, pipeline evaluation, corruption flow và reporting                                    |
| Điều kiện lỗi cần xử lý | Collection không tồn tại, duplicate paper IDs, dữ liệu thiếu metadata, query không tìm thấy document |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; from retrieval.qa import answer_question; s=load_settings(); i=LocalEmbeddingIndex(s); r=answer_question('What are the main topics discussed in the indexed papers?', s, i, top_k=4, collection_name=s.baseline_collection_name); print('ANSWER:'); print(r.answer); print(); print('SOURCES:'); [print(f'{n}. {t} ({d})') for n,(t,d) in enumerate(zip(r.retrieved_titles,r.retrieved_doc_ids),1)]"
```

* **Kết quả mong đợi:** Query được embedding, ChromaDB trả về Top-K documents và pipeline trả về answer cùng source documents.
* **Kết quả thực tế:** Thành công. Pipeline trả về answer và 4 sources.
* **Artifact/log:** `data/results/baseline_metrics.json`, `data/results/baseline_answers.json`, `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json`, `data/reports/corruption_report.md`.

Demo thực tế trả về 4 nguồn:

1. `Advanced Perspectives on Mitigating Ghost Vectors in Dense Retrieval via Idempotent Indexing`
2. `Advanced Perspectives on Hybrid Search Architectures: Combining BM25 with Dense Representations`
3. `Mitigating Ghost Vectors in Dense Retrieval via Idempotent Indexing`
4. `Hybrid Search Architectures: Combining BM25 with Dense Representations`

## 5. Một quyết định kỹ thuật quan trọng

* **Bối cảnh:** Cần xây dựng vector index có thể tái sử dụng cho baseline, corrupted và repaired dataset để so sánh retrieval một cách nhất quán.
* **Các phương án đã cân nhắc:** Dùng một vector store bên ngoài hoặc sử dụng ChromaDB local; embedding có thể được tạo bằng model embedding khác hoặc `all-MiniLM-L6-v2`.
* **Phương án đã chọn:** ChromaDB local kết hợp `sentence-transformers/all-MiniLM-L6-v2`.
* **Lý do:** ChromaDB phù hợp với môi trường local của lab, không yêu cầu dịch vụ vector database bên ngoài. Việc sử dụng cùng embedding model cho các collection giúp giảm thay đổi ngoài ý muốn khi so sánh baseline/corrupted/repaired.
* **Bằng chứng quyết định phù hợp:** Baseline retrieval hit rate đạt `1.0`, corrupted giảm xuống `0.6`, sau repair trở lại `1.0`.

## 6. Một lỗi hoặc blocker đã xử lý

* **Triệu chứng/lỗi nguyên văn:**

```text
RuntimeError: GOOGLE_API_KEY is required when LLM_PROVIDER=gemini.
```

Sau đó khi thử mock LLM:

```text
NotImplementedError
During task with name 'model'...
```

Ngoài ra có lỗi model Gemini không khả dụng cho tài khoản hiện tại:

```text
GoogleModelNotFoundError: Error calling model 'gemini-2.5-flash' (NOT_FOUND)
```

* **Lệnh hoặc bước tái hiện:** Chạy LangChain Agent demo thông qua `build_agent()` và `run_agent_question()`.
* **Nguyên nhân gốc:** Agent sử dụng LLM provider và cần model có khả năng hỗ trợ tool calling. `FakeListChatModel` không implement `bind_tools()`, còn Gemini configuration yêu cầu API key/model khả dụng.
* **Cách xử lý:** Không phụ thuộc LLM Agent để xác minh phần Vector/RAG cốt lõi. Sử dụng trực tiếp `retrieval.qa.answer_question()` kết hợp `LocalEmbeddingIndex`, MiniLM và ChromaDB.
* **Cách xác minh sau khi sửa:** Chạy trực tiếp retrieval QA command. Kết quả trả về answer và Top-4 sources thành công.
* **Điều học được:** Vector retrieval và LLM generation là hai lớp khác nhau. Có thể kiểm tra embedding, vector search, retrieved context và source provenance độc lập với LLM API.

## 7. Hiểu biết về luồng end-to-end

### 1. Dữ liệu đi từ Crossref đến vector index như thế nào?

Crossref được sử dụng làm nguồn dữ liệu scholarly papers. Dữ liệu được ingestion và xử lý thành các record có metadata và nội dung dùng cho embedding. Trường `text_for_embedding` được đưa qua `all-MiniLM-L6-v2` để tạo vector. Các vector cùng document và metadata được lưu trong ChromaDB. Retrieval sau đó embed query bằng cùng embedding model và tìm các document gần nhất trong collection.

### 2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?

Evaluation set chứa câu hỏi cùng document ID được xem là ground truth. Với mỗi câu hỏi, hệ thống retrieval lấy Top-K documents và kiểm tra ground-truth document có xuất hiện trong kết quả hay không. Điều này tạo ra `retrieval_hit_rate`. Các answer sau retrieval tiếp tục được đánh giá bằng token F1 và judge metrics.

### 3. Quality checks khác freshness monitoring ở điểm nào?

Quality checks kiểm tra chất lượng và tính hợp lệ của dữ liệu, ví dụ dữ liệu thiếu trường, summary rỗng hoặc các điều kiện chất lượng khác.

Freshness monitoring tập trung vào tuổi của dữ liệu, đặc biệt là ngày publication và số lượng record vượt quá `freshness_threshold_days`.

Nói cách khác, một dataset có thể có cấu trúc hợp lệ nhưng vẫn không fresh.

### 4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?

Cùng một evaluation set giúp giữ nguyên điều kiện đo. Khi đó thay đổi về retrieval hoặc answer quality có thể được liên hệ với trạng thái dữ liệu thay vì do test questions khác nhau.

### 5. Repair được xem là thành công dựa trên artifact và metric nào?

Repair được kiểm tra thông qua repaired dataset, repaired metrics và comparison report. Trong kết quả thực tế, retrieval hit rate giảm từ `1.0` ở baseline xuống `0.6` ở corrupted và trở lại `1.0` ở repaired. Mean token F1 cũng trở lại baseline `0.396534...`, judge accuracy trở lại `0.5` và mean judge score trở lại `2.4`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal        | Baseline | Corrupted | Repaired | Nhận xét của cá nhân                                                                  |
| -------------------- | -------: | --------: | -------: | ------------------------------------------------------------------------------------- |
| `retrieval_hit_rate` |      1.0 |       0.6 |      1.0 | Corruption làm giảm khả năng tìm đúng document; repair đưa metric về baseline         |
| `mean_token_f1`      | 0.396534 |  0.122929 | 0.396534 | Answer quality giảm mạnh trên corrupted data và phục hồi về mức baseline              |
| `judge_accuracy`     |      0.5 |       0.1 |      0.5 | Judge accuracy giảm rõ rệt khi dữ liệu bị corruption                                  |
| `mean_judge_score`   |      2.4 |       1.2 |      2.4 | Điểm đánh giá answer giảm một nửa ở corrupted dataset                                 |
| Quality checks       |        - |     False |    False | Corrupted không đạt quality check; repaired vẫn còn stale row theo threshold hiện tại |
| Freshness status     |        - |     False |    False | Corrupted và repaired đều có stale row theo freshness threshold                       |

### Kết luận từ số liệu

**1. Data corruption → quality/freshness signal thay đổi → agent metric thay đổi**

Corruption làm dataset từ 24 rows xuống 21 rows và đồng thời áp dụng các biến đổi như blank summary, noise, truncate title, stale date và duplicate rows. Retrieval hit rate giảm từ `1.0` xuống `0.6`. Mean token F1 giảm từ khoảng `0.397` xuống `0.123`, judge accuracy giảm từ `0.5` xuống `0.1`, và mean judge score giảm từ `2.4` xuống `1.2`.

**2. Repair action → quality/freshness signal phục hồi → agent metric phục hồi**

Sau repair, dataset trở lại 24 rows và các retrieval metrics trở lại đúng mức baseline: retrieval hit rate `1.0`, mean token F1 `0.396534`, judge accuracy `0.5`, mean judge score `2.4`.

### Corruption nào ảnh hưởng rõ nhất và vì sao?

Trong kết quả tổng hợp, không thể tách riêng chính xác mức ảnh hưởng của từng corruption operation chỉ từ các aggregate metrics hiện có, vì nhiều corruption được áp dụng trên cùng một corrupted dataset. Tuy nhiên, các thay đổi trực tiếp vào nội dung dùng cho retrieval như blank summary, noise và truncate title có khả năng làm thay đổi nội dung/index representation; việc drop rows cũng trực tiếp làm mất documents có thể là ground truth.

Bằng chứng chắc chắn từ aggregate evaluation là **tổng hợp corruption đã làm retrieval hit rate giảm từ `1.0` xuống `0.6` và answer metrics giảm mạnh**.

### Kết quả nào khác với kỳ vọng ban đầu?

Quality check của repaired dataset vẫn là `False` vì freshness report còn ghi nhận `1` stale row. Điều này cho thấy repair trong pipeline đã phục hồi retrieval/answer metrics về baseline nhưng không làm tất cả freshness conditions trở thành `True`.

Điều này giúp phân biệt hai khái niệm: **retrieval repair thành công không đồng nghĩa mọi data-quality/freshness check đều đạt**.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Điều học được về data pipeline:** Thay đổi dữ liệu đầu vào có thể trực tiếp làm thay đổi kết quả của downstream retrieval. Vì vậy pipeline cần có bước kiểm tra dữ liệu trước khi indexing.

2. **Điều học được về data quality/observability:** Không nên chỉ nhìn vào một metric. Quality checks, freshness signals và retrieval metrics bổ sung cho nhau để phát hiện vấn đề ở các tầng khác nhau.

3. **Điều học được về ảnh hưởng của data đến RAG agent:** Khi corrupted data làm retrieval hit rate giảm từ `1.0` xuống `0.6`, các answer metrics cũng giảm mạnh. Điều này cho thấy chất lượng retrieved context có ảnh hưởng trực tiếp đến chất lượng câu trả lời.

### Nếu có thêm thời gian

Có thể bổ sung evaluation riêng cho từng loại corruption thay vì chỉ đánh giá aggregate corrupted dataset. Mỗi corruption operation sẽ được chạy độc lập và đo `retrieval_hit_rate`, `mean_token_f1` và judge metrics. Cách này giúp xác định chính xác loại corruption nào gây ảnh hưởng lớn nhất và giúp lựa chọn data-quality check phù hợp.

## 10. Cam kết của thành viên

* [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
* [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
* [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
* [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
* [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
* [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Xuân Trường

**Ngày xác nhận:** 2026-09-26
