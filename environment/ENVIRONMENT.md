# Môi trường (environment lock)

| Thành phần | Phiên bản khóa | File |
|---|---|---|
| Python | 3.13.16 | — |
| Gói Python | phiên bản chính xác | `environment/requirements.lock.txt` (cài: `pip install -r environment/requirements.lock.txt`) |
| Lean 4 | v4.35.0 (`leanprover/lean4:v4.35.0`) | `environment/lean-toolchain` |
| Mathlib | v4.35.0, commit `56a005855ea17e0b0958f73ec801ae140b0a1679` | `environment/mathlib-lake-manifest.json` (khóa batteries, aesop, Qq, ProofWidgets, plausible, …) |
| Lean REPL | leanprover-community/repl v4.35.0, commit `58bdde1ff173117960083cc5a052a11d51c49ff1` | — |
| Redis (chỉ cho thí nghiệm broker) | 7.0.15 | — |

`bash scripts/setup_lean.sh` cài đúng các phiên bản trên: toolchain từ GitHub release, Mathlib theo tag `v4.35.0`,
các file `.olean` lấy từ cache chính thức của Mathlib, REPL theo tag `v4.35.0`. Cần khoảng 10 GB đĩa.

## Máy chạy thí nghiệm

| | 16/10/2026 | 26–27/10/2026 |
|---|---|---|
| CPU | 2 vCPU (máy ảo đám mây) | 2 vCPU Intel Xeon @ 2,80 GHz (KVM) |
| RAM | 7,8 GB, có swap | 7,8 GB, không swap |
| GPU | không | không |
| Hệ điều hành | Linux (Ubuntu) | Ubuntu 24.04, kernel 6.18 |

Hai máy cùng số vCPU và RAM. Lần chạy `repro_T1K_A` (26/10) lặp lại đúng một ô của ma trận (16/10) để kiểm tra kết quả hai ngày có so sánh được không.
Thông số máy của từng lần chạy nằm trong `run_record.json` của lần chạy đó.
