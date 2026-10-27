# Kịch bản demo (7 phút): NL → Lean → checker

Chuẩn bị trước buổi bảo vệ, chạy một lần để làm nóng page cache của Mathlib:

```bash
export PYTHONPATH=$PWD/src AFP_LEAN_ROOT=$HOME/lean
python -m afp.demo_one --problem gsm8k:train:02691 > /dev/null
```

Mở sẵn `demo/explorer.html` và `results/figures/`.

| Phút | Người trình bày | Việc | Lệnh / màn hình | Điểm cần nói |
|---|---|---|---|---|
| 0–1,5 | Prompt & model | **NL → Lean**: một đề GSM8K và các ứng viên đã lưu (model, phiên bản prompt) | `python -m afp.demo_one --problem gsm8k:train:02691` (phần 1–2) | Mỗi ứng viên có TaskHash = SHA256(problem_id ‖ prompt_version ‖ candidate_index); output thô được lưu nguyên |
| 1,5–3 | Lean worker pool | **Checker**: REPL nóng import Mathlib một lần, mỗi phát biểu kiểm trong vài chục ms; kết luận ngữ nghĩa tự động | cùng lệnh (phần 3–4) | 442 lần nhanh hơn chạy lạnh; Lean tự suy ra `kyle = 14` từ giả thiết |
| 3–4,5 | Semantic audit | **Compile được nhưng sai nghĩa** | `python -m afp.demo_one --problem gsm8k:train:04141`, rồi `--problem math:test/algebra/2167` | Ví dụ thứ nhất bị heuristic gắn cờ `ARITHMETIC_ONLY`; ví dụ thứ hai lọt kiểm tra tự động, chỉ audit người bắt được, nên audit hai người là bắt buộc |
| 4,5–6 | Batch scheduler | **Batch + chịu lỗi**: 20 bài, 2 worker, giết 1 worker sau 8 kết quả | `python -m afp.demo --n 20 --workers 2 --kill-after 8` | Lease hết hạn, task được giao lại; UPSERT theo TaskHash nên không có dòng trùng |
| 6–7 | Metrics / reproducibility | **Bằng chứng**: biểu đồ batch/worker, run record | `results/figures/*.png`, `results/raw/runs/<id>/run_record.json`, Corpus Explorer | Mỗi lần chạy ghi commit, phiên bản dữ liệu, máy, phần mềm, tham số, seed/timeout, metric và đường dẫn log |

Nếu máy demo không có Lean, chiếu Corpus Explorer (`demo/explorer.html`, chạy offline):
lọc theo trạng thái Lean, kết luận ngữ nghĩa và nhãn audit.
Người trình bày giải thích cùng hai ví dụ ở bước 3.

Câu hỏi phản biện hay gặp, nên chuẩn bị:
1. Vì sao không dùng MapReduce thuần?
2. Vì sao 4 worker chậm hơn 2 worker?
3. Kiểm tra tự động bỏ sót lỗi gì?
4. Batch size ảnh hưởng ra sao ở tầng inference và ở tầng kiểm chứng?
5. Nếu mô hình sinh định lý sai thì ai chịu trách nhiệm?
