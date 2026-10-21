/* =====================================================================
   YojanaBench theme controller (shared by the dashboard + login + the
   grievance portal).

   A tiny, dependency-free light/dark switch. The choice is stored in
   localStorage and applied to <html data-theme="...">, so CSS variables
   drive every surface. Any element with class "theme-toggle" becomes a
   toggle button ("Dark" / "Light").
   ===================================================================== */
(function () {
  "use strict";

  var KEY = "yb_theme";

  function current() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark" : "light";
  }

  function apply(theme) {
    var dark = theme === "dark";
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    try { localStorage.setItem(KEY, dark ? "dark" : "light"); } catch (e) { /* ignore */ }

    var btns = document.querySelectorAll(".theme-toggle");
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute("aria-pressed", String(dark));
      btns[i].title = dark ? "Switch to light theme" : "Switch to dark theme";
      var lbl = btns[i].querySelector(".theme-toggle-label");
      if (lbl) lbl.textContent = dark ? "Light" : "Dark";
    }
  }

  function toggle() {
    apply(current() === "dark" ? "light" : "dark");
  }

  function init() {
    var saved = "light";
    try { saved = localStorage.getItem(KEY) || "light"; } catch (e) { /* ignore */ }
    apply(saved);

    var btns = document.querySelectorAll(".theme-toggle");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", function (e) {
        e.preventDefault();
        apply(current() === "dark" ? "light" : "dark");
      });
    }
  }

  window.YBTheme = { current: current, apply: apply };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
