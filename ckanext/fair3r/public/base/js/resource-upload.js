/**
 * "Add/edit resource" form (Finish / Save & add another) UX helpers:
 *
 * 1. Loading overlay on submit, with a real per-file progress bar — one
 *    file or several are both driven through the CKAN API (resource_create)
 *    via XMLHttpRequest rather than a native form POST, since that's the
 *    only way to get upload-progress events (fetch() has none) and to
 *    upload more than one file from a form that only has a single "upload"
 *    field. Only a resource with no file at all (URL-type, or nothing
 *    selected) still submits natively — there's no byte progress to show
 *    for that anyway.
 *
 * 2. Bulk upload — selecting more than one file turns the single-resource
 *    form into a batch: each file becomes its own resource, named after
 *    itself (same as CKAN's own resource-upload-field.js does for a single
 *    file — full filename, extension included, only when the Name field
 *    hasn't been hand-edited), sharing whatever Description was typed.
 *    Format can't sensibly apply to every file at once, so it's disabled
 *    and left for CKAN to auto-guess per file, same as leaving it blank
 *    normally does. Every file's outcome (✓/✗ with error) is listed as it
 *    finishes, not just in a summary at the end; on any failure the
 *    overlay stays put (a "Close" button, not "Continue") so the page and
 *    its field values aren't lost before retrying.
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

  // CKAN's own i18n never actually gets a translation catalog loaded in
  // this deployment (ckan.i18n.load() is never called), so ckan.i18n._
  // and this fallback both just interpolate %(key)s/%(key)d placeholders
  // without changing language — kept for consistency with the rest of the
  // codebase and in case that ever gets wired up.
  var translate = (window.ckan && ckan.i18n && ckan.i18n._) || function (s, values) {
    if (!values) {
      return s;
    }
    return s.replace(/%\((\w+)\)[ds]/g, function (match, key) {
      return Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : match;
    });
  };

  function csrfFieldName() {
    return $('meta[name="csrf_field_name"]').attr("content") || null;
  }

  function csrfHeaderToken() {
    var fieldName = csrfFieldName();
    return fieldName ? $('meta[name="' + fieldName + '"]').attr("content") : null;
  }

  // ----- Simple overlay: single/no-file case, unchanged from before -----

  function showSimpleOverlay(text) {
    var $overlay = $(".fair3r-upload-overlay");
    if (!$overlay.length) {
      $overlay = $("<div>", { "class": "fair3r-upload-overlay" })
        .append($("<div>", { "class": "spinner" }))
        .append($("<div>", { "class": "fair3r-upload-overlay-text" }))
        .appendTo("body");
    }
    $overlay.find(".fair3r-upload-overlay-text").text(text);
    return $overlay;
  }

  // ----- Rich overlay: bulk mode, live per-file progress + result list -----

  function buildBulkOverlay() {
    var $overlay = $("<div>", { "class": "fair3r-upload-overlay fair3r-upload-overlay-bulk" });
    var $title = $("<div>", { "class": "fair3r-upload-overlay-title" });
    var $currentName = $("<div>", { "class": "fair3r-upload-current-name" });
    var $bar = $("<div>", { "class": "fair3r-upload-progress-bar" });
    var $track = $("<div>", { "class": "fair3r-upload-progress-track" }).append($bar);
    var $pct = $("<div>", { "class": "fair3r-upload-current-pct" });
    var $current = $("<div>", { "class": "fair3r-upload-current" }).append($currentName, $track, $pct);
    var $list = $("<ul>", { "class": "fair3r-upload-status-list" });

    $overlay.append($title, $current, $list).appendTo("body");

    return {
      setTitle: function (text) {
        $title.text(text);
      },
      setCurrent: function (name, pct) {
        $currentName.text(name);
        $bar.css("width", pct + "%");
        $pct.text(pct + "%");
      },
      addResult: function (ok, name, errorMessage) {
        var label = (ok ? "✓ " : "✗ ") + name + (errorMessage ? " — " + errorMessage : "");
        $("<li>", { "class": ok ? "ok" : "error" }).text(label).appendTo($list);
        $list.scrollTop($list.get(0).scrollHeight);
      },
      finish: function (label, onClick) {
        $current.remove();
        $("<button>", { "class": "btn btn-primary fair3r-upload-continue-btn", type: "button" })
          .text(label)
          .on("click", onClick)
          .appendTo($overlay);
      },
      // Swaps back to a plain spinner (same markup/CSS as the single-file
      // overlay) for the gap between the batch finishing and the browser
      // actually finishing navigation to the next page. Deliberately does
      // NOT remove the overlay first: navigation isn't instant, and doing
      // so left the just-finished "add resource" page briefly clickable
      // underneath while the next page was still loading.
      showLoading: function (text) {
        $overlay.empty();
        $overlay.append($("<div>", { "class": "spinner" }));
        $overlay.append($("<div>", { "class": "fair3r-upload-overlay-text" }).text(text));
      },
      remove: function () {
        $overlay.remove();
      }
    };
  }

  // ----- Bulk-mode form UI: disable per-file-meaningless fields, show a hint -----

  var $formatInput = $("#field-format");
  var $nameInput = $("#field-name");
  var $bulkHint = null;

  // CKAN's own "Remove" button for the upload field replaces
  // #field-resource-upload with a clone (see resource_upload_field.html:
  // `$('#field-resource-upload').replaceWith($('#field-resource-upload')
  // .val('').clone(true))`). A jQuery object captured once at load time
  // would then point at a detached, stale node. Delegating from the
  // (never-replaced) form instead means every lookup below always resolves
  // against whatever upload input is actually in the page right now.
  $("#field-resource-upload").attr("multiple", "multiple");

  $form.on("change", "#field-resource-upload", function () {
    // Re-applied here too: the clone already carries the attribute over
    // (plain attributes always survive .clone()), but this stays correct
    // even if that behavior ever changes.
    this.multiple = true;

    var files = this.files || [];
    var isBulk = files.length > 1;

    if ($formatInput.length) {
      $formatInput.prop("disabled", isBulk);
    }
    if ($nameInput.length) {
      $nameInput.prop("disabled", isBulk);
    }

    if (!$bulkHint) {
      $bulkHint = $("<div>", { "class": "fair3r-bulk-upload-hint" }).insertAfter(this);
    }

    if (isBulk) {
      $bulkHint.text(translate(
        "%(count)d files selected — each will become its own resource, named after its file. Format is auto-detected per file.",
        { count: files.length }
      )).show();
    } else {
      $bulkHint.hide();
    }
  });

  // ----- Submit handling -----

  function packageNameFromAction() {
    var action = $form.attr("action") || "";
    var match = action.match(/\/([^\/]+)\/resource\/new\/?(?:\?.*)?$/);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function packageReadUrl() {
    var action = $form.attr("action") || "";
    return action.replace(/\/resource\/new\/?(?:\?.*)?$/, "");
  }

  function extractErrorMessage(payload) {
    if (!payload || !payload.error) {
      return null;
    }
    var err = payload.error;
    if (typeof err.message === "string") {
      return err.message;
    }
    var parts = [];
    Object.keys(err).forEach(function (key) {
      if (key === "__type") {
        return;
      }
      var value = err[key];
      if (Array.isArray(value)) {
        parts.push(key + ": " + value.join(", "));
      } else if (typeof value === "string") {
        parts.push(key + ": " + value);
      }
    });
    return parts.length ? parts.join("; ") : null;
  }

  // XMLHttpRequest rather than fetch(): fetch has no upload-progress event,
  // XHR's xhr.upload "progress" event is the only cross-browser way to get
  // real byte-level percentage for a request body still being sent.
  //
  // `overrideName`: only for bulk (>1 files) — each gets its own resource,
  // so the shared Name field can't apply to all of them and is disabled;
  // this fills in the same value CKAN's own resource-upload-field.js would
  // for a single upload with an empty Name field (full filename, extension
  // included). For exactly one file, the Name field stays enabled and
  // whatever's currently in it (auto-filled by that same CKAN script, or
  // hand-edited) is left untouched — already correctly captured by cloning
  // the live form below.
  function createOneResource(file, packageName, onProgress, overrideName) {
    return new Promise(function (resolve) {
      var fd = new FormData($form.get(0));
      // The multi-file input puts every selected file under "upload"; keep
      // only the one this call is responsible for.
      fd.delete("upload");
      fd.append("upload", file, file.name);
      if (overrideName) {
        fd.set("name", file.name);
      }
      fd.set("package_id", packageName);
      // Cloned from the form as a hidden field, but resource_create's
      // schema doesn't recognize it and would otherwise store it as a
      // stray "extra" on every resource created this way. Sent as a
      // header instead (same as the package_patch call below).
      var fieldName = csrfFieldName();
      if (fieldName) {
        fd.delete(fieldName);
      }

      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/3/action/resource_create", true);
      xhr.withCredentials = true;
      var csrfToken = csrfHeaderToken();
      if (csrfToken) {
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
      }

      xhr.upload.addEventListener("progress", function (e) {
        if (e.lengthComputable && typeof onProgress === "function") {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });

      xhr.onload = function () {
        var payload = null;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch (e) {
          payload = null;
        }
        var ok = xhr.status >= 200 && xhr.status < 300 && !!(payload && payload.success);
        resolve({
          ok: ok,
          file: file,
          errorMessage: ok ? null : (extractErrorMessage(payload) || xhr.statusText || translate("Upload failed"))
        });
      };

      xhr.onerror = function () {
        resolve({ ok: false, file: file, errorMessage: translate("Network error") });
      };

      xhr.send(fd);
    });
  }

  function activateDraftDataset(packageName) {
    var token = csrfHeaderToken();
    var headers = { "Content-Type": "application/json" };
    if (token) {
      headers["X-CSRFToken"] = token;
    }
    return fetch("/api/3/action/package_patch", {
      method: "POST",
      credentials: "same-origin",
      headers: headers,
      body: JSON.stringify({ id: packageName, state: "active" })
    });
  }

  $form.on("submit", function (event) {
    var submitter = event.originalEvent && event.originalEvent.submitter;
    var saveValue = submitter ? submitter.value : null;

    // "Previous" (staged flow, going back to the dataset metadata step):
    // nothing to do with selected files either way, let it submit as-is.
    if (saveValue === "go-dataset") {
      return;
    }

    // Fresh lookup, not a cached reference: see the comment above the
    // "change" delegation for why (the "Remove" button can replace this
    // element with a clone at any time).
    var $currentFileInput = $("#field-resource-upload");
    var files = $currentFileInput.length ? ($currentFileInput.get(0).files || []) : [];

    if (files.length === 0) {
      // Nothing to upload (URL-type resource, or no file chosen): nothing
      // for us to track progress on — let the browser submit the form
      // natively, just show the plain overlay on top while it does.
      if (!$(".fair3r-upload-overlay").length) {
        showSimpleOverlay(translate("Uploading…"));
      }
      return;
    }

    // One file or many: both go through the same API-driven path so a
    // single upload gets the same live progress bar as a batch does.
    event.preventDefault();

    var packageName = packageNameFromAction();
    if (!packageName) {
      // Unexpected page structure. Never fall back to a native submit()
      // when there's more than one file: the form only supports a single
      // "upload" field, and the browser would otherwise send all of them
      // at once, which CKAN's resource_create view can't handle (raises
      // 500 trying to unflatten a repeated file field).
      window.alert(translate(
        "Couldn't determine which dataset to upload to — please reload the page and try again."
      ));
      return;
    }

    var fileArray = Array.prototype.slice.call(files);
    var total = fileArray.length;
    var isBulk = total > 1;
    var failureCount = 0;
    var overlay = buildBulkOverlay();
    overlay.setCurrent(fileArray[0].name, 0);

    var chain = Promise.resolve();
    fileArray.forEach(function (file, index) {
      chain = chain.then(function () {
        overlay.setTitle(isBulk
          ? translate("Uploading %(current)d / %(total)d files", { current: index + 1, total: total })
          : translate("Uploading…"));
        overlay.setCurrent(file.name, 0);
        return createOneResource(file, packageName, function (pct) {
          overlay.setCurrent(file.name, pct);
        }, isBulk).then(function (result) {
          overlay.addResult(result.ok, file.name, result.errorMessage);
          if (!result.ok) {
            failureCount += 1;
          }
        });
      });
    });

    chain.then(function () {
      var successCount = total - failureCount;
      overlay.setTitle(failureCount
        ? translate("Done — %(ok)d / %(total)d uploaded, %(failed)d failed", { ok: successCount, total: total, failed: failureCount })
        : translate("Done — %(total)d / %(total)d uploaded", { total: total }));

      function goToNextStep() {
        // Show the spinner immediately, covering the whole remaining
        // window (finalize call + actual page navigation) — no
        // overlay.remove() here; the browser replaces this entire page
        // once the next one has loaded, so there's nothing to clean up
        // and no gap where the finished page is briefly clickable again.
        overlay.showLoading(translate("Loading…"));

        var redirectUrl = packageReadUrl();
        var finalize = (saveValue === "go-metadata")
          ? activateDraftDataset(packageName).catch(function () { /* best effort */ })
          : Promise.resolve();

        finalize.then(function () {
          if (saveValue === "again") {
            window.location.reload();
          } else {
            window.location.href = redirectUrl;
          }
        });
      }

      if (failureCount > 0) {
        // Don't navigate away on failure: the form's fields (description,
        // any files that failed) are still right there to fix and retry,
        // and navigating would lose that state for no benefit — the
        // successful uploads in this batch, if any, are already saved
        // regardless of what the user does next.
        overlay.finish(translate("Close"), function () {
          overlay.remove();
        });
      } else {
        overlay.finish(translate("Continue"), goToNextStep);
      }
    });
  });
});
