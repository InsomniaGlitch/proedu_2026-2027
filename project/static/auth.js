/**
 * auth.js — обработка входа и регистрации
 */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#login-form");

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const username = document.querySelector("#username").value.trim();
      const password = document.querySelector("#password").value;

      if (!username || !password) {
        alert("Пожалуйста, заполните все поля.");
        return;
      }

      try {
        const response = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });

        const data = await response.json();

        if (data.status === "ok") {
          window.location.href =
            data.role === "teacher" ? "/teacher/dashboard" : "/dashboard";
        } else {
          alert(data.message || "Неверный логин или пароль.");
        }
      } catch (err) {
        console.error("auth.js: сетевая ошибка:", err);
        alert("Не удалось связаться с сервером. Попробуйте позже.");
      }
    });
  }

  const registerForm = document.querySelector("#register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const username = document.querySelector("#username").value.trim();
      const password = document.querySelector("#password").value;
      const passwordConfirm = document.querySelector("#password-confirm").value;

      if (!username || !password || !passwordConfirm) {
        alert("Пожалуйста, заполните все поля.");
        return;
      }
      if (password !== passwordConfirm) {
        alert("Пароли не совпадают.");
        return;
      }

      try {
        const response = await fetch("/api/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const data = await response.json().catch(() => null);

        if (response.ok && data?.status === "ok") {
          window.location.href = data.redirect || "/dashboard";
        } else {
          alert(
            data?.message ||
              `Не удалось зарегистрироваться (ошибка сервера: ${response.status}).`
          );
        }
      } catch (err) {
        console.error("auth.js: сетевая ошибка:", err);
        alert("Не удалось связаться с сервером. Попробуйте позже.");
      }
    });
  }
});
