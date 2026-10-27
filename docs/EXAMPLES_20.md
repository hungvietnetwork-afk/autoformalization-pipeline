# 20 ví dụ NL → Lean (đặc tả tuần 1)

Hai mươi bài của tập con cố định T20 (lấy theo nguồn, thứ tự SHA-256 của `problem_id`; quy tắc trong `data/jobs/v1_zeroshot_1req/SUBSET_20.json`). Phát biểu Lean là output của baseline bắt buộc: zero-shot, một bài mỗi request, một ứng viên (prompt `v1_zeroshot_1req`, mô hình Claude Haiku 5.5). Trạng thái Lean và kết luận ngữ nghĩa lấy từ lần chạy `base_T20_1req_A`.

File này được sinh bằng `python scripts/make_examples.py`; không sửa tay.

## 1. `gsm8k:train:01484`

Nguồn gsm8k, lĩnh vực arithmetic_word_problem. Lean: **COMPILE_OK** (16 ms). Kết luận tự động: **Lean suy ra đáp án từ giả thiết**.

> Lucy lost one-third of her money. She then spent one-fourth of the remainder, and only left with $15. How much money did Lucy have at the beginning?
> Answer: 30

```lean
theorem cand_bb93e44c5422 (x : ℝ) (h : (x - x / 3) - (x - x / 3) / 4 = 15) : x = 30 := by sorry
```

## 2. `gsm8k:train:02960`

Nguồn gsm8k, lĩnh vực arithmetic_word_problem. Lean: **COMPILE_OK** (17 ms). Kết luận tự động: **không thấy lỗi**.

> Emily can type 60 words per minute. How many hours does it take her to write 10,800 words?
> Answer: 3

```lean
theorem cand_691a7b513af7 (rate words hours : ℝ) (h_rate : rate = 60) (h_words : words = 10800) (h_hours : hours = words / rate / 60) : hours = 3 := by sorry
```

## 3. `math:test/algebra/1264`

Nguồn math, lĩnh vực algebra. Lean: **COMPILE_OK** (16 ms). Kết luận tự động: **Lean suy ra đáp án từ giả thiết**.

> Evaluate $24-(2x-y)$ if $x=4$ and $y=3$.
> Answer: 19

```lean
theorem cand_628b5cb3ff5b (x y : ℝ) (hx : x = 4) (hy : y = 3) : 24 - (2 * x - y) = 19 := by sorry
```

## 4. `math:test/algebra/2584`

Nguồn math, lĩnh vực algebra. Lean: **COMPILE_OK** (24 ms). Kết luận tự động: **không thấy lỗi**.

> If $f(x) = \frac{3x-2}{x-2}$, what is the value of $f(-2) +f(-1)+f(0)$? Express your answer as a common fraction.
> Answer: \frac{14}{3}

```lean
theorem cand_846122650434 (f : ℝ → ℝ) (hf : ∀ x : ℝ, x ≠ 2 → f x = (3 * x - 2) / (x - 2)) : f (-2) + f (-1) + f 0 = 14 / 3 := by sorry
```

## 5. `math:test/counting_and_probability/148`

Nguồn math, lĩnh vực counting_probability. Lean: **COMPILE_OK** (99 ms). Kết luận tự động: **không thấy lỗi**.

> The digits from 1 to 6 are arranged to form a six-digit multiple of 5. What is the probability that the number is greater than 500,000? Express your answer as a common fraction.
> Answer: \frac{1}{5}

```lean
theorem cand_10c66ad2752a :
    ((Set.ncard {l : List ℕ | l.Perm [1, 2, 3, 4, 5, 6] ∧ 5 ∣ Nat.ofDigits (10 : ℕ) l.reverse ∧
        500000 < Nat.ofDigits (10 : ℕ) l.reverse} : ℕ) : ℚ) /
      ((Set.ncard {l : List ℕ | l.Perm [1, 2, 3, 4, 5, 6] ∧ 5 ∣ Nat.ofDigits (10 : ℕ) l.reverse} : ℕ) : ℚ) = 1 / 5 := by sorry
```

## 6. `math:test/intermediate_algebra/1079`

Nguồn math, lĩnh vực intermediate_algebra. Lean: **COMPILE_OK** (86 ms). Kết luận tự động: **không thấy lỗi**.

