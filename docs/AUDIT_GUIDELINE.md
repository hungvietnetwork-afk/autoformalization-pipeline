# Hướng dẫn audit ngữ nghĩa (cho hai người chấm của nhóm)

*Phiên bản 2 · chốt sau lần chấm thử bằng hai LLM*

## Mục đích

Lean chỉ kiểm tra phát biểu có đúng kiểu hay không. Audit đo phần Lean không đo được: phát biểu có nói đúng điều đề bài hỏi không.
Kết quả audit gồm độ chính xác ngữ nghĩa trên mẫu và độ đồng thuận giữa hai người chấm (Cohen's κ).
Audit cũng dùng để đo precision và recall của bộ kiểm tra tự động.

## Mẫu

* 100 phát biểu **đã compile được** của lần chạy `q_T1K_zeroshot`, lấy mẫu phân tầng theo nguồn: ProofNet 20, miniF2F 20, MATH 45, GSM8K 15.
* Mẫu đã đóng băng trong `audit/audit_key.csv` (seed cố định). Phiếu chấm của hai người là `audit/rater1.xlsx` và `audit/rater2.xlsx`.
* Phiếu chấm không hiển thị kết luận tự động, để người chấm không bị ảnh hưởng.

## Ba nhãn

| Nhãn | Khi nào |
|---|---|
| **DUNG** | Giữ đủ mọi giả thiết và đúng kết luận của đề, kiểu dữ liệu đúng. Với bài có đáp án, phát biểu khẳng định đúng đáp án cho đúng đại lượng được hỏi. |
| **GAN_DUNG** | Giữ nội dung toán nhưng lệch nhỏ: thừa hoặc thiếu một điều kiện phụ vô hại, cách viết khác nhưng tương đương, dùng ℕ thay ℤ khi mọi giá trị đều dương. |
| **SAI** | Sai nghĩa: thiếu giả thiết quan trọng hoặc giả thiết mâu thuẫn; kết luận khác, yếu hơn hoặc tầm thường; khẳng định sai đáp án hoặc khẳng định cho sai đại lượng; kiểu dữ liệu làm đổi nghĩa (phép trừ, phép chia trên ℕ bị cắt cụt). |

**Quy tắc chốt sau lần chấm thử.** Phát biểu chỉ còn là phép tính của lời giải, không còn biến hay giả thiết đại diện cho các đại lượng của đề (ví dụ `14 - (2 + 4) = 8`), được chấm **SAI**, kể cả khi các con số khớp với câu chuyện trong đề.
Lý do: khi đó phát biểu đúng hay sai phụ thuộc vào việc người formalize đã tự giải bài.

Ví dụ đã gặp: `math:test/algebra/2167` (giả thiết a + b = 7, a³ + b³ = 42 vô nghiệm trên ℝ) là SAI.
`proofnet:Dummit-Foote:exercise_4_2_8` (Lean quy ước `Subgroup.index = 0` cho chỉ số vô hạn, nên định lý đúng một cách tầm thường) là SAI.

## Cách làm

1. Hai người chấm **độc lập**: không trao đổi, không xem phiếu của nhau, không xem `audit_key.csv` hay kết quả kiểm tra tự động.
2. Mỗi dòng của phiếu điền cột `nhan` (DUNG / GAN_DUNG / SAI). Cột `ghi_chu` ghi lý do ngắn khi nhãn không phải DUNG.
3. Thời gian dự kiến: 2–3 giờ mỗi người. Bài ProofNet có cột `tham_khao_gold` là phát biểu do người viết cho Mathlib cũ, chỉ dùng để tham khảo.
4. Khi cả hai đã chấm xong:

```bash
python -m afp.audit kappa --a audit/rater1.xlsx --b audit/rater2.xlsx --out results/figures/audit_kappa_human.json
python -m afp.audit compare --rater audit/rater1.xlsx --sem results/raw/runs/q_T1K_zeroshot/semantic.jsonl \
  --out results/figures/audit_auto_vs_rater1.json
python -m afp.study quality && python -m afp.study layers        # cập nhật bảng chất lượng và ablation bộ kiểm tra
```

5. Sau khi tính κ, hai người thảo luận các mẫu bất đồng để chốt một nhãn cuối cho mỗi mẫu. Độ chính xác ngữ nghĩa cuối cùng tính trên nhãn đã chốt.
   Báo cáo ghi cả κ (trước thảo luận) và độ chính xác (sau thảo luận).
