# Mẫu dữ liệu (data_sample)

Mẫu hợp pháp, được version trong Git, đủ để chạy pipeline từ đầu đến cuối mà không cần tải bộ dữ liệu đầy đủ.

| File | Nội dung |
|---|---|
| `units_T100.jsonl` | 100 DataUnit của tầng T100: ProofNet 4, miniF2F 5, MATH 81, GSM8K 10, lấy mẫu phân tầng với seed 42. Danh sách bài ở `data/tiers/T100.txt`. |
| `candidates_T100.jsonl` | Mọi ứng viên Lean của 100 bài: zero-shot (1 mẫu mỗi bài), few-shot (4 mẫu mỗi bài), baseline một bài mỗi request (20 bài). Mỗi dòng có cả output thô của model và bản đã qua sanitizer. |
| `corpus_T100.jsonl` | Bản ghi corpus đã formalize của 100 bài: phát biểu được chọn, kết luận và cờ ngữ nghĩa. |
| `units_demo.jsonl` | 3 DataUnit dùng trong kịch bản demo nhưng không thuộc T100 (`gsm8k:train:02691`, `gsm8k:train:04141`, `math:test/algebra/2167`); ứng viên của chúng có trong `data/candidates.db`. |

Giấy phép: ProofNet MIT, miniF2F MIT / Apache-2.0, MATH MIT, GSM8K MIT. Chi tiết ở `docs/LICENSE_PRIVACY.md`. Checksum của từng file có trong `data/MANIFEST.json`.

Chạy trên mẫu (cần Lean, cài bằng `bash scripts/setup_lean.sh`):

```bash
bash scripts/quickstart.sh     # test + một lần chạy T100 cấu hình baseline + demo một bài
```

Khi chưa có `data/units/all_units.jsonl`, `afp.paths.UNITS` tự dùng `data_sample/units_T100.jsonl`.
Ứng viên lấy từ `data/candidates.db` (cũng được version), nên lần chạy kiểm chứng không gọi model.
