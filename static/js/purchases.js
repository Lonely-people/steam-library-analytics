/* Purchases page: list, filter by game, create/edit/delete, cost summary. */
(function () {
  "use strict";

  var state = { games: [], editingId: null, filterGame: null };

  function t(key, vars) {
    return window.i18n.t(key, vars);
  }

  function qs(id) {
    return document.getElementById(id);
  }

  function toast(message, isError) {
    var box = qs("toast-box");
    var el = document.createElement("div");
    el.className = "toast align-items-center text-white border-0 mb-2 " +
      (isError ? "bg-danger" : "bg-success");
    el.innerHTML =
      '<div class="d-flex"><div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" ' +
      'data-bs-dismiss="toast"></button></div>';
    el.querySelector(".toast-body").textContent = message;
    box.appendChild(el);
    new bootstrap.Toast(el, { delay: 3000 }).show();
    el.addEventListener("hidden.bs.toast", function () { el.remove(); });
  }

  function request(url, options) {
    return fetch(url, options).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (!response.ok) {
          throw new Error(body && body.error ? body.error : ("HTTP " + response.status));
        }
        return body;
      });
    });
  }

  function money(value) {
    return "¥" + Number(value).toFixed(2);
  }

  function loadGames() {
    return request("/api/games?limit=200").then(function (body) {
      state.games = body.items;
      var options = state.games.map(function (game) {
        var option = document.createElement("option");
        option.value = String(game.game_id);
        option.textContent = game.game_name;
        return option;
      });

      var select = qs("game-select");
      var keep = select.value;
      select.innerHTML = "";
      var all = document.createElement("option");
      all.value = "";
      all.textContent = t("purchases.all_games");
      select.appendChild(all);
      options.forEach(function (o) { select.appendChild(o.cloneNode(true)); });
      select.value = keep;

      var modalSelect = qs("p-game");
      modalSelect.innerHTML = "";
      options.forEach(function (o) { modalSelect.appendChild(o); });
    });
  }

  function loadPurchases() {
    var url = "/api/purchases";
    if (state.filterGame) {
      url += "?game_id=" + encodeURIComponent(state.filterGame);
    }
    return request(url).then(function (body) {
      render(body.items);
    });
  }

  function render(items) {
    var tbody = qs("purchases-body");
    tbody.innerHTML = "";
    if (!items.length) {
      var row = document.createElement("tr");
      var td = document.createElement("td");
      td.colSpan = 7;
      td.className = "text-center text-muted py-4";
      td.textContent = t("purchases.empty");
      row.appendChild(td);
      tbody.appendChild(row);
      return;
    }
    items.forEach(function (item) {
      var tr = document.createElement("tr");

      var gameCell = document.createElement("td");
      gameCell.textContent = item.game_name;
      tr.appendChild(gameCell);

      var dateCell = document.createElement("td");
      dateCell.textContent = item.purchase_date || "—";
      tr.appendChild(dateCell);

      var amountCell = document.createElement("td");
      amountCell.className = "text-end";
      amountCell.textContent = money(item.paid_amount);
      tr.appendChild(amountCell);

      var typeCell = document.createElement("td");
      typeCell.textContent = t("ptype." + item.purchase_type);
      tr.appendChild(typeCell);

      var statusCell = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "badge " +
        (item.status === "refunded" ? "text-bg-warning" : "text-bg-success");
      badge.textContent = t("pstatus." + item.status);
      statusCell.appendChild(badge);
      tr.appendChild(statusCell);

      var notesCell = document.createElement("td");
      notesCell.className = "text-muted small";
      notesCell.textContent = item.notes || "—";
      tr.appendChild(notesCell);

      var actions = document.createElement("td");
      actions.className = "text-nowrap";
      var edit = document.createElement("button");
      edit.type = "button";
      edit.className = "btn btn-sm btn-outline-primary me-1";
      edit.textContent = t("btn.edit");
      edit.addEventListener("click", function () { openEditor(item); });
      actions.appendChild(edit);
      var del = document.createElement("button");
      del.type = "button";
      del.className = "btn btn-sm btn-outline-danger";
      del.textContent = t("btn.delete");
      del.addEventListener("click", function () { remove(item); });
      actions.appendChild(del);
      tr.appendChild(actions);

      tbody.appendChild(tr);
    });
  }

  function renderCost(summary) {
    var panel = qs("cost-panel");
    panel.innerHTML = "";
    if (!summary) {
      return;
    }
    var wrapper = document.createElement("div");
    wrapper.className = "d-flex flex-wrap gap-3 align-items-center";

    function item(labelKey, value, toneClass) {
      var div = document.createElement("div");
      div.className = "small";
      var label = document.createElement("div");
      label.className = "text-muted";
      label.textContent = t(labelKey);
      var val = document.createElement("div");
      val.className = "fw-semibold " + (toneClass || "");
      val.textContent = value;
      div.appendChild(label);
      div.appendChild(val);
      return div;
    }

    wrapper.appendChild(item("coststate." + summary.cost_state, "", ""));
    wrapper.appendChild(item("cost.net_paid", money(summary.net_paid)));
    if (Number(summary.refunded_total) > 0) {
      wrapper.appendChild(item("cost.refunded", money(summary.refunded_total)));
    }
    wrapper.appendChild(item("cost.records", String(summary.record_count)));
    wrapper.appendChild(item(
      "cost.per_hour",
      summary.cost_per_hour === null ? "—" : money(summary.cost_per_hour)
    ));

    var stateDiv = document.createElement("div");
    stateDiv.className = "ms-auto";
    var stateBadge = document.createElement("span");
    stateBadge.className = "badge " +
      (summary.records_complete ? "text-bg-success" : "text-bg-secondary");
    stateBadge.textContent = t(summary.records_complete ? "cost.complete" : "cost.incomplete");
    stateDiv.appendChild(stateBadge);
    wrapper.appendChild(stateDiv);

    var label = document.createElement("div");
    label.className = "small text-muted mt-1";
    label.textContent = summary.game_name + " · "
      + t("coststate." + summary.cost_state);
    wrapper.appendChild(label);

    panel.appendChild(wrapper);
  }

  function refreshCost() {
    if (!state.filterGame) {
      qs("cost-panel").innerHTML = "";
      return;
    }
    request("/api/games/" + state.filterGame + "/cost")
      .then(renderCost)
      .catch(function () { qs("cost-panel").innerHTML = ""; });
  }

  function refresh() {
    loadGames().then(loadPurchases).then(refreshCost).catch(function (err) {
      toast(t("msg.error") + ": " + err.message, true);
    });
  }

  function openEditor(item) {
    state.editingId = item ? item.purchase_id : null;
    qs("purchase-modal-title").textContent = t(
      item ? "purchases.edit_title" : "purchases.add_title"
    );
    if (item) {
      qs("p-game").value = String(item.game_id);
    } else if (state.filterGame) {
      qs("p-game").value = String(state.filterGame);
    }
    qs("p-game").disabled = Boolean(item);
    qs("p-date").value = item && item.purchase_date ? item.purchase_date : "";
    qs("p-amount").value = item ? item.paid_amount : "";
    qs("p-type").value = item ? item.purchase_type : "base";
    qs("p-status").value = item ? item.status : "paid";
    qs("p-notes").value = item && item.notes ? item.notes : "";
    qs("p-records").checked = false;
    qs("p-records").closest(".form-check").classList.toggle("d-none", Boolean(item));
    qs("purchase-error").classList.add("d-none");
    bootstrap.Modal.getOrCreateInstance(qs("purchase-modal")).show();
  }

  function save() {
    var payload = {
      game_id: parseInt(qs("p-game").value, 10),
      purchase_date: qs("p-date").value || null,
      paid_amount: qs("p-amount").value,
      purchase_type: qs("p-type").value,
      status: qs("p-status").value,
      notes: qs("p-notes").value.trim() || null
    };
    var isEdit = state.editingId !== null;
    var url = isEdit ? "/api/purchases/" + state.editingId : "/api/purchases";

    request(url, {
      method: isEdit ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function () {
        if (!isEdit && qs("p-records").checked) {
          return request("/api/games/" + payload.game_id, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ purchase_records_complete: true })
          });
        }
        return null;
      })
      .then(function () {
        bootstrap.Modal.getOrCreateInstance(qs("purchase-modal")).hide();
        toast(t(isEdit ? "msg.purchase_updated" : "msg.purchase_created"), false);
        refresh();
      })
      .catch(function (err) {
        var box = qs("purchase-error");
        box.textContent = err.message;
        box.classList.remove("d-none");
      });
  }

  function remove(item) {
    if (!window.confirm(t("msg.confirm_purchase"))) {
      return;
    }
    request("/api/purchases/" + item.purchase_id, { method: "DELETE" })
      .then(function () {
        toast(t("msg.purchase_deleted"), false);
        refresh();
      })
      .catch(function (err) {
        toast(t("msg.error") + ": " + err.message, true);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    qs("game-select").addEventListener("change", function () {
      state.filterGame = qs("game-select").value || null;
      loadPurchases().then(refreshCost);
    });
    qs("add-purchase").addEventListener("click", function () { openEditor(null); });
    qs("purchase-save").addEventListener("click", save);
    document.addEventListener("languagechange", refresh);
    refresh();
  });
})();
