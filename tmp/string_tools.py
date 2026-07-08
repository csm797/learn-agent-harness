import re


def slugify(text: str) -> str:
    """将文本转换为 URL 友好的 slug 格式。

    将文本转为小写，将非字母数字字符替换为连字符，
    去除首尾连字符，并压缩连续连字符。

    Args:
        text: 要转换的文本。

    Returns:
        URL 友好的 slug 字符串。
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text
