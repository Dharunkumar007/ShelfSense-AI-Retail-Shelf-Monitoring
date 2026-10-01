"use strict";
// Apply the persisted theme before styles paint, including when storage is blocked.
(() => {
  const root = document.documentElement;
  let initial = "dark";
  try { initial = localStorage.getItem("shelfsense-theme") || initial; } catch (_) {}
  root.dataset.theme = initial === "light" ? "light" : "dark";
  document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector("#themeToggle");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const syncTheme = () => {
      const dark = root.dataset.theme === "dark";
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0a0a0a" : "#f5f6f8");
      if (!toggle) return;
      toggle.title = toggle.ariaLabel = `Switch to ${dark ? "light" : "dark"} theme`;
      toggle.setAttribute("aria-pressed", String(dark));
      toggle.innerHTML = `<i data-lucide="${dark ? "sun" : "moon"}"></i>`;
      window.lucide?.createIcons();
    };
    syncTheme();
    toggle?.addEventListener("click", async () => {
      if (toggle.disabled) return;
      const apply = () => {
        root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
        try { localStorage.setItem("shelfsense-theme", root.dataset.theme); } catch (_) {}
        syncTheme();
      };
      if (!document.startViewTransition || reduced.matches) { apply(); return; }
      const rect = toggle.getBoundingClientRect();
      const x = rect.left + rect.width/2, y = rect.top + rect.height/2;
      const radius = Math.max(x, innerWidth-x, y, innerHeight-y);
      toggle.disabled = true;
      try {
        const transition = document.startViewTransition(apply);
        await transition.ready;
        const animation = root.animate({clipPath:[
          `polygon(${x}px ${y}px,${x}px ${y}px,${x}px ${y}px,${x}px ${y}px)`,
          `polygon(${x-radius}px ${y-radius}px,${x+radius}px ${y-radius}px,${x+radius}px ${y+radius}px,${x-radius}px ${y+radius}px)`
        ]}, {duration:450, easing:"ease-in-out", pseudoElement:"::view-transition-new(root)"});
        await animation.finished;
        animation.cancel();
        await transition.finished;
      } catch (_) { syncTheme(); }
      finally { toggle.disabled = false; }
    });

    const picker = document.querySelector("#chooseImage");
    const ripple = (x, y) => {
      if (reduced.matches || picker.querySelector("input").disabled) return;
      const rect = picker.getBoundingClientRect();
      const circle = document.createElement("span");
      circle.className = "ripple";
      circle.style.left = `${x-rect.left}px`; circle.style.top = `${y-rect.top}px`;
      circle.style.width = circle.style.height = `${Math.max(rect.width,rect.height)*2}px`;
      picker.append(circle);
      circle.addEventListener("animationend", () => circle.remove(), {once:true});
      setTimeout(() => circle.remove(), 800);
    };
    picker?.addEventListener("pointerdown", (e) => ripple(e.clientX,e.clientY));
    picker?.addEventListener("keydown", (e) => {
      if (["Enter", " "].includes(e.key)) { const r=picker.getBoundingClientRect(); ripple(r.left+r.width/2,r.top+r.height/2); }
    });

    const progress = document.querySelector("#scrollProgress");
    const header = document.querySelector(".topbar");
    if (!progress || !header) return;
    let scheduled = false;
    const update = () => {
      scheduled = false;
      const rect = header.getBoundingClientRect();
      const max = root.scrollHeight-innerHeight;
      const value = max > 0 ? Math.max(0, Math.min(1, scrollY/max)) : 0;
      progress.style.top = `${Math.max(0,rect.bottom)}px`;
      progress.style.left = `${rect.left}px`; progress.style.width = `${rect.width}px`;
      progress.firstElementChild.style.transform = `scaleX(${value})`;
      progress.setAttribute("aria-valuenow", String(Math.round(value*100)));
      document.querySelector("#scrollValue").textContent = `${Math.round(value*100)}%`;
    };
    const schedule = () => { if (!scheduled) { scheduled=true; requestAnimationFrame(update); } };
    addEventListener("scroll",schedule,{passive:true}); addEventListener("resize",schedule);
    new ResizeObserver(schedule).observe(document.body);
    new ResizeObserver(schedule).observe(header);
    schedule();
  });
})();
