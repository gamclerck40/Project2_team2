(function () {
  const form = document.querySelector(".js-default-account-form");
  const select = document.querySelector(".js-default-account-select");
  if (!form || !select) return;

  select.addEventListener("change", () => {
    const template = form.dataset.actionTemplate || form.getAttribute("action") || "";
    const id = select.value;

    // ✅ /0/ 을 /{id}/ 로 치환
    form.action = template.replace("/0/", `/${id}/`);
    form.submit();
  });
})();
