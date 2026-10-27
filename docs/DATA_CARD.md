# Data card – AI4Math Nhóm 5: Autoformalization corpus

*Phiên bản 1.2 · 27/10/2026 · Lean 4 v4.35.0 · Mathlib v4.35.0 · sanitizer v2*

Thay đổi so với 1.1 (16/10): thêm tập con T20 và 20 ứng viên của baseline một bài mỗi request; thêm `data_sample/` và `data/MANIFEST.json` (nguồn, giấy phép, SHA-256); ghi rõ phần nào nằm trong Git, phần nào dựng lại bằng script (mục 8); ghi lý do thay NuminaMath-CoT bằng MATH và GSM8K (mục 2).

## 1. Tóm tắt

Bộ dữ liệu gồm (a) **22.150 đề toán ngôn ngữ tự nhiên** đã chuẩn hoá về một schema chung (`DataUnit`), và
(b) **corpus đã formalize**: phát biểu Lean 4 do LLM sinh cho 1.000 đề (tầng T1K), đã kiểm chứng bằng Lean,
kèm kết quả kiểm tra ngữ nghĩa tự động. Mục đích: đánh giá và mở rộng quy mô pipeline autoformalization
(NL → Lean 4) trong bài tập lớn môn Dữ liệu lớn.

| Corpus đã formalize (`data/formalized_corpus.jsonl`, `data/lake/formalized/`) | Số bài |
|---|---|
| Bài đã thử | 1.000 (ProofNet 37, miniF2F 49, MATH 814, GSM8K 100) |
| Có ít nhất một phát biểu compile được | 990 (ProofNet 35, miniF2F 49, MATH 806, GSM8K 100) |
| … và không bị kiểm tra tự động gắn cờ | 809 |
| … chứng minh được tương đương phát biểu gold | 29 |
| … Lean tự suy ra đáp án từ giả thiết | 271 |

Mỗi dòng: đề, đáp án, phát biểu Lean được chọn (kết luận ngữ nghĩa tốt nhất, rồi ngắn nhất, rồi kiểm chứng
nhanh nhất trong các ứng viên compile được), `semantic_verdict`, `semantic_flag`, `task_hash`, model, phiên bản
prompt, sanitizer, Lean và Mathlib. Bài bị gắn cờ vẫn được giữ, kèm cờ: người dùng tự lọc. Kết luận tự động không
thay cho audit người (precision khoảng 0,7 so với audit thử 100 mẫu, xem báo cáo mục 6.4).

## 2. Nguồn dữ liệu

| Nguồn | Số bài | Loại bài | Có đáp án | Có phát biểu Lean "gold" | Lấy từ | Giấy phép |
|---|---|---|---|---|---|---|
| ProofNet | 371 | Định lý đại học (giải tích, đại số trừu tượng, tô-pô, đại số tuyến tính, số học, giải tích phức, Putnam) | Không (bài chứng minh) | Có – bản port Lean 4 | `deepseek-ai/DeepSeek-Prover-V1.5/datasets/proofnet.jsonl` + `zhangir-azerbayev/ProofNet` (để biết sách nguồn) | MIT + MIT |
| miniF2F | 488 | Thi Olympic/AMC/AIME/MATH | Ẩn trong đề ("Show that it is …") | Có – bản port Lean 4 | `deepseek-ai/DeepSeek-Prover-V1.5/datasets/minif2f.jsonl` | Apache-2.0 (phần Lean) + MIT |
| MATH | 12.499 | 7 môn, mức 1–5 | Có | Không | `openai/prm800k` (math_splits: 11.999 train + 500 test) | MIT |
| GSM8K | 8.792 | Toán lời văn tiểu học | Có | Không | `openai/grade-school-math` | MIT |
| **Tổng** | **22.150** | | | 859 | | |

**Thay cho NuminaMath-CoT.** Hướng dẫn gợi ý lấy mẫu NuminaMath-CoT (khoảng 860 nghìn bài) để đo throughput. HuggingFace không truy cập được từ môi trường thí nghiệm, nên nhóm dùng MATH và GSM8K: hai bộ này là nguồn con của NuminaMath-CoT, có đáp án và không có nhãn hình thức, đúng vai trò mà hướng dẫn đặt ra. Script `afp.ingest` đọc thêm một nguồn mới bằng một hàm `load_*` trả về `DataUnit`.

Đã loại 1 bản ghi trùng `unique_id` trong MATH (`test/precalculus/24307` xuất hiện 2 lần trong train); có 1 cặp
đề trùng nguyên văn được giữ lại và đánh dấu.

## 3. Schema – `DataUnit`

