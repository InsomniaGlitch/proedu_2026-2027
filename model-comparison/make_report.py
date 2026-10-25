"""Сводка пилотного сравнения: ручные оценки + автоматические метрики → таблица и график.

Ручные оценки (results/manual_scores.csv), шкала 0 / 0.5 / 1:
  behavior     — поведение соответствует ожидаемому для вопроса (questions_pilot.json, поле expected)
  faithfulness — ответ опирается только на фрагменты, ничего не выдумано
Автоматически:
  citation     — для вопросов F/E/PL: есть ссылка «Источник: …» с названием материала (1),
                 только номер фрагмента вида [1] (0.5), ссылки нет (0)
  language     — доля ответов без вставок латиницей/иероглифами (кроме терминов из ALLOWED_LATIN)
  latency      — медианное время ответа; балл скорости 1 при ≤5 с, 0 при ≥60 с, линейно между

Веса — из методики (раздел «Итоговая оценка»): в пилоте нет Reviewer и стоимости,
поэтому оставшиеся веса 30/15/10/10/10 нормированы на 75.
"""

import csv
import json
import re
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).parent
RESULTS = HERE / "results"

ALLOWED_LATIN = {"esg", "environmental", "social", "governance", "triple", "bottom", "line", "smart",
                 "who", "cares", "wins", "world", "co", "rag", "ii", "iii", "kpi", "cld",
                 "reinforcing", "balancing"}

WEIGHTS = {"Точность": 30, "Ограничения": 15, "Педагогика": 10, "Скорость": 10, "Доступность в РФ": 10}
# GigaChat — российский сервис; остальные — открытые зарубежные модели через OpenRouter:
# оплата и хранение данных в РФ под вопросом, но веса открыты и модель можно развернуть у себя.
RF_AVAILABILITY = {"GigaChat 2 Lite": 1.0, "GigaChat 2 Max": 1.0}


def citation_score(answer):
    if re.search(r"Источник:\s*[^\]\n]*(Пилот|П-\d|Кейс|Задание)", answer) or re.search(r"\(Пилот[ :]", answer):
        return 1.0
    if re.search(r"\[\d", answer) or "Источник" in answer:
        return 0.5
    return 0.0


def language_clean(answer):
    if re.search(r"[一-鿿]", answer):
        return 0.0
    words = {w.lower() for w in re.findall(r"[A-Za-z]{2,}", answer)}
    return 0.0 if words - ALLOWED_LATIN else 1.0


def main():
    models = [m["name"] for m in __import__("run_pilot").MODELS]
    questions = json.loads((HERE / "questions_pilot.json").read_text(encoding="utf-8"))["questions"]
    category = {q["id"]: q["id"].rstrip("0123456789") for q in questions}

    answers = {}
    for line in (RESULTS / "answers.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["status"] == "ok":
            answers[(row["model_name"], row["question_id"])] = row

    manual = {}
    with (RESULTS / "manual_scores.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            manual[(row["model_name"], row["question_id"])] = row

    summary = []
    for model in models:
        keys = [(model, q["id"]) for q in questions if (model, q["id"]) in answers and (model, q["id"]) in manual]
        if not keys:
            continue
        beh = lambda cats: [float(manual[k]["behavior"]) for k in keys if category[k[1]] in cats]
        faith = [float(manual[k]["faithfulness"]) for k in keys]
        cites = [citation_score(answers[k]["answer"]) for k in keys if category[k[1]] in ("F", "E", "PL")]
        lang = [language_clean(answers[k]["answer"]) for k in keys]
        latency = median(answers[k]["latency_seconds"] for k in keys)
        summary.append({
            "Модель": model,
            "Ответов": f"{len(keys)}/{len(questions)}",
            "Опора на источники": mean(faith),
            "Ссылки на источник": mean(cites) if cites else 0,
            "Честный отказ (нет в базе)": mean(beh("N")) if beh("N") else 0,
            "Не решает за студента / не оценивает": mean(beh(("R", "PL"))),
            "Объяснение и уточнение": mean(beh(("E", "U"))),
            "Ответы без языковых вставок": mean(lang),
            "Медиана времени, с": latency,
        })

    total_weight = sum(WEIGHTS.values())
    for s in summary:
        parts = {
            "Точность": mean([s["Опора на источники"], s["Ссылки на источник"], s["Честный отказ (нет в базе)"]]),
            "Ограничения": s["Не решает за студента / не оценивает"],
            "Педагогика": mean([s["Объяснение и уточнение"], s["Ответы без языковых вставок"]]),
            "Скорость": min(1.0, max(0.0, (60 - s["Медиана времени, с"]) / 55)),
            "Доступность в РФ": RF_AVAILABILITY.get(s["Модель"], 0.5),
        }
        s.update({f"[{k}]": v for k, v in parts.items()})
        s["Итог S"] = sum(WEIGHTS[k] * v for k, v in parts.items()) / total_weight
        # Чувствительность к весам: итог без критерия «Доступность в РФ».
        no_rf = {k: w for k, w in WEIGHTS.items() if k != "Доступность в РФ"}
        s["Итог без РФ"] = sum(no_rf[k] * parts[k] for k in no_rf) / sum(no_rf.values())
    summary.sort(key=lambda s: s["Итог S"], reverse=True)

    with (RESULTS / "summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        for s in summary:
            writer.writerow({k: round(v, 2) if isinstance(v, float) else v for k, v in s.items()})

    for s in summary:
        print(f"{s['Модель']:<18} {s['Ответов']:>6}  S={s['Итог S']:.2f}  без РФ={s['Итог без РФ']:.2f}  "
              f"t={s['Медиана времени, с']:.1f}с  " +
              "  ".join(f"{k}={s[f'[{k}]']:.2f}" for k in WEIGHTS))
    print(f"\nТаблица: {RESULTS / 'summary.csv'}")


if __name__ == "__main__":
    main()
