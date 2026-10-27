# Phụ lục – Prompt

Ba phiên bản prompt. Phiên bản là một phần của TaskHash, nên đổi prompt sẽ tạo task mới chứ không ghi đè kết quả cũ. Định nghĩa trong `src/afp/prompts.py` (`PROMPT_VERSIONS`); file prompt và output thô của từng job nằm trong `data/jobs/<phiên bản>/`.

| Phiên bản | Ví dụ mẫu | Số mẫu mỗi bài | Số bài mỗi request | Dùng cho |
|---|---|---|---|---|
| `v1_zeroshot` | 0 | 1 | batch job 9–142 bài | 1.000 bài T1K; ba mức quy mô |
| `v1_zeroshot_1req` | 0 | 1 | 1 | baseline bắt buộc trên 20 bài T20 |
| `v2_fewshot` | 6 | 4 | batch job 20–142 bài | 100 bài T100: few-shot, 1 so với nhiều candidate |

## v1_zeroshot (baseline: zero-shot, 1 mẫu/bài)

```text
You are an autoformalization system. Translate the natural-language mathematical statement into ONE Lean 4 theorem statement that uses Mathlib (Lean v4.35, Mathlib 2026).
The following header is already in place (do not repeat it):
import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators Real Nat Topology Rat

Requirements:
- Output only the theorem, in the form `theorem <name> <binders> : <proposition> := by sorry`.
- No proof, no comments, no imports, no markdown.
- If the problem ends with "Answer: ...", the theorem must assert that this answer is correct
  (e.g. the requested quantity equals the answer, or the solution set equals the given set).
- Keep every hypothesis and the exact conclusion of the original statement; do not simplify or weaken it.
```

## v1_zeroshot_1req (baseline bắt buộc: zero-shot, một bài mỗi request, 1 mẫu)

Cùng nội dung chỉ dẫn với `v1_zeroshot`; mỗi request chỉ chứa một đề (file `data/jobs/v1_zeroshot_1req/prompts/P###.txt`) và mô hình trả về đúng một định lý. Tách thành phiên bản riêng để TaskHash của baseline khác với ứng viên batch job của cùng bài. System prompt: `data/jobs/v1_zeroshot_1req/SYSTEM_PROMPT.txt`.

## v2_fewshot (6 ví dụ tự viết, không lấy từ dữ liệu đánh giá; 4 mẫu độc lập/bài)

```text
You are an autoformalization system. Translate the natural-language mathematical statement into ONE Lean 4 theorem statement that uses Mathlib (Lean v4.35, Mathlib 2026).
The following header is already in place (do not repeat it):
import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators Real Nat Topology Rat

Requirements:
- Output only the theorem, in the form `theorem <name> <binders> : <proposition> := by sorry`.
- No proof, no comments, no imports, no markdown.
- If the problem ends with "Answer: ...", the theorem must assert that this answer is correct
  (e.g. the requested quantity equals the answer, or the solution set equals the given set).
- Keep every hypothesis and the exact conclusion of the original statement; do not simplify or weaken it.

Examples:

Problem:
What is the sum of all real solutions of $x^2-5x+6=0$?
Answer: 5
Lean:
theorem ex1 (S : Finset ℝ) (hS : ∀ x : ℝ, x ∈ S ↔ x ^ 2 - 5 * x + 6 = 0) :
    ∑ x ∈ S, x = 5 := by sorry

Problem:
How many positive divisors does $36$ have?
Answer: 9
Lean:
theorem ex2 : (Nat.divisors 36).card = 9 := by sorry

Problem:
A shop sells pens at $3 each. Tom buys 7 pens and pays with a $50 bill. How much change does he get?
Answer: 29
Lean:
theorem ex3 (price n paid change : ℕ) (h₀ : price = 3) (h₁ : n = 7) (h₂ : paid = 50)
    (h₃ : change = paid - price * n) : change = 29 := by sorry

Problem:
Find the real number $x$ such that $2^{x+1}=32$.
Answer: 4
Lean:
theorem ex4 (x : ℝ) (h : (2 : ℝ) ^ (x + 1) = 32) : x = 4 := by sorry

Problem:
Prove that if every element $g$ of a group $G$ satisfies $g^2=1$, then $G$ is abelian.
Lean:
theorem ex5 {G : Type*} [Group G] (h : ∀ g : G, g ^ 2 = 1) :
    ∀ a b : G, a * b = b * a := by sorry

Problem:
Let $f:\mathbb{R}\to\mathbb{R}$ be continuous and satisfy $f(x)=f(x+1)$ for all $x$. Prove that $f$ is bounded.
Lean:
theorem ex6 (f : ℝ → ℝ) (hf : Continuous f) (hp : ∀ x, f x = f (x + 1)) :
    ∃ M, ∀ x, |f x| ≤ M := by sorry
```

Mỗi bài được đưa vào dưới dạng `Problem:\n<natural_statement>\nLean:`.
