# Installation Scripts

This directory contains scripts for installing and setting up the AI Memory SQLite system.

## Files

### install.sh

One-command installer that sets up memory-tool on your system.

**Usage:**
```bash
bash scripts/install.sh
```

**What it does:**
- Checks Python 3.8+ and SQLite 3.37+ requirements
- Creates `~/.local/share/ai-memory/` directory
- Copies `memory-tool.py` to the installation directory
- Creates symlink at `~/.local/bin/memory-tool`
- Adds `~/.local/bin` to PATH (if needed)
- Initializes the database
- Provides next steps

**Idempotent:** Safe to run multiple times. Will replace existing installation.

### setup-embedding-model.sh

Downloads and configures the all-MiniLM-L6-v2 ONNX model for semantic search.

**Usage:**
```bash
bash scripts/setup-embedding-model.sh
```

**What it does:**
- Installs Python dependencies (numpy, onnxruntime, tokenizers, etc.)
- Downloads ONNX model from HuggingFace
- Verifies model works with a test embedding
- Reindexes existing memories with embeddings
- Enables semantic and hybrid search modes

**Requirements:**
- memory-tool must be installed first
- ~380MB download for the model
- Optional but recommended for better search results

## Installation Order

1. Run `install.sh` first
2. Restart your shell or run `source ~/.bashrc`
3. Verify with `memory-tool stats`
4. Optionally run `setup-embedding-model.sh` for semantic search
5. Configure Claude Code hooks (see `hooks/claude-code/README.md`)

## Troubleshooting

**Python version too old:**
- Install Python 3.8 or higher from your package manager

**SQLite version warning:**
- Warning is non-fatal, but upgrade SQLite for better performance
- On Ubuntu/Debian: `sudo apt update && sudo apt install sqlite3`

**Permission denied:**
- Make scripts executable: `chmod +x scripts/*.sh`

**PATH not updated:**
- Manually add to `~/.bashrc`: `export PATH="$HOME/.local/bin:$PATH"`
- Then run: `source ~/.bashrc`

**Model download fails:**
- Check internet connection
- Try again (may be temporary HuggingFace issue)
- Manually download from: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
