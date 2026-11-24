#!/usr/bin/env python3
"""
Находит страницы глав учебника в PDF и записывает их в Sources Formatter.

Учебное пособие «Устойчивое развитие: системный подход» (УрФУ, 2026):
https://elar.urfu.ru/bitstream/10995/150343/1/978-5-7996-4169-6_2026.pdf

В PDF первые две страницы - обложка, поэтому печатная страница N - это
страница N + 2 в PDF (7-я страница PDF = 5-я печатная). Смещение задаётся
параметром --offset.

Что делает скрипт:
  1. Читает PDF (pypdf) и ищет заголовок каждого документа из базы
     (documents.filename без .txt) на страницах учебника.
     Страницы оглавления пропускаются.
  2. Если заголовок на странице не найден - пробует закладки PDF (outline).
  3. Печатает отчёт: документ -> страница PDF -> печатная страница.
  4. Записывает словарь TEXTBOOK_PAGES между маркерами
     BEGIN/END TEXTBOOK_PAGES в custom_components/sources_formatter.py.
  5. С флагом --sync-flow копирует код компонента в flow/tutor-flow.json
     (в экспорте Flow код компонента хранится внутри JSON).

Использование:
    pip install pypdf
    python scripts/build_textbook_toc.py путь/к/978-5-7996-4169-6_2026.pdf
    python scripts/build_textbook_toc.py book.pdf --dry-run        # только отчёт
    python scripts/build_textbook_toc.py book.pdf --sync-flow
    python scripts/build_textbook_toc.py --sync-flow-only          # без PDF
    python scripts/build_textbook_toc.py book.pdf --titles-file titles.txt

ВАЖНО: просмотрите отчёт. Документы, которых нет в учебнике (например,
«0.1. O курсе»), остаются без ссылки - это нормально.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMATTER = ROOT / "custom_components" / "sources_formatter.py"
FLOW = ROOT / "flow" / "tutor-flow.json"

BEGIN = "# BEGIN TEXTBOOK_PAGES"
END = "# END TEXTBOOK_PAGES"

# Названия документов в sustainability_course_db (documents.filename без
# расширения). Можно заменить своим списком через --titles-file.
DEFAULT_TITLES = [
    "0.1. O курсе",
    "0.2. Введение",
    "1.1. Экологическая устойчивость и экологические кризисы",
    "1.2. Осознание глобальных проблем",
    "1.3. Вызовы антропоцена",
    "2.1. Социальные системы",
    "2.2. Стратегическое планирование",
    "3.1. Алгоритм решения задач управления",
    "3.2. Концепция Run — Change — Disrupt Model",
    "4.1. Стратегии устойчивого развития",
    "4.2. Проекты устойчивого развития",
    "4.3. Отчетность об устойчивом развитии",
    "Приложение 1",
    "Приложение 2",
    "Приложение 3",
]

SECTION_RE = re.compile(r"^\s*(\d+\.\d+)\.?(?:\s|$)")
APPENDIX_RE = re.compile(r"^\s*приложение\s+(\d+)\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# Ключ документа - ДОЛЖЕН совпадать с section_key() в sources_formatter.py
# --------------------------------------------------------------------------
def section_key(title: str) -> str:
    title = (title or "").strip()

    match = SECTION_RE.match(title)
    if match:
        return match.group(1)

    match = APPENDIX_RE.match(title)
    if match:
        return f"прил.{match.group(1)}"

    return re.sub(r"\s+", " ", title).lower()


def normalize(text: str) -> str:
    """Нижний регистр, ё -> е, любые разделители -> один пробел."""
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_title(title: str):
    """
    "1.1. Название" -> ("1 1", "название"); "Приложение 2" -> ("", "приложение 2").
    Номера вида 0.x в учебнике не бывает (это нумерация курса), поэтому для
    них номер не используется.
    """
    match = SECTION_RE.match(title)

    if match and not match.group(1).startswith("0."):
        return normalize(match.group(1)), normalize(title[match.end():])

    if match:  # 0.x
        return "", normalize(title[match.end():])

    return "", normalize(title)


def is_toc_page(raw: str) -> bool:
    """Оглавление: заголовок «Оглавление/Содержание» или много точек-заполнителей."""
    head = normalize(raw[:300])

    if head.startswith(("оглавление", "содержание")):
        return True

    leaders = len(re.findall(r"(?:\.\s*){5,}|…{2,}|·{3,}", raw))
    return leaders >= 5


def heading_matches(lines: list[str], number: str, name: str) -> bool:
    """Есть ли в строках страницы строка-заголовок (до 3 строк подряд)."""
    if not name:
        return False

    exact_only = len(name.split()) <= 2  # «введение», «приложение 1»
    targets = {name}

    if number:
        targets.add(f"{number} {name}")

    for i in range(len(lines)):
        for span in (1, 2, 3):
            candidate = normalize(" ".join(lines[i:i + span]))

            if not candidate:
                continue

            for target in targets:
                if candidate == target:
                    return True

                if not exact_only and candidate.startswith(target + " "):
                    return True

    return False


def find_by_headings(pages: list[str], title: str):
    """Первая не-оглавленческая страница PDF (нумерация с 1), где есть заголовок."""
    number, name = split_title(title)

    for index, raw in enumerate(pages):
        if index < 2 or is_toc_page(raw):
            continue

        lines = [line.strip() for line in raw.splitlines() if line.strip()]

        if heading_matches(lines, number, name):
            return index + 1

    return None


def find_by_outline(reader, title: str):
    """Запасной вариант: закладки PDF."""
    number, name = split_title(title)
    wanted = {name, f"{number} {name}".strip()}

    def walk(items):
        for item in items:
            if isinstance(item, list):
                yield from walk(item)
            else:
                yield item

    try:
        for item in walk(reader.outline):
            if normalize(getattr(item, "title", "") or "") in wanted:
                return reader.get_destination_page_number(item) + 1
    except Exception:  # noqa: BLE001 - закладки необязательны
        return None

    return None


def read_pages(pdf_path: Path):
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Нужен pypdf: pip install pypdf")

    reader = PdfReader(str(pdf_path))
    pages = []

    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")

    return reader, pages


def locate(titles, pages, reader=None, offset=2):
    """Возвращает список (title, key, pdf_page|None, printed_page|None, how)."""
    result = []

    for title in titles:
        pdf_page = find_by_headings(pages, title)
        how = "заголовок"

        if pdf_page is None and reader is not None:
            pdf_page = find_by_outline(reader, title)
            how = "закладка"

        if pdf_page is None:
            result.append((title, section_key(title), None, None, "не найден"))
            continue

        printed = pdf_page - offset

        if printed < 1:
            result.append(
                (title, section_key(title), pdf_page, None, "до 1-й печатной")
            )
            continue

        result.append((title, section_key(title), pdf_page, printed, how))

    return result


def render_block(rows) -> str:
    found = [row for row in rows if row[3]]

    if not found:
        return "TEXTBOOK_PAGES = {}"

    body = ["TEXTBOOK_PAGES = {"]

    for title, key, _pdf, printed, _how in found:
        body.append(f'    "{key}": {printed},  # {title}')

    body.append("}")
    return "\n".join(body)


def write_formatter(block: str) -> str:
    code = FORMATTER.read_text(encoding="utf-8")
    start = code.index(BEGIN) + len(BEGIN)
    end = code.index(END)
    new_code = f"{code[:start]}\n{block}\n{code[end:]}"
    FORMATTER.write_text(new_code, encoding="utf-8")
    return new_code


def find_component_codes(node, found=None):
    """Все строки внутри Flow, похожие на код компонента SourcesFormatter."""
    found = [] if found is None else found

    if isinstance(node, dict):
        for value in node.values():
            find_component_codes(value, found)
    elif isinstance(node, list):
        for value in node:
            find_component_codes(value, found)
    elif isinstance(node, str) and "class SourcesFormatter" in node:
        found.append(node)

    return found


def sync_flow(new_code: str) -> bool:
    """Подменяет код компонента внутри flow/tutor-flow.json (текстово,
    чтобы не переформатировать весь экспорт)."""
    raw = FLOW.read_text(encoding="utf-8")
    old_codes = find_component_codes(json.loads(raw))

    if not old_codes:
        return False

    for old_code in set(old_codes):
        for ensure_ascii in (False, True):
            old_json = json.dumps(old_code, ensure_ascii=ensure_ascii)[1:-1]

            if old_json in raw:
                new_json = json.dumps(new_code, ensure_ascii=ensure_ascii)[1:-1]
                raw = raw.replace(old_json, new_json)
                break
        else:
            return False

    FLOW.write_text(raw, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Найти страницы глав учебника и обновить Sources Formatter."
    )
    parser.add_argument("pdf", type=Path, nargs="?", help="PDF учебника")
    parser.add_argument("--offset", type=int, default=2,
                        help="страниц обложки перед нумерацией (по умолчанию 2)")
    parser.add_argument("--titles-file", type=Path,
                        help="файл с названиями документов, по одному в строке")
    parser.add_argument("--dry-run", action="store_true",
                        help="только отчёт, файлы не менять")
    parser.add_argument("--sync-flow", action="store_true",
                        help="обновить код компонента в flow/tutor-flow.json")
    parser.add_argument("--sync-flow-only", action="store_true",
                        help="только скопировать текущий код компонента в Flow "
                             "(PDF не нужен)")
    args = parser.parse_args()

    if args.sync_flow_only:
        code = FORMATTER.read_text(encoding="utf-8")
        print("Flow обновлён." if sync_flow(code) else "Код компонента во Flow не найден.")
        return 0

    if args.pdf is None:
        parser.error("укажите путь к PDF (или используйте --sync-flow-only)")

    titles = DEFAULT_TITLES

    if args.titles_file:
        titles = [
            line.strip()
            for line in args.titles_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    reader, pages = read_pages(args.pdf)
    print(f"Страниц в PDF: {len(pages)}; смещение обложки: {args.offset}\n")

    rows = locate(titles, pages, reader, args.offset)

    print(f"{'Документ':62} {'PDF':>5} {'печ.':>5}  как найден")
    for title, _key, pdf_page, printed, how in rows:
        print(f"{title[:62]:62} {pdf_page or '-':>5} {printed or '-':>5}  {how}")

    missing = [row for row in rows if not row[3]]
    print(f"\nНайдено: {len(rows) - len(missing)} из {len(rows)}.")

    if missing:
        print("Без ссылки останутся: " + "; ".join(row[0] for row in missing))

    # Проверка порядка: страницы нумерованных глав должны не убывать.
    ordered = [row[3] for row in rows if row[3] and row[1][0].isdigit()]

    if ordered != sorted(ordered):
        print("ВНИМАНИЕ: страницы глав идут не по порядку - проверьте вручную.")

    if args.dry_run:
        print("\n--dry-run: файлы не изменены.")
        return 0

    new_code = write_formatter(render_block(rows))
    print(f"\nОбновлён {FORMATTER.relative_to(ROOT)}")

    if args.sync_flow:
        if sync_flow(new_code):
            print(f"Обновлён {FLOW.relative_to(ROOT)}")
        else:
            print(
                "Не удалось найти старый код компонента в flow/tutor-flow.json: "
                "вставьте код вручную (кнопка Code на узле Sources Formatter)."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
