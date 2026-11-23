/* Analytics charts. All numbers come from the stats API; only formatting
 * and labels live here, so the display language never changes the data. */
(function () {
  "use strict";

  var charts = {};

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

  function mount(id) {
    var el = qs(id);
    if (!charts[id]) {
      charts[id] = echarts.init(el);
    }
    return charts[id];
  }

  function emptyOption(titleKey) {
    return {
      title: {
        text: t("ana.no_data"),
        left: "center",
        top: "middle",
        textStyle: { color: "#888", fontSize: 14, fontWeight: "normal" }
      }
    };
  }

  function renderGenres(items) {
    var chart = mount("genre-chart");
    // Drop zero-minute buckets (e.g. an uncategorised game never launched);
    // they add legend noise without carrying information.
    var visible = items.filter(function (item) { return item.minutes > 0; });
    if (!visible.length) {
      chart.setOption(emptyOption(), true);
      return;
    }
    var data = visible.map(function (item) {
      var name = item.genre_id === 0
        ? t("ana.uncategorised")
        : (window.i18n.getLang() === "en" ? item.name_en : item.name_zh) || item.name_zh;
      return { name: name, value: item.minutes };
    });
    chart.setOption({
      tooltip: {
        trigger: "item",
        formatter: function (p) {
          return p.name + "<br/>" + (p.value / 60).toFixed(1) + " " + t("chart.hours")
            + " (" + p.percent + "%)";
        }
      },
      legend: { bottom: 0, type: "scroll" },
      series: [{
        type: "pie",
        radius: ["35%", "65%"],
        center: ["50%", "45%"],
        data: data,
        label: { formatter: "{b}: {d}%" }
      }]
    }, true);
  }

  function renderCost(payload) {
    var chart = mount("cost-chart");
    var items = payload.ranked || [];
    if (!items.length) {
      chart.setOption(emptyOption(), true);
      return;
    }
    // Horizontal bar: reverse so the top item appears at the top.
    var rows = items.slice().reverse();
    chart.setOption({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: function (params) {
          var p = params[0];
          var row = rows[p.dataIndex];
          return row.game_name + "<br/>" + t("ana.per_hour") + ": " + p.value
            + "<br/>" + t("ana.minutes") + ": " + row.play_minutes;
        }
      },
      grid: { left: 8, right: 56, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: "value", name: t("ana.per_hour"), nameLocation: "end", nameGap: 8 },
      yAxis: {
        type: "category",
        data: rows.map(function (r) { return r.game_name; }),
        axisLabel: { width: 140, overflow: "truncate" }
      },
      series: [{
        type: "bar",
        data: rows.map(function (r) { return Number(r.cost_per_hour); }),
        itemStyle: { color: "#0d6efd" },
        label: { show: true, position: "right", formatter: "{c}" }
      }]
    }, true);
  }

  function renderIdle(payload) {
    var chart = mount("idle-chart");
    qs("idle-total").textContent = "¥" + Number(payload.idle_total).toFixed(2);
    var items = payload.idle || [];
    if (!items.length) {
      chart.setOption(emptyOption(), true);
      return;
    }
    var rows = items.slice().reverse();
    chart.setOption({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: function (params) {
          var row = rows[params[0].dataIndex];
          return row.game_name + "<br/>" + t("ana.yuan") + ": " + row.net_paid;
        }
      },
      grid: { left: 8, right: 56, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: "value", name: t("ana.yuan"), nameLocation: "end", nameGap: 8 },
      yAxis: {
        type: "category",
        data: rows.map(function (r) { return r.game_name; }),
        axisLabel: { width: 140, overflow: "truncate" }
      },
      series: [{
        type: "bar",
        data: rows.map(function (r) { return Number(r.net_paid); }),
        itemStyle: { color: "#dc3545" },
        label: { show: true, position: "right", formatter: "{c}" }
      }]
    }, true);
  }

  function renderYearly(payload) {
    var chart = mount("yearly-chart");
    var items = payload.items || [];
    if (!items.length) {
      chart.setOption(emptyOption(), true);
    } else {
      chart.setOption({
        tooltip: { trigger: "axis" },
        grid: { left: 8, right: 24, top: 24, bottom: 8, containLabel: true },
        xAxis: {
          type: "category",
          data: items.map(function (i) { return String(i.year); })
        },
        yAxis: { type: "value", name: t("ana.yuan") },
        series: [{
          type: "line",
          smooth: true,
          symbolSize: 8,
          data: items.map(function (i) { return Number(i.net_paid); }),
          areaStyle: { opacity: 0.15 },
          label: { show: true, formatter: "{c}" }
        }]
      }, true);
    }
    var note = qs("undated-note");
    note.textContent = payload.undated_records
      ? payload.undated_records + " " + t("ana.undated")
      : "";
  }

  function renderZeroCost(payload) {
    var box = qs("zero-cost-list");
    box.innerHTML = "";
    var items = payload.zero_cost || [];
    if (!items.length) {
      box.textContent = t("ana.no_data");
      return;
    }
    var badges = document.createElement("div");
    badges.className = "d-flex flex-wrap gap-2";
    items.forEach(function (item) {
      var badge = document.createElement("span");
      badge.className = "badge text-bg-success-subtle text-success-emphasis border";
      badge.textContent = item.game_name + " · " + item.play_minutes + " " + t("ana.minutes");
      badges.appendChild(badge);
    });
    box.appendChild(badges);
  }

  function loadCosts(order) {
    return get("/api/stats/costs?order=" + encodeURIComponent(order)).then(function (payload) {
      renderCost(payload);
      renderIdle(payload);
      renderZeroCost(payload);
    });
  }

  function refresh() {
    get("/api/stats/genres").then(function (payload) {
      renderGenres(payload.items);
    }).catch(function () { mount("genre-chart").setOption(emptyOption(), true); });

    loadCosts(qs("cost-order").value);
    get("/api/stats/yearly").then(renderYearly).catch(function () {
      mount("yearly-chart").setOption(emptyOption(), true);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    qs("cost-order").addEventListener("change", function () {
      loadCosts(qs("cost-order").value);
    });
    document.addEventListener("languagechange", refresh);
    window.addEventListener("resize", function () {
      Object.keys(charts).forEach(function (id) { charts[id].resize(); });
    });
    refresh();
  });
})();
