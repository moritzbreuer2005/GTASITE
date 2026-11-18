(function () {
  var lang = document.documentElement.lang || "en";
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  // Today's date in the masthead, in the page's language
  var today = document.querySelector("[data-today]");
  if (today) today.textContent = new Date().toLocaleDateString(lang,
    { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  // Launch countdown (midnight in the visitor's own time zone)
  var bar = document.querySelector(".ticker[data-launch]");
  if (bar) {
    var target = new Date(bar.getAttribute("data-launch")); // no "Z" => local time
    var cd = bar.querySelector("[data-cd]");
    var text = bar.querySelector(".ticker-text");
    var pad = function (n) { return String(n).padStart(2, "0"); };
    var tick = function () {
      var ms = target - new Date();
      if (ms <= 0) { text.textContent = bar.getAttribute("data-out"); return false; }
      var s = Math.floor(ms / 1000), d = Math.floor(s / 86400);
      cd.textContent = " — " + (d ? d + "d " : "") + pad(Math.floor(s / 3600) % 24) + ":" +
        pad(Math.floor(s / 60) % 60) + ":" + pad(s % 60);
      return true;
    };
    if (!isNaN(target) && cd && tick()) {
      var id = setInterval(function () { if (!tick()) clearInterval(id); }, 1000);
    }
  }

  // Relative times in the news list ("vor 4 Minuten", "hace 4 minutos", ...)
  var rtf = window.Intl && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(lang, { numeric: "auto" }) : null;
  var now = Date.now();
  document.querySelectorAll(".river time[datetime]").forEach(function (t) {
    var d = new Date(t.getAttribute("datetime"));
    if (isNaN(d)) return;
    var mins = Math.round((now - d) / 60000);
    if (rtf && mins < 60) t.textContent = rtf.format(-Math.max(mins, 0), "minute");
    else if (rtf && mins < 1440) t.textContent = rtf.format(-Math.round(mins / 60), "hour");
    else t.textContent = d.toLocaleDateString(lang, { month: "short", day: "numeric" });
    t.title = d.toLocaleString(lang);
  });

  // Language switcher: remember the choice, close when clicking elsewhere
  var sw = document.querySelector("details.lang");
  if (sw) {
    sw.addEventListener("click", function (e) {
      var a = e.target.closest("a[data-lang]");
      if (a) store.set("lang", a.getAttribute("data-lang"));
    });
    document.addEventListener("click", function (e) { if (!sw.contains(e.target)) sw.open = false; });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") sw.open = false; });
  }

  // Offer the visitor's own language once, if this page exists in it
  if (!store.get("lang")) {
    var hints = {};
    try { hints = JSON.parse(document.documentElement.getAttribute("data-hints") || "{}"); } catch (e) {}
    var wanted = (navigator.languages || [navigator.language || ""]).map(function (l) { return l.slice(0, 2).toLowerCase(); });
    for (var i = 0; i < wanted.length; i++) {
      var w = wanted[i];
      if (w === lang) break; // already reading in a preferred language
      var alt = document.querySelector('link[rel="alternate"][hreflang="' + w + '"]');
      if (alt && hints[w]) {
        var div = document.createElement("div");
        div.className = "lang-hint";
        div.innerHTML = '<div class="wrap"><a></a><button type="button" aria-label="Close">×</button></div>';
        var link = div.querySelector("a");
        link.href = new URL(alt.href).pathname;
        link.lang = w;
        link.textContent = hints[w] + " →";
        link.addEventListener("click", function () { store.set("lang", w); });
        div.querySelector("button").addEventListener("click", function () { store.set("lang", lang); div.remove(); });
        var ticker = document.querySelector(".ticker");
        ticker.parentNode.insertBefore(div, ticker.nextSibling);
        break;
      }
    }
  }
})();
