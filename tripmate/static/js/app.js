document.documentElement.classList.add("has-motion");

document.querySelectorAll("[data-nav-toggle]").forEach((toggle) => {
  const nav = document.querySelector("[data-primary-nav]");
  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    nav?.classList.toggle("is-open", !isOpen);
  });
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll("[data-assistant-form]").forEach((form) => {
  form.addEventListener("submit", () => {
    if (!form.checkValidity()) return;

    const button = form.querySelector("[data-assistant-submit]");
    const output = document.querySelector("[data-assistant-output]");
    const loading = output?.querySelector("[data-assistant-loading]");
    const thinkingText = loading?.querySelector("[data-thinking-text]");

    form.setAttribute("aria-busy", "true");
    if (button) {
      button.disabled = true;
      button.textContent = button.dataset.loadingLabel || "Thinking...";
    }
    if (output && loading) {
      output.setAttribute("aria-busy", "true");
      output.querySelectorAll("[data-assistant-state]").forEach((state) => {
        state.hidden = true;
      });
      loading.hidden = false;
      let dots = 1;
      window.setInterval(() => {
        dots = (dots % 3) + 1;
        if (thinkingText) thinkingText.textContent = `Thinking${".".repeat(dots)}`;
      }, 420);
    }
  });
});

const revealItems = document.querySelectorAll(
  "[data-reveal], .record, .request-card, .form-card, .action-panel, .form-section"
);

const showAllRevealItems = () => {
  revealItems.forEach((item) => item.classList.add("is-visible"));
};

if (
  window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
  typeof IntersectionObserver !== "function"
) {
  showAllRevealItems();
} else {
  try {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    revealItems.forEach((item) => observer.observe(item));

    // Some embedded or background browsers do not deliver intersection events.
    // Content must remain usable even when the enhancement cannot run.
    window.setTimeout(showAllRevealItems, 700);
  } catch (_error) {
    showAllRevealItems();
  }
}
