@echo off
echo ============================================================
echo  Co-scientist - Virtual Environment Setup (Windows)
echo ============================================================

set VENV_DIR=%~dp0venv

echo.
echo [1/6] Creating virtual environment...
python -m venv "%VENV_DIR%"
if errorlevel 1 ( echo ERROR: Failed. && pause && exit /b 1 )

echo.
echo [2/6] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [3/6] Installing core dependencies...
pip install --upgrade pip
pip install biomni langgraph chromadb python-dotenv
if errorlevel 1 ( echo ERROR: Failed. && pause && exit /b 1 )

echo.
echo [4/6] Installing PyTorch (CUDA 12.8)...
pip install torch --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 ( echo WARNING: Falling back to CPU torch... && pip install torch )

echo.
echo [5/6] Upgrading pyarrow for NumPy 2.x...
pip install "pyarrow>=14.0" --upgrade

echo.
echo [6/6] Installing STAgent + spatial transcriptomics dependencies (pip)...
rem pims (pulled by squidpy) uses legacy setup.py -- disable build isolation
set PIP_NO_BUILD_ISOLATION=1
pip install -r vendors\STAgent\requirements-pip.txt
set PIP_NO_BUILD_ISOLATION=
copy vendors\STAgent\src\.env.example vendors\STAgent\src\.env 2>nul

echo.
echo [7/7] Installing CellAtria + CellExpress dependencies...
rem Core scientific stack
pip install numpy pandas scipy h5py anndata scanpy tqdm scikit-learn networkx annoy
rem CellAtria agent dependencies
pip install gradio GEOparse beautifulsoup4 pymupdf psutil
pip install langchain langchain-core langchain-community langchain-anthropic langchain-openai langgraph
rem CellExpress annotation + QC tools
pip install celltypist scrublet "harmonypy==0.0.9" scimilarity
rem Restore zarr>=3 (scimilarity may downgrade it)
pip install "zarr>=3.0" --upgrade

echo.
echo ============================================================
echo  Setup complete!
echo  To run:
echo    venv\Scripts\activate
echo    python co_scientist.py
echo.
echo  API keys -- create a .env file in this folder:
echo    ANTHROPIC_API_KEY=your_key_here
echo    NCBI_API_KEY=your_key_here  (optional, for GEO/SRA)
echo.
echo  ST Agent runs in this venv (pip) by default.
echo  Leave the Python: field blank in the UI.
echo.
echo  For a different Python env per workflow, set the
echo  Python: field in the UI to that env's python.exe.
echo ============================================================
pause
