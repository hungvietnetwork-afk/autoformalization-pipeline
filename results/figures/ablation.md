| Thành phần | Thiết lập | Có | Không có | Nguồn |
| --- | --- | --- | --- | --- |
| REPL nóng (import Mathlib một lần mỗi worker) | kiểm một ứng viên, Mathlib v4.35.0 | 45,8 ms | 20,2 s (nhanh hơn 442 lần) | `results/raw/cold_vs_warm.json` |
| Heartbeat là giới hạn chính (wall timeout 30 s thay vì 10 s) | 10.000 task, 2 worker, lô 8 | 51,9 ứng viên/s, 0 timeout | 24,2 ứng viên/s, 7 timeout | `results/figures/scaling_median.csv (sc_T10K_w2)` |
| Trả lại phần còn lại của lô trước khi khởi động lại REPL (release) | 1.000 task, 2 worker, lô 8, timeout 10 s, 3 lần mỗi bên | 43,2 s, 1 timeout | 84,9 s, 1 timeout | `results/raw/release_runs.csv` |
| Index phủ cho hàng đợi (chế độ indexed) | lease 1 task khi hàng đợi còn 100.000 task; đầu cuối: lô 1, 2 worker, timeout 30 s | 0,06 ms/lease; T10K: 18,8 bài/s | 96,8 ms/lease; T10K: 16 bài/s | `results/raw/bench_queue.json` |
| Work stealing (worker rảnh lấy task của partition khác) | mô phỏng trên 1.000 latency thật của T1K zero-shot, 8 worker | 10 s (lý tưởng 5,9 s) | chia tĩnh: 14,7 s | `results/figures/skew_q_T1K_zeroshot.json` |
| Giao lại task khi lease hết hạn (retry hệ thống, tối đa 3 lần) | 1.000 task, 2 worker, lô 8, giết 1 worker sau 300 kết quả, lease 30 s, 3 lần mỗi bên | 1.000/1.000 bài, 0 dead-letter, 0 dòng trùng, 99,7 s | 995/1.000 bài, 8 dead-letter, 88 s | `results/raw/retry_runs.csv` |
| Gửi lại phần thiếu của batch job (retry ở tầng inference) | 1.400 ứng viên dự kiến (1.000 zero-shot + 400 few-shot) | 1.400/1.400 | 784 (56 %) | `results/figures/inference_batching.json` |
| Gom nhiều bài vào một request LLM (20–26 bài) | cùng prompt zero-shot; token tính cả ngữ cảnh cố định khoảng 80K mỗi request | 2.080 token/bài, 7,7 % request lỗi | 87.561 token/bài, 0 % request lỗi | `results/figures/inference_batching.json` |
| Few-shot (6 ví dụ) thay cho zero-shot | 100 bài của T100, mẫu đầu tiên của mỗi bài | compile 100 %, cờ 13 %, 672 token | compile 99 %, cờ 17,2 %, 330 token | `results/raw/runs/q_T100_fewshot` |
| 4 ứng viên mỗi bài thay cho 1 | few-shot, 100 bài, 4 mẫu mỗi bài | Pass@4 1, 2.689 token, cờ 13 % | Pass@1 0,9825, 672 token, cờ 13 % | `results/figures/candidates_retry.json` |
| Sanitizer v2 (không cắt `:=` của `let`/`have`) | 1.000 ứng viên zero-shot T1K, cùng output thô | compile 98,9 %, 3 lỗi cú pháp | compile 98,3 %, 10 lỗi cú pháp | `results/raw/runs/q_T1K_zeroshot` |
| Kết hợp hai lớp kiểm tra tự động (Lean + heuristic) | 100 mẫu audit của T1K zero-shot; nhãn tham chiếu: người chấm thử A | P 0,73, R 0,58 | chỉ heuristic: P 0,77, R 0,53; chỉ Lean: P 0,5, R 0,05 | `results/figures/semantic_layers.json` |
| Kiểm tra tương đương với phát biểu gold | mutation test trên phát biểu gold đã compile: 5 loại lỗi cài sẵn + mẫu đối chứng | bắt 100 % mỗi loại lỗi cài sẵn; báo động nhầm 2 % | đáp án sai 26 %, đảo quan hệ 15 %, bỏ giả thiết 0 %, giả thiết mâu thuẫn 99 %, tầm thường 100 % | `results/figures/mutation_summary.json` |
