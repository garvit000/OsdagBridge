// OsdagBridge documentation site — theme toggle, mobile nav, tabs, active link highlighting.
(function () {
  "use strict";

  var THEME_KEY = "osdagbridge-theme";
  var root = document.documentElement;
  var themeToggle = document.getElementById("themeToggle");

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    if (themeToggle) {
      themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
      themeToggle.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      );
    }
  }

  function getPreferredTheme() {
    var stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  applyTheme(getPreferredTheme());

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  }

  // Mobile navigation toggle
  var navToggle = document.getElementById("navToggle");
  var navLinks = document.getElementById("navLinks");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("open");
    });
    navLinks.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        navLinks.classList.remove("open");
      });
    });
  }

  // Highlight the active nav link based on current page
  var currentPage = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a[href]").forEach(function (link) {
    var href = link.getAttribute("href");
    if (href === currentPage || (currentPage === "" && href === "index.html")) {
      link.classList.add("active");
    }
  });

  // Simple tab switcher used on the installation page (Windows / Linux)
  document.querySelectorAll(".tabs").forEach(function (tabGroup) {
    var buttons = tabGroup.querySelectorAll(".tab-btn");
    var panelContainer = tabGroup.nextElementSibling;
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-tab");

        buttons.forEach(function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");

        if (panelContainer) {
          panelContainer.querySelectorAll(".tab-panel").forEach(function (panel) {
            panel.classList.toggle("active", panel.getAttribute("data-panel") === target);
          });
        }
      });
    });
  });
})();