`DataUnit = ⟨problem_id, source, natural_statement, domain, metadata⟩`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `problem_id` | string | ổn định, đọc được: `proofnet:<sách>:<bài>`, `minif2f:<split>:<tên>`, `math:<unique_id>`, `gsm8k:<split>:<số>` |
| `source` | string | `proofnet` · `minif2f` · `math` · `gsm8k` |
| `natural_statement` | string | đề bài; với bài có đáp án, nối thêm dòng `Answer: <đáp án>` để phát biểu Lean khẳng định đáp án |
| `domain` | string | 19 giá trị, ví dụ `abstract_algebra`, `topology`, `algebra`, `counting_probability`, `arithmetic_word_problem` |
| `metadata.difficulty` | string | MATH `L1`–`L5`; miniF2F `MATH`/`AMC12`/`AIME`/`IMO`/`custom`; ProofNet `undergraduate`; GSM8K `grade_school` |
| `metadata.answer` | string \| null | đáp án tham chiếu (MATH, GSM8K) |
| `metadata.gold_formal_statement` | string \| null | phát biểu Lean 4 do người viết (ProofNet, miniF2F) |
| `metadata.length_chars`, `metadata.est_tokens` | int | độ dài; số token ước lượng = ký tự / 3,5 (không có tokenizer offline) |
| `metadata.split`, `metadata.license`, `metadata.origin` | string | truy vết nguồn |

## 4. Phân vùng và lưu trữ

* **Runtime (hàng đợi):** `partition = SHA256(problem_id) mod R` (R = 16). Dùng SHA-256 thay cho `hash()` của
  Python (bị salt theo tiến trình) để mọi máy tính ra cùng một partition.
* **Lưu trữ lâu dài:** Parquet, thư mục Hive `data/lake/units/source=<s>/domain=<d>/part-0.parquet`
  (3,2 MB cho 22.150 bài); corpus đã formalize: `data/lake/formalized/source=<s>/domain=<d>/`. Truy vấn trực tiếp
  bằng DuckDB/Spark với partition pruning, ví dụ
  `SELECT domain, count(*) FROM read_parquet('data/lake/units/**/*.parquet', hive_partitioning=1) WHERE source='math' GROUP BY 1`.
* **Tầng thí nghiệm (lồng nhau, seed 42):** T100 ⊂ T1K ⊂ T10K, cùng tỷ lệ nguồn

| Tầng | ProofNet | miniF2F | MATH | GSM8K | Tổng |
|---|---|---|---|---|---|
| T100 | 4 | 5 | 81 | 10 | 100 |
| T1K | 37 | 49 | 814 | 100 | 1.000 |
| T10K | 371 | 488 | 8.141 | 1.000 | 10.000 |

Ngoài ba tầng còn hai tập con cố định:

* **T20** (`data/tiers/T20_1REQ.txt`): 20 bài của T100, lấy theo nguồn (ProofNet 2, miniF2F 2, GSM8K 2, MATH 14), thứ tự SHA-256 của `problem_id`. Dùng cho baseline bắt buộc một bài mỗi request. Quy tắc chọn ghi trong `data/jobs/v1_zeroshot_1req/SUBSET_20.json`.
* **Mẫu audit**: 100 ứng viên compile được của T1K, phân tầng theo nguồn, đóng băng trong `audit/audit_key.csv`.

SHA-256 của mọi danh sách nằm trong `data/MANIFEST.json`; thí nghiệm ghi SHA-256 của danh sách đã dùng vào `run_record.json`.

## 5. Kiểm tra môi trường bằng phát biểu gold

Phát biểu gold được viết cho Mathlib năm 2024; trên Mathlib v4.35.0 chỉ **729/859 (84,9 %)** còn compile.
77 lỗi parse do cú pháp `∑ x in s` đã bị bỏ (nay là `∑ x ∈ s`), 4 lỗi do ký hiệu `φ` của `Nat.totient`.
Sau một luật viết lại cú pháp, **798/859 (92,9 %)** compile (miniF2F 485/488, ProofNet 313/371) – chỉ các gold
compile được mới dùng làm tham chiếu ngữ nghĩa.

## 6. Hạn chế và rủi ro đã biết

