document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

const revealItems = document.querySelectorAll(
  ".hero > *, .home-intro > *, .trip-card, .record, .request-card, .form-card, .action-panel"
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
    window.setTimeout(showAllRevealItems, 1200);
  } catch (_error) {
    showAllRevealItems();
  }
}
