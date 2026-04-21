"""
Kokoro グローバル設定ユーティリティ。

KOKORO_DATA_DIR: データディレクトリのルートパス（logs/、memories/ はここ以下に作成）。
デフォルト: ./data
"""
import os
from pathlib import Path


def get_data_dir() -> Path:
    """Kokoro データディレクトリを返す（KOKORO_DATA_DIR 環境変数、デフォルト ./data）。"""
    return Path(os.environ.get("KOKORO_DATA_DIR", "./data"))
