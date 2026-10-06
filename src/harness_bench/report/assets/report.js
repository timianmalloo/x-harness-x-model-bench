/* harness-bench report.js (design phase4-report.md, section 5-7, R4).
 *
 * Vanilla, no import, under 12 KB. Progressive enhancement only: every table, <details> and link
 * already works without this file (R1-R3). This script adds:
 *   - the leaderboard's sort buttons (section 6 row 3);
 *   - the combo legend and pack switch (section 6, classes on <main>, UIA-14);
 *   - the evidence popovers (section 7: click/Enter/Space via focus, hover shows, Esc closes and
 *     returns focus);
 *   - the Runs filter (task, combo, pack, outcome, validity; section 6 row 10);
 *   - the leaderboard's "Show cells" link, which filters Runs to its row's combo and pack first.
 * Its own bytes are hashed into the page's CSP `script-src` (html_builder.csp_meta); nothing here
 * fetches, and it never writes outside this document.
 */
"use strict";
(function () {
  var main = document.querySelector("main");

  /* --- Evidence popovers (section 7) ------------------------------------------------------ */
  var owner = null;
  var popSeq = 0;

  function ownerPopover(btn) {
    var p = btn.nextElementSibling;
    return p && p.classList.contains("popover") ? p : null;
  }

  function showPopover(btn) {
    var pop = ownerPopover(btn);
    if (!pop) return;
    if (owner && owner !== btn) hidePopover();
    owner = btn;
    pop.hidden = false;
    if (!pop.id) pop.id = "pop-" + (++popSeq);
    btn.setAttribute("aria-describedby", pop.id);
  }

  function hidePopover() {
    if (!owner) return;
    var pop = ownerPopover(owner);
    if (pop) pop.hidden = true;
    owner.removeAttribute("aria-describedby");
    owner = null;
  }

  document.addEventListener("focusin", function (e) {
    if (e.target.classList && e.target.classList.contains("ev")) showPopover(e.target);
  });
  document.addEventListener("mouseover", function (e) {
    var t = e.target;
    if (t.classList && t.classList.contains("ev")) showPopover(t);
  });
  document.addEventListener("focusout", function (e) {
    if (e.target === owner) hidePopover();
  });
  document.addEventListener("mouseout", function (e) {
    if (e.target === owner && document.activeElement !== owner) hidePopover();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && owner) {
      var o = owner;
      hidePopover();
      o.focus();
    }
  });

  /* --- "Show cells" (a popover link into Runs, filtered to this row's combo/pack) ------------- */
  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a[data-runs-combo]") : null;
    if (!link) return;
    var fc = document.getElementById("filter-combo");
    var fp = document.getElementById("filter-pack");
    if (fc) fc.value = link.getAttribute("data-runs-combo");
    if (fp) fp.value = link.getAttribute("data-runs-pack");
    applyRunsFilter();
  });

  /* --- Combo legend + pack switch (section 6): classes on <main> do the hiding --------------- */
  function reasonId(btn) {
    return btn.dataset.combo ? "reason-" + btn.dataset.combo : "reason-pack-" + btn.dataset.pack;
  }

  function disableToggle(btn, why) {
    btn.setAttribute("aria-disabled", "true");
    var id = reasonId(btn);
    var p = document.getElementById(id);
    if (!p) {
      p = document.createElement("p");
      p.id = id;
      var reasons = document.getElementById("bar-reasons");
      if (reasons) reasons.appendChild(p);
    }
    p.textContent = why;
    btn.setAttribute("aria-describedby", id);
  }

  function enableToggle(btn) {
    if (btn.getAttribute("aria-disabled") !== "true") return;
    var id = btn.getAttribute("aria-describedby");
    btn.removeAttribute("aria-disabled");
    btn.removeAttribute("aria-describedby");
    var p = id && document.getElementById(id);
    if (p) p.remove();
  }

  var comboButtons = Array.prototype.slice.call(document.querySelectorAll("#legend .tg"));
  comboButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (btn.getAttribute("aria-disabled") === "true") return;
      var pressed = comboButtons.filter(function (b) {
        return b.getAttribute("aria-pressed") === "true";
      });
      if (pressed.length === 1 && pressed[0] === btn) {
        disableToggle(btn, "At least one combo must stay visible.");
        return;
      }
      comboButtons.forEach(enableToggle);
      btn.setAttribute("aria-pressed", btn.getAttribute("aria-pressed") === "true" ? "false" : "true");
      applyComboFilter();
    });
  });

  function applyComboFilter() {
    if (!main) return;
    for (var i = 1; i <= 8; i++) main.classList.remove("hide-c" + i);
    comboButtons.forEach(function (b) {
      if (b.getAttribute("aria-pressed") === "false") main.classList.add("hide-" + b.dataset.combo);
    });
  }

  var packButtons = Array.prototype.slice.call(document.querySelectorAll("#pack-switch .tg"));
  packButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (btn.getAttribute("aria-disabled") === "true") return;
      packButtons.forEach(function (b) {
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      applyPackFilter();
    });
  });

  function applyPackFilter() {
    if (!main) return;
    Array.prototype.slice.call(main.classList).forEach(function (c) {
      if (c.indexOf("pack-") === 0) main.classList.remove(c);
    });
    var pressed = packButtons.filter(function (b) {
      return b.getAttribute("aria-pressed") === "true";
    })[0];
    var setting = pressed ? pressed.dataset.pack : "both";
    if (setting !== "both") main.classList.add("pack-" + setting);
  }

  /* --- Sort (section 6 row 3): order a table's tbody by a column's data-sort-value ----------- */
  Array.prototype.forEach.call(document.querySelectorAll(".sort"), function (btn) {
    btn.addEventListener("click", function () {
      var key = btn.dataset.sortKey;
      var th = btn.closest("th");
      var table = btn.closest("table");
      if (!th || !table || !key) return;
      var tbody = table.querySelector("tbody");
      if (!tbody) return;
      var dir = th.getAttribute("aria-sort") === "descending" ? 1 : -1; // default: first click sorts descending
      Array.prototype.forEach.call(table.querySelectorAll("th[aria-sort]"), function (h) {
        if (h !== th) h.removeAttribute("aria-sort");
      });
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var av = a.querySelector('[data-sort="' + key + '"]');
        var bv = b.querySelector('[data-sort="' + key + '"]');
        var an = av && av.hasAttribute("data-sort-value") ? parseFloat(av.getAttribute("data-sort-value")) : null;
        var bn = bv && bv.hasAttribute("data-sort-value") ? parseFloat(bv.getAttribute("data-sort-value")) : null;
        if (an === null && bn === null) return 0;
        if (an === null) return 1; // NA always sorts last, either direction
        if (bn === null) return -1;
        return dir === -1 ? bn - an : an - bn;
      });
      rows.forEach(function (r) {
        tbody.appendChild(r);
      });
      th.setAttribute("aria-sort", dir === -1 ? "descending" : "ascending");
    });
  });

  /* --- Runs filter (section 6 row 10): task, combo, pack, outcome, validity ------------------ */
  var FILTERS = [
    ["filter-task", "task"],
    ["filter-combo", "comboName"],
    ["filter-pack", "pack"],
    ["filter-outcome", "outcome"],
    ["filter-validity", "validity"],
  ];

  function applyRunsFilter() {
    var body = document.getElementById("runs-body");
    if (!body) return;
    var values = FILTERS.map(function (f) {
      var el = document.getElementById(f[0]);
      return el ? el.value : "";
    });
    var visible = 0;
    Array.prototype.forEach.call(body.querySelectorAll("tr"), function (tr) {
      var match = FILTERS.every(function (f, i) {
        return !values[i] || tr.dataset[f[1]] === values[i];
      });
      tr.hidden = !match;
      if (match) visible++;
    });
    var noMatch = document.getElementById("runs-no-match");
    if (noMatch) noMatch.hidden = visible !== 0;
  }

  FILTERS.forEach(function (f) {
    var el = document.getElementById(f[0]);
    if (el) el.addEventListener("change", applyRunsFilter);
  });

  performance.mark("report-ready");
})();
