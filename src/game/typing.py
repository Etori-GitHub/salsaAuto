"""
打字练习游戏服务
"""
import json
import random
from pathlib import Path
from typing import Optional

# 词库文件路径
DATA_DIR = Path(__file__).parent / "data" / "typing"
VOCABS_FILE = DATA_DIR / "vocabs.json"

# 词库缓存
_vocabs_cache: Optional[dict] = None


def _load_vocabs() -> dict:
    """加载词库"""
    global _vocabs_cache
    if _vocabs_cache is None:
        with open(VOCABS_FILE, "r", encoding="utf-8") as f:
            _vocabs_cache = json.load(f)
    return _vocabs_cache


def get_vocab_list() -> list:
    """获取词库列表"""
    vocabs = _load_vocabs()
    return [
        {"key": key, "name": vocab["name"], "count": len(vocab["words"])}
        for key, vocab in vocabs.items()
    ]


def get_random_word(vocab_key: str = "programmer") -> dict:
    """
    获取随机单词
    
    Args:
        vocab_key: 词库键名
        
    Returns:
        单词信息 {"word": str, "pos": str, "reading": str, "trans": str}
    """
    vocabs = _load_vocabs()
    
    if vocab_key not in vocabs:
        vocab_key = "programmer"
    
    words = vocabs[vocab_key]["words"]
    word = random.choice(words)
    
    return {
        "word": word["word"],
        "pos": word["pos"],
        "reading": word["reading"],
        "trans": word["trans"]
    }


def verify_word(vocab_key: str, word: str, user_input: str) -> dict:
    """
    验证用户输入
    
    Args:
        vocab_key: 词库键名
        word: 目标单词
        user_input: 用户输入
        
    Returns:
        验证结果 {"correct": bool, "word": str}
    """
    return {
        "correct": user_input.strip().lower() == word.strip().lower(),
        "word": word
    }
