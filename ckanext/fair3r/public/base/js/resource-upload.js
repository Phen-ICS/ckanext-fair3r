/**
 * Loading overlay on the "add/edit resource" form (Finish / Save & add
 * another) — uploading a resource can take a while with zero feedback
 * otherwise, which reads as a frozen page and invites repeat clicks.
 *
 * Loaded directly (not through the fair3r-js webassets bundle, which is
 * only included on the FDF dataset-metadata pages) via a plain <script>
 * tag in templates/base.html <head>, the same way fair3r.css is linked
 * directly on every page — so this runs everywhere, and just no-ops on
 * pages that don't have a #resource-edit form.
 *
 * Deliberately does not reference jQuery until DOMContentLoaded: this tag
 * sits in <head>, executing before CKAN's own <script> tags (jQuery
 * included) further down the page — by DOMContentLoaded time, though,
 * every synchronous script the browser parsed before it has already run,
 * jQuery included.
 */
document.addEventListener("DOMContentLoaded", function () {
  "use strict";

  var $ = window.jQuery;
  if (!$) {
    return;
  }

  var $form = $("#resource-edit");
  if (!$form.length) {
    return;
  }

  $form.on("submit", function () {
    if ($(".fair3r-upload-overlay").length) {
      return;
    }
    var translate = (window.ckan && ckan.i18n && ckan.i18n._) || function (s) { return s; };
    $("<div>", { "class": "fair3r-upload-overlay" })
      .append($("<div>", { "class": "spinner" }))
      .append($("<div>", { "class": "fair3r-upload-overlay-text" }).text(translate("Uploading…")))
      .appendTo("body");
  });
});
