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

  // The <meta> tag only exists when ckanext-zenodo is installed and
  // enabled (see fair3r_zenodo_routing_config() / base.html) - on a
  // deployment without it, this whole feature (checkbox included) simply
  // isn't there, rather than a dead control that would always no-op.
  function zenodoRoutingConfig() {
    var raw = $('meta[name="zenodo-routing-config"]').attr("content");
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  var zenodoConfig = zenodoRoutingConfig();
  // Kept as $forceZenodoCheckbox for the rest of this file (the submit
  // loop below only ever reads its inner <input>'s checked state) - the
  // first version of this (a pill that only changed background colour,
  // with a single "Z" letter as its only branding) tested confusing: no
  // clear on/off affordance, and "Z" alone didn't read as "Zenodo" to
  // anyone not already looking for it. Rebuilt as an actual switch (a
  // sliding track+thumb - the one widget shape everyone already reads as
  // on/off unambiguously) plus a persistent icon+"Zenodo" label that
  // never changes, so what the control is *for* doesn't depend on
  // noticing its current state.
  var $forceZenodoCheckbox = null;
  var $zenodoRoutingHint = null;
  var $zenodoCapacity = null;

  if (zenodoConfig && $("#field-resource-upload").length) {
    $forceZenodoCheckbox = $(
      '<label class="fair3r-zenodo-toggle" for="field-force-zenodo">' +
        // The (visually hidden) <input> comes first, before the brand
        // span - not just before the switch - so CSS's general sibling
        // selector (~, which only ever matches *later* siblings) can
        // also grey out the brand icon+label when off, same as it
        // already does for the switch/state below (see fair3r.css).
        // Its own position:absolute already takes it out of the
        // visible flex flow, so this reorder has no layout effect of
        // its own.
        '<input type="checkbox" id="field-force-zenodo" class="fair3r-zenodo-toggle-input">' +
        '<span class="fair3r-zenodo-toggle-brand">' +
          '<i class="fa fa-archive" aria-hidden="true"></i> Zenodo' +
        '</span>' +
        '<span class="fair3r-zenodo-toggle-switch" aria-hidden="true">' +
          '<span class="fair3r-zenodo-toggle-switch-thumb"></span>' +
        '</span>' +
        '<span class="fair3r-zenodo-toggle-state" aria-hidden="true"></span>' +
        // Placed on the same flex row as the brand/switch/state above
        // (not the full-width text below, which always wraps to its own
        // line) and pushed to the far right of that row by its own
        // margin-left:auto (see fair3r.css) - the toggle is the one spot
        // on this form already dedicated to Zenodo, so a glance to its
        // right is where this is most likely to actually get read,
        // right as the user is about to pick a file.
        '<span class="fair3r-zenodo-capacity" aria-live="polite"></span>' +
        '<span class="fair3r-zenodo-toggle-text"></span>' +
      '</label>'
    ).insertAfter($("#field-resource-upload"));
    var $zenodoToggleState = $forceZenodoCheckbox.find(".fair3r-zenodo-toggle-state");
    var $zenodoToggleText = $forceZenodoCheckbox.find(".fair3r-zenodo-toggle-text");
    $zenodoCapacity = $forceZenodoCheckbox.find(".fair3r-zenodo-capacity");
    var updateZenodoToggleState = function () {
      var on = $forceZenodoCheckbox.find("input").is(":checked");
      $zenodoToggleState.text(on ? translate("On") : translate("Off"));
      // Describes what will actually happen in the current state, not a
      // static "what turning this on does" sentence - so it stays
      // correct and useful even without looking at the switch itself.
      // The *why* (size/format thresholds) is a separate line, always
      // visible, below - see $zenodoRoutingHint/genericZenodoExplanation.
      var baseText = on
        ? translate("Store this file on Zenodo instead of this catalogue")
        : translate("Store this file on this catalogue instead of Zenodo");
      // No space before the colon - a space there lets the browser wrap
      // the line right before it, leaving a lone ":" dangling on its own
      // row when the container is narrow. Safe to add our own now that
      // CKAN's own label:after{content:":"} is suppressed for this
      // label in fair3r.css - it used to double up with this one.
      $zenodoToggleText.text(baseText + ":");
    };
    updateZenodoToggleState();
    $forceZenodoCheckbox.find("input").on("change", updateZenodoToggleState);
    $zenodoRoutingHint = $("<div>", { "class": "fair3r-zenodo-routing-hint" })
      .insertAfter($forceZenodoCheckbox);
    // Shown right away, before any file is even picked - genericZenodoExplanation,
    // updateZenodoRoutingHint and refreshZenodoCapacity are function
    // declarations further down, hoisted, so calling them here is safe.
    updateZenodoRoutingHint(null);
    refreshZenodoCapacity();
  }

  // ----- Live "how big a file could actually go through right now" badge -----
  //
  // Advisory only, never authoritative: disk space can change between
  // this call and the user's actual upload (someone else's upload can
  // start or finish in between), so the real gate stays server-side
  // (disk_guard.reserve() in ckanext-zenodo's /zenodo/upload/ blueprint,
  // which re-checks for real at accept time and rejects with a clear
  // error if it no longer fits). This is purely so the user isn't
  // surprised by that rejection after already waiting through most of a
  // multi-GB upload.
  //
  // The number itself already comes capped by max_file_size_bytes from
  // the server (GET /zenodo/upload-capacity) - raw disk headroom alone
  // would otherwise advertise far more than this plugin will ever
  // actually accept (e.g. hundreds of GB free on a dev machine, when
  // the plugin itself caps any single file well below that regardless).
  // So the color below reads as a fraction *of that cap*, not of disk
  // space in isolation: close to the cap (disk isn't the bottleneck) is
  // green, well under it (disk pressure is actually biting) is red.

  function formatGigabytes(bytes) {
    return (bytes / (1024 * 1024 * 1024)).toFixed(1);
  }

  function updateZenodoCapacityDisplay(availableBytes) {
    if (!$zenodoCapacity || !$zenodoCapacity.length) {
      return;
    }
    $zenodoCapacity.removeClass(
      "fair3r-zenodo-capacity-red fair3r-zenodo-capacity-orange fair3r-zenodo-capacity-green"
    );
    if (availableBytes === null || availableBytes === undefined) {
      // Couldn't fetch it (network hiccup, session expired) - say
      // nothing rather than show a stale or made-up number.
      $zenodoCapacity.text("");
      return;
    }
    var maxFile = zenodoConfig && zenodoConfig.max_file_size_bytes;
    var level = "green";
    if (maxFile) {
      var ratio = availableBytes / maxFile;
      if (ratio < 0.3) {
        // Disk pressure has cut deep into the per-file cap - the next
        // large upload may well be rejected outright.
        level = "red";
      } else if (ratio < 0.9) {
        level = "orange";
      }
    }
    $zenodoCapacity.addClass("fair3r-zenodo-capacity-" + level);
    $zenodoCapacity.text(
      translate("up to %(size)s GB can be uploaded right now", { size: formatGigabytes(availableBytes) })
    );
  }

  function refreshZenodoCapacity() {
    if (!$zenodoCapacity || !$zenodoCapacity.length) {
      return;
    }
    fetch("/zenodo/upload-capacity", { credentials: "same-origin" })
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (payload) {
        updateZenodoCapacityDisplay(
          payload && payload.success ? payload.result.available_bytes : null
        );
      })
      .catch(function () {
        updateZenodoCapacityDisplay(null);
      });
  }

  // The background explanation of *why* a file might end up on Zenodo
  // even with the toggle off - shown by default (before any file is
  // picked, and whenever nothing currently selected actually routes
  // there), computed from the real config rather than hardcoded. Only
  // ever called when not forced - see updateZenodoRoutingHint below for
  // why there's no "forced" version of this to show instead.
  function genericZenodoExplanation() {
    var size = zenodoConfig ? Math.round(zenodoConfig.max_resource_size_bytes / (1024 * 1024)) : null;
    return translate(
      "Files larger than %(size)s MB, or in a format the data viewer can't read, go to Zenodo automatically either way.",
      { size: size }
    );
  }

  // Pure decision, no DOM/network - file.size/.name/.type are already
  // known synchronously the instant a file is picked. Mirrors (and
  // supersedes) the version worked out and verified in isolation at
  // ckanext-zenodo's docs/stage3-routing-design.js - kept in sync with
  // this one by hand until that design file is deleted.
  function shouldRouteToZenodo(file, config, forced) {
    if (forced) {
      return true;
    }
    if (!config) {
      // Can't decide - this check is a UX nicety only, never
      // authoritative (the server re-validates size/format for real in
      // the /zenodo/upload/ blueprint) - default to "stays on CKAN"
      // rather than surprising the user by routing somewhere unasked.
      return false;
    }
    if (file.size > config.max_resource_size_bytes) {
      return true;
    }
    var ext = (file.name.split(".").pop() || "").toLowerCase();
    var type = (file.type || "").toLowerCase();
    var readable = config.xloader_formats.some(function (f) {
      return f.toLowerCase() === ext || f.toLowerCase() === type;
    });
    return !readable;
  }

  // Real-time feedback on where the selected file(s) will actually end
  // up - the root issue a plain unchecked checkbox didn't solve: a file
  // that auto-routes to Zenodo (too large, or an unreadable format) did
  // so correctly even with the toggle off, but nothing on screen said so
  // until the dataset page was checked after the fact.
  function updateZenodoRoutingHint(files) {
    if (!$zenodoRoutingHint) {
      return;
    }
    var forced = !!($forceZenodoCheckbox && $forceZenodoCheckbox.find("input").is(":checked"));
    if (forced) {
      // The toggle's own label (updateZenodoToggleState, right above)
      // already says, unambiguously, that *every* file goes to Zenodo
      // while it's on - showing this hint too just repeated the same
      // sentence a second time right underneath it.
      $zenodoRoutingHint.hide();
      return;
    }
    if (!files || !files.length) {
      $zenodoRoutingHint.text(genericZenodoExplanation()).show();
      return;
    }
    var toZenodo = 0;
    Array.prototype.forEach.call(files, function (file) {
      if (shouldRouteToZenodo(file, zenodoConfig, forced)) {
        toZenodo += 1;
      }
    });
    if (toZenodo === 0) {
      // Nothing currently selected actually routes to Zenodo - the
      // background explanation of when it would is still useful here,
      // rather than showing nothing at all.
      $zenodoRoutingHint.text(genericZenodoExplanation()).show();
      return;
    }
    // No reason clause here, unlike genericZenodoExplanation above -
    // that one explains *when* a file would route to Zenodo before any
    // file is picked; once one actually is (this branch), it's going
    // there regardless of which reason applied, so the reason adds
    // nothing a user needs to act on.
    var message = files.length === 1
      ? translate('This file will be stored on Zenodo, not in this catalogue.')
      : translate("%(count)d of %(total)d file(s) will be stored on Zenodo, not in this catalogue.", { count: toZenodo, total: files.length });
    $zenodoRoutingHint.text(message).show();
  }

  // ----- "A file with this name is already here" warning -----
  //
  // CKAN itself allows several resources with the same name (only the
  // id is unique), so this only warns, never blocks. What re-uploading
  // actually does depends on where the file goes: a Zenodo file sent to
  // Zenodo again replaces it there (same name = same key in the
  // deposition's bucket - confirmed on the sandbox), anything else adds
  // a second copy next to the existing one.

  var $duplicateHint = null;
  var existingFilesPromise = null;
  var duplicateCheckSeq = 0;

  function fileNameFromUrl(url) {
    var path = (url || "").split(/[?#]/)[0];
    try {
      return decodeURIComponent(path.substring(path.lastIndexOf("/") + 1));
    } catch (e) {
      return "";
    }
  }

  // name -> true if a resource of that name is a Zenodo file. Fetched
  // once per page: the page is reloaded after every upload anyway.
  function existingFiles(packageName) {
    if (!existingFilesPromise) {
      existingFilesPromise = fetch(
        "/api/3/action/package_show?id=" + encodeURIComponent(packageName),
        { credentials: "same-origin" }
      )
        .then(function (response) {
          return response.ok ? response.json() : null;
        })
        .then(function (payload) {
          var byName = Object.create(null);
          var resources = payload && payload.success ? payload.result.resources || [] : [];
          resources.forEach(function (res) {
            var onZenodo = /zenodo\.org\/records\//.test(res.url || "");
            var uploadedName = res.url_type === "upload" ? fileNameFromUrl(res.url) : null;
            [res.name, uploadedName].forEach(function (name) {
              if (name) {
                byName[name] = byName[name] === true || onZenodo;
              }
            });
          });
          return byName;
        })
        .catch(function () {
          return Object.create(null);
        });
    }
    return existingFilesPromise;
  }

  function updateDuplicateHint(files) {
    var packageName = packageNameFromAction();
    if (!$duplicateHint || !packageName) {
      return;
    }
    var seq = ++duplicateCheckSeq;
    if (!files || !files.length) {
      $duplicateHint.empty().hide();
      return;
    }
    var forced = !!($forceZenodoCheckbox && $forceZenodoCheckbox.find("input").is(":checked"));
    existingFiles(packageName).then(function (byName) {
      if (seq !== duplicateCheckSeq) {
        return; // a newer selection already replaced this one
      }
      $duplicateHint.empty();
      Array.prototype.forEach.call(files, function (file) {
        if (!(file.name in byName)) {
          return;
        }
        var replaces = byName[file.name] && shouldRouteToZenodo(file, zenodoConfig, forced);
        var message = replaces
          ? translate("%(name)s is already on Zenodo in this dataset: uploading it again replaces it.", { name: file.name })
          : translate("%(name)s already exists in this dataset: uploading it again adds a second copy next to it.", { name: file.name });
        $duplicateHint.append($("<div>").text(message));
      });
      $duplicateHint.toggle($duplicateHint.children().length > 0);
    });
  }

  if ($forceZenodoCheckbox) {
    $forceZenodoCheckbox.find("input").on("change", function () {
      var files = $("#field-resource-upload")[0].files;
      updateZenodoRoutingHint(files);
      updateDuplicateHint(files);
    });
  }

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

    updateZenodoRoutingHint(files);
    // Freshest read right as the user is about to decide, not whatever
    // was available back when the page first loaded.
    refreshZenodoCapacity();

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

    if (!$duplicateHint) {
      $duplicateHint = $("<div>", { "class": "fair3r-duplicate-upload-hint", role: "status" })
        .insertAfter($bulkHint);
    }
    updateDuplicateHint(files);
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
          resourceId: ok ? payload.result.id : null,
          errorMessage: ok ? null : (extractErrorMessage(payload) || xhr.statusText || translate("Upload failed"))
        });
      };

      xhr.onerror = function () {
        resolve({ ok: false, file: file, errorMessage: translate("Network error") });
      };

      xhr.send(fd);
    });
  }

  // Same XHR-with-progress shape as createOneResource above, pointed at
  // ckanext-zenodo's upload blueprint instead of resource_create - that
  // endpoint streams straight to Zenodo's bucket rather than CKAN's own
  // storage, so there's no CKAN resource id to report back (resourceId
  // stays null; nothing here needs it).
  function createZenodoResource(file, packageName, onProgress, forced) {
    return new Promise(function (resolve) {
      var fd = new FormData();
      fd.append("upload", file, file.name);
      if (forced) {
        fd.append("force_zenodo", "true");
      }

      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/zenodo/upload/" + encodeURIComponent(packageName), true);
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
          resourceId: null,
          errorMessage: ok ? null : (extractErrorMessage(payload) || xhr.statusText || translate("Upload to Zenodo failed"))
        });
      };

      xhr.onerror = function () {
        resolve({ ok: false, file: file, errorMessage: translate("Network error") });
      };

      xhr.send(fd);
    });
  }

  // The real root cause (found by reading ckan/logic/action/update.py):
  // resource_update (which ckanext-xloader's own completion callback,
  // xloader_hook, triggers on every uploaded resource) fetches the whole
  // parent package via package_show to embed the changed resource in it,
  // then re-saves that entire package. If that package_show call answers
  // with a stale Solr-cached copy (still "draft", from before this file's
  // own activation call), that stale copy - not just its resource list -
  // gets written straight back over the DB, undoing our activation
  // outright (confirmed directly: the *database* state column reverted
  // to 'draft', not just what package_show displayed).
  //
  // package_patch (tried first) doesn't help: it fetches its own
  // "original" copy via package_show too and can lose the same race.
  // package_revise is CKAN's own recommended fix for exactly this class
  // of concurrent-update problem (see github.com/ckan/ckan/issues/6420)
  // - it fetches the package once under a row lock (for_update=True) and
  // hands that same locked copy straight to package_update, instead of
  // package_update fetching (and possibly getting a stale copy) again
  // itself.
  function activateDraftDataset(packageName) {
    var token = csrfHeaderToken();
    var headers = { "Content-Type": "application/json" };
    if (token) {
      headers["X-CSRFToken"] = token;
    }
    return fetch("/api/3/action/package_revise", {
      method: "POST",
      credentials: "same-origin",
      headers: headers,
      body: JSON.stringify({
        match: { name: packageName },
        update: { state: "active" }
      })
    });
  }

  // A previous version of this file waited here for ckanext-xloader's own
  // background job (which can race activateDraftDataset above - see its
  // comment) to reach a terminal status via xloader_status, bounded to 10s,
  // before activating. That could only narrow the race, never close it, and
  // cost every save a real delay for a race that's now caught server-side
  // instead (ckanext/fair3r/lib/fdf/draft_guard.py) - removed rather than
  // tuned, since no bound is actually safe.

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

    var forceZenodo = !!($forceZenodoCheckbox && $forceZenodoCheckbox.find("input").is(":checked"));

    var chain = Promise.resolve();
    fileArray.forEach(function (file, index) {
      chain = chain.then(function () {
        overlay.setTitle(isBulk
          ? translate("Uploading %(current)d / %(total)d files", { current: index + 1, total: total })
          : translate("Uploading…"));
        overlay.setCurrent(file.name, 0);
        var routeToZenodo = shouldRouteToZenodo(file, zenodoConfig, forceZenodo);
        // 4th arg means something different per function: "forced" for
        // createZenodoResource, "overrideName" (bulk) for createOneResource.
        var uploadFn = routeToZenodo ? createZenodoResource : createOneResource;
        var fourthArg = routeToZenodo ? forceZenodo : isBulk;
        return uploadFn(file, packageName, function (pct) {
          overlay.setCurrent(file.name, pct);
        }, fourthArg).then(function (result) {
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
        // "go-metadata" (Publish) is CKAN's own signal that this is the
        // last resource of a still-draft dataset - its server-side handler
        // activates the dataset for us. "go-dataset-complete" (Add) is
        // meant for adding a resource to an *already active* dataset, and
        // its handler deliberately does nothing to activate it. Which
        // button actually renders, though, is decided server-side from a
        // package_show call of its own (views/resource.py's GET handler)
        // that's subject to the exact same staleness this file already
        // works around above - so a dataset that's still genuinely draft
        // can end up showing "Add" instead of "Publish", and then never
        // gets activated by anything at all. Activating here too is a
        // harmless no-op on an already-active dataset, and closes that
        // gap regardless of which button CKAN happened to render.
        //
        // No wait-for-xloader step before this call: xloader's own
        // background job racing this activation (see activateDraftDataset
        // above) is now caught server-side instead, by
        // ckanext/fair3r/lib/fdf/draft_guard.py - any bounded client-side
        // wait here could only ever narrow that race, never close it
        // (xloader can always take longer than whatever's guessed), so
        // it's not worth the user-visible delay on every save.
        var finalize = (saveValue === "go-metadata" || saveValue === "go-dataset-complete")
          ? activateDraftDataset(packageName).catch(function () { /* best effort */ })
          : Promise.resolve();

        finalize.then(function () {
          if (saveValue === "again") {
            // CKAN's own resource-upload-field.js decides once, at page
            // load, whether the Name field is "dirty" (has any value at
            // all) and if so never auto-fills it again from the next
            // selected file. A plain reload can leave the browser's own
            // form-restore autofill sitting in this field (it's a generic
            // name="name" input) before that script even runs - so the
            // *next* resource silently inherits this one's name. Clearing
            // it right before reloading is what the field needs to look
            // empty again once the fresh page loads.
            if ($nameInput.length) {
              $nameInput.val("");
            }
            // Same browser quirk as the Name field above: a plain reload
            // can restore this file input's previous selection too, even
            // though a script can never *set* a file input to an actual
            // file (security restriction) - clearing it to "" is the one
            // exception browsers do allow, and is exactly what a truly
            // fresh "add another resource" form should show.
            if ($currentFileInput.length) {
              $currentFileInput.val("");
            }
            window.location.reload();
          } else {
            window.location.href = redirectUrl;
          }
        });
      }

      if (successCount > 0) {
        // At least one resource was actually created — navigate on
        // regardless of any failures in the same batch: those successes
        // are already saved, there's nothing to "retry" by staying, and
        // the result list above already showed which file(s) failed and
        // why before this button appeared.
        overlay.finish(translate("Continue"), goToNextStep);
      } else {
        // Nothing in the batch succeeded: no new resource to go see, so
        // stay put with the same selection/fields in place to fix and
        // retry, rather than navigating to a page with nothing new on it.
        overlay.finish(translate("Close"), function () {
          overlay.remove();
          // CKAN's own basic-form.js disables button[name="save"] on every
          // submit, assuming the page is about to navigate away shortly
          // after. Since we're staying put here, nothing else would ever
          // re-enable it — without this the form looks stuck (Finish
          // un-clickable) even though it's perfectly usable again.
          $form.find('button[name="save"]').prop("disabled", false);
        });
      }
    });
  });
});
