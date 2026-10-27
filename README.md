# AI4Math – Nhóm 5: Autoformalization Pipeline

Sinh hàng loạt phát biểu Lean 4 từ đề toán ngôn ngữ tự nhiên, kiểm chứng chúng bằng Lean ở quy mô 100 → 1.000 → 10.000 task,
và đánh giá riêng tính hợp lệ hình thức (compile) với tính đúng nghĩa.

Học phần Dữ liệu lớn INT4418, Học viện Công nghệ Bưu chính Viễn thông. Giảng viên: TS. Nguyễn Kiều Linh.
Thành viên: Nguyễn Mai Hạnh (B25CHHT093), Lê Quang Đức (B25CHHT086), Nguyễn Việt Hưng (B25CHHT099), Kim Anh Dũng (B25CHHT087),
Bùi Giang Linh (B25CHHT103), Vũ Quốc Hùng (B25CHHT098). Phân vai: `contributions.md`.

## Mục tiêu và câu hỏi nghiên cứu

* **Q1.** Batching và số candidate ảnh hưởng thế nào tới throughput, chi phí và compile rate?
* **Q2.** Làm sao phát hiện trường hợp Lean chấp nhận nhưng phát biểu hình thức sai ý đề tự nhiên?

Nút thắt Big Data: chi phí tính toán và độ trễ. Mỗi Lean worker phải nạp Mathlib (27–45 s để một REPL sẵn sàng, 4,2 GB `.olean`), thời gian
kiểm một phát biểu có đuôi dài, mỗi request tới LLM bị giới hạn token đầu ra, và ở hàng nghìn bài sự kiện hiếm thành chắc chắn.

## Kiến trúc

```
Input queue ─► Prompt/version ─► Batch LLM inference ─► Candidate store ─► Lean worker pool ─► Result/error store ─► Aggregator
(16 partition,   (v1_zeroshot,      (batch job hoặc         (SQLite, khóa    (REPL nóng,          (UPSERT theo      + kiểm tra ngữ nghĩa
 SHA256 mod R)    v1_zeroshot_1req,  API OpenAI-compatible,  TaskHash, giữ    heartbeat 400000,    TaskHash,          + mẫu audit 100
                  v2_fewshot)        cache theo TaskHash)    output thô)      wall timeout 10/30 s) log thô)           → corpus)
```

`TaskHash = SHA256(problem_id ‖ prompt_version ‖ candidate_index)` là khóa của cache, hàng đợi và kết quả: chạy lại bao nhiêu lần thì
kết quả cuối vẫn như nhau. Hàng đợi có lease, ack, nack, release, retry tối đa 3 lần, dead-letter và work stealing; SQLite WAL cho một
máy, Redis Streams cho nhiều máy.

## Cấu trúc repository

| Đường dẫn | Nội dung |
|---|---|
| `src/afp/` | Mã nguồn (gói `afp`): `schema`, `ingest`, `queue`, `redis_backend`, `inference/`, `prompts`, `store`, `lean/`, `workers`, `pipeline`, `aggregator`, `semantic`, `mutation`, `audit`, `experiments`, `study`, `ablation`, `analysis`, `plots`, `runrecord`, `demo`, `demo_one` |
| `tests/` | Kiểm thử: hàng đợi (lease, release, chế độ indexed), TaskHash, sanitizer, backend với server giả lập lỗi 429, Redis Streams, Lean REPL, cấu hình |
| `configs/` | `experiments.json`: lưới tham số của mọi thí nghiệm (đọc bởi `afp.experiments`); `pipeline_defaults.json` |
| `data/` | Split cố định (`tiers/`), `MANIFEST.json` (nguồn, giấy phép, SHA-256), candidate store, job inference, corpus đã formalize |
| `data_sample/` | 100 bài T100 + ứng viên + bản ghi corpus: đủ để chạy pipeline khi chưa tải dữ liệu đầy đủ |
| `scripts/` | Cài Lean, tải dữ liệu, chạy nhanh, chạy lại toàn bộ thí nghiệm, sinh manifest, bảng, biểu đồ, ví dụ, gói bàn giao |
| `results/raw/` | Kết quả thô: `runs/<run_id>/` (raw_results, events, memory, metrics, config, `run_record.json`), `*_runs.csv`, `runs_manifest.csv` |
| `results/figures/` | Bảng và hình sinh bằng script từ `results/raw/` |
| `audit/` | Mẫu audit 100 bài (đóng băng), phiếu cho hai người chấm, nhãn chạy thử của hai LLM |
| `docs/` | Data card, system card, AI-use statement, giấy phép và quyền riêng tư, prompt, định dạng log, hướng dẫn audit, đề cương 1 trang, 20 ví dụ, kịch bản demo, đối chiếu yêu cầu, nhật ký thay đổi |
| `environment/` | Phiên bản khóa: Python packages, Lean toolchain, lake-manifest của Mathlib, mô tả máy |
| `demo/explorer.html` | Corpus Explorer offline: duyệt 1.000 phát biểu theo nguồn, trạng thái Lean, kết luận ngữ nghĩa, nhãn audit |
| `slides/` | Link bộ slide và cách xuất PDF/PPTX |
| `report.pdf`, `report.docx` | Báo cáo |
| `contributions.md` | Vai trò, người dự phòng, nhật ký đóng góp |

