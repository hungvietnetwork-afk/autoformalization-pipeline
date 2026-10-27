# Giấy phép và quyền riêng tư

## Dữ liệu đầu vào

| Nguồn | Lấy từ | Giấy phép | Bản sao giấy phép |
|---|---|---|---|
| ProofNet (đề và phát biểu Lean 3 gốc) | `zhangir-azerbayev/ProofNet` | MIT | `docs/licenses/proofnet.txt` |
| ProofNet, miniF2F bản Lean 4 | `deepseek-ai/DeepSeek-Prover-V1.5/datasets/` | MIT (mã DeepSeek-Prover) | `docs/licenses/deepseek_prover_code.txt` |
| miniF2F | `openai/miniF2F` (qua bản port trên) | MIT / Apache-2.0 (phần Lean) | `docs/licenses/minif2f_readme.md` |
| MATH | `openai/prm800k` (math_splits) | MIT | `docs/licenses/math.txt`, `docs/licenses/prm800k.txt` |
| GSM8K | `openai/grade-school-math` | MIT | `docs/licenses/gsm8k.txt` |

Toàn bộ dữ liệu là đề toán công khai, không chứa thông tin cá nhân. Theo yêu cầu của đề bài, bộ dữ liệu đầy đủ **không** được đưa vào Git.
Git chỉ giữ mẫu hợp pháp trong `data_sample/`, các split cố định trong `data/tiers/`, manifest kèm checksum trong `data/MANIFEST.json`, và script tải lại: `scripts/download_data.sh`, `python -m afp.ingest`.

## Công cụ

Lean 4, Mathlib và leanprover-community/repl đều dùng giấy phép Apache-2.0. Pipeline chỉ gọi các công cụ này, không sửa đổi chúng.

## Dữ liệu sinh ra

* Phát biểu Lean ứng viên do Claude Haiku 5.5 sinh. Việc sử dụng tuân theo điều khoản của nhà cung cấp mô hình (Anthropic).
  Corpus `data/formalized_corpus.jsonl` là sản phẩm phái sinh từ các đề toán ở trên, và ghi nguồn cùng giấy phép của từng bài.
* Nhãn audit là nhận xét về phát biểu toán học, không chứa dữ liệu cá nhân ngoài tên người chấm nếu nhóm điền vào.

## Mã nguồn của nhóm

Đề xuất phát hành theo giấy phép MIT. Nhóm cần xác nhận trước khi công khai repository.

## Rủi ro đã biết

Dữ liệu MATH, GSM8K và miniF2F đã công khai từ lâu, nên có thể đã nằm trong dữ liệu huấn luyện của LLM. Đây là rủi ro rò rỉ dữ liệu khi đọc compile rate như năng lực của mô hình (xem báo cáo, mục 7).