> Let $(a_1,b_1),$ $(a_2,b_2),$ $\dots,$ $(a_n,b_n)$ be all the ordered pairs $(a,b)$ of complex numbers with $a^2+b^2\neq 0,$
> \[a+\frac{10b}{a^2+b^2}=5, \quad \text{and} \quad b+\frac{10a}{a^2+b^2}=4.\]Find $a_1 + b_1 + a_2 + b_2 + \dots + a_n + b_n.$
> Answer: 18

```lean
theorem cand_88298253950f (S : Finset (ℂ × ℂ))
    (hS : ∀ p : ℂ × ℂ, p ∈ S ↔ (p.1 ^ 2 + p.2 ^ 2 ≠ 0 ∧ p.1 + 10 * p.2 / (p.1 ^ 2 + p.2 ^ 2) = 5 ∧ p.2 + 10 * p.1 / (p.1 ^ 2 + p.2 ^ 2) = 4)) :
    ∑ p ∈ S, (p.1 + p.2) = 18 := by sorry
```

## 7. `math:test/intermediate_algebra/243`

Nguồn math, lĩnh vực intermediate_algebra. Lean: **COMPILE_OK** (26 ms). Kết luận tự động: **không thấy lỗi**.

> Let $f_1$, $f_2$, $f_3$, $\dots$ be a sequence of numbers such that
> \[
>   f_n = f_{n - 1} + f_{n - 2}
> \]for every integer $n \ge 3$.  If $f_7 = 83$, what is the sum of the first 10 terms of the sequence?
> Answer: 913

```lean
theorem cand_57d34b51e338 (f : ℕ → ℝ) (hrec : ∀ n : ℕ, 3 ≤ n → f n = f (n - 1) + f (n - 2)) (h7 : f 7 = 83) : (∑ i ∈ Finset.Icc 1 10, f i) = 913 := by sorry
```

## 8. `math:test/precalculus/1043`

Nguồn math, lĩnh vực precalculus. Lean: **COMPILE_OK** (75 ms). Kết luận tự động: **cờ: thiếu đáp án**.

> Let $\mathbf{A} = \begin{pmatrix} 15 & 25 \\ -9 & -15 \end{pmatrix}.$  Compute
> \[\mathbf{I} + 2 \mathbf{A} + 3 \mathbf{A}^2 + 4 \mathbf{A}^3 + \dotsb.\]
> Answer: \begin{pmatrix} 31 & 50 \\ -18 & -29 \end{pmatrix}

```lean
theorem cand_947d71c5b28c (A : Matrix (Fin 2) (Fin 2) ℝ) (hA : A = !![15, 25; -9, -15]) : ∑' n : ℕ, ((n : ℝ) + 1) • (A ^ n) = !![31, 50; -18, -29] := by sorry
```

## 9. `math:test/precalculus/428`

Nguồn math, lĩnh vực precalculus. Lean: **COMPILE_OK** (28 ms). Kết luận tự động: **không thấy lỗi**.

> A graph is defined in polar coordinates by $r = \cos \theta + \frac{1}{2}.$  Find the smallest $x$-coordinate of any point on this graph.
> Answer: -\frac{1}{16}

```lean
theorem cand_501cd1237aa4 : IsLeast (Prod.fst '' {p : ℝ × ℝ | ∃ θ : ℝ, p = ((Real.cos θ + 1 / 2) * Real.cos θ, (Real.cos θ + 1 / 2) * Real.sin θ)}) (-1 / 16) := by sorry
```

## 10. `math:train/algebra/2132`

Nguồn math, lĩnh vực algebra. Lean: **COMPILE_OK** (23 ms). Kết luận tự động: **không thấy lỗi**.

> Murtha has decided to start a pebble collection. She collects one pebble the first day and two pebbles on the second day. On each subsequent day she collects one more pebble than the previous day. How many pebbles will she have collected at the end of the twelfth day?
> Answer: 78

```lean
theorem cand_e67ef1822bce (d : ℕ → ℕ) (h1 : d 1 = 1) (h2 : d 2 = 2) (hstep : ∀ n : ℕ, 2 ≤ n → d (n + 1) = d n + 1) : (∑ i ∈ Finset.Icc 1 12, d i) = 78 := by sorry
```

## 11. `math:train/algebra/2234`

Nguồn math, lĩnh vực algebra. Lean: **COMPILE_OK** (63 ms). Kết luận tự động: **không thấy lỗi**.

> How many terms are in the expansion of  \[(a+b+c)(d+e+f+g)?\]
> Answer: 12

