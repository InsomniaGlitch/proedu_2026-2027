document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#chat-input");
  const messages = document.querySelector("#chat-messages");
  const status = document.querySelector("#chat-status");
  const submitButton = form.querySelector('button[type="submit"]');

  function addMessage(text, sender) {
    const bubble = document.createElement("div");
    bubble.className = `chat-message ${sender}-message`;
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    bubble.append(paragraph);
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) {
      input.focus();
      return;
    }

    status.textContent = "";
    addMessage(message, "user");
    input.value = "";
    submitButton.disabled = true;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || data.detail || "Не удалось получить ответ от чата.");
      }

      addMessage(data.response, "bot");
    } catch (error) {
      console.error("chat.js: ошибка чата:", error);
      status.textContent = error.message || "Не удалось связаться с сервером.";
      status.classList.add("error");
    } finally {
      submitButton.disabled = false;
      input.focus();
    }
  });
});
