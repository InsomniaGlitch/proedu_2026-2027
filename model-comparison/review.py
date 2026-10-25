"""Перепроверка ручных оценок человеком (~20% выборки).

    python3 review.py make      # создать results/review_sample.csv для слепой проверки
    python3 review.py compare   # сравнить твои оценки с оценками Claude

Выборка: все ответы, где Claude снизил балл (они сильнее всего влияют на итог),
плюс случайные ответы с полным баллом — чтобы проверить и пропуски ошибок.
Оценки Claude в файле не показываются, чтобы не влиять на проверяющего.
CSV с разделителем «;» — так его правильно открывает Excel с русскими настройками.
"""

import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "results"
SAMPLE_FILE = RESULTS / "review_sample.csv"
SAMPLE_SIZE = 15  # ~20% от 76 оценённых ответов
SEED = 42


def load_manual():
    with (RESULTS / "manual_scores.csv").open(encoding="utf-8") as f:
        return {(r["model_name"], r["question_id"]): r for r in csv.DictReader(f)}


def make():
    manual = load_manual()
    answers = {}
    for line in (RESULTS / "answers.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["status"] == "ok":
            answers[(row["model_name"], row["question_id"])] = row
    questions = {q["id"]: q for q in json.loads((HERE / "questions_pilot.json").read_text(encoding="utf-8"))["questions"]}

    lowered = [k for k, r in manual.items() if float(r["behavior"]) < 1 or float(r["faithfulness"]) < 1]
    full = sorted(k for k in manual if k not in lowered)
    rng = random.Random(SEED)
    sample = lowered + rng.sample(full, max(0, SAMPLE_SIZE - len(lowered)))
    rng.shuffle(sample)

    with SAMPLE_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["№", "Модель", "Вопрос ID", "Вопрос", "Ожидаемое поведение", "Ответ модели",
                         "Поведение (0 / 0.5 / 1)", "Опора на источники (0 / 0.5 / 1)", "Комментарий"])
        for i, key in enumerate(sample, start=1):
            q = questions[key[1]]
            writer.writerow([i, key[0], key[1], q["question"], q["expected"], answers[key]["answer"].strip(), "", "", ""])
    print(f"Готово: {SAMPLE_FILE} — {len(sample)} ответов ({len(lowered)} со сниженным баллом, "
          f"{len(sample) - len(lowered)} случайных с полным).")


def kappa(pairs):
    """Каппа Коэна для категорий 0 / 0.5 / 1."""
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    cats = {0.0, 0.5, 1.0}
    expected = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in cats)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def compare():
    manual = load_manual()
    # Excel может пересохранить файл с другим разделителем и в другой кодировке.
    raw = SAMPLE_FILE.read_bytes()
    for encoding in ("utf-8-sig", "cp1251", "mac_cyrillic"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    delimiter = ";" if text.splitlines()[0].count(";") >= text.splitlines()[0].count(",") else ","
    rows = list(csv.DictReader(text.splitlines(keepends=True), delimiter=delimiter))

    def to_score(value):
        value = value.strip().replace(",", ".")
        return float(value) if value else None

    for column, field in [("Поведение (0 / 0.5 / 1)", "behavior"), ("Опора на источники (0 / 0.5 / 1)", "faithfulness")]:
        pairs, diffs = [], []
        for r in rows:
            mine = to_score(r[column])
            if mine is None:
                continue
            claude = float(manual[(r["Модель"], r["Вопрос ID"])][field])
            pairs.append((mine, claude))
            if mine != claude:
                diffs.append(f"  №{r['№']} {r['Модель']} {r['Вопрос ID']}: ты {mine}, Claude {claude}")
        if not pairs:
            print(f"{column}: оценок нет — заполни столбец в {SAMPLE_FILE.name}")
            continue
        agree = sum(a == b for a, b in pairs) / len(pairs)
        print(f"{column}: проверено {len(pairs)}, совпадение {agree:.0%}, каппа Коэна {kappa(pairs):.2f}")
        print("\n".join(diffs) if diffs else "  расхождений нет")
    print("\nКаппа > 0.8 — почти полное согласие, 0.6–0.8 — существенное, < 0.6 — оценки Claude стоит пересмотреть.")


if __name__ == "__main__":
    {"make": make, "compare": compare}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
