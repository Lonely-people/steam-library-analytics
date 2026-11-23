/*
 * Bilingual dictionary (zh-CN default, en fallback chain: en -> zh-CN -> key).
 *
 * Every user-visible string added to a template or script must have both
 * languages here. The chosen language is persisted in localStorage.
 */
(function () {
  "use strict";

  var DICT = {
    "zh-CN": {
      "app.title": "Steam 个人游戏库与游玩成本分析",
      "nav.library": "游戏库",
      "nav.dashboard": "总览",
      "nav.purchases": "购买记录",
      "nav.analytics": "统计分析",
      "lang.switch": "English",

      "library.title": "游戏库",
      "library.search": "搜索游戏名称",
      "library.search_btn": "搜索",
      "library.reset": "重置",
      "library.add": "手动添加游戏",
      "library.sync": "同步 Steam",
      "library.syncing": "同步中…",
      "library.filter.source": "来源",
      "library.filter.acquisition": "获取方式",
      "library.filter.completion": "通关状态",
      "library.filter.include_hidden": "包含已隐藏",
      "library.any": "全部",

      "col.name": "游戏",
      "col.minutes": "游玩时长",
      "col.acquisition": "获取方式",
      "col.completion": "通关状态",
      "col.progress": "进度",
      "col.purchases": "购买记录",
      "col.actions": "操作",
      "col.source": "来源",

      "btn.edit": "编辑",
      "btn.hide": "隐藏",
      "btn.unhide": "取消隐藏",
      "btn.delete": "删除",
      "btn.save": "保存",
      "btn.cancel": "取消",
      "btn.confirm": "确认",

      "form.name": "游戏名称",
      "form.developer": "开发商",
      "form.acquisition": "获取方式",
      "form.completion": "通关状态",
      "form.progress": "完成进度（%）",
      "form.records_complete": "购买记录已完整",
      "form.hidden": "隐藏",
      "form.add_title": "手动添加游戏",
      "form.edit_title": "编辑游戏",

      "status.unknown": "未知",
      "status.paid": "付费",
      "status.free_to_play": "永久免费",
      "status.free_claimed": "免费领取",
      "status.gift": "礼物",

      "completion.unknown": "未知",
      "completion.playing": "游玩中",
      "completion.completed": "已通关",
      "completion.abandoned": "已弃坑",
      "completion.not_applicable": "不适用",

      "source.steam": "Steam",
      "source.manual": "手动",

      "msg.loading": "加载中…",
      "msg.empty": "没有符合条件的游戏",
      "msg.created": "游戏已添加",
      "msg.updated": "游戏已更新",
      "msg.hidden": "游戏已隐藏",
      "msg.unhidden": "游戏已取消隐藏",
      "msg.deleted": "游戏已删除",
      "msg.sync_ok": "同步完成",
      "msg.sync_fail": "同步失败",
      "msg.confirm_delete": "确定删除这个手动游戏吗？其购买记录也会一并删除。",
      "msg.error": "操作失败",
      "msg.cancel": "已取消",
      "msg.no_purchase": "0 条",

      "unit.minutes": "分钟",
      "unit.hours": "小时",
      "total": "共 {n} 款",

      "purchases.title": "购买记录",
      "purchases.select_game": "选择游戏",
      "purchases.all_games": "全部游戏",
      "purchases.add": "新增购买记录",
      "purchases.add_title": "新增购买记录",
      "purchases.edit_title": "编辑购买记录",
      "purchases.empty": "暂无购买记录",
      "purchases.hint_unknown": "没有购买记录并不代表免费。请确认消费记录是否完整。",

      "pcol.game": "游戏",
      "pcol.date": "购买日期",
      "pcol.amount": "金额（CNY）",
      "pcol.type": "类型",
      "pcol.status": "状态",
      "pcol.notes": "备注",
      "pcol.actions": "操作",

      "ptype.base": "基础游戏",
      "ptype.dlc": "DLC",
      "pstatus.paid": "已支付",
      "pstatus.refunded": "已退款",

      "form.purchase_date": "购买日期",
      "form.paid_amount": "支付金额（CNY）",
      "form.purchase_type": "类型",
      "form.purchase_status": "状态",
      "form.notes": "备注",
      "form.records_hint": "勾选后，该游戏视为消费记录完整，才会进入成本统计。",

      "cost.title": "消费概况",
      "cost.net_paid": "净支出",
      "cost.refunded": "已退款",
      "cost.records": "记录数",
      "cost.state": "消费状态",
      "cost.per_hour": "每小时成本",
      "cost.incomplete": "消费记录不完整",
      "cost.complete": "消费记录完整",

      "coststate.unknown": "消费未知",
      "coststate.free": "零成本",
      "coststate.paid": "已付费",
      "coststate.none": "未标记",

      "msg.purchase_created": "购买记录已添加",
      "msg.purchase_updated": "购买记录已更新",
      "msg.purchase_deleted": "购买记录已删除",
      "msg.confirm_purchase": "确定删除这条购买记录吗？",
      "msg.select_game_first": "请先选择一款游戏",
      "msg.save_incomplete": "消费记录已标记为完整",
      "msg.save_incomplete_off": "消费记录已标记为不完整",
      "msg.mark_complete": "标记消费记录完整",
      "msg.mark_incomplete": "标记为不完整"
    },
    "en": {
      "app.title": "Steam Library & Play-Cost Analysis",
      "nav.library": "Library",
      "nav.dashboard": "Dashboard",
      "nav.purchases": "Purchases",
      "nav.analytics": "Analytics",
      "lang.switch": "中文",

      "library.title": "Library",
      "library.search": "Search games",
      "library.search_btn": "Search",
      "library.reset": "Reset",
      "library.add": "Add game",
      "library.sync": "Sync Steam",
      "library.syncing": "Syncing…",
      "library.filter.source": "Source",
      "library.filter.acquisition": "Acquired via",
      "library.filter.completion": "Completion",
      "library.filter.include_hidden": "Include hidden",
      "library.any": "Any",

      "col.name": "Game",
      "col.minutes": "Playtime",
      "col.acquisition": "Acquired",
      "col.completion": "Completion",
      "col.progress": "Progress",
      "col.purchases": "Purchases",
      "col.actions": "Actions",
      "col.source": "Source",

      "btn.edit": "Edit",
      "btn.hide": "Hide",
      "btn.unhide": "Unhide",
      "btn.delete": "Delete",
      "btn.save": "Save",
      "btn.cancel": "Cancel",
      "btn.confirm": "Confirm",

      "form.name": "Game name",
      "form.developer": "Developer",
      "form.acquisition": "Acquired via",
      "form.completion": "Completion",
      "form.progress": "Progress (%)",
      "form.records_complete": "Purchase records complete",
      "form.hidden": "Hidden",
      "form.add_title": "Add a game manually",
      "form.edit_title": "Edit game",

      "status.unknown": "Unknown",
      "status.paid": "Paid",
      "status.free_to_play": "Free to play",
      "status.free_claimed": "Claimed free",
      "status.gift": "Gift",

      "completion.unknown": "Unknown",
      "completion.playing": "Playing",
      "completion.completed": "Completed",
      "completion.abandoned": "Abandoned",
      "completion.not_applicable": "Not applicable",

      "source.steam": "Steam",
      "source.manual": "Manual",

      "msg.loading": "Loading…",
      "msg.empty": "No games match the filters",
      "msg.created": "Game added",
      "msg.updated": "Game updated",
      "msg.hidden": "Game hidden",
      "msg.unhidden": "Game unhidden",
      "msg.deleted": "Game deleted",
      "msg.sync_ok": "Sync finished",
      "msg.sync_fail": "Sync failed",
      "msg.confirm_delete": "Delete this manual game? Its purchase records are deleted too.",
      "msg.error": "Operation failed",
      "msg.cancel": "Cancelled",
      "msg.no_purchase": "0",
      "unit.minutes": "min",
      "unit.hours": "h",
      "total": "{n} games",

      "purchases.title": "Purchases",
      "purchases.select_game": "Select a game",
      "purchases.all_games": "All games",
      "purchases.add": "Add purchase",
      "purchases.add_title": "Add a purchase record",
      "purchases.edit_title": "Edit purchase record",
      "purchases.empty": "No purchase records",
      "purchases.hint_unknown": "No records does not mean free. Confirm whether the cost data is complete.",

      "pcol.game": "Game",
      "pcol.date": "Purchase date",
      "pcol.amount": "Amount (CNY)",
      "pcol.type": "Type",
      "pcol.status": "Status",
      "pcol.notes": "Notes",
      "pcol.actions": "Actions",

      "ptype.base": "Base game",
      "ptype.dlc": "DLC",
      "pstatus.paid": "Paid",
      "pstatus.refunded": "Refunded",

      "form.purchase_date": "Purchase date",
      "form.paid_amount": "Amount paid (CNY)",
      "form.purchase_type": "Type",
      "form.purchase_status": "Status",
      "form.notes": "Notes",
      "form.records_hint": "When checked, this game's cost data counts as complete and enters cost statistics.",

      "cost.title": "Cost summary",
      "cost.net_paid": "Net paid",
      "cost.refunded": "Refunded",
      "cost.records": "Records",
      "cost.state": "Cost state",
      "cost.per_hour": "Cost per hour",
      "cost.incomplete": "Cost data incomplete",
      "cost.complete": "Cost data complete",

      "coststate.unknown": "Cost unknown",
      "coststate.free": "Zero cost",
      "coststate.paid": "Paid",
      "coststate.none": "Not marked",

      "msg.purchase_created": "Purchase added",
      "msg.purchase_updated": "Purchase updated",
      "msg.purchase_deleted": "Purchase deleted",
      "msg.confirm_purchase": "Delete this purchase record?",
      "msg.select_game_first": "Select a game first",
      "msg.save_incomplete": "Cost data marked complete",
      "msg.save_incomplete_off": "Cost data marked incomplete",
      "msg.mark_complete": "Mark cost data complete",
      "msg.mark_incomplete": "Mark incomplete"
    }
  };

  var STORAGE_KEY = "steam_library_lang";
  var DEFAULT_LANG = "zh-CN";
  var FALLBACK = "zh-CN";

  function getLang() {
    var saved = null;
    try {
      saved = localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      saved = null;
    }
    return DICT[saved] ? saved : DEFAULT_LANG;
  }

  function setLang(lang) {
    if (!DICT[lang]) {
      return;
    }
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch (e) {
      /* storage unavailable: language only lives for this page */
    }
    document.documentElement.lang = lang;
    apply();
    document.dispatchEvent(new CustomEvent("languagechange", { detail: { lang: lang } }));
  }

  function t(key, vars) {
    var lang = getLang();
    var value = (DICT[lang] && DICT[lang][key]);
    if (value === undefined) {
      value = DICT[FALLBACK][key];
    }
    if (value === undefined) {
      return key;
    }
    if (vars) {
      Object.keys(vars).forEach(function (name) {
        value = value.replace(new RegExp("\\{" + name + "\\}", "g"), vars[name]);
      });
    }
    return value;
  }

  function apply(root) {
    var scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    scope.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    scope.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply();
    var toggle = document.getElementById("lang-toggle");
    if (toggle) {
      toggle.addEventListener("click", function (event) {
        event.preventDefault();
        setLang(getLang() === "zh-CN" ? "en" : "zh-CN");
        var label = toggle.querySelector("[data-i18n]");
        if (label) {
          label.setAttribute("data-i18n", "lang.switch");
        }
        apply();
      });
    }
  });

  window.i18n = {
    t: t,
    apply: apply,
    getLang: getLang,
    setLang: setLang
  };
})();
