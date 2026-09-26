from flask import Flask, jsonify, render_template_string, request

from core.config import load_settings
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

app = Flask(__name__)

settings = load_settings()
index = LocalEmbeddingIndex(settings)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RAG / Vector Demo</title>
    <style>
        :root {
            --bg: #f6f7fb;
            --card: #ffffff;
            --border: #e4e7ee;
            --text: #1c1f2a;
            --muted: #6b7280;
            --primary: #4f46e5;
            --primary-dark: #4338ca;
            --accent-bg: #eef0ff;
        }

        * {
            box-sizing: border-box;
        }

        body {
            font-family: "Segoe UI", Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 48px 20px 80px;
            background: var(--bg);
            color: var(--text);
        }

        header {
            text-align: center;
            margin-bottom: 32px;
        }

        h1 {
            font-size: 28px;
            margin-bottom: 8px;
        }

        .subtitle {
            color: var(--muted);
            font-size: 15px;
            line-height: 1.6;
        }

        .pipeline {
            display: inline-flex;
            gap: 6px;
            flex-wrap: wrap;
            justify-content: center;
            margin-top: 12px;
        }

        .pipeline span {
            background: var(--accent-bg);
            color: var(--primary);
            font-size: 13px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 999px;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
            margin-bottom: 20px;
        }

        textarea {
            width: 100%;
            min-height: 100px;
            padding: 14px;
            font-size: 15px;
            font-family: inherit;
            border: 1px solid var(--border);
            border-radius: 10px;
            resize: vertical;
            outline: none;
            transition: border-color 0.15s ease;
        }

        textarea:focus {
            border-color: var(--primary);
        }

        .suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 14px 0 4px;
        }

        .chip {
            background: var(--accent-bg);
            color: var(--primary-dark);
            border: none;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 13px;
            cursor: pointer;
            transition: background 0.15s ease;
        }

        .chip:hover {
            background: #e0e2ff;
        }

        .actions {
            display: flex;
            justify-content: flex-end;
            margin-top: 14px;
        }

        button.ask-btn {
            background: var(--primary);
            color: #fff;
            border: none;
            padding: 11px 24px;
            font-size: 15px;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            transition: background 0.15s ease;
        }

        button.ask-btn:hover {
            background: var(--primary-dark);
        }

        button.ask-btn:disabled {
            background: #b9b9c4;
            cursor: not-allowed;
        }

        h2 {
            font-size: 17px;
            margin: 0 0 12px;
        }

        #answer {
            font-size: 15px;
            line-height: 1.7;
            color: var(--text);
            white-space: pre-wrap;
        }

        #answer.placeholder {
            color: var(--muted);
            font-style: italic;
        }

        .source {
            margin-bottom: 10px;
            padding: 12px 14px;
            background: var(--accent-bg);
            border-radius: 10px;
            font-size: 14px;
        }

        .source b {
            color: var(--primary-dark);
        }

        .source .pid {
            color: var(--muted);
            font-size: 13px;
        }

        #sources:empty::after {
            content: "Chưa có nguồn nào — hãy đặt một câu hỏi.";
            color: var(--muted);
            font-style: italic;
            font-size: 14px;
        }
    </style>
</head>
<body>

<header>
    <h1>🔍 RAG / Vector Search Demo</h1>
    <p class="subtitle">Đặt câu hỏi, hệ thống sẽ tìm tài liệu liên quan và trả lời dựa trên nội dung tìm được.</p>
    <div class="pipeline">
        <span>MiniLM Embedding</span>
        <span>→ ChromaDB</span>
        <span>→ Top-K Retrieval</span>
        <span>→ Answer + Sources</span>
    </div>
</header>

<div class="card">
    <textarea id="question" placeholder="Ví dụ: Mô hình này giải quyết vấn đề gì?"></textarea>

    <div class="suggestions">
        <button class="chip" onclick="useSuggestion(this)">Bài báo này đề xuất phương pháp gì?</button>
        <button class="chip" onclick="useSuggestion(this)">Tóm tắt đóng góp chính của nghiên cứu</button>
        <button class="chip" onclick="useSuggestion(this)">Bộ dữ liệu nào được sử dụng để đánh giá?</button>
        <button class="chip" onclick="useSuggestion(this)">Kết quả thực nghiệm cho thấy điều gì?</button>
    </div>

    <div class="actions">
        <button class="ask-btn" id="ask-btn" onclick="askQuestion()">Hỏi ngay</button>
    </div>
</div>

<div class="card">
    <h2>💬 Câu trả lời</h2>
    <div id="answer" class="placeholder">Đang chờ câu hỏi của bạn...</div>
</div>

<div class="card">
    <h2>📚 Nguồn tham khảo</h2>
    <div id="sources"></div>
</div>

<script>
function useSuggestion(el) {
    document.getElementById("question").value = el.innerText;
    document.getElementById("question").focus();
}

async function askQuestion() {
    const question = document.getElementById("question").value;
    const askBtn = document.getElementById("ask-btn");
    const answerEl = document.getElementById("answer");
    const sourcesEl = document.getElementById("sources");

    if (!question.trim()) {
        alert("Vui lòng nhập câu hỏi.");
        return;
    }

    askBtn.disabled = true;
    askBtn.innerText = "Đang tìm...";
    answerEl.classList.add("placeholder");
    answerEl.innerText = "Đang tìm kiếm tài liệu liên quan...";
    sourcesEl.innerHTML = "";

    try {
        const response = await fetch("/api/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ question })
        });

        const data = await response.json();

        if (data.error) {
            answerEl.classList.add("placeholder");
            answerEl.innerText = data.error;
            return;
        }

        answerEl.classList.remove("placeholder");
        answerEl.innerText = data.answer;

        data.sources.forEach((source, index) => {
            const div = document.createElement("div");
            div.className = "source";
            div.innerHTML =
                "<b>" + (index + 1) + ". " + source.title + "</b><br>" +
                "<span class='pid'>Paper ID: " + source.paper_id + "</span>";
            sourcesEl.appendChild(div);
        });
    } catch (err) {
        answerEl.classList.add("placeholder");
        answerEl.innerText = "Đã xảy ra lỗi khi kết nối tới máy chủ.";
    } finally {
        askBtn.disabled = false;
        askBtn.innerText = "Hỏi ngay";
    }
}

document.getElementById("question").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        askQuestion();
    }
});
</script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question is required."}), 400

    try:
        result = answer_question(
            question,
            settings,
            index,
            top_k=4,
            collection_name=settings.baseline_collection_name,
        )

        sources = [
            {
                "title": title,
                "paper_id": paper_id,
            }
            for title, paper_id in zip(
                result.retrieved_titles,
                result.retrieved_doc_ids,
            )
        ]

        return jsonify({
            "answer": result.answer,
            "sources": sources,
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)