* Số token là ước lượng theo ký tự, không phải tokenizer thật của model.
* Phát biểu gold là bản port sang Lean 4 của bên thứ ba, cho Mathlib cũ; một số không còn compile.
* Dữ liệu MATH/GSM8K/miniF2F công khai từ lâu, có thể đã nằm trong dữ liệu huấn luyện của LLM (rò rỉ dữ liệu).
* Đáp án MATH ở dạng LaTeX; việc so khớp đáp án với phát biểu Lean là heuristic.
* Nhãn đáp án có nhiễu: ví dụ `math:test/algebra/1730` có trường `answer = 3` trong khi lời giải chính thức
  ra `d = −3` (và ghi "3 cũng được chấp nhận"). Một phát biểu trung thực với dữ liệu nhưng dùng đáp án tham chiếu
  sẽ SAI; hai mẫu few-shot độc lập của LLM đã tự phát hiện mâu thuẫn này.
* `math:train/intermediate_algebra/1964` ("|z − 3| = 2|z + 3| cắt |z| = k tại đúng một điểm, tìm mọi k") có nhãn
  `9`, nhưng tập đúng là {1, 9} (đường tròn (x+5)² + y² = 16 tiếp xúc |z| = 1 tại z = −1 và |z| = 9 tại z = −9).
  Model đã formalize {1, 9} thay vì nhãn; kiểm tra tay xác nhận.
* Một số đề GSM8K bị lỗi định dạng số (ví dụ "2 132 contracts").

## 7. Quá trình sinh corpus (provenance)

* **Model:** Claude Haiku 5.5, gọi theo kiểu batch job (file đầu vào → file đầu ra, giống Batch API), mỗi job do
  một agent chạy; 1.000 bài zero-shot (`v1_zeroshot`, k = 1, tầng T1K) + 100 bài × 4 mẫu few-shot (`v2_fewshot`,
  tầng T100) = 1.400 ứng viên. Thêm 20 ứng viên của baseline bắt buộc (`v1_zeroshot_1req`, tầng T20): 20 request riêng, mỗi request một bài, cùng nội dung prompt với `v1_zeroshot`. Prompt đầy đủ: `docs/PROMPTS.md`. Nhật ký job và token: `results/raw/inference_jobs.json`; token và thời gian từng request của baseline: `data/jobs/v1_zeroshot_1req/v1_zeroshot_1req_s0_t20.manifest.json`.
* **Sự cố và sai khác giao thức:** 8/21 job dừng vì vượt giới hạn 64.000 token đầu ra mỗi lần trả lời khi gom quá
  nhiều bài; phần còn lại được sinh lại theo khoá (`P###` ↔ `task_hash`) trong các job nhỏ hơn (25, rồi 9 bài/job).
  51 bài cuối của partition p02 (zero-shot) được sinh với thêm chỉ dẫn "nghĩ ngắn" để không vượt giới hạn; cùng
  prompt hệ thống, cùng định dạng đầu ra.
* **Hậu xử lý (sanitizer) có phiên bản:** output thô của model được lưu nguyên trong `candidates.db`
  (`raw_output`); `lean_code` là kết quả của sanitizer. Sanitizer v1 cắt nhầm tại `:=` của một `let` nằm trong
  phát biểu (7 ứng viên zero-shot + 1 few-shot thành lỗi parse); v2 sửa lỗi này. Thí nghiệm scalability dùng bộ
  ứng viên v1 (workload cố định); số liệu chất lượng và corpus cuối dùng v2. Không có lần gọi model nào bị lặp lại.
* **Header cố định:** `import Mathlib`, `import Aesop`, `set_option maxHeartbeats 400000`,
  `open BigOperators Real Nat Topology Rat` (header chuẩn của miniF2F/DeepSeek-Prover). `open Nat` biến `φ` thành
  ký hiệu hàm Euler, nên phát biểu dùng `φ` làm tên biến không parse được.

## 8. Những gì nằm trong Git

Theo yêu cầu dữ liệu của hướng dẫn, Git không chứa bộ dữ liệu đầy đủ.

| Trong Git | Dựng lại bằng script |
|---|---|
| `data/tiers/` (các split), `data/MANIFEST.json` (nguồn, giấy phép, kích thước, SHA-256) | `data/raw/`: `bash scripts/download_data.sh` |
| `data_sample/`: 100 bài T100, ứng viên và bản ghi corpus của chúng | `data/units/`, `data/lake/units/`: `python -m afp.ingest` (seed 42) |
| `data/candidates.db`: 2.279 ứng viên (1.420 do model sinh + 859 phát biểu gold) | `data/MANIFEST.json`, `data_sample/`: `python scripts/make_manifest.py` |
| `data/jobs/`: prompt và output thô của từng job | |
| `data/formalized_corpus.jsonl`, `data/lake/formalized/`: corpus 1.000 bài | |

Ứng viên được version vì chúng là kết quả của các lần gọi model không lặp lại được (mô hình không cho đặt seed); mọi thí nghiệm
dùng lại đúng các ứng viên này theo TaskHash.
