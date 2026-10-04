"use strict";
const form = document.getElementById("test-form");
if (form) {
  const groups = [...form.querySelectorAll("fieldset")];
  const update = () => {
    const count = groups.filter(group => group.querySelector("input:checked")).length;
    document.getElementById("answered-count").textContent = count;
    document.getElementById("answer-progress").value = count;
    document.getElementById("missing-warning").textContent = count === groups.length ? "Все вопросы заполнены." : `Пропущено вопросов: ${groups.length - count}.`;
  };
  form.addEventListener("change", update); update();
  form.addEventListener("submit", event => {
    const missing = groups.some(group => !group.querySelector("input:checked"));
    if (missing && !form.querySelector("[name=confirm_missing]").checked) {
      event.preventDefault(); document.getElementById("missing-warning").textContent = "Есть пропуски. Выберите ответы или отметьте разрешение отправки с пропусками.";
      groups.find(group => !group.querySelector("input:checked")).querySelector("input").focus();
    } else { form.querySelector("button[type=submit]").disabled = true; }
  });
  window.addEventListener("pageshow", () => { form.querySelector("button[type=submit]").disabled = false; update(); });
}
