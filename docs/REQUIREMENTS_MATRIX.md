# Đối chiếu yêu cầu – Nhóm 5, Autoformalization Pipeline

Bảng này đối chiếu từng yêu cầu của **Hướng dẫn bài tập lớn INT4418** (phần chung và phần Nhóm 5) và **slide môn học** với sản phẩm trong repository.
Đường dẫn tính từ thư mục gốc. "Báo cáo §n" là mục n của báo cáo (`report.pdf`, `report.docx`).

Ký hiệu: **Đạt** · **Một phần** (có giải thích) · **Nhóm làm** (việc chỉ thành viên nhóm làm được, chưa xong).

## 1. Yêu cầu chung bắt buộc (hướng dẫn, mục 2)

| Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|
| Câu hỏi nghiên cứu chỉ ra nút thắt Big Data | Đạt | Báo cáo §1: nút thắt chi phí tính toán và độ trễ, giả thuyết H1–H3; `docs/PROPOSAL_1PAGE.md` |
| Baseline đơn giản, chạy end-to-end trước phương pháp nâng cao | Đạt | Báo cáo §5, §6.1; `python -m afp.experiments baseline`; `results/figures/baseline_runs.json`, `baseline_compare.json`. Cấu hình kiểm chứng của baseline (A: 1 worker, lô 1) chạy từ 16/10 trong ma trận; phần sinh mã một bài mỗi request chạy bổ sung ngày 26/10 trên 20 bài (T20) |
| Tối thiểu ba mức quy mô, cách nhau gần một bậc | Đạt | 100 → 1.000 → 10.000 task (Báo cáo §6.3). Mức 10.000 là trace replay của 1.000 ứng viên thật, ghi rõ trong §3, §7 |
| Báo cáo đồng thời chất lượng và chi phí | Đạt | Báo cáo §6.1–6.2: compile, Pass@k, cờ ngữ nghĩa cùng token, thời gian, throughput |
| Biểu đồ sinh từ raw results bằng script; ghi phần cứng, phần mềm, seed, timeout, số lần lặp | Đạt | `src/afp/plots.py` (PNG), `scripts/doc_widgets.py` (biểu đồ trong báo cáo), `src/afp/study.py`, `src/afp/ablation.py`; Báo cáo §5; `run_record.json` của mỗi lần chạy |
| Error analysis, ablation, limitation | Đạt | Báo cáo §7; `results/figures/ablation.md`, `taxonomy_*.json`, `failure_causes_*.json` |
| Code, dữ liệu mẫu, data/model card, README cho phép thành viên khác chạy lại | Đạt | `README.md`, `data_sample/`, `docs/DATA_CARD.md`, `docs/SYSTEM_CARD.md`, `scripts/quickstart.sh`, `environment/` |
| Mỗi thành viên có vai trò chính và dự phòng | Một phần | `contributions.md` là bảng đề xuất; nhóm cần xác nhận và điền issue, pull request |
| Khai báo AI; nhóm kiểm chứng mã và kết luận do AI hỗ trợ | Một phần | `docs/AI_USE_STATEMENT.md`, Phụ lục A của báo cáo. Danh sách việc nhóm phải tự kiểm chứng nằm ở mục 3 của file đó |

## 2. Cấu trúc sản phẩm bàn giao (hướng dẫn, mục 4)

| Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|
| `README.md`: mục tiêu, kiến trúc, cài đặt, dữ liệu, chạy nhanh, tái tạo kết quả chính | Đạt | `README.md` |
| `src/` mã nguồn có cấu trúc | Đạt | `src/afp/` (gói Python `afp`, `pyproject.toml`) |
| `tests/` | Đạt | `tests/`: hàng đợi, TaskHash, sanitizer, backend, Redis, Lean REPL, cấu hình; `python -m pytest -q` |
| `configs/` cấu hình từng thí nghiệm | Đạt | `configs/experiments.json` (đọc bởi `afp.experiments`), `configs/pipeline_defaults.json`; tham số thật của từng lần chạy trong `results/raw/runs/<id>/config.json` |
| `data_sample/` dữ liệu mẫu hợp pháp; `scripts/` tải hoặc tạo dữ liệu đầy đủ | Đạt | `data_sample/` (100 bài T100 + ứng viên + corpus), `scripts/download_data.sh`, `python -m afp.ingest`, `scripts/make_manifest.py` |
| `results/raw/` kết quả thô; `results/figures/` bảng, hình tạo bằng script | Đạt | `results/raw/runs/<id>/` (raw_results, events, memory, metrics, run_record), `results/raw/*_runs.csv`; `results/figures/` (csv, json, png, md) |
| `docs/`: data card, model/system card, AI-use statement, privacy/license note | Đạt | `docs/DATA_CARD.md`, `docs/SYSTEM_CARD.md`, `docs/AI_USE_STATEMENT.md`, `docs/LICENSE_PRIVACY.md` |
| `report.pdf/docx` | Đạt | `report.pdf`, `report.docx` (xuất từ bản báo cáo trên Claude Docs): cấu trúc Phụ lục C, phần chính (Tóm tắt, mục 1–8) 20 trang, phụ lục và tài liệu tham khảo 4 trang |
| `slides/demo`: slide và kịch bản trình diễn | Đạt | `slides/slides.pdf` (17 trang), `slides/deck/` (mã nguồn slide), `slides/NOTES.md` (ghi chú người trình bày), `slides/README.md` (link bản trình chiếu, xuất được PDF/PPTX), `docs/DEMO_SCRIPT.md`, `python -m afp.demo_one`, `demo/explorer.html` |
| `contributions.md`: vai trò, issue, pull request, phần bảo vệ của từng thành viên | Một phần | Có bảng vai trò và phần bảo vệ; **Nhóm làm:** xác nhận người, điền issue/PR |

## 3. Tiến độ và minh chứng theo tuần (hướng dẫn, mục 3 phần chung và mục 6 Nhóm 5)

| Tuần | Minh chứng yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Đề cương 1 trang; specification; risk/ethics note; 20 examples; board nhiệm vụ | Một phần | `docs/PROPOSAL_1PAGE.md` (mẫu Phụ lục A), `docs/SYSTEM_CARD.md` (specification, mục rủi ro và đạo đức), `docs/EXAMPLES_20.md`. **Nhóm làm:** board nhiệm vụ (issue trên repository của nhóm) |
| 2 | Data contract, schema, script đọc; data sample + data card v0.1; checker script; audit guideline | Đạt | `src/afp/schema.py`, `src/afp/ingest.py`, `data_sample/`, `docs/DATA_CARD.md`, `src/afp/lean/`, `docs/AUDIT_GUIDELINE.md` |
| 3 | Zero-shot, one-request/one-candidate baseline; baseline compile/pass metrics; prompt v1 | Đạt | `base_T20_1req_A`, `results/figures/baseline_compare.json`; `src/afp/prompts.py` (`v1_zeroshot`, `v1_zeroshot_1req`), `docs/PROMPTS.md` |
| 4 | Batch inference, queue, candidate store; pipeline 100 samples; retry/error logs | Đạt | `src/afp/inference/`, `src/afp/queue.py`, `src/afp/store.py`; các lần chạy T100 (`mx_T100_*`, `quickstart_T100_A`); `results/raw/inference_jobs.json`, `events.jsonl` |
| 5 | Worker pool, timeout, sandbox; concurrency test; worker throughput; failure recovery | Một phần | Đường cong 1/2/4/8 worker, giết worker, retry (Báo cáo §6.3, §6.5). Mỗi REPL là một tiến trình riêng, bị giới hạn bằng heartbeat và wall timeout, bị kill khi quá hạn; chưa có sandbox dạng container (Docker), ghi trong §7 |
| 6 | Nhiều candidate hoặc few-shot; versioned prompts; token/cost logs; sample audit | Đạt | `v2_fewshot` k = 4, `results/figures/candidates_retry.json`, `results/raw/inference_jobs.json`, `audit/` |
| 7 | 100/1K/10K; batch size và worker count; throughput, P95, compile rate, cost; raw results | Đạt | `results/raw/matrix_runs.csv`, `batch_runs.csv`, `scaling_runs.csv`; Báo cáo §6.2–6.3 |
| 8 | Semantic audit, error taxonomy, ablation; agreement, semantic accuracy, failure examples | Một phần | Báo cáo §6.4, §7; κ và độ chính xác hiện từ hai người chấm thử bằng LLM. **Nhóm làm:** hai thành viên chấm `audit/rater1.xlsx`, `audit/rater2.xlsx` |
| 9 | Đóng gói pipeline, corpus, report; release candidate; model/data card | Đạt | Thẻ Git `v1.0.0-rc1`; `data/formalized_corpus.jsonl`; `docs/`; báo cáo |
| 10 | Demo NL → Lean → checker; bảo vệ cá nhân; contribution log | Một phần | `python -m afp.demo_one`, `docs/DEMO_SCRIPT.md`, bộ slide. **Nhóm làm:** contribution log thật, luyện bảo vệ |

