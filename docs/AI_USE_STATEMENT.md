# Khai báo sử dụng AI (AI-use statement)

*Nhóm 5 – INT4418 · cập nhật 27/10/2026*

Học phần yêu cầu khai báo mọi phần việc có AI hỗ trợ, và mọi mã nguồn, kết luận do AI hỗ trợ vẫn phải được nhóm kiểm chứng.
Dự án này dùng AI ở ba vai trò khác nhau. Không vai trò nào thay cho trách nhiệm của nhóm với sản phẩm nộp.

## 1. Công cụ và mục đích

| Công cụ | Vai trò | Phần việc |
|---|---|---|
| Claude (Anthropic), trong ứng dụng Claude; mô hình cấu hình `claude-opus-5-5` | Trợ lý lập trình và viết | Viết phần lớn mã nguồn trong `src/afp/`, test, script thí nghiệm và phân tích; chạy thí nghiệm trên máy ảo đám mây; soạn data card, system card, báo cáo, slide và tài liệu trong `docs/`. Một thành viên nhóm giao việc theo đề bài, slide môn học và hướng dẫn bài tập lớn, quyết định phạm vi (ví dụ: chỉ sinh mã cho 1.000 bài để tiết kiệm), duyệt kết quả theo từng bước. |
| Claude Haiku 5.5 | **Đối tượng thí nghiệm**: mô hình autoformalization | Sinh 1.420 phát biểu Lean ứng viên (prompt `v1_zeroshot`, `v2_fewshot`, `v1_zeroshot_1req`). Output thô được lưu nguyên trong `data/candidates.db`. |
| Claude Sonnet, Claude Opus | Người chấm thử (pilot) cho audit ngữ nghĩa | Chấm độc lập 100 mẫu để thử quy trình và hướng dẫn chấm (`audit/llm_rater_*.csv`). **Không thay cho hai người chấm của nhóm.** |

## 2. Cách kết quả do AI tạo ra được kiểm chứng

* **Lean là bộ kiểm tra hình thức.** Mọi phát biểu do mô hình sinh đều được Lean 4 / Mathlib kiểm chứng. Lean chỉ bảo đảm đúng kiểu, không bảo đảm đúng nghĩa, nên báo cáo không tuyên bố đúng nghĩa chỉ dựa vào compile.
* **Ngữ nghĩa được kiểm bằng ba lớp có đo độ tin cậy:** kiểm tra bằng Lean, heuristic, và audit hai người trên 100 mẫu (Cohen's κ). Mutation test đo bộ kiểm tra tự động bắt được bao nhiêu lỗi đã biết.
* **Mã nguồn có test:** 26 test (hàng đợi, TaskHash, sanitizer, backend, Redis, Lean REPL, cấu hình), chạy bằng `python -m pytest -q`.
* **Số liệu có nguồn:** mọi bảng và hình được script sinh lại từ `results/raw/`. Mỗi lần chạy có `run_record.json` theo mẫu Phụ lục B của hướng dẫn. Số trong báo cáo đã được đối chiếu với các file này.
* **Lỗi do chính pipeline gây ra đã được tìm và ghi lại**, ví dụ sanitizer v1 cắt nhầm `let … :=` (docs/CHANGELOG.md).

## 3. Việc nhóm phải tự làm và xác nhận trước khi nộp

Phần này để từng thành viên đánh dấu. Một ô chưa đánh dấu nghĩa là chưa kiểm chứng.

| Việc | Người thực hiện | Xong |
|---|---|---|
| Hai thành viên chấm độc lập 100 mẫu (`audit/rater1.xlsx`, `audit/rater2.xlsx`), tính κ | | ☐ |
| Mỗi người đọc và giải thích được phần mã mình phụ trách (xem `contributions.md`) | cả nhóm | ☐ |
| Chạy lại `python -m pytest -q` và một thí nghiệm nhỏ (`bash scripts/quickstart.sh`) trên máy của nhóm | | ☐ |
| Đọc lại báo cáo và slide, sửa chỗ chưa đúng với hiểu biết của nhóm | cả nhóm | ☐ |
| Kiểm tra giấy phép dữ liệu (`docs/LICENSE_PRIVACY.md`) | | ☐ |

## 4. Trách nhiệm

Nếu mô hình ngôn ngữ sinh một định lý sai, trách nhiệm thuộc về người dùng hệ thống, ở đây là nhóm, chứ không thuộc về mô hình.
Vì vậy corpus giữ kết luận và cờ ngữ nghĩa cho từng bài, và không bài nào được gọi là "đúng nghĩa" chỉ vì Lean chấp nhận.
