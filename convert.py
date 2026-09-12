#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hojo-TTS-Light-40M 模型获取与转换引导工具

用途：
  - 检查 models/ 目录中的模型文件是否为运行所需的 FP32 ONNX 格式
  - 如果检测到 PyTorch 权重（.pt / .pth / .safetensors），给出明确指引：
    本项目使用官方预转换的 FP32 ONNX 打包文件，请从 Hugging Face 下载 ONNX 版本
  - 可交互选择下载镜像（中国 hf-mirror / 官网）并下载 ONNX 模型

用法：
  python convert.py --check            # 仅检查 models/ 目录
  python convert.py --download         # 交互式下载（选择镜像或官网）
  python convert.py --download --mirror   # 使用 hf-mirror.com 镜像下载
  python convert.py --download --official # 使用 huggingface.co 官网下载
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REQUIRED_ONNX_FILES = (
    "Hojo-TTS-Light-40M-llm.onnx",
    "Hojo-TTS-Light-40M-fine_local.onnx",
    "Hojo-TTS-Light-40M-decoder.onnx",
    "Hojo-TTS-Light-40M-voice.npz",
    "tokenizer.json",
    "tokenizer_config.json",
    "config.json",
)

PYTORCH_EXTENSIONS = (".pt", ".pth", ".safetensors", ".bin", ".ckpt")

MODEL_REPO = "HojoAI/Hojo-TTS-Light-40M"
MIRROR_ENDPOINT = "https://hf-mirror.com"


def _models_dir() -> Path:
    return Path(__file__).resolve().parent / "models"


def check_models(models_dir: Path) -> tuple[bool, list[str]]:
    """Return (ok, missing_files)."""
    missing = [name for name in REQUIRED_ONNX_FILES if not (models_dir / name).is_file()]
    return (not missing), missing


def find_pytorch_weights(models_dir: Path) -> list[str]:
    """Find PyTorch-weight files that cannot be used directly."""
    if not models_dir.is_dir():
        return []
    hits = []
    for p in models_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in PYTORCH_EXTENSIONS:
            hits.append(str(p))
    return sorted(hits)


def _print_report(ok: bool, missing: list[str], pytorch: list[str]) -> None:
    print("\n" + "=" * 60)
    print("  Hojo-TTS-Light-40M 模型检查报告")
    print("=" * 60)
    if ok:
        print("  [OK] ONNX 模型文件齐全，可以直接启动。")
    else:
        print(f"  [缺失] {len(missing)} 个文件：")
        for name in missing:
            print(f"    - {name}")
    if pytorch:
        print("\n  [提示] 检测到以下 PyTorch 权重文件（不可直接使用）：")
        for p in pytorch:
            print(f"    - {p}")
        print("\n  本项目使用官方预转换的 FP32 ONNX 打包文件。")
        print("  请勿尝试在本地手动转换 PyTorch 权重 —— 直接下载 ONNX 版本即可：")
        print(f"    python convert.py --download")
    print("=" * 60 + "\n")


def download_models(models_dir: Path, mirror: bool, official: bool) -> None:
    """Download the ONNX bundle from HuggingFace (mirror or official)."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[错误] 未安装 huggingface_hub，请先执行：pip install huggingface_hub")
        sys.exit(1)

    if mirror and not official:
        print("[信息] 使用中国镜像 hf-mirror.com 下载 ...")
        os.environ["HF_ENDPOINT"] = MIRROR_ENDPOINT
    else:
        print("[信息] 使用官网 huggingface.co 下载 ...")
        os.environ.pop("HF_ENDPOINT", None)

    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"[信息] 模型仓库: {MODEL_REPO}")
    print(f"[信息] 下载目录: {models_dir}")
    snapshot_download(
        repo_id=MODEL_REPO,
        local_dir=str(models_dir),
        allow_patterns=list(REQUIRED_ONNX_FILES),
    )
    print("[完成] 模型下载完成，文件已就位于 models/ 目录。")

    ok, missing = check_models(models_dir)
    if not ok:
        print(f"[警告] 仍有文件缺失: {missing}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查模型文件")
    parser.add_argument("--download", action="store_true", help="下载模型")
    parser.add_argument("--mirror", action="store_true", help="使用 hf-mirror.com 镜像下载")
    parser.add_argument("--official", action="store_true", help="使用 huggingface.co 官网下载")
    args = parser.parse_args()

    models_dir = _models_dir()
    ok, missing = check_models(models_dir)
    pytorch = find_pytorch_weights(models_dir)

    if args.check or not args.download:
        _print_report(ok, missing, pytorch)
        if not args.download:
            return

    # Interactive region selection
    if args.download and not args.mirror and not args.official:
        print("\n请选择下载区域：")
        print("  1. China          使用镜像站 hf-mirror.com（国内快）")
        print("  2. Other countries 使用官网 huggingface.co")
        choice = input("请输入 [1/2]（默认 1）：").strip() or "1"
        args.mirror = choice != "2"
        args.official = choice == "2"

    download_models(models_dir, mirror=args.mirror, official=args.official)


if __name__ == "__main__":
    main()