## 4. Yêu cầu riêng của Nhóm 5

| Mục hướng dẫn | Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Q1: batching và số candidate ảnh hưởng thế nào tới throughput, chi phí, compile rate | Đạt | Báo cáo §6.2 |
| 1 | Q2: phát hiện phát biểu Lean chấp nhận nhưng sai ý đề | Đạt | Báo cáo §6.4 |
| 2 | ProofNet: chiến lược Lean 4 hoặc dùng để đánh giá alignment | Đạt | Bản port Lean 4 của DeepSeek-Prover-V1.5; gold dùng để kiểm tra tương đương (Báo cáo §3, §6.4) |
| 2 | NuminaMath-CoT: lấy mẫu bài toán lớn để đo throughput | Một phần | HuggingFace không truy cập được từ môi trường thí nghiệm; thay bằng MATH và GSM8K, hai nguồn con của NuminaMath-CoT (Báo cáo §3) |
| 2 | Tập 100–300 mẫu semantic audit, hai người kiểm tra độc lập | Một phần | 100 mẫu phân tầng đã đóng băng, phiếu và hướng dẫn chấm sẵn; **Nhóm làm:** hai thành viên chấm |
| 2 | Không đưa toàn bộ dữ liệu lớn vào Git; sample, manifest, checksum, script; split cố định và có phiên bản | Đạt | `.gitignore` loại `data/raw`, `data/units`, `data/lake/units`; `data/MANIFEST.json` (nguồn, giấy phép, SHA-256); `data/tiers/` |
| 3 | Kiến trúc: input queue, prompt/version manager, batch LLM inference, candidate store, Lean worker pool, result/error store, semantic audit sample | Đạt | Báo cáo §4 (bảng đối chiếu từng thành phần) |
| 4 | Công cụ gợi ý | Một phần | Lean 4, LLM, hàng đợi Python (SQLite, Redis), Parquet/SQLite, manifest tự xây: có. Docker, Ray/Spark, MLflow: không dùng; môi trường khóa bằng `environment/` và `scripts/setup_lean.sh` |
| 5 | Sáu vai trò, mỗi vai trò có người dự phòng | Một phần | `contributions.md` (đề xuất, cần nhóm xác nhận) |
| 7 | Baseline: zero-shot, một bài mỗi request, một candidate, một Lean worker, không repair; cùng dữ liệu, split, phần cứng, timeout | Đạt | Báo cáo §5, §6.1 |
| 8 | 100 → 1K → 10K; batch 1/8/32; 1/2/4+ worker; 1 so với nhiều candidate; zero-shot so với few-shot; có/không retry | Đạt | Báo cáo §5 (bảng yếu tố), §6.2–6.5, §7 |
| 8 | Mỗi cấu hình lưu timestamp, commit, data version, machine, software, seed, parameters, runtime, status, log | Đạt | `results/raw/runs/<id>/run_record.json`, `results/raw/runs_manifest.csv`. Lần chạy ngày 16/10 có record ghi bù, đánh dấu trong `backfilled_fields` |
| 8 | Runtime biến động: ít nhất 3 lần, median và khoảng biến thiên | Một phần | Ma trận, batch size, retry, ablation release, repro: 3 lần. Đường cong worker: 2 lần với 1–2 worker, 1 lần với 4 và 8 worker (12–13 phút mỗi lần), ghi trong §5, §7 |
| 9 | Parse rate, compile rate, semantic accuracy, Pass@k; throughput, P50/P95, token cost, failure rate theo loại; chọn 1–2 primary metrics | Một phần | Báo cáo §5, §6; `results/figures/quality_metrics.json`. Semantic accuracy hiện từ người chấm thử bằng LLM; số cuối chờ audit người |
| 10 | Versioned prompt set; batch pipeline; Lean checker workers; formalized corpus + manifest; semantic audit set; error taxonomy; raw results; README/demo | Đạt | `src/afp/prompts.py` + `data/jobs/`; `src/afp/`; `data/formalized_corpus.jsonl` + `data/MANIFEST.json`; `audit/`; `results/figures/taxonomy_*.json`; `results/raw/`; `README.md`, `docs/DEMO_SCRIPT.md` |
| 11 | Phân biệt compile correctness và semantic correctness | Đạt | Báo cáo §4, §6.4; corpus giữ kết luận và cờ ngữ nghĩa |
| 11 | Có semantic audit hai người | Nhóm làm | Phiếu sẵn; chạy thử bằng hai LLM để kiểm tra quy trình |
| 11 | Có zero-shot baseline | Đạt | Báo cáo §6.1 |
| 11 | Có 3 mức quy mô | Đạt | Báo cáo §6.3 |
| 11 | Ghi token/cost và failure logs | Đạt | `results/raw/inference_jobs.json`, `data/jobs/*/*.manifest.json`, `raw_results.csv`, `events.jsonl` |
| 11 | Không tuyên bố đúng ngữ nghĩa chỉ dựa vào Lean compile | Đạt | Báo cáo §6.4, `docs/SYSTEM_CARD.md` |
| 12 | Threats to validity | Đạt | Báo cáo §7 |

