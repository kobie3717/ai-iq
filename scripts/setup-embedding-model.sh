#!/bin/bash
set -e

# AI-IQ - Semantic Search Setup
# Downloads all-MiniLM-L6-v2 ONNX model for embeddings

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}AI-IQ - Semantic Search Setup${NC}"
echo "=========================================="
echo ""
echo "This script will:"
echo "  1. Install Python dependencies (numpy, onnxruntime, etc.)"
echo "  2. Download all-MiniLM-L6-v2 ONNX model from HuggingFace"
echo "  3. Verify the model works"
echo "  4. Reindex your memories with embeddings"
echo ""

# Check if memory-tool is installed
if ! command -v memory-tool &> /dev/null; then
    echo -e "${RED}ERROR:${NC} memory-tool not found. Please run scripts/install.sh first."
    exit 1
fi

# Determine model directory
MODEL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ai-iq/models/all-MiniLM-L6-v2"

echo "Model will be installed to: $MODEL_DIR"
echo ""

read -p "Continue? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Install Python dependencies
echo ""
echo -e "${GREEN}Step 1: Installing Python dependencies${NC}"
echo "----------------------------------------"

DEPS=(
    "numpy"
    "onnxruntime"
    "tokenizers"
    "sqlite-vec"
    "huggingface-hub"
)

for dep in "${DEPS[@]}"; do
    echo -n "Installing $dep... "
    if python3 -m pip install --user "$dep" &> /dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${YELLOW}WARNING${NC} (may already be installed)"
    fi
done

# Create model directory
echo ""
echo -e "${GREEN}Step 2: Downloading model from HuggingFace${NC}"
echo "-------------------------------------------"

mkdir -p "$MODEL_DIR"

# Download files using huggingface-hub
echo "Downloading all-MiniLM-L6-v2 ONNX model..."
python3 - <<EOF
from huggingface_hub import hf_hub_download
import sys

files = [
    'onnx/model.onnx',
    'tokenizer.json',
    'config.json',
]

try:
    for file in files:
        print(f"  Downloading {file}...", end=' ', flush=True)
        hf_hub_download(
            repo_id='sentence-transformers/all-MiniLM-L6-v2',
            filename=file,
            cache_dir='$MODEL_DIR',
            local_dir='$MODEL_DIR',
            local_dir_use_symlinks=False
        )
        print('\033[0;32mOK\033[0m')
except Exception as e:
    print(f'\033[0;31mFAILED\033[0m')
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR:${NC} Failed to download model files."
    exit 1
fi

# Verify model works
echo ""
echo -e "${GREEN}Step 3: Verifying model${NC}"
echo "------------------------"

python3 - <<EOF
import sys
import os
import numpy as np

try:
    # Set model path
    model_dir = '$MODEL_DIR'

    # Import required libraries
    from tokenizers import Tokenizer
    import onnxruntime as ort

    # Load tokenizer
    print("  Loading tokenizer...", end=' ', flush=True)
    tokenizer = Tokenizer.from_file(os.path.join(model_dir, 'tokenizer.json'))
    print('\033[0;32mOK\033[0m')

    # Load ONNX model
    print("  Loading ONNX model...", end=' ', flush=True)
    session = ort.InferenceSession(
        os.path.join(model_dir, 'onnx', 'model.onnx'),
        providers=['CPUExecutionProvider']
    )
    print('\033[0;32mOK\033[0m')

    # Test embedding
    print("  Testing embedding generation...", end=' ', flush=True)
    test_text = "This is a test sentence."
    encoding = tokenizer.encode(test_text)

    # Prepare inputs
    input_ids = np.array([encoding.ids], dtype=np.int64)
    attention_mask = np.array([encoding.attention_mask], dtype=np.int64)

    # Run inference
    outputs = session.run(None, {
        'input_ids': input_ids,
        'attention_mask': attention_mask
    })

    # Mean pooling
    embeddings = outputs[0]
    attention_mask_expanded = np.expand_dims(attention_mask, -1)
    sum_embeddings = np.sum(embeddings * attention_mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(attention_mask_expanded, axis=1), a_min=1e-9, a_max=None)
    embedding = sum_embeddings / sum_mask

    # Normalize
    embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)

    print('\033[0;32mOK\033[0m')
    print(f"  Embedding dimension: {embedding.shape[1]}")

except Exception as e:
    print('\033[0;31mFAILED\033[0m')
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR:${NC} Model verification failed."
    exit 1
fi

# Reindex memories
echo ""
echo -e "${GREEN}Step 4: Reindexing memories${NC}"
echo "----------------------------"

echo "Running memory-tool reindex..."
if memory-tool reindex; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC} (no memories to index, or reindex not yet implemented)"
fi

# Success
echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Semantic search is now enabled. Try:"
echo "  memory-tool search \"your query\" --semantic"
echo "  memory-tool search \"your query\"  # Hybrid is default"
echo ""
echo "The system will automatically generate embeddings for new memories."
echo ""
