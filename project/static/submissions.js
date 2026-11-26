document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#submission-form");
  const fileInput = document.querySelector("#submission-file");
  const message = document.querySelector("#submission-message");
  const submitButton = form.querySelector('button[type="submit"]');
  const reviewerError = "Reviewer не смог проверить работу";
  const reviewedStatuses = new Set(["На проверке", "На доработке", "Проверено"]);

  async function waitForReviewerResult(existingIds, filename) {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1500));

      try {
        const response = await fetch("/api/submissions", { cache: "no-store" });
        if (!response.ok) continue;

        const data = await response.json();
        const resultSaved = data.submissions?.some((submission) =>
          !existingIds.has(submission.id)
          && submission.filename === filename
          && reviewedStatuses.has(submission.status)
          && (submission.status === "Проверено"
            || (typeof submission.feedback === "string" && submission.feedback.trim()))
        );

        if (resultSaved) return true;
      } catch (error) {
        console.error("submissions.js: ошибка проверки результата:", error);
      }
    }

    return false;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    message.classList.remove("error");

    if (!fileInput.files.length) {
      message.textContent = "Выберите файл для загрузки.";
      message.classList.add("error");
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    const existingIds = new Set(
      [...document.querySelectorAll("[data-submission-id]")]
        .map((row) => Number(row.dataset.submissionId))
    );
    const filename = fileInput.files[0].name;
    submitButton.disabled = true;

    try {
      const response = await fetch("/api/submissions", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok || data.status !== "ok") {
        if (data.message === reviewerError) {
          message.textContent = `${reviewerError}. Ожидаю сохранения результата...`;
          if (await waitForReviewerResult(existingIds, filename)) {
            window.location.reload();
            return;
          }
        }
        message.textContent = data.message || "Не удалось загрузить работу.";
        message.classList.add("error");
        return;
      }

      window.location.reload();
    } catch (error) {
      console.error("submissions.js: ошибка загрузки:", error);
      message.textContent = "Не удалось связаться с сервером. Попробуйте позже.";
      message.classList.add("error");
    } finally {
      submitButton.disabled = false;
    }
  });
});
