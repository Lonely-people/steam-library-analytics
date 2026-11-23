/* Library page behaviour: fetch, filter, create, edit, hide, delete. */
(function () {
  "use strict";

  var state = { limit: 20, offset: 0, total: 0, filters: {} };
  var editingId = null;

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
    el.setAttribute("role", "alert");
    el.innerHTML =
      '<div class="d-flex"><div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" ' +
      'data-bs-dismiss="toast"></button></div>';
    el.querySelector(".toast-body").textContent = message;
    box.appendChild(el);
    var instance = new bootstrap.Toast(el, { delay: 3000 });
    instance.show();
    el.addEventListener("hidden.bs.toast", function () {
      el.remove();
    });
  }

  function request(url, options) {
    return fetch(url, options).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (body) {
        if (!response.ok) {
          var message = body && body.error ? body.error : ("HTTP " + response.status);
          throw new Error(message);
        }
        return body;
      });
    });
  }

  function readFilters() {
    state.filters = {
      search: qs("filter-search").value.trim(),
      source: qs("filter-source").value,
      acquisition_type: qs("filter-acquisition").value,
      completion_status: qs("filter-completion").value,
      include_hidden: qs("filter-hidden").checked ? "true" : ""
    };
  }

  function buildQuery() {
    var params = new URLSearchParams();
    Object.keys(state.filters).forEach(function (key) {
      if (state.filters[key]) {
        params.set(key, state.filters[key]);
      }
    });
    params.set("limit", String(state.limit));
    params.set("offset", String(state.offset));
    return params.toString();
  }

  function minutesLabel(minutes) {
    if (minutes < 60) {
      return minutes + " " + t("unit.minutes");
    }
    return (minutes / 60).toFixed(1) + " " + t("unit.hours");
  }

  function statusBadge(value, prefix) {
    var span = document.createElement("span");
    var tone = {
      paid: "text-bg-primary",
      free_to_play: "text-bg-success",
      free_claimed: "text-bg-info",
      gift: "text-bg-warning",
      unknown: "text-bg-secondary",
      playing: "text-bg-info",
      completed: "text-bg-success",
      abandoned: "text-bg-danger",
      not_applicable: "text-bg-secondary"
    }[value] || "text-bg-secondary";
    span.className = "badge " + tone;
    span.textContent = t(prefix + "." + value);
    return span;
  }

  function cell(text) {
    var td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  function actionButton(label, className, handler) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-sm " + className + " me-1";
    button.textContent = label;
    button.addEventListener("click", handler);
    return button;
  }

  function renderRow(game) {
    var tr = document.createElement("tr");

    var nameCell = document.createElement("td");
    var title = document.createElement("div");
    title.textContent = game.game_name;
    nameCell.appendChild(title);
    var meta = document.createElement("small");
    meta.className = "text-muted";
    var parts = [t("source." + game.source)];
    if (game.steam_appid) {
      parts.push("AppID " + game.steam_appid);
    }
    meta.textContent = parts.join(" · ");
    nameCell.appendChild(meta);
    if (game.is_hidden) {
      var hidden = document.createElement("span");
      hidden.className = "badge text-bg-dark ms-2";
      hidden.textContent = t("form.hidden");
      nameCell.appendChild(hidden);
    }
    tr.appendChild(nameCell);

    tr.appendChild(cell(minutesLabel(game.play_minutes)));

    var acq = document.createElement("td");
    acq.appendChild(statusBadge(game.acquisition_type, "status"));
    tr.appendChild(acq);

    var completion = document.createElement("td");
    completion.appendChild(statusBadge(game.completion_status, "completion"));
    tr.appendChild(completion);

    tr.appendChild(cell(game.progress_percent === null ? "—" : game.progress_percent + "%"));
    tr.appendChild(cell(game.purchase_count === 0 ? t("msg.no_purchase") : String(game.purchase_count)));

    var actions = document.createElement("td");
    actions.className = "text-nowrap";
    actions.appendChild(actionButton(t("btn.edit"), "btn-outline-primary", function () {
      openEditor(game);
    }));
    if (game.source === "steam" || game.is_hidden) {
      actions.appendChild(actionButton(
        game.is_hidden ? t("btn.unhide") : t("btn.hide"),
        "btn-outline-secondary",
        function () { setHidden(game, !game.is_hidden); }
      ));
    }
    if (game.source === "manual") {
      actions.appendChild(actionButton(t("btn.delete"), "btn-outline-danger", function () {
        removeGame(game);
      }));
    }
    tr.appendChild(actions);
    return tr;
  }

  function renderList(body) {
    var tbody = qs("games-body");
    tbody.innerHTML = "";
    if (!body.items.length) {
      var row = document.createElement("tr");
      var td = document.createElement("td");
      td.colSpan = 8;
      td.className = "text-center text-muted py-4";
      td.textContent = t("msg.empty");
      row.appendChild(td);
      tbody.appendChild(row);
    } else {
      body.items.forEach(function (game) {
        tbody.appendChild(renderRow(game));
      });
    }
    state.total = body.total;
    qs("total-count").textContent = t("total", { n: body.total });
    renderPager();
  }

  function renderPager() {
    var page = Math.floor(state.offset / state.limit) + 1;
    var pages = Math.max(1, Math.ceil(state.total / state.limit));
    qs("page-info").textContent = page + " / " + pages;
    qs("prev-page").disabled = state.offset <= 0;
    qs("next-page").disabled = state.offset + state.limit >= state.total;
  }

  function load() {
    readFilters();
    qs("loading").classList.remove("d-none");
    request("/api/games?" + buildQuery())
      .then(function (body) {
        renderList(body);
      })
      .catch(function (err) {
        toast(t("msg.error") + ": " + err.message, true);
      })
      .finally(function () {
        qs("loading").classList.add("d-none");
      });
  }

  function openEditor(game) {
    editingId = game ? game.game_id : null;
    qs("editor-title").textContent = game ? t("form.edit_title") : t("form.add_title");
    qs("field-name").value = game ? game.game_name : "";
    qs("field-developer").value = game && game.developer ? game.developer : "";
    qs("field-acquisition").value = game ? game.acquisition_type : "unknown";
    qs("field-completion").value = game ? game.completion_status : "unknown";
    qs("field-progress").value =
      game && game.progress_percent !== null ? game.progress_percent : "";
    qs("field-records").checked = game ? game.purchase_records_complete : false;
    qs("field-hidden").checked = game ? game.is_hidden : false;
    qs("field-hidden").closest(".form-check").classList.toggle("d-none", !game);
    qs("editor-error").classList.add("d-none");
    var modal = bootstrap.Modal.getOrCreateInstance(qs("editor-modal"));
    modal.show();
  }

  function submitEditor() {
    var payload = {
      game_name: qs("field-name").value.trim(),
      developer: qs("field-developer").value.trim() || null,
      acquisition_type: qs("field-acquisition").value,
      completion_status: qs("field-completion").value,
      progress_percent: qs("field-progress").value === ""
        ? null
        : parseInt(qs("field-progress").value, 10),
      purchase_records_complete: qs("field-records").checked,
      is_hidden: qs("field-hidden").checked
    };
    var isEdit = editingId !== null;
    var url = isEdit ? "/api/games/" + editingId : "/api/games";
    var options = {
      method: isEdit ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    };

    request(url, options)
      .then(function () {
        bootstrap.Modal.getOrCreateInstance(qs("editor-modal")).hide();
        toast(t(isEdit ? "msg.updated" : "msg.created"), false);
        load();
      })
      .catch(function (err) {
        var box = qs("editor-error");
        box.textContent = err.message;
        box.classList.remove("d-none");
      });
  }

  function setHidden(game, hidden) {
    request("/api/games/" + game.game_id, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_hidden: hidden })
    })
      .then(function () {
        toast(t(hidden ? "msg.hidden" : "msg.unhidden"), false);
        load();
      })
      .catch(function (err) {
        toast(t("msg.error") + ": " + err.message, true);
      });
  }

  function removeGame(game) {
    if (!window.confirm(t("msg.confirm_delete"))) {
      return;
    }
    request("/api/games/" + game.game_id + "?force=true", { method: "DELETE" })
      .then(function () {
        toast(t("msg.deleted"), false);
        load();
      })
      .catch(function (err) {
        toast(t("msg.error") + ": " + err.message, true);
      });
  }

  function sync() {
    var button = qs("sync-button");
    button.disabled = true;
    button.textContent = t("library.syncing");
    request("/api/steam/sync", { method: "POST" })
      .then(function (body) {
        toast(t("msg.sync_ok") + " (" + body.fetched_count + ")", false);
        load();
      })
      .catch(function (err) {
        toast(t("msg.sync_fail") + ": " + err.message, true);
      })
      .finally(function () {
        button.disabled = false;
        button.textContent = t("library.sync");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    qs("search-form").addEventListener("submit", function (event) {
      event.preventDefault();
      state.offset = 0;
      load();
    });
    qs("reset-button").addEventListener("click", function () {
      qs("filter-search").value = "";
      qs("filter-source").value = "";
      qs("filter-acquisition").value = "";
      qs("filter-completion").value = "";
      qs("filter-hidden").checked = false;
      state.offset = 0;
      load();
    });
    ["filter-source", "filter-acquisition", "filter-completion", "filter-hidden"]
      .forEach(function (id) {
        qs(id).addEventListener("change", function () {
          state.offset = 0;
          load();
        });
      });
    qs("add-button").addEventListener("click", function () { openEditor(null); });
    qs("sync-button").addEventListener("click", sync);
    qs("editor-save").addEventListener("click", submitEditor);
    qs("prev-page").addEventListener("click", function () {
      state.offset = Math.max(0, state.offset - state.limit);
      load();
    });
    qs("next-page").addEventListener("click", function () {
      state.offset += state.limit;
      load();
    });
    document.addEventListener("languagechange", function () {
      load();
    });
    load();
  });
})();
