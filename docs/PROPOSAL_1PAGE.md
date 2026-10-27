# Đề cương một trang (mẫu Phụ lục A) – bản đối chiếu cuối kỳ

| Mục | Nội dung |
|---|---|
| **Tên nhóm và đề tài** | Nhóm 5 – Autoformalization Pipeline: chuyển đề toán sang Lean theo lô |
| **Câu hỏi nghiên cứu** | (Q1) Batching và số candidate ảnh hưởng thế nào tới throughput, chi phí và compile rate? (Q2) Làm sao phát hiện trường hợp Lean chấp nhận nhưng phát biểu hình thức sai ý đề tự nhiên? |
| **Nút thắt Big Data** | Chi phí tính toán và độ trễ: nạp Mathlib mất 20–45 s mỗi lần; kiểm chứng có đuôi dài và cần timeout từng task; giới hạn token đầu ra của mỗi request tới LLM; hàng đợi và log lớn dần theo số task. Giả thuyết đo được: (H1) ở 10.000 task, giá của sự kiện hiếm (timeout dẫn tới khởi động lại REPL) chiếm phần lớn thời gian worker; (H2) throughput tăng theo số worker đến khi chạm số nhân CPU; (H3) gom nhiều bài vào một request giảm token mỗi bài nhưng tăng tỷ lệ request thất bại. |
| **Dữ liệu và giấy phép** | ProofNet 371 bài (MIT, bản Lean 4 của DeepSeek-Prover-V1.5); miniF2F 488 (MIT / Apache-2.0); MATH 12.499 (MIT); GSM8K 8.792 (MIT). NuminaMath-CoT không tải được (HuggingFace bị chặn trong môi trường), thay bằng MATH và GSM8K, hai nguồn con của nó. Tổng 22.150 đề. |
| **Baseline** | Zero-shot, một bài mỗi request, một candidate, Lean kiểm tra bằng một worker, không repair. Cùng dữ liệu, cùng split, cùng phần cứng, cùng timeout với phương pháp chính. |
| **Ba mức quy mô / tải** | 100 → 1.000 → 10.000 bài (T100 ⊂ T1K ⊂ T10K, seed 42). Thêm batch size 1/8/32, 1/2/4/8 Lean worker, 1 so với 4 candidate, zero-shot so với few-shot, retry 1 so với 3 lần. |
| **Primary metrics** | (1) Semantic accuracy trên tập audit (chất lượng); (2) throughput ổn định, tính bằng ứng viên mỗi giây (hệ thống). Chỉ số phụ: parse rate, compile rate, Pass@k, P50/P95, token, tỷ lệ lỗi theo loại. |
| **Kiến trúc** | Input queue (16 partition) → prompt/version manager → batch LLM inference → candidate store (TaskHash) → Lean worker pool (REPL nóng) → result/error store (UPSERT) → aggregator + kiểm tra ngữ nghĩa + mẫu audit. |
| **Phân vai** | Data/evaluation · Prompt & model · Batch scheduler · Lean worker pool · Semantic audit · Metrics/reproducibility. Mỗi vai trò có người dự phòng (`contributions.md`). |
| **Rủi ro và phương án dự phòng** | Hết ngân sách token: giảm còn 1.000 bài, tầng 10K dùng trace replay. Mathlib mới làm hỏng phát biểu gold: khóa phiên bản, viết lại cú pháp. Máy chỉ có 2 vCPU: đo đến 8 worker, ngoại suy có ghi rõ, thiết kế sẵn Redis cho nhiều máy. Thiếu người chấm: chạy thử quy trình bằng LLM, giữ phiếu cho hai thành viên. |
