#!/usr/bin/env bash
set -e
echo "============================================================"
echo " Co-scientist - Virtual Environment Setup (Linux/Mac)"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# ── System packages (Debian/Ubuntu only) ─────────────────────────────────────
if command -v apt-get &> /dev/null; then
    echo
    echo "[0/6] Checking system packages (Debian/Ubuntu)..."
    MISSING=()
    dpkg -s python3-venv &>/dev/null || MISSING+=(python3-venv)
    dpkg -s python3-tk  &>/dev/null || MISSING+=(python3-tk)
    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "  Installing: ${MISSING[*]}"
        sudo apt-get install -y "${MISSING[@]}"
    else
        echo "  python3-venv and python3-tk already installed."
    fi
fi

echo && echo "[1/6] Creating virtual environment..."
python3 -m venv "$VENV_DIR"

echo && echo "[2/6] Activating..."
source "$VENV_DIR/bin/activate"

echo && echo "[3/6] Installing core dependencies..."
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"
pip install chromadb   # chromadb used by biomni/STAgent vector store

echo && echo "[4/6] Installing PyTorch..."
TORCH_URL="https://download.pytorch.org/whl/cpu"
if command -v nvidia-smi &> /dev/null; then
    CUDA_VER=$(nvidia-smi 2>/dev/null | awk '/CUDA Version/{print $NF}' | cut -d. -f1)
    if [[ "$CUDA_VER" =~ ^[0-9]+$ ]]; then
        if [ "$CUDA_VER" -ge 12 ]; then
            TORCH_URL="https://download.pytorch.org/whl/cu128"
        elif [ "$CUDA_VER" -ge 11 ]; then
            TORCH_URL="https://download.pytorch.org/whl/cu118"
        fi
    fi
fi
echo "  Using torch index: $TORCH_URL"
pip install torch --index-url "$TORCH_URL"

echo && echo "[5/6] Upgrading pyarrow..."
pip install "pyarrow>=14.0" --upgrade

echo && echo "[6/7] Installing STAgent + spatial transcriptomics dependencies..."
# pims (pulled by squidpy) uses legacy setup.py — disable build isolation
PIP_NO_BUILD_ISOLATION=1 pip install -r "$SCRIPT_DIR/requirements-stagent.txt"
cp "$SCRIPT_DIR/vendors/STAgent/src/.env.example" "$SCRIPT_DIR/vendors/STAgent/src/.env" 2>/dev/null || true

echo && echo "[7/7] Installing CellAtria + CellExpress dependencies..."
pip install -r "$SCRIPT_DIR/vendors/cellatria/agent/requirements-pip.txt"
# Restore zarr>=3 last (scimilarity may downgrade it during the above install)
pip install "zarr>=3.0" --upgrade

echo
echo "============================================================"
echo " Setup complete!"
echo " To run:"
echo "   source venv/bin/activate"
echo "   python co_scientist.py"
echo
echo " API keys — create a .env file in this folder:"
echo "   ANTHROPIC_API_KEY=your_key_here"
echo "   NCBI_API_KEY=your_key_here  (optional, for GEO/SRA)"
echo
echo " ST Agent runs in this venv (pip) by default."
echo " Leave the Python: field blank in the UI."
echo
echo " For a different Python env per workflow, set the"
echo " Python: field in the UI to that env's python binary."
echo "============================================================"