## 5. Phụ lục của hướng dẫn

| Phụ lục | Yêu cầu | Bằng chứng |
|---|---|---|
| A | Đề cương 1 trang | `docs/PROPOSAL_1PAGE.md` |
| B | Mẫu ghi một lần chạy | `run_record.json` của mỗi lần chạy; Phụ lục D của báo cáo |
| C | Cấu trúc báo cáo: Tóm tắt, 8 mục, phụ lục AI-use, đóng góp, lệnh tái lập | Báo cáo theo đúng thứ tự này |
| D | Nguồn khởi đầu cho Nhóm 5: [1] NuminaMath-CoT, [2] ProofNet repository, [3][4] LeanDojo, [10] ProofNet paper | Báo cáo §2, §3, tài liệu tham khảo. LeanDojo không dùng: nhóm gọi Lean qua REPL chính thức để đo trực tiếp chi phí kiểm chứng |

## 6. Câu hỏi trên slide môn học

| Slide | Câu hỏi | Trả lời ở |
|---|---|---|
| 1-3 | Một chương trình chạy đúng đã đủ để gọi là xử lý Big Data chưa? | Báo cáo §6.3, §8: kết luận thay đổi theo quy mô (sự kiện 0,1 % thành chắc chắn ở 10.000 task) |
| 1-6 | Phần tự học nào phải tạo ra bằng chứng kiểm tra được? | Mỗi thí nghiệm có run record, log thô, bảng sinh bằng script (Phụ lục D của báo cáo) |
| 1-8 | Vai trò Big Data phải được chứng minh bằng thí nghiệm nào? | Báo cáo §8 (bảng thí nghiệm theo quy mô) |
| 1-14 | Compile được nhưng sai nghĩa: hệ thống phải phát hiện thế nào? | Báo cáo §6.4 |
| 1-19 | Chia việc thế nào để commit và bằng chứng phản ánh đúng đóng góp? | `contributions.md`, Phụ lục B của báo cáo |
| 1-21 | Ai chịu trách nhiệm nếu mô hình ngôn ngữ sinh theorem sai? | Phụ lục A của báo cáo, `docs/AI_USE_STATEMENT.md` mục 4 |
| 1-22 | Bằng chứng nào giúp phân biệt đóng góp cá nhân? | Lịch sử Git, issue, pull request và nhật ký trong `contributions.md` |
