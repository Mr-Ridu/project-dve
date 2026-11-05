// Custom site JavaScript. Loaded with `defer` from templates/base.html.
document.addEventListener("DOMContentLoaded", () => {
  document.documentElement.dataset.js = "ready";

  // Mobile menu toggle.
  const toggle = document.getElementById("menu-toggle");
  const menu = document.getElementById("mobile-menu");
  if (toggle && menu) {
    toggle.addEventListener("click", () => {
      const open = menu.classList.toggle("hidden") === false;
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });

    // Close after following a link so the next page starts on top.
    menu.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        menu.classList.add("hidden");
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Open menu");
      }
    });
  }

  // User-spotlight tabs: one visible panel at a time.
  const spotTabs = document.querySelectorAll(".spot-tab");
  const spotPanels = document.querySelectorAll("[data-spot-panel]");
  if (spotTabs.length && spotPanels.length) {
    spotTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const target = tab.dataset.spot;
        spotTabs.forEach((t) => {
          const active = t === tab;
          t.classList.toggle("is-active", active);
          t.setAttribute("aria-selected", String(active));
        });
        spotPanels.forEach((panel) => {
          panel.classList.toggle("hidden", panel.dataset.spotPanel !== target);
        });
      });
    });
  }

  // Featured News: two manual slides with progress-tab controls.
  const news = document.querySelector("[data-news-carousel]");
  if (news) {
    const slides = Array.from(news.querySelectorAll("[data-news-slide]"));
    const dots = Array.from(news.querySelectorAll("[data-news-dot]"));
    const controls = news.querySelector('[aria-label="Featured news slides"]');
    let current = 0;

    const show = (index) => {
      current = (index + slides.length) % slides.length;
      slides.forEach((slide, i) => {
        slide.classList.toggle("is-active", i === current);
        slide.setAttribute("aria-hidden", String(i !== current));
      });
      dots.forEach((dot, i) => dot.setAttribute("aria-pressed", String(i === current)));
    };

    dots.forEach((dot, i) => dot.addEventListener("click", () => show(i)));
    if (controls) {
      controls.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        show(current + (event.key === "ArrowRight" ? 1 : -1));
        dots[current].focus();
      });
    }
    show(0);
  }

  // Back-to-top button: shown once the page has scrolled a screenful.
  const toTop = document.getElementById("back-to-top");
  if (toTop) {
    const sync = () => {
      toTop.classList.toggle("hidden", window.scrollY < 400);
    };
    sync();
    window.addEventListener("scroll", sync, { passive: true });
    toTop.addEventListener("click", (event) => {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
});
