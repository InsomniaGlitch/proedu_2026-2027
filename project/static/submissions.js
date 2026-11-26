document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#submission-form");
  const fileInput = document.querySelector("#submission-file");
  const message = document.querySelector("#submission-message");
  const submitButton = form.querySelector('button[type="submit"]');

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
    submitButton.disabled = true;

    try {
      const response = await fetch("/api/submissions", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok || data.status !== "ok") {
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
