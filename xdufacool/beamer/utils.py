"""Utility helpers for the beamer-translate pipeline.

Provides batching, token estimation, and output-file writing.
"""

import logging
import math
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Average characters per token (rough estimate for mixed LaTeX / English).
_CHARS_PER_TOKEN = 4


def strip_latex_comments(text: str) -> str:
    """Remove whole-line LaTeX comments (lines starting with %).

    Args:
        text: LaTeX source text.

    Returns:
        Text with comment-only lines removed. Inline comments and
        escaped % characters are preserved.
    """
    lines = text.split('\n')
    filtered = []
    for line in lines:
        stripped = line.lstrip()
        # Skip lines that start with % (whole-line comments)
        if stripped.startswith('%'):
            continue
        filtered.append(line)
    return '\n'.join(filtered)


def estimate_tokens(text: str) -> int:
    """Return a rough token count for *text*.

    Args:
        text: Arbitrary string (LaTeX source, etc.).

    Returns:
        Estimated number of tokens (``len(text) / 4``).
    """
    return math.ceil(len(text) / _CHARS_PER_TOKEN)


def batch_frames(
    frames: List[str],
    batch_size: int = 3,
    max_tokens: int = 20_000,
) -> List[List[str]]:
    """Split *frames* into batches respecting both count and token limits.

    Args:
        frames: Ordered list of frame strings.
        batch_size: Maximum number of frames per batch.
        max_tokens: Soft token ceiling per batch.

    Returns:
        A list of batches, each batch being a list of frame strings.
    """
    batches: List[List[str]] = []
    current_batch: List[str] = []
    current_tokens = 0

    for frame in frames:
        frame_tokens = estimate_tokens(frame)

        # If adding this frame would exceed limits, flush the current batch.
        if current_batch and (
            len(current_batch) >= batch_size
            or current_tokens + frame_tokens > max_tokens
        ):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(frame)
        current_tokens += frame_tokens

    if current_batch:
        batches.append(current_batch)

    logger.info(
        "Created %d batch(es) from %d frame(s).",
        len(batches),
        len(frames),
    )
    return batches


def default_output_path(input_path: Path) -> Path:
    """Derive the default output path by inserting ``-zh`` before the extension.

    Args:
        input_path: Original ``.tex`` file path.

    Returns:
        E.g. ``slides.tex`` → ``slides-zh.tex``.
    """
    stem = input_path.stem
    suffix = input_path.suffix
    return input_path.parent / f"{stem}-zh{suffix}"


def write_output(text: str, output_path: Path) -> None:
    """Write *text* to *output_path* with UTF-8 encoding.

    Args:
        text: LaTeX source text to write.
        output_path: Destination file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    logger.info("Output written to %s.", output_path)


# ---------------------------------------------------------------------------
# Optional: ML terminology dictionary for post-processing consistency
# ---------------------------------------------------------------------------

#: Common ML term translations (English → Chinese) for consistency.
ML_TERMINOLOGY: Dict[str, str] = {
    "machine learning": "机器学习",
    "deep learning": "深度学习",
    "neural network": "神经网络",
    "gradient descent": "梯度下降",
    "loss function": "损失函数",
    "overfitting": "过拟合",
    "underfitting": "欠拟合",
    "regularization": "正则化",
    "backpropagation": "反向传播",
    "convolutional neural network": "卷积神经网络",
    "recurrent neural network": "循环神经网络",
    "attention mechanism": "注意力机制",
    "transformer": "Transformer",
    "supervised learning": "监督学习",
    "unsupervised learning": "无监督学习",
    "reinforcement learning": "强化学习",
    "classification": "分类",
    "regression": "回归",
    "clustering": "聚类",
    "feature extraction": "特征提取",
    "hyperparameter": "超参数",
    "batch normalization": "批归一化",
    "dropout": "Dropout",
    "epoch": "轮次",
    "learning rate": "学习率",
    "activation function": "激活函数",
    "cross-entropy": "交叉熵",
    "softmax": "Softmax",
    "embedding": "嵌入",
    "generative adversarial network": "生成对抗网络",
}