```lean
theorem cand_c8e05678a7d3 : (MvPolynomial.support ((MvPolynomial.X 0 + MvPolynomial.X 1 + MvPolynomial.X 2) * (MvPolynomial.X 3 + MvPolynomial.X 4 + MvPolynomial.X 5 + MvPolynomial.X 6) : MvPolynomial (Fin 7) ℤ)).card = 12 := by sorry
```

## 12. `math:train/counting_and_probability/177`

Nguồn math, lĩnh vực counting_probability. Lean: **COMPILE_OK** (47 ms). Kết luận tự động: **không thấy lỗi**.

> Each face of a cube is painted either  red or blue, each with probability 1/2. The color of each face is determined independently.  What is the probability that the painted cube can be placed on a horizontal surface so that the four vertical faces are all the same color?
> Answer: \frac{5}{16}

```lean
theorem cand_eca54f5fc09b :
    (Finset.card (Finset.filter (fun c : Fin 6 → Bool =>
        ∃ b : Fin 6, ∃ col : Bool, ∀ f : Fin 6,
          f ≠ b → f ≠ (![1, 0, 3, 2, 5, 4] : Fin 6 → Fin 6) b → c f = col)
        (Finset.univ : Finset (Fin 6 → Bool))) : ℝ) /
      (Fintype.card (Fin 6 → Bool) : ℝ) = 5 / 16 := by sorry
```

## 13. `math:train/intermediate_algebra/448`

Nguồn math, lĩnh vực intermediate_algebra. Lean: **COMPILE_OK** (52 ms). Kết luận tự động: **không thấy lỗi**.

> The polynomial equation \[x^3 + bx + c = 0,\]where $b$ and $c$ are rational numbers, has $3-\sqrt{7}$ as a root. It also has an integer root. What is it?
> Answer: -6

```lean
theorem cand_98ff687b88cd (b c : ℚ) (h_root : (3 - Real.sqrt 7) ^ 3 + (b : ℝ) * (3 - Real.sqrt 7) + (c : ℝ) = 0) (h_int : ∃ n : ℤ, (n : ℝ) ^ 3 + (b : ℝ) * (n : ℝ) + (c : ℝ) = 0) : ∀ n : ℤ, (n : ℝ) ^ 3 + (b : ℝ) * (n : ℝ) + (c : ℝ) = 0 → n = -6 := by sorry
```

## 14. `math:train/intermediate_algebra/471`

Nguồn math, lĩnh vực intermediate_algebra. Lean: **COMPILE_OK** (104 ms). Kết luận tự động: **không thấy lỗi**.

> Compute the sum of the squares of the roots of the equation \[x^{2018} +44x^{2015} + 3x^3 + 404 = 0.\]
> Answer: 0

```lean
theorem cand_5686a554eb6a : (((Polynomial.X ^ 2018 + 44 * Polynomial.X ^ 2015 + 3 * Polynomial.X ^ 3 + 404 : Polynomial ℂ).roots).map (fun r => r ^ 2)).sum = 0 := by sorry
```

## 15. `math:train/number_theory/7029`

Nguồn math, lĩnh vực number_theory. Lean: **COMPILE_OK** (68 ms). Kết luận tự động: **không thấy lỗi**.

> A $150\times 324\times 375$ rectangular solid is made by gluing together $1\times 1\times 1$ cubes. An internal diagonal of this solid passes through the interiors of how many of the $1\times 1\times 1$ cubes?
> Answer: 768

```lean
theorem cand_4aef41e2b9b3 :
    Set.ncard {c : ℕ × ℕ × ℕ | c.1 < 150 ∧ c.2.1 < 324 ∧ c.2.2 < 375 ∧
      ∃ t : ℝ, 0 ≤ t ∧ t ≤ 1 ∧
        (c.1 : ℝ) < 150 * t ∧ 150 * t < (c.1 : ℝ) + 1 ∧
        (c.2.1 : ℝ) < 324 * t ∧ 324 * t < (c.2.1 : ℝ) + 1 ∧
        (c.2.2 : ℝ) < 375 * t ∧ 375 * t < (c.2.2 : ℝ) + 1} = 768 := by sorry
```

## 16. `math:train/precalculus/301`

Nguồn math, lĩnh vực precalculus. Lean: **COMPILE_OK** (36 ms). Kết luận tự động: **cờ: thiếu đáp án**.