## Cài đặt

Linux, Python ≥ 3.11 (đã dùng 3.13), khoảng 10 GB đĩa.

```bash
python -m pip install -e ".[test]"        # hoặc: pip install -r environment/requirements.lock.txt
bash scripts/setup_lean.sh                # Lean 4 v4.35.0, Mathlib v4.35.0 (.olean từ cache.mathlib.org), REPL v4.35.0
export AFP_LEAN_ROOT=$HOME/lean
```

## Dữ liệu

22.150 đề từ ProofNet (bản Lean 4), miniF2F, MATH, GSM8K, tải từ GitHub. NuminaMath-CoT không tải được trong môi trường thí nghiệm
nên được thay bằng MATH và GSM8K, hai nguồn con của nó. Ba tầng lồng nhau T100 ⊂ T1K ⊂ T10K (seed 42) và tập con T20 cho baseline.
Git không chứa bộ dữ liệu đầy đủ: chỉ có `data_sample/`, các split, manifest có SHA-256 và script dựng lại. Chi tiết: `docs/DATA_CARD.md`.

```bash
bash scripts/download_data.sh             # data/raw/
python -m afp.ingest                      # data/units/, data/lake/units/ (Parquet source=/domain=), data/tiers/
python scripts/make_manifest.py           # data/MANIFEST.json, data_sample/
```

## Chạy nhanh

```bash
bash scripts/quickstart.sh     # test, một lần chạy cấu hình baseline trên T100, demo NL → Lean → checker cho một bài (5–8 phút)
python -m afp.demo_one --problem gsm8k:train:02691          # demo một bài
python -m afp.demo --n 20 --workers 2 --kill-after 8          # 20 bài, giết 1 worker giữa chừng
```

## Tái tạo kết quả chính

Ứng viên đã sinh nằm trong `data/candidates.db` theo TaskHash, nên các lệnh dưới không gọi lại mô hình.

```bash
bash scripts/run_all.sh                   # mọi thí nghiệm của báo cáo, đúng thứ tự; chạy tiếp được nếu bị ngắt
# hoặc từng phần
python -m afp.experiments baseline        # baseline bắt buộc trên T20
python -m afp.experiments matrix          # 100/1K/10K × A/B/C × 3 lần
python -m afp.experiments batch           # batch size 1/8/32 + index, 2 worker, 3 tầng × 3 lần
python -m afp.experiments scaling         # 1/2/4/8 Lean worker trên 10.000 task
python -m afp.experiments retry           # giết worker, giao tối đa 1 hoặc 3 lần
python -m afp.experiments release         # ablation release khi khởi động lại REPL
python -m afp.experiments repro           # ô T1K/A trên máy hiện tại, 3 lần
python -m afp.study all                   # bảng: inference batching, candidates, chất lượng, các lớp ngữ nghĩa, baseline, ablation, manifest
python -m afp.plots                       # hình PNG trong results/figures/
python -m pytest -q                       # Redis test cần redis-server ở cổng 6390, nếu không sẽ bỏ qua
```

