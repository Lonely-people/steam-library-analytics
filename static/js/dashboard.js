/* Dashboard KPI tiles and the latest sync status. */
(function () {
  "use strict";

  function t(key, vars) {
    return window.i18n.t(key, vars);
  }

  function qs(id) {
    return document.getElementById(id);
  }

  function get(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    });
  }

  function tile(labelKey, value, hint) {
    var col = document.createElement("div");
    col.className = "col-6 col-lg-3";
    var card = document.createElement("div");
    card.className = "card h-100";
    var body = document.createElement("div");
    body.className = "card-body";

    var label = document.createElement("div");
    label.className = "text-muted small";
    label.textContent = t(labelKey);

    var val = document.createElement("div");
    val.className = "fs-3 fw-semibold";
    val.textContent = value;

    body.appendChild(label);
    body.appendChild(val);

    if (hint) {
      var hintEl = document.createElement("div");
      hintEl.className = "small text-muted mt-1";
      hintEl.textContent = hint;
      body.appendChild(hintEl);
    }

    card.appendChild(body);
    col.appendChild(card);
    return col;
  }

  function percent(value) {
    return value === null || value === undefined ? "—" : value.toFixed(1) + "%";
  }

  function renderKpis(ov) {
    var row = qs("kpi-row");
    row.innerHTML = "";
    row.appendChild(tile("dash.total_games", String(ov.total_games),
      ov.hidden_games ? "+ " + ov.hidden_games + " " + t("form.hidden") : null));
    row.appendChild(tile("dash.total_hours", (ov.total_minutes / 60).toFixed(1) + " " +
      t("chart.hours")));
    row.appendChild(tile("dash.known_spend", "¥" + ov.known_spend,
      ov.incomplete_cost_games
        ? ov.incomplete_cost_games + " " + t("dash.incomplete_cost")
        : null));
    row.appendChild(tile("dash.unstarted_rate", percent(ov.unstarted_rate),
      ov.unstarted_count + " / " + ov.total_games));

    // PLAN.md §6.1 requires the uncompleted rate on the dashboard. The
    // denominator is only the games whose status the user actually set;
    // "status unconfirmed" is reported separately so the rate cannot be
    // read as covering the whole library.
    row.appendChild(tile("dash.uncompleted_rate", percent(ov.uncompleted_rate),
      ov.uncompleted_count + " / " + ov.completion_determined));
    row.appendChild(tile("dash.status_unknown", String(ov.status_unknown_count)));
  }

  function renderSync(logs) {
    var panel = qs("sync-panel");
    panel.innerHTML = "";
    if (!logs.length) {
      panel.textContent = t("dash.sync_never");
      return;
    }
    var latest = logs[0];
    var badge = document.createElement("span");
    var tone = latest.status === "success" ? "text-bg-success"
      : latest.status === "failed" ? "text-bg-danger" : "text-bg-secondary";
    badge.className = "badge " + tone;
    badge.textContent = t("dash.sync_" + latest.status);

    var line = document.createElement("div");
    line.className = "d-flex align-items-center gap-2 flex-wrap";
    var when = document.createElement("span");
    when.className = "small text-muted";
    when.textContent = (latest.sync_finished_at || latest.sync_started_at || "")
      .toString().replace("T", " ").slice(0, 19);
    var count = document.createElement("span");
    count.className = "small text-muted";
    count.textContent = latest.fetched_count + " " + t("ana.games");

    line.appendChild(badge);
    line.appendChild(when);
    line.appendChild(count);
    panel.appendChild(line);

    if (latest.message) {
      var msg = document.createElement("div");
      msg.className = "small text-danger mt-2";
      msg.textContent = latest.message;
      panel.appendChild(msg);
    }
  }

  function refresh() {
    get("/api/stats/overview").then(renderKpis).catch(function () {
      qs("kpi-row").innerHTML = "";
    });
    get("/api/steam/sync-logs?limit=1").then(function (body) {
      renderSync(body.items);
    }).catch(function () { renderSync([]); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.addEventListener("languagechange", refresh);
    refresh();
  });
})();
