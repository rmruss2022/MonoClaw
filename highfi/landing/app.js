/* HighFi landing — mobile nav, smooth scroll, gallery lightbox, waitlist validation */
(function () {
  "use strict";

  /* ---- Current year ---- */
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  /* ---- Mobile nav toggle ---- */
  var toggle = document.getElementById("nav-toggle");
  var links = document.getElementById("nav-links");

  function closeNav() {
    if (!toggle || !links) return;
    links.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  }

  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    // Close the menu after tapping a link (mobile)
    links.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeNav();
    });
  }

  /* ---- Smooth scroll for in-page anchors (respects reduced motion) ---- */
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = a.getAttribute("href");
      if (!id || id === "#") return;
      var target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      // Move focus for accessibility without an extra jump
      target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    });
  });

  /* ---- Gallery: hide the section if every tile failed to load ---- */
  var grid = document.getElementById("gallery-grid");
  var emptyMsg = document.getElementById("gallery-empty");
  function checkGalleryEmpty() {
    if (!grid) return;
    var tiles = grid.querySelectorAll(".tile");
    var visible = 0;
    tiles.forEach(function (t) { if (!t.classList.contains("is-hidden")) visible++; });
    if (emptyMsg) emptyMsg.hidden = visible !== 0;
  }
  // Run after images have had a chance to error out
  window.addEventListener("load", checkGalleryEmpty);
  setTimeout(checkGalleryEmpty, 1500);

  /* ---- Lightbox ---- */
  var lightbox = document.getElementById("lightbox");
  var lightboxImg = document.getElementById("lightbox-img");
  var lightboxClose = document.getElementById("lightbox-close");
  var lastFocused = null;

  function openLightbox(src, alt) {
    if (!lightbox || !lightboxImg) return;
    lastFocused = document.activeElement;
    lightboxImg.src = src;
    lightboxImg.alt = alt || "";
    lightbox.hidden = false;
    lightbox.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (lightboxClose) lightboxClose.focus();
  }
  function closeLightbox() {
    if (!lightbox) return;
    lightbox.hidden = true;
    lightbox.setAttribute("aria-hidden", "true");
    if (lightboxImg) lightboxImg.src = "";
    document.body.style.overflow = "";
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  }

  if (grid) {
    grid.addEventListener("click", function (e) {
      var tile = e.target.closest(".tile");
      if (!tile) return;
      var img = tile.querySelector("img");
      // Only open if the image actually loaded
      if (!img || img.classList.contains("img--missing") || !img.naturalWidth) return;
      openLightbox(tile.getAttribute("data-full") || img.src, img.alt);
    });
  }
  if (lightboxClose) lightboxClose.addEventListener("click", closeLightbox);
  if (lightbox) {
    lightbox.addEventListener("click", function (e) {
      if (e.target === lightbox) closeLightbox();
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && lightbox && !lightbox.hidden) closeLightbox();
  });

  /* ---- Waitlist form (front-end only) ---- */
  var form = document.getElementById("waitlist-form");
  var input = document.getElementById("email");
  var msg = document.getElementById("waitlist-msg");
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (form && input && msg) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var value = input.value.trim();
      msg.classList.remove("is-ok", "is-err");
      if (!EMAIL_RE.test(value)) {
        input.classList.add("is-invalid");
        msg.textContent = "Please enter a valid email address.";
        msg.classList.add("is-err");
        input.focus();
        return;
      }
      input.classList.remove("is-invalid");
      msg.textContent = "You're on the list — we'll be in touch when HighFi is ready. 🔊";
      msg.classList.add("is-ok");
      form.reset();
    });
    input.addEventListener("input", function () {
      input.classList.remove("is-invalid");
    });
  }
})();
