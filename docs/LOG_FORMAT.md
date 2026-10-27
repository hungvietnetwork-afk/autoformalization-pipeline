# Định dạng log thô và run record

Mỗi lần chạy ghi `results/raw/runs/<run_id>/` gồm:

| File | Nội dung |
|---|---|
| `run_record.json` | bản ghi theo mẫu Phụ lục B của hướng dẫn (bảng cuối file này) |
| `config.json` | cấu hình lần chạy (tier, workers, batch, partitions R, timeout, lease, backend, broker) |
| `run.db` | SQLite: `q_problems`, `q_verify` (hàng đợi), `results`, `events`; không đưa vào bộ nộp bài vì nội dung đã có trong các file dưới |
| `raw_results.csv` / `.jsonl` | **một dòng cho mỗi lần kiểm chứng** (xem bảng dưới); bộ nộp bài chỉ giữ bản CSV cho các lần chạy lặp lại (`mx_*`, `sc_*`, `bs_*`, `rt_*`, `ab_release_*`, `repro_*`, `fault_*`, `broker_*`) |
| `events.jsonl` | sự kiện: `run_start`, `problems_enqueued`, `worker_ready` (pid, thời gian khởi động REPL, RAM), `inference_batch`, `inference_done`, `repl_timeout`, `repl_crash`, `repl_restarted` (thời gian khởi động lại, số task của lô được trả lại cho worker khác), `repl_recycled` (làm mới REPL sau 5.000 lệnh), `fault_injected`, `worker_exit`, `run_end` |
| `memory.csv` | mẫu bộ nhớ mỗi 0,5 s |
| `metrics.json` | chỉ số tổng hợp của lần chạy |
| `semantic.jsonl` | (nếu có) kết quả kiểm tra ngữ nghĩa từng ứng viên COMPILE_OK |

## `raw_results.csv`

| Cột | Ý nghĩa |
|---|---|
| `run_id` | mã lần chạy |
| `task_hash` | SHA256(problem_id ‖ prompt_version ‖ candidate_index) – khoá UPSERT |
| `problem_id`, `prompt_version`, `candidate_index` | định danh ứng viên |
| `status` | COMPILE_OK / PARSE_ERROR / UNKNOWN_IDENTIFIER / TYPE_MISMATCH / TIMEOUT / OTHER_ERROR / EMPTY_OUTPUT |
| `error_kinds` | mọi loại lỗi tìm thấy, theo thứ tự vị trí (`parse_error;type_mismatch;...`) |
| `compiler_message` | thông điệp lỗi (cắt 300 ký tự trong CSV, đầy đủ trong JSONL/DB) |
| `latency_ms` | thời gian Lean elaborate ứng viên (wall clock, từ lúc gửi đến lúc nhận phản hồi REPL) |
| `peak_ram_mb` | VmHWM của tiến trình REPL tại thời điểm xong task (đỉnh RSS, gồm cả trang `.olean` dùng chung) |
| `worker_id` | `lean-<i>` |
| `attempt` | lần thử (1..3); > 1 nghĩa là task được giao lại sau sự cố |
| `finished_at` | epoch giây |
| `stmt_chars` | độ dài mã Lean |
| `write_count` | số lần dòng này được ghi (UPSERT); > 1 = kết quả bị ghi đè khi chạy lại |

## `memory.csv`

| Cột | Ý nghĩa |
|---|---|
| `used_mb` | MemTotal − MemAvailable của máy |
| `swap_mb` | swap đang dùng |
| `pool_mb` | footprint thực của pool = max(RssFile) + Σ RssAnon (trang `.olean` mmap chỉ đếm một lần) |
| `repl_anon_mb` | Σ heap riêng của các REPL |
| `repl_file_mb` | trang file (`.olean`) đang thường trú |
| `repl_rss_sum_mb` | Σ RSS – **đếm trùng** trang dùng chung, chỉ để so sánh |
| `n_repl`, `cpu_pct` | số REPL đang sống, % CPU toàn máy |

## `run_record.json` (mẫu Phụ lục B của hướng dẫn)

| Trường | Nội dung | Nguồn |
|---|---|---|
| `run_id` | mã duy nhất | tham số |
| `timestamp` | thời điểm bắt đầu (UTC) | đồng hồ máy |
| `git_commit` | `commit` và `code_dirty` (có sửa chưa commit trong `src/`, `configs/`, `scripts/` không) | `git rev-parse HEAD`, `git status` |
| `data_version` | tầng, file danh sách và SHA-256 của nó, số bản replay, file DataUnit, SHA-256 của `data/candidates.db` | `data/tiers/`, `data/candidates.db` |
| `machine` | CPU, số vCPU, RAM, swap, GPU, hệ điều hành | `/proc`, `platform` |
| `software` | Python và các gói chính, Lean, commit Mathlib, commit REPL | `environment/`, `lake-manifest.json` |
| `parameters` | toàn bộ tham số của lần chạy | `config.json` |
| `seed_timeout` | seed lấy mẫu tầng (42), seed của LLM (không đặt được: `null`), wall timeout, maxHeartbeats, lease | tham số, header Lean |
| `metrics` | chỉ số chất lượng và chi phí | `metrics.json` |
| `status`, `logs` | `ok`, `ok_with_worker_failures` hoặc `incomplete`; đường dẫn từng file log | lần chạy |

`results/raw/runs_manifest.csv` gom mọi run record thành một bảng (`python -m afp.study runs`).
Các lần chạy ngày 16/10 có trước khi dùng Git; record của chúng được ghi bù bằng `scripts/backfill_run_records.py`
từ `config.json`, `metrics.json` và thông tin máy, các trường ghi bù liệt kê trong `backfilled_fields`.

## Log của tầng inference

| File | Nội dung |
|---|---|
| `results/raw/inference_jobs.json` | mỗi batch job: trạng thái (xong, dừng giữa chừng, gửi lại phần thiếu), số bài, token, thời gian; tổng số ứng viên và token; lỗi nhãn dữ liệu phát hiện khi sinh |
| `data/jobs/<phiên bản>/*.manifest.json` | khóa `P###` ↔ TaskHash của từng job; với baseline một bài mỗi request: token và thời gian từng request |
| `data/jobs/<phiên bản>/*.out.txt` | output thô của mô hình, lưu nguyên |
