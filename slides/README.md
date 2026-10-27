# Slide và demo

* **Bộ slide** (17 slide): `slides.pdf` trong thư mục này; bản trình chiếu trên trình duyệt (có ghi chú cho người trình bày,
  tải về được dạng PDF hoặc PPTX từ menu Share › Export): https://claude.ai/artifact/GkFy8gQD2RwgtxRHup43CF
* **Mã nguồn slide:** `deck/deck.json` (thứ tự, các phần) và `deck/slides/*.html` (mỗi slide một file, khung 1920 × 1080);
  ghi chú cho người trình bày của từng slide: `NOTES.md`.
* **Kịch bản demo 7 phút:** `docs/DEMO_SCRIPT.md`
* **Lệnh demo:** `python -m afp.demo_one --problem gsm8k:train:04141` (NL → Lean → checker cho một bài),
  `python -m afp.demo --n 20 --workers 2 --kill-after 8` (20 bài, giết một worker giữa chừng).
* **Không có Lean trên máy trình chiếu:** mở `demo/explorer.html` (Corpus Explorer, chạy offline).

| Phần | Slide | Nội dung |
|---|---|---|
| Mở đầu | 1–4 | Bài toán, hai câu hỏi nghiên cứu, dữ liệu |
| Hệ thống | 5–6 | Kiến trúc, baseline, các yếu tố thay đổi, metric chính |
| Câu hỏi 1 | 7–9 | Baseline và chất lượng, batching ở tầng inference, batch size ở tầng kiểm chứng |
| Khả năng mở rộng | 10–11 | Ma trận 100 → 10.000, đường cong worker |
| Câu hỏi 2 | 12–13 | Ba lớp kiểm tra ngữ nghĩa, audit, mutation test |
| Kết thúc | 14–17 | Chịu lỗi và retry, kết luận, phân vai và khai báo AI, hỏi đáp |

Mỗi con số trên slide lấy từ `results/figures/` hoặc `results/raw/`; nguồn ghi ở chân slide.