> Let $\mathbf{M}$ be a matrix, and let $\mathbf{v}$ and $\mathbf{w}$ be vectors, such that
> \[\mathbf{M} \mathbf{v} = \begin{pmatrix} 1 \\ -5 \end{pmatrix} \quad \text{and} \quad \mathbf{M} \mathbf{w} = \begin{pmatrix} 7 \\ 2 \end{pmatrix}.\]Compute $\mathbf{M} (-2 \mathbf{v} + \mathbf{w}).$
> Answer: \begin{pmatrix} 5 \\ 12 \end{pmatrix}

```lean
theorem cand_a796e63634a4 (M : Matrix (Fin 2) (Fin 2) ℝ) (v w : Fin 2 → ℝ)
    (hv : M.mulVec v = ![1, -5]) (hw : M.mulVec w = ![7, 2]) :
    M.mulVec ((-2 : ℝ) • v + w) = ![5, 12] := by sorry
```

## 17. `minif2f:test:amc12a_2020_p25`

Nguồn minif2f, lĩnh vực competition. Lean: **COMPILE_OK** (50 ms). Kết luận tự động: **không thấy lỗi**.

> The number $a=\frac{p}{q}$, where $p$ and $q$ are relatively prime positive integers, has the property that the sum of all real numbers $x$ satisfying
> $ \lfloor x \rfloor \cdot \{x\} = a \cdot x^2$
> is $420$, where $\lfloor x \rfloor$ denotes the greatest integer less than or equal to $x$ and $\{x\}=x- \lfloor x \rfloor$ denotes the fractional part of $x$. What is $p+q$?
> 
> $\textbf{(A) } 245 \qquad \textbf{(B) } 593 \qquad \textbf{(C) } 929 \qquad \textbf{(D) } 1331 \qquad \textbf{(E) } 1332$ Show that it is \textbf{(C) } 929.

```lean
theorem cand_b1c08aac3cdf (p q : ℕ) (hp : 0 < p) (hq : 0 < q) (hpq : Nat.Coprime p q) (h : (∑ᶠ x ∈ {x : ℝ | ((⌊x⌋ : ℤ) : ℝ) * Int.fract x = ((p : ℝ) / (q : ℝ)) * x ^ 2}, x) = 420) : p + q = 929 := by sorry
```

## 18. `minif2f:test:induction_pord1p1on2powklt5on2`

Nguồn minif2f, lĩnh vực induction. Lean: **COMPILE_OK** (22 ms). Kết luận tự động: **không thấy lỗi**.

> Show that for positive integer $n$, $(\prod_{k=1}^{n} (1 + 1/2^k)) < 5/2$.

```lean
theorem cand_752a2f7b6d8d (n : ℕ) (hn : 0 < n) : (∏ k ∈ Finset.Icc 1 n, (1 + (1 : ℝ) / 2 ^ k)) < 5 / 2 := by sorry
```

## 19. `proofnet:Ireland-Rosen:exercise_4_11`

Nguồn proofnet, lĩnh vực number_theory. Lean: **COMPILE_OK** (35 ms). Kết luận tự động: **không thấy lỗi**.

> Prove that $1^{k}+2^{k}+\cdots+(p-1)^{k} \equiv 0(p)$ if $p-1 \nmid k$ and $-1(p)$ if $p-1 \mid k$.

```lean
theorem cand_56f925cda58e (p k : ℕ) (hp : p.Prime) : (¬ (p - 1 ∣ k) → (∑ i ∈ Finset.Icc 1 (p - 1), (i : ℤ) ^ k) ≡ 0 [ZMOD (p : ℤ)]) ∧ ((p - 1 ∣ k) → (∑ i ∈ Finset.Icc 1 (p - 1), (i : ℤ) ^ k) ≡ -1 [ZMOD (p : ℤ)]) := by sorry
```

## 20. `proofnet:Munkres:exercise_32_2a`

Nguồn proofnet, lĩnh vực topology. Lean: **COMPILE_OK** (20 ms). Kết luận tự động: **tương đương gold (Lean chứng minh)**.

> Show that if $\prod X_\alpha$ is Hausdorff, then so is $X_\alpha$. Assume that each $X_\alpha$ is nonempty.

```lean
theorem cand_394e4177d059 {ι : Type*} (X : ι → Type*) [∀ α : ι, TopologicalSpace (X α)] (hne : ∀ α : ι, Nonempty (X α)) (hT2 : T2Space (∀ α : ι, X α)) : ∀ α : ι, T2Space (X α) := by sorry
```
