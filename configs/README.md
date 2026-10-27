# configs/

| File | Nội dung | Ai đọc |
|---|---|---|
| `experiments.json` | Lưới tham số của mọi thí nghiệm: tầng dữ liệu, cấu hình worker/batch, số lần lặp, timeout, cách giết worker, retry, ablation release, repro | `src/afp/experiments.py` |
| `pipeline_defaults.json` | Giá trị mặc định của một lần chạy (`python -m afp.pipeline`): số partition, timeout, lease, giới hạn heartbeat, số lần giao tối đa | tài liệu; giá trị thật nằm trong `src/afp/pipeline.py`, `src/afp/queue.py`, `src/afp/prompts.py` và được test `tests/test_configs.py` kiểm tra khớp |

Phiên bản prompt (`v1_zeroshot`, `v1_zeroshot_1req`, `v2_fewshot`) nằm trong `src/afp/prompts.py`, mô tả trong `docs/PROMPTS.md`.
Mỗi lần chạy ghi đủ tham số đã dùng vào `results/raw/runs/<run_id>/config.json` và `run_record.json`.