Sinh lại ứng viên bằng một mô hình khác: `python -m afp.inference.batchfile export --tier data/tiers/T1K.txt --version v1_zeroshot --k 1 --partitions 8`,
cho mô hình điền `data/jobs/v1_zeroshot/*.out.txt`, rồi `python -m afp.inference.batchfile import --jobs data/jobs/v1_zeroshot --model <tên>`;
hoặc dùng backend OpenAI-compatible trong `src/afp/inference/backends.py`.

Audit người: hai thành viên chấm độc lập `audit/rater1.xlsx`, `audit/rater2.xlsx` theo `docs/AUDIT_GUIDELINE.md`, rồi
`python -m afp.audit kappa --a audit/rater1.xlsx --b audit/rater2.xlsx` và `python -m afp.study quality`.

## Kết quả chính

Máy 2 vCPU, 7,8 GB RAM, không GPU. Mỗi lần chạy có `run_record.json` (mẫu Phụ lục B của hướng dẫn).

| | |
|---|---|
| Baseline một bài mỗi request (T20) so với batch job | Cùng chất lượng (20/20 compile, 2/20 bị gắn cờ); 87.561 so với 1.752–2.080 token mỗi bài |
| Compile rate zero-shot, 1.000 bài | 98,9 % (parse rate 99,7 %); 18,7 % phát biểu compile được bị gắn cờ sai nghĩa, 29,4 % được Lean xác nhận |
| Gom bài vào một request LLM | 1 → 20–26 bài: token mỗi bài giảm 42 lần, 7,7 % request hỏng; 100–142 bài: 58 % request hỏng |
| 1 so với 4 candidate (few-shot) | Pass@1 0,9825 → Pass@4 1,00 với gấp 4 lần token; tỷ lệ bị gắn cờ không đổi (13 %) |
| Batch size kiểm chứng (2 worker, 3 lần mỗi ô) | Lô 1, 8, 32 cho throughput như nhau trong biên độ giữa các lần chạy: khoảng 1,6 bài/s ở 100 bài, 10,8–11,2 ở 1.000 bài, 16,0–18,8 ở 10.000 task (median); ở 10.000 task, số timeout (2–6 mỗi lần chạy) quyết định tốc độ, index hàng đợi không đổi kết luận |
| Ma trận 100 → 10.000, wall timeout 10 s | Thêm worker không nhanh hơn ở cả ba mức; ở 10.000 task, khởi động lại REPL chiếm 45 % thời gian worker với 2 worker |
| Chạy lại ô T1K/A trên máy đợt 26/10 (3 lần) | 8,6 so với 15,8 bài/s: khởi động REPL 40 so với 27 s và 2/3 lần chạy gặp một timeout; tốc độ kiểm một ứng viên như nhau. Chỉ so sánh trong cùng một đợt |
| Đường cong worker, heartbeat là giới hạn chính | 29,8 → 51,9 ứng viên/s từ 1 lên 2 worker (1,74 lần); 4 và 8 worker sụp vì tranh CPU và RAM |
| Giết worker; retry | Giao lại tối đa 3 lần: 1.000/1.000, 0 trùng. Không giao lại: 995/1.000, 8 task vào dead-letter |
| Trả lô về hàng đợi khi khởi động lại REPL (1.000 task, timeout 10 s) | Makespan 106 s so với 147 s, thời gian ổn định 43 s so với 85 s (median 3 lần mỗi bên) |
| Kiểm tra ngữ nghĩa so với người chấm thử | Precision 0,73, recall 0,58; mutation test: có gold thì bắt mọi lỗi cài sẵn, không có gold thì đáp án sai chỉ bị bắt 26 % |
| REPL nóng so với chạy lạnh | 45,8 ms so với 20,2 s mỗi ứng viên (442 lần) |

Độ chính xác ngữ nghĩa trên tập audit hiện là kết quả chạy thử bằng hai LLM (81 % và 82 % ĐÚNG); số cuối chờ hai thành viên chấm.
Báo cáo đầy đủ: `report.pdf` (bản trực tuyến trên Claude Docs: https://claude.ai/code/artifact/6b20a6e7-97b7-414e-bae6-64d113472841).

## Sử dụng AI

Dự án dùng Claude làm trợ lý lập trình và viết, Claude Haiku 5.5 làm mô hình sinh mã được đánh giá, và hai LLM làm người chấm thử.
Chi tiết và việc nhóm phải tự kiểm chứng: `docs/AI_USE_STATEMENT.md`.
