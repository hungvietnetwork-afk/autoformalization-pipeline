# Đóng góp và phân vai – Nhóm 5

> **Cần nhóm xác nhận trước khi nộp.** Bảng dưới đây gán sáu vai trò của hướng dẫn (Nhóm 5, mục 5) theo thứ tự danh sách thành viên.
> Đây chỉ là đề xuất. Nhóm sửa lại cho đúng người thực sự làm từng phần, rồi điền issue và pull request trên repository của nhóm.
> Các commit hiện có được tạo với sự hỗ trợ của trợ lý AI (xem `docs/AI_USE_STATEMENT.md`). Commit, issue và PR từ đây trở đi là bằng chứng đóng góp cá nhân.

## Phân vai (mỗi vai trò có người chính và người dự phòng)

| Vai trò (hướng dẫn) | Nhóm vai trò (slide môn học) | Người chính | Dự phòng | Phần phụ trách trong repository | Phần trình bày / bảo vệ |
|---|---|---|---|---|---|
| 1. Data / evaluation | Data | Nguyễn Mai Hạnh (B25CHHT093) | Bùi Giang Linh | `src/afp/ingest.py`, `src/afp/schema.py`, `data/`, `data_sample/`, `docs/DATA_CARD.md`, `data/MANIFEST.json` | Dữ liệu, schema `DataUnit`, khóa phân vùng, các split cố định, nhãn dữ liệu bị nhiễu |
| 2. Prompt & model | Model | Lê Quang Đức (B25CHHT086) | Nguyễn Việt Hưng | `src/afp/prompts.py`, `src/afp/inference/`, `data/jobs/`, `docs/PROMPTS.md` | Prompt có phiên bản, baseline một bài mỗi request, batching ở tầng inference, token và chi phí |
| 3. Batch scheduler | System | Nguyễn Việt Hưng (B25CHHT099) | Lê Quang Đức | `src/afp/queue.py`, `src/afp/redis_backend.py`, `src/afp/workers.py` (inference), `src/afp/pipeline.py` | Hàng đợi phân vùng, lease / retry / dead-letter, batch size, Redis, giết worker |
| 4. Lean worker pool | System | Kim Anh Dũng (B25CHHT087) | Vũ Quốc Hùng | `src/afp/lean/`, `src/afp/workers.py` (verifier), `scripts/setup_lean.sh` | REPL nóng, heartbeat và timeout, đường cong worker, bộ nhớ dùng chung |
| 5. Semantic audit | Model / Evaluation | Bùi Giang Linh (B25CHHT103) | Nguyễn Mai Hạnh | `src/afp/semantic.py`, `src/afp/mutation.py`, `src/afp/audit.py`, `audit/`, `docs/AUDIT_GUIDELINE.md` | Compile được nhưng sai nghĩa, ba lớp kiểm tra, mutation test, Cohen's κ |
| 6. Metrics / reproducibility | Evaluation | Vũ Quốc Hùng (B25CHHT098) | Kim Anh Dũng | `src/afp/aggregator.py`, `src/afp/experiments.py`, `src/afp/study.py`, `src/afp/ablation.py`, `src/afp/runrecord.py`, `results/`, `configs/`, `environment/` | Ma trận 100 → 10K, run record, environment lock, tái lập kết quả |

Slide môn học (1-19) chia bốn nhóm vai trò: Data (nguồn, schema, quality, provenance), System (pipeline, storage, serving, monitoring), Model (baseline, model, error analysis), Evaluation (scale, reproducibility, report, demo). Cột thứ hai cho biết mỗi vai trò của hướng dẫn thuộc nhóm nào.

Hai người chấm audit (đề xuất): **rater1** – Bùi Giang Linh, **rater2** – Nguyễn Mai Hạnh, chấm độc lập theo `docs/AUDIT_GUIDELINE.md`.

## Nhật ký đóng góp (điền khi làm việc)

| Thành viên | Issue | Pull request / commit | Việc đã làm | Đã đọc và giải thích được |
|---|---|---|---|---|
| Nguyễn Mai Hạnh | | | | ☐ toàn pipeline ☐ phần phụ trách |
| Lê Quang Đức | | | | ☐ toàn pipeline ☐ phần phụ trách |
| Nguyễn Việt Hưng | | | | ☐ toàn pipeline ☐ phần phụ trách |
| Kim Anh Dũng | | | | ☐ toàn pipeline ☐ phần phụ trách |
| Bùi Giang Linh | | | | ☐ toàn pipeline ☐ phần phụ trách |
| Vũ Quốc Hùng | | | | ☐ toàn pipeline ☐ phần phụ trách |

Mỗi thành viên phải trả lời được về toàn bộ pipeline, không chỉ phần mình phụ trách. Danh sách câu hỏi nên chuẩn bị nằm cuối `docs/DEMO_SCRIPT.md`.
