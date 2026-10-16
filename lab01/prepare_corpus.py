"""Очистка TXT, полученного из EPUB «Преступление и наказание»."""

import argparse
import re
from pathlib import Path


def prepare(source: Path) -> None:
    text = source.read_text(encoding="utf-8")
    start_marker = "В начале июля, в чрезвычайно жаркое время"
    end_marker = "теперешний рассказ наш окончен."
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise ValueError("Не найдены начало и конец романа; проверьте исходный TXT.")
    text = text[start : end + len(end_marker)]
    # Сноски редакторов и номера ссылок не являются текстом романа.
    text = re.sub(r"(?m)^\s*↑[^\n]*$", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"(?m)^\s*(?:Глава\s+[IVXLC]+|Часть\s+\S+|Эпилог|[IVXLC]+)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Пунктуацию выбрасываем. Латинские слова в авторских репликах сохраняем.
    tokens = re.findall(r"[а-яёa-z]+", text.lower())
    if len(tokens) < 100_000:
        raise ValueError(f"Корпус меньше 100 тысяч слов: {len(tokens)}")
    clean = source.with_name(source.stem + "_clean.txt")
    training = source.with_name(source.stem + "_tokens.txt")
    clean.write_text(text + "\n", encoding="utf-8")
    training.write_text(" ".join(tokens) + "\n", encoding="utf-8")
    print(f"Слов: {len(tokens):,}; словарь: {len(set(tokens)):,}")
    print(f"Очищенный текст: {clean.name}")
    print(f"Токены для модели: {training.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source)
