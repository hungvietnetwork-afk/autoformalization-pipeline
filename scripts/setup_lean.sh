#!/usr/bin/env bash
# Install Lean 4 v4.35.0 + Mathlib v4.35.0 (prebuilt cache) + leanprover-community/repl.
# Needs network access to github.com, release-assets.githubusercontent.com and cache.mathlib.org.
# Disk: ~3 GB toolchain + ~6 GB Mathlib build artefacts.  RAM: >= 4 GB per Lean worker is comfortable.
set -euo pipefail
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
LEAN_ROOT="${AFP_LEAN_ROOT:-$HOME/lean}"
VER="${LEAN_VERSION:-4.35.0}"
mkdir -p "$LEAN_ROOT" && cd "$LEAN_ROOT"

if [ ! -x "lean-$VER-linux/bin/lean" ]; then
  echo ">> downloading Lean $VER"
  curl -sSL -o "lean-$VER-linux.tar.zst" "https://github.com/leanprover/lean4/releases/download/v$VER/lean-$VER-linux.tar.zst"
  python3 -c "import zstandard" 2>/dev/null || pip install zstandard
  python3 - "$VER" <<'EOF'
import sys, tarfile, zstandard
v = sys.argv[1]
with open(f"lean-{v}-linux.tar.zst", "rb") as f:
    with tarfile.open(fileobj=zstandard.ZstdDecompressor().stream_reader(f), mode="r|") as t:
        t.extractall(".", filter="fully_trusted")
EOF
  rm -f "lean-$VER-linux.tar.zst"
fi
export PATH="$LEAN_ROOT/lean-$VER-linux/bin:$PATH"
lean --version

if [ ! -d mathlib4 ]; then
  git clone --depth 1 --branch "v$VER" https://github.com/leanprover-community/mathlib4.git
fi
cd mathlib4
lake env true                      # clones batteries, aesop, Qq, ProofWidgets, ... from the manifest
lake exe cache get                 # ~9,000 prebuilt .olean archives (1-2 minutes)
lake build Mathlib                 # should be a no-op after the cache
cd ..

if [ ! -d repl ]; then
  git clone --depth 1 --branch "v$VER" https://github.com/leanprover-community/repl.git
fi
(cd repl && lake build)
echo ">> done. export AFP_LEAN_ROOT=$LEAN_ROOT"
