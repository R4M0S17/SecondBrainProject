#!/usr/bin/env python3
"""Download GGUF models from Hugging Face Hub."""

import sys
from pathlib import Path

import requests
from tqdm import tqdm


def download_model(repo_id: str, filename: str, output_dir: Path) -> Path:
    """
    Download a model from Hugging Face Hub.

    Args:
        repo_id: Repository ID (e.g., "hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF")
        filename: Model filename (e.g., "llama-3.2-3b-instruct-q4_k_m.gguf")
        output_dir: Directory to save the model

    Returns:
        Path to downloaded model
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    if output_path.exists():
        print(f"✓ Model already exists at {output_path}")
        return output_path

    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    print(f"Downloading {filename} from {repo_id}...")
    print(f"URL: {url}")

    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        total_size = int(response.headers.get("content-length", 0))

        if total_size == 0:
            print("⚠ Could not determine file size. Attempting download...")
            response = requests.get(url, stream=True, timeout=30)
        else:
            print(f"File size: {total_size / (1024**3):.2f} GB")

        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(output_path, "wb") as f:
                with tqdm(
                    total=int(r.headers.get("content-length", 0)),
                    unit="B",
                    unit_scale=True,
                    desc=filename,
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

        print(f"✓ Downloaded to {output_path}")
        return output_path

    except Exception as e:
        print(f"✗ Download failed: {e}")
        if output_path.exists():
            output_path.unlink()
        raise


if __name__ == "__main__":
    models_dir = Path(__file__).parent.parent / "bin" / "models"

    print("=== Cerebro Model Efficiency Testing ===\n")
    print("Available models:")
    print("1. qwen  — Qwen2.5-Coder-3B-Instruct-Q4_K_M (default chat model)")
    print("2. llama — Llama-3.2-3B-Instruct-Q4_K_M (legacy fallback)\n")

    targets = {
        "qwen": (
            "bartowski/Qwen2.5-Coder-3B-Instruct-GGUF",
            "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
        ),
        "llama": (
            "hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF",
            "llama-3.2-3b-instruct-q4_k_m.gguf",
        ),
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "qwen"
    if choice not in targets:
        print(f"Unknown model {choice!r}. Use: qwen | llama")
        sys.exit(1)

    repo_id, filename = targets[choice]
    print(f"Downloading {filename}...")
    try:
        model_path = download_model(repo_id=repo_id, filename=filename, output_dir=models_dir)
        print(f"\n✓ Model ready at: {model_path}")
        print("\nTo use this model, set:")
        print(f'  export CEREBRO_LLAMACPP_MODEL="{model_path.name}"')
    except Exception as e:
        print(f"\n✗ Failed to download model: {e}")
        sys.exit(1)
