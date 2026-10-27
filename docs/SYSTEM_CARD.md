# System card – Autoformalization Pipeline (Nhóm 5)

*Phiên bản 0.3 · 27/10/2026*

## Hệ thống làm gì

Hệ thống nhận đề toán bằng ngôn ngữ tự nhiên và sinh hàng loạt phát biểu Lean 4. Phần chứng minh để `sorry`, vì nhóm kiểm chứng phát biểu chứ chưa chứng minh định lý.
Lean 4 / Mathlib kiểm chứng từng phát biểu. Sau đó một bộ kiểm tra ngữ nghĩa ba lớp phân biệt phát biểu *compile được* với phát biểu *đúng nghĩa*.
Đầu ra là một corpus: mỗi bài có phát biểu được chọn kèm kết luận ngữ nghĩa và cờ.

```
Hàng đợi đề ─► Prompt/version ─► Batch LLM inference ─► Candidate store ─► Lean worker pool ─► Result/error store ─► Aggregator + kiểm tra ngữ nghĩa ─► corpus
(16 partition)  (v1, v2, v1_1req)  (batch job / 1 bài một request)  (TaskHash)   (REPL nóng)   (UPSERT)   (Pass@k, audit)
```

## Thành phần

| Thành phần | Hiện thực | Phiên bản |
|---|---|---|
| Mô hình sinh mã | Claude Haiku 5.5, không fine-tune; gọi theo batch job hoặc một bài mỗi request | — |
| Prompt | `v1_zeroshot`, `v1_zeroshot_1req` (cùng nội dung, một bài mỗi request), `v2_fewshot` (6 ví dụ tự viết, 4 mẫu) | `docs/PROMPTS.md` |
| Bộ kiểm chứng | Lean 4 + Mathlib + leanprover-community/repl; maxHeartbeats 400000, hard timeout 10 s hoặc 30 s | `environment/ENVIRONMENT.md` |
| Hàng đợi | SQLite WAL (một máy) hoặc Redis Streams (nhiều máy); lease, retry ≤ 3, dead-letter, work stealing | `src/afp/queue.py`, `src/afp/redis_backend.py` |
| Kiểm tra ngữ nghĩa | Lean: giả thiết mâu thuẫn, phản chứng, tự chứng minh, tương đương gold. Heuristic: đáp án có trong phát biểu, chỉ còn phép tính, kiểu ℕ cắt cụt. | `src/afp/semantic.py` |

## Mục đích sử dụng

* **Phù hợp:** sinh ứng viên phát biểu hình thức cho người kiểm tra; đo chi phí và khả năng mở rộng của tầng kiểm chứng; nghiên cứu cách phát hiện phát biểu compile được nhưng sai nghĩa.
* **Không phù hợp:** coi phát biểu compile được là bản dịch đúng; dùng corpus làm dữ liệu chuẩn (gold) khi chưa có audit người; dùng làm bằng chứng toán học.

## Đánh giá (chi tiết trong báo cáo)

| Khía cạnh | Kết quả |
|---|---|
| Hợp lệ hình thức | Zero-shot, 1.000 bài: parse rate 99,7 %, compile rate 98,9 % |
| Ngữ nghĩa, tự động | 18,7 % phát biểu compile được bị gắn cờ; 29,4 % được Lean xác nhận (tương đương gold hoặc Lean tự suy ra đáp án) |
| Ngữ nghĩa, audit 100 mẫu | Chạy thử với 2 LLM: 81 % và 82 % được chấm ĐÚNG, κ = 0,83 (đúng / không). Kiểm tra tự động so với người chấm thử: precision 0,73, recall 0,58. Audit hai người: chưa có. |
| Chi phí sinh mã | Một bài mỗi request: 87.561 token mỗi bài (gồm khoảng 80K ngữ cảnh cố định của mỗi request); gom 20–26 bài: 2.080 token, 7,7 % request hỏng; gom 100–142 bài: 1.752 token, 58 % request hỏng |
| Hệ thống | REPL nóng nhanh hơn chạy lạnh 442 lần; 2 worker nhanh gấp 1,74 lần 1 worker trên 2 vCPU; giết một worker giữa chừng không làm mất hay trùng kết quả khi có retry (không retry: mất 0,5 % kết quả); trả lô về hàng đợi khi khởi động lại REPL giảm makespan 28 %; ở 2 worker, lô 1, 8 hay 32 task cho throughput như nhau |

## Hạn chế

Hệ thống chỉ thử với một mô hình sinh mã và trên một máy 2 vCPU. Tầng 10.000 task là trace replay (10 bản sao của 1.000 ứng viên thật).
Kiểm tra tự động chỉ chứng minh được theo một chiều: không tìm ra lỗi chưa có nghĩa là đúng. Với bài chỉ có đáp án, kiểm tra tự động bỏ sót phần lớn lỗi nội dung (mutation test: đáp án sai chỉ bị bắt 26 %).

## Rủi ro và đạo đức (risk/ethics note)

| Rủi ro | Biện pháp |
|---|---|
| Định lý sai nghĩa nhưng compile được được dùng như đúng | Mọi bản ghi corpus kèm kết luận và cờ ngữ nghĩa; không tuyên bố đúng nghĩa chỉ dựa vào compile; audit hai người |
| Rò rỉ dữ liệu: đề công khai có thể đã nằm trong dữ liệu huấn luyện của LLM | Ghi trong data card; không diễn giải compile rate như năng lực tổng quát của mô hình |
| Dùng LLM làm người chấm gây thiên lệch | LLM chỉ chấm thử để kiểm tra quy trình; số liệu cuối dùng hai người chấm |
| Chi phí token, năng lượng | Ghi token theo từng job hoặc request (`results/raw/inference_jobs.json`); cache theo TaskHash, nên chạy lại không gọi lại model |
| Nhãn dữ liệu sai làm phát biểu "trung thành với nhãn" thành sai | Hai lỗi nhãn MATH đã ghi trong data card |
| Liêm chính học thuật | Khai báo AI đầy đủ (`docs/AI_USE_STATEMENT.md`) |

Dữ liệu không chứa thông tin cá nhân. Giấy phép dữ liệu: `docs/LICENSE_PRIVACY.md`.
