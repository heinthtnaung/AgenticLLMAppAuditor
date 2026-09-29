/* The page's only script. It sends no network request: no network APIs, no
   external URL. With it off, every panel shows and nothing is hidden; the `js`
   class is the only thing that turns panels into tabs. */
(function () {
  var root = document.documentElement;
  root.classList.add("js");

  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  var names = tabs.map(function (tab) { return tab.dataset.tab; });

  function show(name) {
    if (names.indexOf(name) < 0) name = names[0];
    tabs.forEach(function (tab) {
      var on = tab.dataset.tab === name;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
      document.getElementById(tab.getAttribute("aria-controls")).hidden = !on;
    });
    return name;
  }

  function route() {
    var hash = decodeURIComponent(location.hash.slice(1));
    var slash = hash.indexOf("/");
    var name = show(slash < 0 ? hash : hash.slice(0, slash));
    if (slash < 0) return;
    var target = document.getElementById(name + "-" + hash.slice(slash + 1));
    if (!target) return;
    var hiddenBy = target.closest("[hidden]");
    if (hiddenBy && hiddenBy.matches("tr, article")) resetFilters(hiddenBy.closest(".panel"));
    if (target.tagName === "DETAILS") target.open = true;
    target.scrollIntoView({ block: "start" });
    flash(target);
  }

  function flash(target) {
    target.classList.remove("flash");
    void target.offsetWidth;
    target.classList.add("flash");
  }

  window.addEventListener("hashchange", route);

  var tablist = document.querySelector('[role="tablist"]');
  if (tablist) tablist.addEventListener("keydown", onArrowKey);

  function onArrowKey(event) {
    var here = tabs.indexOf(document.activeElement);
    if (here < 0) return;
    var moves = { ArrowRight: here + 1, ArrowLeft: here - 1, Home: 0, End: tabs.length - 1 };
    var to = moves[event.key];
    if (to === undefined) return;
    event.preventDefault();
    var tab = tabs[(to + tabs.length) % tabs.length];
    tab.focus();
    location.hash = tab.dataset.tab;
  }

  var resets = [];

  function resetFilters(panel) {
    resets.forEach(function (one) { if (panel.contains(one.bar)) one.reset(); });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-filter-for]"), wireFilterBar);

  function wireFilterBar(bar) {
    var host = document.getElementById(bar.dataset.filterFor);
    var items = filterItems(host);
    var empty = (host.tagName === "TABLE" ? host.parentNode : host).querySelector(".empty");
    var counter = bar.querySelector(".result-count");
    var buttons = Array.prototype.slice.call(bar.querySelectorAll("[data-filter]"));
    var search = bar.querySelector("[data-search]");
    var state = { mode: "all" };

    function apply() {
      var term = search ? search.value.trim().toLowerCase() : "";
      var shown = countShown(items, state.mode, term);
      if (empty) empty.hidden = shown > 0;
      var count = shown === items.length ? "" : shown + " of " + items.length;
      if (counter) counter.textContent = count;
    }

    wireButtons(buttons, state, apply);
    if (search) search.addEventListener("input", apply);
    registerReset(bar, state, buttons, search, apply);
  }

  function wireButtons(buttons, state, apply) {
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        state.mode = button.dataset.filter;
        press(buttons, button);
        apply();
      });
    });
  }

  function registerReset(bar, state, buttons, search, apply) {
    resets.push({ bar: bar, reset: function () {
      state.mode = "all";
      if (search) search.value = "";
      pressDefault(buttons);
      apply();
    } });
  }

  function filterItems(host) {
    var selector = host.tagName === "TABLE" ? "tbody tr" : "[data-tags], .purls li";
    return Array.prototype.slice.call(host.querySelectorAll(selector));
  }

  function countShown(items, mode, term) {
    var shown = 0;
    items.forEach(function (item) {
      var tags = (item.dataset.tags || "").split(" ");
      var matchTag = mode === "all" || tags.indexOf(mode) >= 0;
      var matchTerm = !term || item.textContent.toLowerCase().indexOf(term) >= 0;
      item.hidden = !(matchTag && matchTerm);
      if (matchTag && matchTerm) shown++;
    });
    return shown;
  }

  function press(buttons, chosen) {
    buttons.forEach(function (one) {
      one.setAttribute("aria-pressed", one === chosen ? "true" : "false");
    });
  }

  function pressDefault(buttons) {
    buttons.forEach(function (one) {
      one.setAttribute("aria-pressed", one.dataset.filter === "all" ? "true" : "false");
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-toggle-all]"), wireToggleAll);

  function wireToggleAll(button) {
    var host = document.getElementById(button.dataset.toggleAll);
    button.addEventListener("click", function () {
      var open = button.dataset.open !== "true";
      Array.prototype.forEach.call(host.querySelectorAll("details.metric"), function (one) {
        one.open = open;
      });
      button.dataset.open = open ? "true" : "false";
      button.textContent = open ? button.dataset.less : button.dataset.more;
    });
  }

  window.addEventListener("beforeprint", function () {
    Array.prototype.forEach.call(document.querySelectorAll("details"), function (one) {
      one.open = true;
    });
  });

  route();
})();
