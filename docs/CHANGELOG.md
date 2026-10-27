# Nhật ký thay đổi

Repository được khởi tạo Git ngày 26/10/2026. Commit đầu tiên `c031d89` là ảnh chụp mã nguồn đã dùng cho các thí nghiệm ngày 16/10.
Các thay đổi trong ngày 16/10 được ghi lại dưới đây, để biết lần chạy nào dùng phiên bản nào.

## 16/10/2026 — xây dựng và thí nghiệm chính

| Thay đổi | Lý do | Lần chạy bị ảnh hưởng |
|---|---|---|
| Pipeline đầu tiên: hàng đợi phân vùng SQLite, inference theo batch job, pool Lean REPL nóng, aggregator, log thô | Thiết kế tuần 2 | — |
| `COMPILE_OK` chỉ được ghi khi Lean thực sự elaborate một khai báo (có cảnh báo `sorry`) | Một phát biểu chỉ còn các dòng `open` vẫn "compile" | mọi lần chạy về sau |
| Trả lại phần còn lại của lô (`release`) trước khi khởi động lại REPL | Worker đang khởi động lại giữ cả lô 30–40 s | ma trận và các lần chạy sau đều dùng bản đã sửa (T1K/B ngày 16/10: thời gian ổn định 54,7 → 36,7 s; đo lại ngày 26/10 trong `ab_release_*`, 3 lần mỗi bên: 84,9 → 43,2 s, makespan 147,4 → 106,2 s) |
| Sanitizer v2: bỏ qua `:=` thuộc `let`/`have` trong phát biểu | Error taxonomy chỉ ra 7 ứng viên bị cắt nhầm | `q_T1K_zeroshot`, `q_T100_fewshot` chạy lại trên output thô đã lưu, không gọi lại model; bản cũ giữ ở `*_sanitizer_v1`; thí nghiệm scalability giữ bộ ứng viên v1 để workload cố định |
| Chế độ hàng đợi `indexed` (index phủ, quét định kỳ), tắt theo mặc định | Micro-benchmark hàng đợi | không dùng trong ma trận; đo riêng (`bench_queue`, `bs_*_b1_idx`) |

## 26–27/10/2026 — cập nhật theo hướng dẫn bài tập lớn

* Cấu trúc bàn giao: `src/afp/`, `configs/`, `data_sample/`, `results/raw/`, `results/figures/`, `docs/`, `contributions.md`. Mọi đường dẫn đi qua `afp.paths`.
  Các bảng được sinh lại sau khi đổi cấu trúc và giống hệt bản cũ từng byte.
* `run_record.json` cho mỗi lần chạy (Phụ lục B). Các lần chạy ngày 16/10 được ghi bù bằng `scripts/backfill_run_records.py`, có đánh dấu trường nào ghi bù.
* Baseline đúng chuẩn: mỗi request một bài, prompt `v1_zeroshot_1req`, 20 bài phân tầng.
* Thí nghiệm mới:
  * batch size 1/8/32 và lô 1 có index ở 2 worker, ba tầng, 3 lần (`bs_*`);
  * retry budget 1 so với 3 khi giết worker (`rt_*`);
  * bật/tắt release khi khởi động lại REPL (`ab_release_*`): thêm cờ `release_on_restart` (mặc định bật, đúng hành vi của mọi lần chạy từ 16/10) để đo lại bản trước khi sửa;
  * chạy lại ô T1K/A ba lần trên máy mới (`repro_T1K_A`, `repro_T1K_A_r1`, `repro_T1K_A_r2`).
* `configs/experiments.json`: lưới tham số của mọi thí nghiệm, `afp.experiments` đọc từ file này thay vì hằng số trong code; `configs/pipeline_defaults.json` và test kiểm tra khớp với code.
* Phân tích mới trong `afp.study`: batching ở tầng inference, 1 so với nhiều candidate, parse rate, các lớp kiểm tra ngữ nghĩa so với audit, baseline, manifest các lần chạy. `afp.ablation`: một bảng cho mọi so sánh bật/tắt, đọc từ file nguồn.
* Hình mới: `inference_batching.png`, `batch_sweep.png`.
* `afp.demo_one`: demo NL → Lean → checker cho một bài.
* Tài liệu: system card, AI-use statement, giấy phép, hướng dẫn audit v2, kịch bản demo, đề cương một trang, 20 ví dụ (`docs/EXAMPLES_20.md`, sinh bằng `scripts/make_examples.py`), bảng đối chiếu yêu cầu (`docs/REQUIREMENTS_MATRIX.md`), data card 1.2.
* `afp.ablation`: thêm dòng work stealing (mô phỏng trên trace latency thật của T1K, `results/figures/skew_q_T1K_zeroshot.json`).
* Báo cáo viết lại theo cấu trúc Phụ lục C của hướng dẫn (Tóm tắt, mục 1–8, phụ lục AI-use, đóng góp, lệnh tái lập, run record); bộ slide 17 trang theo cùng cấu trúc, bản PDF trong `slides/`.
