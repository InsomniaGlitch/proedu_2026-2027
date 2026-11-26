document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#review-decision-form");
  const message = document.querySelector("#review-message");
  const buttons = form.querySelectorAll('button[type="submit"]');

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    message.classList.remove("error");

    const decision = event.submitter?.dataset.decision;
    if (!decision) {
      message.textContent = "Выберите решение.";
      message.classList.add("error");
      return;
    }

    buttons.forEach((button) => {
      button.disabled = true;
    });

    try {
      const response = await fetch(
        `/api/submissions/${form.dataset.submissionId}/review`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            decision,
            comment: form.elements.comment.value,
          }),
        }
      );
      const data = await response.json();
      if (!response.ok || data.status !== "ok") {
        throw new Error(data.message || "Не удалось сохранить решение.");
      }

      window.location.href = "/teacher/queue";
    } catch (error) {
      console.error("teacher_review.js: ошибка сохранения:", error);
      message.textContent = error.message || "Не удалось связаться с сервером.";
      message.classList.add("error");
      buttons.forEach((button) => {
        button.disabled = false;
      });
    }
  });
});
