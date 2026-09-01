ckan.module("fdf-form-module", function ($, translate, i18n) {
  "use strict";

  // CKAN passes jed.translate as the 2nd arg (returns an object); use i18n._ for strings.
  const _ = i18n._;

  // Simple debounce implementation since _.debounce may not be available
  const debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const context = this; // Capture the jQuery context
      const later = () => {
        clearTimeout(timeout);
        func.apply(context, args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };

  // Back-compat only: fields listed here used to bake a "Label: " prefix into
  // their stored `subject` text (schema `tpl.subject`, e.g. "Gene: $label").
  // The schema no longer declares that prefix for newly-saved data (the
  // display template and the DataCite converter already derive the label
  // from `subjectScheme` instead), but datasets saved before this change
  // still carry it in their stored text. Keyed by field id (not scheme,
  // since gene_search's scheme is resolved dynamically per API and can't be
  // used as a lookup key) so editing those older datasets still prefills
  // the right raw value instead of "Gene: Apoe".
  const LEGACY_SUBJECT_PREFIXES = {
    strain_search: "Strain: ",
    gene_search: "Gene: ",
    transgene_origin_species: "Transgene origin: ",
    gene_chromosome_location: "Gene locus: ",
    allele_search: "Allele: ",
    allele_identifier_free: "Allele: ",
    genetic_background: "Strain: ",
    xenopus_line_type: "Line type: ",
    mutationType_display: "Mutation type: ",
  };

  // Simple get implementation for nested object access and basic JMESPath-like syntax
  const getNestedValue = function(obj, path, defaultValue = null) {
    if (!obj) return defaultValue;
    if (path === null || path === undefined || String(path).trim() === "") return obj;
    
    path = path.trim();
    // Normalize array access: convert ".[0]" to "[0]" for consistent handling
    path = path.replace(/\.\[(\d+)\]/g, '[$1]');
    const filterRegex = /^([a-zA-Z_][a-zA-Z0-9_.]*)\.\[\?([a-zA-Z_][a-zA-Z0-9_.]*)\s*=\s*([^\]]+)\](?:\.([a-zA-Z_][a-zA-Z0-9_]*))?$/;
    const filterMatch = path.match(filterRegex);

    if (filterMatch) {
      const [, arrayKey, filterKey, filterValue, resultKey] = filterMatch;
      const array = arrayKey.includes(".")
        ? getNestedValue(obj, arrayKey, undefined)
        : obj[arrayKey];

      if (!Array.isArray(array)) {
        return defaultValue;
      }

      // Find item matching the filter (filterKey may itself be a nested
      // path, e.g. "noteType.name", to filter on a nested object's field)
      const item = array.find(el => {
        const filterField = filterKey.includes(".")
          ? getNestedValue(el, filterKey, undefined)
          : el[filterKey];
        if (Array.isArray(filterField)) {
          return filterField.includes(filterValue);
        }
        return filterField === filterValue;
      });
      
      if (!item) {
        return defaultValue;
      }
      
      if (resultKey) {
        return item[resultKey] || defaultValue;
      }
      return item || defaultValue;
    }
    
    // Handle simple dot notation
    const parts = path.split('.');
    let value = obj;
    
    for (let part of parts) {
      if (!value) return defaultValue;
      
      // Handle array index like "addresses[0]"
      if (part.includes('[')) {
        const indexMatch = part.match(/^([^\[]+)\[(\d+)\]$/);
        if (indexMatch) {
          const [, key, index] = indexMatch;
          value = value[key]?.[parseInt(index)] || null;
        } else {
          value = null;
        }
      } else {
        // Regular property access
        value = value[part] || null;
      }
      
      if (!value) return defaultValue;
    }
    
    return value || defaultValue;
  };

  // Field ids referenced by name in several places below; centralized here
  // to avoid repeating (and risking a typo in) the literal string.
  const FIELD_NAMES = {
    ALLELE: "allele_search",
    GENE: "gene_search"
  };

  return {
    options: {},

    initialize: function () {
      this.container = $("#fdf-form-container");
      if (!this.container.length) {
        return;
      }

      let schema = window.FDF_SCHEMA;
      this.prefillData = window.FDF_DATA || null;
      this.mode = null;
      this.isDraft = false;

      if (typeof this.prefillData === "string") {
        try {
          this.prefillData = JSON.parse(this.prefillData);
        } catch (e) {
          console.error("FDF data JSON parsing error:", e);
          this.prefillData = null;
        }
      }

      window.FDF_SCHEMA = schema;
      window.FDF_EXISTING_DATA = this.prefillData || {};
      window.FDF_DATA = this.prefillData || {};


      if (typeof schema === "string") {
        try {
          schema = JSON.parse(schema);
        } catch (e) {
          console.error("Schema JSON parsing error:", e);
          this.container.html("<p>Schema parsing error.</p>");
          $("#fdf-alert").remove();
          return;
        }
      }

      if (!schema || !Array.isArray(schema.sections)) {
        console.error("Invalid or missing FDF schema:", schema);
        this.container.html("<p>Invalid or missing FDF schema.</p>");
        $("#fdf-alert").remove();
        return;
      }

      this.schema = schema;

      const hasPrefillData =
        this.prefillData && Object.keys(this.prefillData).length > 0;
      this._draftKey = null;
      if (!hasPrefillData) {
        this._draftKey = `fair3r_fdf_draft:${window.location.pathname}`;
        const savedDraft = window.localStorage.getItem(this._draftKey);
        if (savedDraft) {
          const url = new URL(window.location.href);
          const resumeParam = url.searchParams.get("resume_draft") === "1";
          let samePageReferrer = false;
          let isReload = false;
          const navEntries = performance.getEntriesByType("navigation");
          if (navEntries && navEntries.length > 0) {
            isReload = navEntries[0].type === "reload";
          } else if (performance && performance.navigation) {
            isReload = performance.navigation.type === 1;
          }
          if (document.referrer) {
            try {
              const refUrl = new URL(document.referrer);
              samePageReferrer = refUrl.pathname === window.location.pathname;
            } catch (e) {
              samePageReferrer = false;
            }
          }

          if (resumeParam || samePageReferrer || isReload) {
            try {
              this.prefillData = JSON.parse(savedDraft);
            } catch (e) {
            }
          } else {
            window.localStorage.removeItem(this._draftKey);
          }
        }
      }


      this.renderForm();
      $("#fdf-alert").remove();
      this._hideManagedFields();
      this._observeManagedFields();
      this.bindConditions();
      this.evalConditions(); // Evaluate conditions for initial state (pre-filled values)
      this._applyFieldVisibility();

      const allFields = this.schema.sections.flatMap(section => section.fields || []);

      allFields.forEach(field => {
        if (Array.isArray(field.on_change)) {
          // Determine the correct selector based on field type (input, select, textarea)
          let selector = "[name='" + field.id + "']";
          // For select elements, we might have a CKAN-specific structure, so also check for select with name
          $(document).on("change", selector, () => {
            field.on_change.forEach(change => {
              if (change.action === "reset_fields" && Array.isArray(change.fields)) {
                change.fields.forEach(fieldId => {
                  // Get field metadata from schema
                  const fieldMetadata = self._getFieldMetadata(fieldId);
                  
                  // Reset the value of the target field(s) and trigger change if it's a select to update any dependent logic
                  $("[name='" + fieldId + "']").each(function() {
                    if (this.tagName === "SELECT") {
                      $(this).val("").trigger("change");
                    } else {
                      $(this).val("").removeData("selected-id").removeData("selected-label");
                    }
                    // Remove displayed xrefs
                    const inputEl = $(this);
                    inputEl.closest(".fdf-api-input-wrapper").nextAll(".xrefs-display").remove();

                    // Clear fields dependent on this field (from schema metadata)
                    if (fieldMetadata && Array.isArray(fieldMetadata.clear_dependent_fields)) {
                      const instanceEl = $(this).closest(".fdf-instance");
                      fieldMetadata.clear_dependent_fields.forEach(dependentFieldId => {
                        const depField = instanceEl.find("[name='" + dependentFieldId + "']").first();
                        if (depField.length) {
                          depField.val("").trigger("change");
                          depField.siblings(".fdf-search-input").val("").removeData("selected-id").removeData("selected-label");
                        }
                      });
                    }

                    // Clear fields that display data from this field (from schema metadata)
                    if (fieldMetadata && fieldMetadata.update_display_field) {
                      const instanceEl = $(this).closest(".fdf-instance");
                      instanceEl.find("[name='" + fieldMetadata.update_display_field + "']").val("");
                    }
                  });
                });
              }
            });
          });
        }
      });

      // Handle form submission
      const self = this;
      
      // Find the parent form - try multiple approaches
      let form = null;
      const fdfContainer = document.getElementById('fdf-form-container');
      
      // Method 1: Try closest() for cases where FDF div is inside the form
      form = $(fdfContainer).closest('form');
      
      // Method 2: If no parent form found, try to find by common CKAN form IDs
      if (form.length === 0) {
        form = $('#dataset-edit');  // Standard CKAN edit form
        if (form.length === 0) {
          form = $('form.dataset-form');  // Fallback
        }
        if (form.length === 0) {
          form = $(fdfContainer).parents('body').find('form').first();  // Find any form in body
        }
      }
      
      if (form.length === 0) {
        console.error("Could not find parent form for FDF! Tried: closest(), #dataset-edit, .dataset-form");
        return;
      }
      
      
      // Strategy 1: Attach to form.submit event (for normal HTML form submission)
      form.on("submit", function(e) {
        if (!self.validateFDFForm()) {
          e.preventDefault();
          e.stopImmediatePropagation();
          return false;
        }
        self._populateFDFField();
        return true;
      });
      
      // Strategy 2: Also intercept clicks on save button to catch async submissions
      form.on("click", "button[type='submit'], input[type='submit']", function(e) {
        // Give jQuery a chance to populate the field before async submission
        self._populateFDFField();
      });
      
      // Strategy 3: Monitor form data before any submission
      const originalFormSubmit = form[0].submit;
      if (originalFormSubmit) {
        form[0].submit = function() {
          if (!self.validateFDFForm()) {
            return false;
          }
          self._populateFDFField();
          return originalFormSubmit.apply(this, arguments);
        };
      }
      
      
      // Attach event handlers for form interactions
      this._attachFormHandlers();
      this._attachDraftSaver();
    },

    _hideManagedFields: function() {
      const fieldsToHide = ["author", "author_email", "maintainer", "maintainer_email"];

      fieldsToHide.forEach(function(fieldName) {
        const input = document.querySelector('input[name="' + fieldName + '"]') ||
          document.getElementById('field-' + fieldName) ||
          document.getElementById('field-' + fieldName.replace('_', '-')) ||
          document.querySelector('[name="' + fieldName + '"]');

        if (!input) {
          return;
        }

        const controlGroup = input.closest('.control-group') ||
          input.closest('.control-full') ||
          input.closest('.form-group');

        if (controlGroup) {
          controlGroup.style.display = 'none';
        }
      });

      const customFieldsModule = document.querySelector('[data-module="custom-fields"]');
      if (customFieldsModule) {
        const customFieldsFieldset = customFieldsModule.closest('fieldset');
        if (customFieldsFieldset) {
          customFieldsFieldset.style.display = 'none';
        } else {
          customFieldsModule.style.display = 'none';
        }
      }

      const customFieldInputs = document.querySelectorAll('input[name^="extras__"]');
      customFieldInputs.forEach(function(input) {
        const controlGroup = input.closest('.control-group') ||
          input.closest('.form-group') ||
          input.closest('.control-full');
        if (controlGroup) {
          controlGroup.style.display = 'none';
        }
      });
    },

    _observeManagedFields: function() {
      const self = this;
      const formContainer = document.querySelector('.dataset-form') || document.querySelector('form');
      if (!formContainer) {
        return;
      }

      const observer = new MutationObserver(function() {
        self._hideManagedFields();
      });

      observer.observe(formContainer, { childList: true, subtree: true });
    },

    _populateFDFField: function() {
      const self = this;
      
      // Collect form data according to schema
      const formData = self.collectFormData();
      
      // Put JSON into hidden field
      const jsonField = $("#fdf-output-json");
      if (jsonField.length === 0) {
        console.error("ERROR: fdf-output-json field not found!");
        return;
      }
      
      const jsonString = JSON.stringify(formData);
      jsonField.val(jsonString);

      // Keep CKAN extras__n__value in sync when present.
      const extrasKeyInputs = $("input[name^='extras__'][name$='__key']");
      extrasKeyInputs.each(function () {
        const keyInput = $(this);
        if (keyInput.val() === "fdf_output_json") {
          const valueName = keyInput.attr("name").replace("__key", "__value");
          const valueInput = $("input[name='" + valueName + "']");
          if (valueInput.length > 0) {
            valueInput.val(jsonString);
          }
        }
      });
      
    },

    _attachFormHandlers: function() {
      const self = this;

      // Handle __OTHER__ search behavior
      this.container.on("change", "select", function () {
        self._unlockSubmitButtons();
        const select = $(this);
        const searchInput = select.siblings(".fdf-search-input");
        if (select.val() === "__OTHER__") {
          searchInput.show();
        } else {
          searchInput.hide().val("");
        }
      });

      // Handle API search for preset_or_search fields (fdf-search-input)
      this.container.on(
        "input",
        ".fdf-search-input",
        debounce(async function () {
          self._unlockSubmitButtons();
          const input = $(this);
          if (input.data("skip-search")) {
            input.data("skip-search", false);
            return;
          }
          input.removeData("selected-id");
          input.removeData("selected-label");
          input.removeData("mapped-extra");
          
          const defaultApiKey = input.data("api");
          const apiKey = self._resolveApiKeyForInput(defaultApiKey, input);
          const val = input.val().trim();
          const resultsContainer = input.closest(".fdf-api-input-wrapper").siblings(".fdf-api-results");

          if (!val) {
            // Use schema metadata to clear dependent fields
            const instanceEl = input.closest(".fdf-instance");
            const fieldName = input.attr("name");
            self._clearDependentFields(fieldName, instanceEl);
            resultsContainer.hide().empty();
            return;
          }

          if (!apiKey) {
            if (input.data("allow-manual")) {
              resultsContainer.hide().empty();
              return;
            }
            resultsContainer.empty().show()
              .append(`<div style="padding:10px; color:#999;">${self._getApiUnavailableMessage(input)}</div>`);
            return;
          }

          const api = self.schema.apis[apiKey];
          if (!api) {
            return;
          }

          // Enforce dependency if configured (e.g. allele search depends on gene_search)
          if (api.depends_on) {
            const dependencyValue = self._getContextValue(api.depends_on, input);
            if (dependencyValue === null || dependencyValue === undefined || String(dependencyValue).trim() === "") {
              resultsContainer.empty().show()
                .append(`<div style="padding:10px; color:#999;">${_("Please select or enter the dependent field first.")}</div>`);
              return;
            }
          }

          const params = new URLSearchParams();
          if (api.query_param) {
            params.append(api.query_param, val);
          }
          if (api.extra_params) {
            Object.entries(api.extra_params).forEach(([k, v]) =>
              params.append(k, v)
            );
          }

          try {
            self._setApiLoading(resultsContainer, true);
            let url = api.url;
            if (api.path_params_from_context) {
              Object.entries(api.path_params_from_context).forEach(([placeholder, contextKey]) => {
                const contextValue = self._getContextValue(contextKey, input);
                const rawValue = contextValue !== null && contextValue !== undefined
                  ? String(contextValue).trim()
                  : "";
                const invalidValue = !rawValue || /undefined|null/i.test(rawValue);
                if (!invalidValue) {
                  url = url.replace(`{${placeholder}}`, encodeURIComponent(rawValue));
                }
              });
            }
            if (/\{[^}]+\}/.test(url)) {
              resultsContainer.empty().show()
                .append(`<div style="padding:10px; color:#999;">${self._getApiUnavailableMessage(input)}</div>`);
              self._setApiLoading(resultsContainer, false);
              return;
            }
            const queryString = params.toString();
            if (queryString) {
              url += "?" + queryString;
            }
            
            const res = await fetch(url, {
              headers: api.headers || {},
              mode: 'cors',
              credentials: 'omit'
            });
            
            if (!res.ok) {
              console.error(`API Error ${res.status}:`, res.statusText);
              resultsContainer.empty().show()
                .append(`<div style="color:red; padding:10px;">${_("Error")}: ${res.status} ${res.statusText}</div>`);
              self._setApiLoading(resultsContainer, false);
              return;
            }
            
            const data = await res.json();
            
            let items = self._filterApiResults(getNestedValue(data, api.result_path, []), api, input);
            if (!Array.isArray(items)) {
              resultsContainer.empty().show()
                .append(`<div style="padding:10px; color:#999;">${_("Invalid response format")}</div>`);
              self._setApiLoading(resultsContainer, false);
              return;
            }

            resultsContainer.empty().show();
            if (!items || items.length === 0) {
              resultsContainer.append(`<div style="padding:10px; color:#999;">${_("No results")}</div>`);
              self._setApiLoading(resultsContainer, false);
              return;
            }
            
            items.slice(0, api.result_limit || 8).forEach((item) => {
              let label = "";
              let id = "";
              let sublabel = "";
              
              // Extract label - handle both {{a || b}} and {{a}} {{b}} patterns
              if (api.mapper.label) {
                let labelTemplate = api.mapper.label;
                const isSingleWrapper = labelTemplate.startsWith("{{") && 
                                       labelTemplate.endsWith("}}") && 
                                       !labelTemplate.includes("}} {{");
                
                if (isSingleWrapper) {
                  const innerContent = labelTemplate.slice(2, -2);
                  
                  if (innerContent.includes("||")) {
                    const paths = innerContent.split('||').map(p => p.trim());
                    for (let path of paths) {
                      const value = getNestedValue(item, path, "");
                      if (value) {
                        label = value;
                        break;
                      }
                    }
                  } else {
                    label = getNestedValue(item, innerContent, "");
                  }
                } else {
                  label = labelTemplate.replace(
                    /\{\{([^}]+)\}\}/g,
                    (match, path) => getNestedValue(item, path.trim(), "")
                  );
                }
              } else if (api.mapper.strategy === "obo_ontology") {
                // For OLS/ontology APIs without explicit label template, use common fields
                label = item.label || item.name || item.id || "";
              }
              
              // Extract sublabel
              if (api.mapper.sublabel) {
                sublabel = api.mapper.sublabel.replace(
                  /\{\{([^}]+)\}\}/g,
                  (match, path) => {
                    const expr = path.trim();
                    if (expr.includes("||")) {
                      const paths = expr.split("||").map((p) => p.trim());
                      for (let p of paths) {
                        const value = getNestedValue(item, p, "");
                        if (value !== null && value !== undefined && String(value).trim() !== "") {
                          return value;
                        }
                      }
                      return "";
                    }
                    return getNestedValue(item, expr, "");
                  }
                );
              } else if (api.mapper.strategy === "obo_ontology") {
                sublabel = item.description || item.obo_id || "";
              }
              sublabel = self._sanitizeSublabel(sublabel);
              
              // Extract id - simple interpolation
              if (api.mapper.id) {
                id = api.mapper.id.replace(
                  /\{\{([^}]+)\}\}/g,
                  (match, path) => getNestedValue(item, path.trim(), "")
                );
              } else if (api.mapper.strategy === "obo_ontology") {
                // For OLS/ontology APIs without explicit id template, use common fields
                id = item.iri || item.id || "";
              }

              if (api.mapper.id_candidates) {
                id = self._resolveIdCandidates(item, api.mapper.id_candidates) || id;
              }
              
              if (label && id) {
                const safeLabel = self._escapeHtml(label);
                const safeSublabel = self._escapeHtml(sublabel);
                let itemHtml = `<div class="fdf-api-item" data-id="${id}" style="padding:8px 12px; border-bottom:1px solid #eee; cursor:pointer;" onmouseover="this.style.backgroundColor='#f5f5f5'" onmouseout="this.style.backgroundColor='white'">
                  <div style="font-weight:500; color:#333;">${safeLabel}</div>`;
                if (sublabel) {
                  itemHtml += `<div style="font-size:12px; color:#666; margin-top:2px;">${safeSublabel}</div>`;
                }
                itemHtml += `</div>`;
                const itemEl = $(itemHtml);
                itemEl.data("label", label);
                // Store complete item data for xrefs processing
                itemEl.data("item-data", item);
                itemEl.data("api-key", apiKey);
                resultsContainer.append(itemEl);
              }
            });
            self._setApiLoading(resultsContainer, false);
          } catch (e) {
            console.error("API search error for " + apiKey, e);
            resultsContainer.empty().show()
              .append(`<div style="color:red; padding:10px;">${_("Request error")}: ${e.message}</div>`);
            self._setApiLoading(resultsContainer, false);
          }
        }, 300)
      );

      // Handle selection from search results for preset_or_search
      this.container.on("click", ".fdf-api-item", function () {
        const item = $(this);
        const formGroup = item.closest(".form-group");
        const searchInput = formGroup.find(".fdf-search-input");
        const select = formGroup.find("select");
        const id = item.data("id");
        const label = item.data("label") || item.text();
        
        if (searchInput.length > 0 && searchInput.hasClass("fdf-search-input")) {
          searchInput.data("selected-id", id);
          searchInput.data("selected-label", label);
          searchInput.val(label);
          searchInput.data("skip-search", true);
        } else {
          const input = formGroup.find(".fdf-api-input");
          if (input.length > 0) {
            const displayValue = label && label !== id ? `${id} — ${label}` : id;
            input.val(displayValue);
            input.data("selected-id", id);
            input.data("selected-label", label);
            input.data("skip-search", true);
          }
        }
        
        item.parent().hide();
      });

      this.container.on(
        "input",
        ".fdf-api-input",
        debounce(async function () {
          const input = $(this);

          if (input.data("skip-search")) {
            input.data("skip-search", false);
            return;
          }
          input.removeData("selected-id");
          input.removeData("selected-label");
          
          const defaultApiKey = input.data("api");
          const apiKeys = self._resolveApiKeysForInput(defaultApiKey, input);
          const val = input.val().trim();
          const resultsContainer = input.closest(".fdf-api-input-wrapper").siblings(".fdf-api-results");

          if (!val) {
            // Use schema metadata to clear dependent fields
            const instanceEl = input.closest(".fdf-instance");
            const fieldName = input.attr("name");
            self._clearDependentFields(fieldName, instanceEl);
            resultsContainer.hide().empty();
            return;
          }

          if (!apiKeys.length) {
            resultsContainer.empty().show()
              .append(`<div style="padding:10px; color:#999;">${self._getApiUnavailableMessage(input)}</div>`);
            return;
          }

          // Mapping of group-level taxids → species-level taxids
          const groupToSpecies = {
            9443: [9606, 9598, 9593, 9601, 9544],   // Primates
            40674: [9606, 10090, 10116],            // Mammalia (human, mouse, rat)
            314295: [9606, 10090, 10116, 9593],     // Tetrapoda
            32523: [9606, 10090, 10116],            // Vertebrata
            33208: [9606, 10090],                   // Euteleostomi
            7711: [9606],                           // Metazoa (example: human)
            6072: [9606],                           // Eukaryota
            9031: [9615],                            // Canidae (dog)
            28384: [10090, 10116],                  // Rodentia (mouse, rat)
            260799: [9031, 7955],                   // Aves (example: dog, zebrafish)
            1239: [4896]                             // Fungi (example: Saccharomyces cerevisiae)
          };


          const runApiSearch = async (currentApiKey) => {
            const api = self.schema.apis[currentApiKey];
            if (!api) {
              return { api: null, items: [] };
            }

            if (api.depends_on) {
              const dependencyValue = self._getContextValue(api.depends_on, input);
              if (dependencyValue === null || dependencyValue === undefined || String(dependencyValue).trim() === "") {
                return { api, items: [], dependencyMissing: true };
              }
            }

            // Generic search mode: build query params from API config

            // Generic server-side lookup mode: backend proxy/action is selected by schema.
            // Kept backward-compatible with the historical `gene_mutants` mode.
            if (api.query_mode === "server_side_lookup" || api.query_mode === "gene_mutants") {
              const params = new URLSearchParams();
              if (api.extra_params) {
                Object.entries(api.extra_params).forEach(([k, v]) => params.append(k, v));
              }

              if (api.extra_params_from_context) {
                for (const [param, contextKey] of Object.entries(api.extra_params_from_context)) {
                  const contextValue = self._getContextValue(contextKey, input);
                  const rawValue = contextValue !== null && contextValue !== undefined
                    ? String(contextValue).trim()
                    : "";
                  if (!rawValue) {
                    return { api, items: [], dependencyMissing: true };
                  }
                  params.append(param, rawValue);
                }
              }

              let fetchUrl = api.url;
              const queryString = params.toString();
              if (queryString) {
                fetchUrl += "?" + queryString;
              }

              // Use same-origin credentials by default so the CKAN session cookie is sent
              // to same-origin server-side lookup actions.
              const res = await fetch(fetchUrl, {
                headers: api.headers || {},
                mode: "cors",
                credentials: api.credentials || "same-origin"
              });
              if (!res.ok) {
                throw new Error(`${res.status} ${res.statusText}`);
              }

              const data = await res.json();
              let mutants = getNestedValue(data, api.result_path, []);
              if (!Array.isArray(mutants)) {
                mutants = [];
              }

              if (val && val.trim()) {
                const needle = val.trim().toLowerCase();
                const filterFields = api.filter_fields || api.gene_mutants_filter_fields ||
                  ["name_clean", "display_clean", "name", "display", "lineId"];
                const filtered = mutants.filter((m) => {
                  return filterFields.some((field) => {
                    const fv = m[field];
                    return typeof fv === "string" && fv.toLowerCase().includes(needle);
                  });
                });
                mutants = filtered.length > 0 ? filtered : mutants;
              }

              const limit = api.result_limit || 10;
              mutants = mutants.slice(0, limit);
              return { api, items: mutants };
            }

            const queryCandidates = [val];

            if (api.query_prefix_with_gene) {
              const selectedGeneSymbol = self._getSelectedGeneSymbolForAlleles(input);
              const geneInput = input.closest(".fdf-instance").find("[name='gene_search']").first();
              const selectedGeneId = (geneInput.data("selected-id") || "").toString().trim();

              const lowerVal = val.toLowerCase();
              if (selectedGeneId && !lowerVal.includes(selectedGeneId.toLowerCase())) {
                queryCandidates.unshift(`${selectedGeneId} ${val}`);
              } else if (selectedGeneSymbol && !lowerVal.includes(selectedGeneSymbol.toLowerCase())) {
                queryCandidates.unshift(`${selectedGeneSymbol} ${val}`);
              }
            }

            for (const candidateQuery of queryCandidates) {
              const params = new URLSearchParams();
              if (api.query_param) {
                params.append(api.query_param, candidateQuery);
              }
              if (api.extra_params) {
                Object.entries(api.extra_params).forEach(([k, v]) => params.append(k, v));
              }

              if (api.extra_params_from_context) {
                // For gene_search, skip the species filter when cross-species mode is active
                const isCrossSpecies = input.attr("name") === "gene_search" &&
                  input.closest(".fdf-instance").find("input[name='cross_species_gene']:checked").length > 0;

                Object.entries(api.extra_params_from_context).forEach(([param, contextKey]) => {
                  // Skip species injection for cross-species gene search
                  if (isCrossSpecies && contextKey === "organism_taxon_id") {
                    return;
                  }

                  let value = null;

                  if (typeof self._getContextValue === "function") {
                    value = self._getContextValue(contextKey, input);
                  }

                  if (!value && contextKey === "organism_taxon_id") {
                    const organismInput = $("select[name='organism_choice']");
                    if (organismInput.length) {
                      let selectVal = organismInput.val();
                      if (selectVal === "__OTHER__") {
                        const searchInput = organismInput.siblings(".fdf-search-input");
                        value = searchInput.data("selected-id") || searchInput.val();
                      } else {
                        value = organismInput.find(":selected").data("taxon-id") || selectVal;
                      }
                    }
                  }

                  if (typeof value === "string" && value.startsWith("http")) {
                    const match = value.match(/NCBITaxon_(\d+)|(\d+)$/);
                    if (match) {
                      value = match[1] || match[2];
                    }
                  }

                  if (value && /^\d{4,7}$/.test(value)) {
                    const numValue = Number(value);
                    if (groupToSpecies[numValue]) {
                      groupToSpecies[numValue].forEach((speciesTaxid) => params.append(param, speciesTaxid));
                    } else {
                      params.append(param, numValue);
                    }
                  } else if (value !== null && value !== undefined && String(value).trim() !== "") {
                    params.append(param, String(value).trim());
                  }
                });
              }

              let url = api.url;
              if (api.path_params_from_context) {
                Object.entries(api.path_params_from_context).forEach(([placeholder, contextKey]) => {
                  const contextValue = self._getContextValue(contextKey, input);
                  const rawValue = contextValue !== null && contextValue !== undefined
                    ? String(contextValue).trim()
                    : "";
                  const invalidValue = !rawValue || /undefined|null/i.test(rawValue);
                  if (!invalidValue) {
                    url = url.replace(`{${placeholder}}`, encodeURIComponent(rawValue));
                  }
                });
              }

              if (/\{[^}]+\}/.test(url)) {
                return { api, items: [], unresolvedContext: true };
              }

              const queryString = params.toString();
              if (queryString) {
                url += "?" + queryString;
              }

              const res = await fetch(url, {
                headers: api.headers || {},
                mode: "cors",
                credentials: "omit"
              });

              if (!res.ok) {
                throw new Error(`${res.status} ${res.statusText}`);
              }

              const data = await res.json();
              let items = self._filterApiResults(getNestedValue(data, api.result_path, []), api, input);
              if (!Array.isArray(items)) {
                throw new Error("Invalid response format");
              }

              // Client-side filter by user input when the API ignores the query param (e.g. Ensembl region)
              if (api.filter_by_query && val && val.trim()) {
                const needle = val.trim().toLowerCase();
                const filtered = items.filter((item) => {
                  return Object.values(item).some((v) =>
                    typeof v === "string" && v.toLowerCase().includes(needle)
                  );
                });
                if (filtered.length > 0) {
                  items = filtered;
                }
              }


              if (items.length > 0) {
                return { api, items };
              }
            }

            return { api, items: [] };
          };

          try {
            self._setApiLoading(resultsContainer, true);

            const seenIds = new Set();
            let totalItems = 0;
            let dependencyMissing = false;
            let unresolvedContext = false;

            for (const currentApiKey of apiKeys) {
              let searchResult;
              try {
                searchResult = await runApiSearch(currentApiKey);
              } catch (apiError) {
                if (apiKeys.length === 1) {
                  throw apiError;
                }
                console.error("API search error for " + currentApiKey, apiError);
                continue;
              }

              if (!searchResult || !searchResult.api) {
                continue;
              }

              if (searchResult.dependencyMissing) {
                dependencyMissing = true;
                continue;
              }

              if (searchResult.unresolvedContext) {
                unresolvedContext = true;
                continue;
              }

              const currentLimit = searchResult.api.result_limit || 8;
              searchResult.items.slice(0, currentLimit).forEach((item) => {
                const sourceTag = self._getApiSourceTag(currentApiKey, item);
                const mapped = self._mapApiResultItem(item, searchResult.api);
                if (!mapped) {
                  return;
                }

                if (seenIds.has(mapped.id)) {
                  return;
                }
                seenIds.add(mapped.id);

                  const isAlleleResult = input && input.attr("name") === FIELD_NAMES.ALLELE;
                const taggedSublabel = sourceTag
                  ? `[${sourceTag}]${mapped.sublabel ? " " + mapped.sublabel : ""}`
                  : mapped.sublabel;
                const safeMappedLabel = self._escapeHtml(mapped.label);
                const safeSourceTag = self._escapeHtml(sourceTag);
                const safeMappedSublabel = self._escapeHtml(mapped.sublabel);
                const safeTaggedSublabel = self._escapeHtml(taggedSublabel);
                let itemHtml = `<div class="fdf-api-item" data-id="${mapped.id}" style="padding:8px 12px; border-bottom:1px solid #eee; cursor:pointer;" onmouseover="this.style.backgroundColor='#f5f5f5'" onmouseout="this.style.backgroundColor='white'">
                  <div style="font-weight:500; color:#333;">${safeMappedLabel}</div>`;
                if (isAlleleResult && sourceTag && mapped.sublabel) {
                  itemHtml += `<div style="font-size:12px; color:#666; margin-top:4px; display:flex; align-items:center; gap:6px; flex-wrap:wrap;"><span style="display:inline-block; padding:1px 6px; border-radius:999px; background:#e9f2ff; color:#1f5aa6; font-weight:600; font-size:11px;">${safeSourceTag}</span><span>${safeMappedSublabel}</span></div>`;
                } else if (isAlleleResult && sourceTag) {
                  itemHtml += `<div style="font-size:12px; color:#666; margin-top:4px; display:flex; align-items:center; gap:6px; flex-wrap:wrap;"><span style="display:inline-block; padding:1px 6px; border-radius:999px; background:#e9f2ff; color:#1f5aa6; font-weight:600; font-size:11px;">${safeSourceTag}</span></div>`;
                } else if (taggedSublabel) {
                  itemHtml += `<div style="font-size:12px; color:#666; margin-top:2px;">${safeTaggedSublabel}</div>`;
                }
                itemHtml += `</div>`;

                const itemEl = $(itemHtml);
                itemEl.data("label", mapped.label);
                itemEl.data("item-data", item);
                itemEl.data("api-key", currentApiKey);
                itemEl.data("mapped-extra", mapped.extra || {});
                resultsContainer.append(itemEl);
                totalItems += 1;
              });
            }

            if (totalItems === 0) {
              if (dependencyMissing) {
                resultsContainer.append(`<div style="padding:10px; color:#999;">${_("Please select or enter the dependent field first.")}</div>`);
              } else if (unresolvedContext) {
                resultsContainer.append(`<div style="padding:10px; color:#999;">${self._getApiUnavailableMessage(input)}</div>`);
              } else {
                resultsContainer.append(`<div style="padding:10px; color:#999;">${self._getNoResultsMessage(input)}</div>`);
              }
            }

            self._setApiLoading(resultsContainer, false);
          } catch (e) {
            console.error("API search error", e);
            const friendlyMessage = self._getRequestErrorMessage(input, e);
            resultsContainer.empty().show()
              .append(`<div style="color:#a94442; padding:10px;">${friendlyMessage}</div>`);
            self._setApiLoading(resultsContainer, false);
          }
        }, 300)
      );

      this.container.on("click", ".fdf-api-item", function () {
        const item = $(this);
        const input = item.closest(".form-group").find(".fdf-api-input");
        const id = item.data("id");
        const label = item.data("label") || item.text();
        const itemData = item.data("item-data");
        const apiKey = item.data("api-key");
        const mappedExtra = item.data("mapped-extra") || {};
        
        // Display ID + label in the field, but keep raw ID/label in data attributes
        const displayValue = label && label !== id ? `${id} — ${label}` : id;
        input.val(displayValue);
        input.data("selected-id", id);
        input.data("selected-label", label);
        input.data("item-data", itemData);
        input.data("mapped-extra", mappedExtra);
        input.data("selected-api-key", apiKey || "");

        // Use schema metadata to update dependent fields
        const instanceEl = input.closest(".fdf-instance");
        const fieldName = input.attr("name");
        const mergedExtra = Object.assign({}, mappedExtra);
        
        // For allele_search: merge gene info from parent
        if (fieldName === FIELD_NAMES.ALLELE) {
          const geneInput = instanceEl.find("[name='" + FIELD_NAMES.GENE + "']").first();
          const selectedGeneLabel = (geneInput.data("selected-label") || "").toString().trim();
          const selectedGeneId = (geneInput.data("selected-id") || "").toString().trim();
          if (!mergedExtra.gene_symbol && selectedGeneLabel) {
            mergedExtra.gene_symbol = selectedGeneLabel;
          }
          if (!mergedExtra.gene_id && selectedGeneId) {
            mergedExtra.gene_id = selectedGeneId;
          }
        }
        
        self._updateDependentFields(fieldName, instanceEl, mergedExtra);

        // Best-effort enrichment: some apis only expose a structured
        // mutation/consequence type for a minority of results. When the
        // schema declares mapper.detail_fetch, fetch the full record for
        // richer fields (e.g. a curated mutation description) and re-run
        // the dependent-field update once it resolves. Never blocks the
        // main selection flow and fails silently if the request errors.
        const detailFetch = apiKey && self.schema.apis[apiKey]?.mapper?.detail_fetch;
        if (detailFetch && detailFetch.url && itemData) {
          self._fetchMapperDetailEnrichment(detailFetch, itemData)
            .then((enrichment) => {
              if (!enrichment || Object.keys(enrichment).length === 0) return;
              // Only apply if this field's selection hasn't changed since,
              // and only fill in keys the initial (synchronous) mapping
              // didn't already provide — never overwrite a known value.
              if ((input.data("selected-id") || "") !== id) return;
              const enrichedExtra = Object.assign({}, mergedExtra);
              let changed = false;
              Object.entries(enrichment).forEach(([key, value]) => {
                if (!mergedExtra[key] && value) {
                  enrichedExtra[key] = value;
                  changed = true;
                }
              });
              if (!changed) return;
              input.data("mapped-extra", enrichedExtra);
              self._updateDependentFields(fieldName, instanceEl, enrichedExtra);
            })
            .catch(() => {});
        }

        if (apiKey && self.schema.apis[apiKey]?.provides_chromosome_location) {
          const location = self._extractChromosomeLocation(itemData);
          const locationInput = instanceEl.find("[name='gene_chromosome_location']").first();
          if (locationInput.length > 0) {
            locationInput.val(location || "");
          }
        }
        
        // Process and store xrefs
        let xrefs = null;
        if (apiKey && itemData && self.schema.apis[apiKey]?.mapper?.xrefs) {
          xrefs = self._parseXrefs(itemData, self.schema.apis[apiKey].mapper.xrefs);
        } else if (apiKey && itemData && self.schema.apis[apiKey]?.mapper) {
          // Build xrefs from mapper.id and mapper.extra (backward compatibility)
          xrefs = self._buildXrefsFromMapper(itemData, self.schema.apis[apiKey].mapper);
        }

        if (xrefs && Object.keys(xrefs).length > 0) {
          input.data("xrefs", xrefs);
          self._displayXrefs(input, xrefs, label);
        }
        
        // Auto-fill label to sibling fields if configured
        const autofillLabelTo = input.attr("data-autofill-label-to");
        if (autofillLabelTo) {
          const targets = autofillLabelTo.split(',').map(s => s.trim()).filter(Boolean);
          const instanceEl = input.closest(".fdf-instance");
          targets.forEach(targetName => {
            const targetInput = instanceEl.find(`[name="${targetName}"]`);
            if (targetInput.length) {
              targetInput.val(label.trim());
            }
          });
        }

        input.data("skip-search", true);
        item.parent().hide();

        // Show the clear button when a value is selected
        const wrapper = input.closest(".fdf-api-input-wrapper");
        if (wrapper.length) {
          const clearBtn = wrapper.find(".fdf-clear-btn");
          if (clearBtn.length) {
            clearBtn.show();
          }
        }
      });

      // Clear button handler for api_search fields
      this.container.on("click", ".fdf-clear-btn", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const clearBtn = $(this);
        const wrapper = clearBtn.closest(".fdf-api-input-wrapper");
        const input = wrapper.find(".fdf-api-input");
        if (input.length === 0) return;

        // Clear the input value and data attributes
        input.val("");
        input.removeData("selected-id");
        input.removeData("selected-label");
        input.removeData("item-data");
        input.removeData("mapped-extra");
        input.removeData("xrefs");
        input.removeData("skip-search");
        input.css("padding-right", "12px");

        // Hide the clear button (don't remove it, so it can reappear)
        clearBtn.hide();

        // Remove cross-reference display if present
        wrapper.nextAll(".xrefs-display").remove();

        // Hide and clear API results (sibling of wrapper, not input)
        wrapper.siblings(".fdf-api-results").hide().empty();

        // Trigger input event to notify dependent fields
        input.trigger("input");
      });

      // Auto-fill API fields from other fields
      this.container.on("change input", "input[type='text']", function () {
        self._unlockSubmitButtons();
        const changedInput = $(this);
        const fieldId = changedInput.attr("id");
        const instanceDiv = changedInput.closest(".fdf-instance");
        
        self.schema.sections.forEach((section) => {
          if (!section.fields) return;
          section.fields.forEach((field) => {
            if (field.type !== "api_search") return;
            const autofillFields = field.orcid_autofill_from || field.autofill_from;
            if (!autofillFields || !autofillFields.length) return;

            let shouldTrigger = false;
            autofillFields.forEach((autofillFieldId) => {
              if (fieldId && fieldId.includes(autofillFieldId)) {
                shouldTrigger = true;
              }
            });

            if (shouldTrigger) {
              const values = [];
              autofillFields.forEach((autofillFieldId) => {
                const inp = instanceDiv.find(`input[id*="${autofillFieldId}"], [name="${autofillFieldId}"]`);
                const val = inp.val();
                if (val) values.push(val);
              });

              if (values.length > 0) {
                const searchQuery = values.join(" ");
                // For orcid_autofill_from: target by api key; for autofill_from: target by field id
                let apiInput;
                if (field.orcid_autofill_from) {
                  apiInput = instanceDiv.find(`input[data-api="${field.api}"]`);
                } else {
                  apiInput = instanceDiv.find(`input[name="${field.id}"]`);
                }
                if (apiInput.length > 0) {
                  apiInput.val(searchQuery).trigger("input");
                }
              }
            }
          });
        });
      });
    },

    _attachDraftSaver: function() {
      if (!this._draftKey) {
        return;
      }

      const self = this;
      this.container.on(
        "input change",
        "input, textarea, select",
        debounce(function () {
          const draftData = self.collectFormData();
          window.localStorage.setItem(self._draftKey, JSON.stringify(draftData));
        }, 500)
      );
    },

    _formatFieldLabel: function(field) {
      const safeLabel = field.label || _("Field");
      if (field.required) {
        return `${safeLabel} <span class="fdf-required-star" title="${_("Required")}" style="color:#d9534f; margin-left:2px;">*</span>`;
      }
      return safeLabel;
    },

    _escapeHtml: function(value) {
      return $("<div>").text(value == null ? "" : String(value)).html();
    },

    _sanitizeSublabel: function(value) {
      if (value === null || value === undefined) {
        return "";
      }

      let normalized = String(value)
        .replace(/\s+/g, " ")
        .replace(/\s*,\s*/g, ", ")
        .trim();

      normalized = normalized
        .replace(/^[,;:\/\-\s]+/, "")
        .replace(/[,;:\/\-\s]+$/, "")
        .trim();

      if (!/[A-Za-z0-9]/.test(normalized)) {
        return "";
      }

      return normalized;
    },

    _setApiLoading: function(resultsContainer, loading) {
      if (!resultsContainer || resultsContainer.length === 0) {
        return;
      }

      if (loading) {
        resultsContainer.empty().show().append(
          `<div class="fdf-api-loading"><span class="spinner"></span><span>${_("Searching…")}</span></div>`
        );
      } else {
        resultsContainer.find('.fdf-api-loading').remove();
      }
    },

    _extractChromosomeLocation: function(itemData) {
      if (!itemData || typeof itemData !== "object") {
        return "";
      }

      const genomicPos = itemData.genomic_pos || itemData.genomic_pos_hg19 || itemData.genomic_pos_hg38;
      const positions = Array.isArray(genomicPos) ? genomicPos : [genomicPos];

      for (const pos of positions) {
        if (!pos || typeof pos !== "object") {
          continue;
        }
        const chromosome = (pos.chr || pos.chromosome || pos.chrom || "").toString().trim();
        const start = pos.start ?? pos.begin ?? pos.from;
        const end = pos.end ?? pos.stop ?? pos.to;
        const startNum = Number(start);
        const endNum = Number(end);
        const validCoords = Number.isFinite(startNum) && Number.isFinite(endNum) && startNum > 0 && endNum > 0;
        if (chromosome && validCoords) {
          return `${chromosome}:${Math.trunc(startNum)}-${Math.trunc(endNum)}`;
        }
      }

      const mapLocation = (itemData.map_location || itemData.mapLocation || "").toString().trim();
      if (mapLocation) {
        const match = mapLocation.match(/([A-Za-z0-9._-]+)\s*[:]\s*(\d+)\s*[-]\s*(\d+)/);
        if (match) {
          return `${match[1]}:${match[2]}-${match[3]}`;
        }
      }

      return "";
    },

    _getContextValue: function(contextKey, inputEl = null) {
      if (!contextKey) {
        return null;
      }

      const key = String(contextKey).trim();
      const instanceEl = inputEl && inputEl.length ? inputEl.closest(".fdf-instance") : this.container;

      const readByName = (name) => {
        if (!name) return null;
        const field = instanceEl.find(`[name="${name}"]`).first();
        if (field.length === 0) return null;
        const selectedId = field.data("selected-id");
        if (selectedId) return selectedId;
        const value = field.val();
        return value !== undefined && value !== null && String(value).trim() !== "" ? value : null;
      };

      const direct = readByName(key);
      if (direct) {
        return direct;
      }

      const lastToken = key.split(".").pop();
      if (lastToken && lastToken !== key) {
        const byLastToken = readByName(lastToken);
        if (byLastToken) {
          return byLastToken;
        }
      }

      if (key.indexOf("geneChromosomeLocation") >= 0 || key === "gene_chromosome_location") {
        const manualLocation = readByName("gene_chromosome_location");
        if (manualLocation) {
          return manualLocation;
        }

        const geneInput = instanceEl.find("[name='gene_search']").first();
        if (geneInput.length > 0) {
          const geneItemData = geneInput.data("item-data");
          const inferredLocation = this._extractChromosomeLocation(geneItemData);
          if (inferredLocation) {
            return inferredLocation;
          }
        }
      }

      if (key === "organism_ensembl_species") {
        const preset = this._getSelectedOrganismPreset();
        if (preset && preset.ensembl_species) {
          return preset.ensembl_species;
        }
      }

      // Generic cross-reference lookup: "<field_name>.xref:<xref_key>" reads
      // the xref that _parseXrefs/_buildXrefsFromMapper already attached to
      // another field's selection (e.g. "gene_search.xref:xenbase"). This
      // lets any schema-declared api pull an external identifier produced by
      // a previous search step, without this code knowing which provider or
      // field it is.
      const xrefMatch = key.match(/^([a-zA-Z_][\w]*)\.xref:([a-zA-Z0-9_]+)$/);
      if (xrefMatch) {
        const [, sourceFieldName, xrefKey] = xrefMatch;
        const sourceInput = instanceEl.find(`[name="${sourceFieldName}"]`).first();
        if (sourceInput.length > 0) {
          const xrefs = sourceInput.data("xrefs") || {};
          const xref = xrefs[xrefKey];
          const xrefId = (xref && (xref.id || xref) || "").toString().trim();
          if (xrefId) {
            return xrefId;
          }
        }
        return null;
      }

      if (key === "organism_species_name") {
        const preset = this._getSelectedOrganismPreset();
        return (preset && preset.label) || null;
      }

      return null;
    },

    _getFieldSchemaByName: function(fieldName) {
      if (!fieldName || !this.schema || !Array.isArray(this.schema.sections)) {
        return null;
      }

      for (const section of this.schema.sections) {
        const fields = section.fields || [];
        const field = fields.find((candidate) => candidate && candidate.id === fieldName);
        if (field) {
          return field;
        }
      }

      return null;
    },

    _getOrganismTaxonId: function() {
      const organismInput = $("select[name='organism_choice']");
      if (!organismInput.length) {
        return null;
      }

      let value = organismInput.find(":selected").data("taxon-id") || organismInput.val();

      if (value === "__OTHER__") {
        const searchInput = organismInput.siblings(".fdf-search-input");
        value = searchInput.data("selected-id") || searchInput.val();
      }

      if (typeof value === "string" && value.startsWith("http")) {
        const match = value.match(/NCBITaxon_(\d+)|(\d+)$/);
        if (match) {
          value = match[1] || match[2];
        }
      }

      return value ? String(value) : null;
    },

    _getSelectedOrganismPreset: function() {
      const organismInput = $("select[name='organism_choice']");
      if (!organismInput.length) {
        return null;
      }

      let selectedId = organismInput.val();
      if (selectedId === "__OTHER__") {
        const searchInput = organismInput.siblings(".fdf-search-input");
        selectedId = searchInput.data("selected-id") || searchInput.val();
      }

      const items = this.schema?.vocabularies?.organism_presets?.items || [];
      return items.find((item) => item && item.id === selectedId) || null;
    },

    _resolveApiKeyForInput: function(defaultApiKey, inputEl) {
      if (!defaultApiKey) {
        return defaultApiKey;
      }

      const fieldName = inputEl && inputEl.length ? inputEl.attr("name") : null;
      const field = this._getFieldSchemaByName(fieldName);
      const apiByTaxon = field && field.api_by_taxon;
      if (!apiByTaxon || typeof apiByTaxon !== "object") {
        return defaultApiKey;
      }

      const taxonId = this._getOrganismTaxonId();
      const resolved = apiByTaxon[taxonId] || apiByTaxon[String(taxonId)];
      if (resolved) {
        return resolved;
      }

      return apiByTaxon.default || null;
    },

    _getInstanceElFromInput: function(inputEl) {
      if (!inputEl || !inputEl.length) {
        return null;
      }
      const instanceEl = inputEl.closest(".fdf-instance");
      return instanceEl && instanceEl.length ? instanceEl : null;
    },

    _isGeneSelectedForInstance: function(instanceEl) {
      if (!instanceEl || !instanceEl.length) {
        return false;
      }
      const geneInput = instanceEl.find("[name='gene_search']").first();
      if (!geneInput.length) {
        return false;
      }
      return Boolean(geneInput.data("selected-id") || geneInput.data("item-data") || geneInput.val());
    },

    _resolveApiKeysForInput: function(defaultApiKey, inputEl) {
      const primaryApiKey = this._resolveApiKeyForInput(defaultApiKey, inputEl);
      if (!primaryApiKey) {
        return [];
      }


      const fieldName = inputEl && inputEl.length ? inputEl.attr("name") : "";
      const taxonId = this._getOrganismTaxonId();
      const apiKeys = [primaryApiKey];

      // Add fallback APIs from schema
      const field = this._getFieldSchemaByName(fieldName);
      const apiFallback = field && field.api_fallback;
      if (apiFallback && Array.isArray(apiFallback[taxonId])) {
        apiFallback[taxonId].forEach(key => {
          if (!apiKeys.includes(key)) {
            apiKeys.push(key);
          }
        });
      }

      const sourcePriority = {
        alliance_allele_search_mouse: 0,
        alliance_allele_search_rat: 1,
        ensembl_allele: 2
      };

      return apiKeys
        .filter((key) => this.schema && this.schema.apis && this.schema.apis[key])
        .sort((a, b) => (sourcePriority[a] ?? 99) - (sourcePriority[b] ?? 99));
    },

    _getApiUnavailableMessage: function(inputEl) {
      const fieldName = inputEl && inputEl.length ? inputEl.attr("name") : "";
      const taxonId = this._getOrganismTaxonId();
        if (!taxonId && (fieldName === FIELD_NAMES.GENE || fieldName === FIELD_NAMES.ALLELE)) {
        return _("Please select an organism model first.");
      }
      return _("Search is not available for the selected organism.");
    },

    // Resolves the api the given field/input is currently using, so
    // messages below can name the actual external source instead of
    // hardcoding a provider name.
    _getActiveApiLabel: function(inputEl) {
      const fieldName = inputEl && inputEl.length ? inputEl.attr("name") : "";
      const field = this._getFieldSchemaByName(fieldName);
      if (!field) return "";
      const apiKey = this._resolveApiKeyForInput(field.api, inputEl);
      return (apiKey && this.schema?.apis?.[apiKey]?.label) || "";
    },

    _getNoResultsMessage: function(inputEl) {
      const apiLabel = this._getActiveApiLabel(inputEl);
      if (apiLabel) {
        return `${_("No results found in")} ${apiLabel} ${_("for this search. You can enter one manually.")}`;
      }
      return _("No results found. You can enter one manually");
    },

    _getRequestErrorMessage: function(inputEl, error) {
      const rawError = (error && error.message ? error.message : error || "").toString();
      const lowerError = rawError.toLowerCase();

      const isBrowserNetworkError =
        lowerError.includes("networkerror") ||
        lowerError.includes("failed to fetch") ||
        lowerError.includes("load failed");

      if (isBrowserNetworkError) {
        const apiLabel = this._getActiveApiLabel(inputEl);
        if (apiLabel) {
          return `${apiLabel} ${_("lookup failed (the server could not reach the external service). You can still enter the value manually.")}`;
        }
      }

      return `${_("Request error")}: ${rawError}`;
    },

    // Short display badge for a search result ("MGI", "Alliance", "Ensembl"...).
    // Entirely schema-driven: `apis[apiKey].source_tag` is the static badge,
    // and `apis[apiKey].dynamic_source_tag` opts into refining it per-result
    // via `_getAllianceSourceTag` (xref_catalog) and the selected organism's
    // `allele_source_label`. No API key or database name is known here.
    _getApiSourceTag: function(apiKey, itemData = null) {
      const apiDef = (this.schema && this.schema.apis && this.schema.apis[apiKey]) || null;
      if (!apiDef) return "";

      if (apiDef.dynamic_source_tag) {
        const dynamic = this._getAllianceSourceTag(itemData);
        if (dynamic) return dynamic;
        const preset = this._getSelectedOrganismPreset();
        if (preset && preset.allele_source_label) return preset.allele_source_label;
      }

      return apiDef.source_tag || "";
    },

    // Identifies which external database an Alliance Genome search result
    // came from, purely from the schema's `xref_catalog` (accession prefix
    // and, as a secondary signal, the species/provider text Alliance
    // returns alongside the item). No database name is known to this code.
    _getAllianceSourceTag: function(itemData) {
      if (!itemData) {
        return "";
      }

      const catalog = (this.schema && this.schema.xref_catalog) || {};
      const id = (itemData.id || itemData.primaryKey || "").toString();
      const idPrefix = (id.split(":")[0] || "").toUpperCase();
      if (catalog[idPrefix]) {
        return catalog[idPrefix].label || idPrefix;
      }

      const provider = (
        itemData?.species?.dataProviderShortName ||
        itemData?.species?.commonNames ||
        ""
      ).toString().toUpperCase();
      if (provider) {
        for (const [prefix, entry] of Object.entries(catalog)) {
          const aliases = [prefix, ...(entry.provider_aliases || [])];
          if (aliases.some((alias) => provider.includes(alias))) {
            return entry.label || prefix;
          }
        }
      }
      return "";
    },

    _extractAccessionByPrefix: function(text, prefix) {
      if (!text || !prefix) {
        return "";
      }
      const normalizedPrefix = String(prefix).trim().toUpperCase();
      const safePrefix = normalizedPrefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(`\\b${safePrefix}:[A-Za-z0-9._-]+`, "i");
      const match = String(text).match(regex);
      return match ? match[0].replace(/\s+/g, "") : "";
    },

    _extractGeneSymbolCandidate: function(rawValue) {
      if (!rawValue) {
        return "";
      }

      const text = String(rawValue).trim();
      if (!text) {
        return "";
      }

      const withoutUri = text.replace(/^https?:\/\/\S+\s*[-—]\s*/i, "");
      const firstSegment = withoutUri.split(",")[0].trim();
      const match = firstSegment.match(/[A-Za-z][A-Za-z0-9._-]*/);
      return match ? match[0] : "";
    },

    _normalizeMutationType: function(rawValue) {
      const value = (rawValue || "").toString().trim();
      if (!value) {
        return "";
      }

      const lower = value.toLowerCase();

      // Filter generic descriptors that do not represent mutation classes.
      const genericPatterns = [
        /^allele with\b/,
        /^allele of\b/,
        /^allele\b$/,
        /associated variant/
      ];

      if (genericPatterns.some((pattern) => pattern.test(lower))) {
        return "";
      }

      // Keep informative mutation labels from curated sources (e.g. MouseMine/MGI),
      // while only filtering the clearly generic descriptors above.
      return value;
    },

    _getSelectedGeneSymbolForAlleles: function(inputEl) {
      if (!inputEl || !inputEl.length) {
        return "";
      }

      const instanceEl = inputEl.closest(".fdf-instance");
      const geneInput = instanceEl.find("[name='gene_search']").first();
      if (!geneInput.length) {
        return "";
      }

      const geneItemData = geneInput.data("item-data") || {};
      const selectedGeneLabel = (geneInput.data("selected-label") || "").toString().trim();
      if (geneItemData.symbol) {
        return this._extractGeneSymbolCandidate(geneItemData.symbol) || String(geneItemData.symbol).trim();
      }
      if (selectedGeneLabel) {
        return this._extractGeneSymbolCandidate(selectedGeneLabel) || selectedGeneLabel;
      }

      const rawGeneValue = (geneInput.val() || "").toString().trim();
      if (!rawGeneValue) {
        return "";
      }

      const valueParts = rawGeneValue.split("—");
      const inferred = (valueParts.length > 1
        ? valueParts[valueParts.length - 1]
        : rawGeneValue).trim();
      return this._extractGeneSymbolCandidate(inferred) || inferred;
    },

    _mapApiResultItem: function(item, api) {
      if (!item || !api || !api.mapper) {
        return null;
      }

      const resolvePathWithFallback = (pathExpr) => {
        const paths = String(pathExpr || "").split("||").map((p) => p.trim()).filter(Boolean);
        for (const path of paths) {
          const value = getNestedValue(item, path, "");
          if (value !== null && value !== undefined && String(value).trim() !== "") {
            return value;
          }
        }
        return "";
      };

      const renderMapperTemplate = (template) => {
        if (!template || typeof template !== "string") {
          return "";
        }

        const isSingleWrapper = /^\s*\{\{[^{}]+\}\}\s*$/.test(template);

        if (isSingleWrapper) {
          return resolvePathWithFallback(template.slice(2, -2).trim());
        }

        return template.replace(/\{\{([^}]+)\}\}/g, (match, expr) => {
          return resolvePathWithFallback(expr.trim());
        });
      };

      let label = "";
      let id = "";
      let sublabel = "";

      if (api.mapper.label) {
        label = renderMapperTemplate(api.mapper.label);
      } else if (api.mapper.strategy === "obo_ontology") {
        label = item.label || item.name || item.id || "";
      }

      if (api.mapper.sublabel) {
        sublabel = renderMapperTemplate(api.mapper.sublabel);
      } else if (api.mapper.strategy === "obo_ontology") {
        sublabel = item.description || item.obo_id || "";
      }
      sublabel = this._sanitizeSublabel(sublabel);

      if (api.mapper.id) {
        id = renderMapperTemplate(api.mapper.id);
      } else if (api.mapper.strategy === "obo_ontology") {
        id = item.iri || item.id || "";
      }

      if (api.mapper.id_candidates) {
        id = this._resolveIdCandidates(item, api.mapper.id_candidates) || id;
      }

      if (!label || !id) {
        return null;
      }

      let extra = {};
      if (api.mapper.extra && typeof api.mapper.extra === "object") {
        Object.entries(api.mapper.extra).forEach(([key, tplValue]) => {
          if (typeof tplValue !== "string") {
            extra[key] = tplValue;
            return;
          }

          extra[key] = tplValue.replace(/\{\{([^}]+)\}\}/g, (match, expr) => {
            const parts = String(expr).split("||").map((p) => p.trim()).filter(Boolean);
            for (const part of parts) {
              const val = getNestedValue(item, part, "");
              if (val !== null && val !== undefined && String(val).trim() !== "") {
                return String(val);
              }
            }
            return "";
          });
        });

        if (!extra.mutation_type && extra.consequenceType) {
          extra.mutation_type = extra.consequenceType;
        }

        const mutationCandidates = [
          extra.mutation_type,
          extra.consequenceType,
          extra.alterationType,
          extra.type,
          extra.soTerm,
          extra.category
        ];
        let normalizedMutationType = "";
        for (const candidate of mutationCandidates) {
          normalizedMutationType = this._normalizeMutationType(candidate);
          if (normalizedMutationType) {
            break;
          }
        }
        extra.mutation_type = normalizedMutationType;

        if (!extra.gene_symbol && extra.geneSymbol) {
          extra.gene_symbol = extra.geneSymbol;
        }
        if (!extra.gene_id && extra.geneAccessionId) {
          extra.gene_id = extra.geneAccessionId;
        }
      }

      return { label, id, sublabel, extra };
    },

    _filterApiResults: function(items, api, inputEl) {
      if (!Array.isArray(items)) {
        return items;
      }

      let filteredItems = items;

      if (api && api.result_filter) {
        filteredItems = filteredItems.filter((item) => {
          return Object.entries(api.result_filter).every(([path, expected]) => {
            return getNestedValue(item, path, null) === expected;
          });
        });
      }

      if (api && api.filter_by_selected_gene) {
        const geneFiltered = this._filterItemsBySelectedGene(filteredItems, inputEl);
        filteredItems = geneFiltered;
      }

      if (api && Array.isArray(api.exclude_categories) && api.exclude_categories.length > 0) {
        const excluded = new Set(api.exclude_categories.map((v) => String(v).toLowerCase()));
        filteredItems = filteredItems.filter((item) => {
          const category = (getNestedValue(item, "category", "") || "").toString().toLowerCase();
          return !excluded.has(category);
        });
      }

      if (api && Array.isArray(api.result_label_keywords) && api.result_label_keywords.length > 0) {
        const keywords = api.result_label_keywords
          .map((k) => String(k || "").trim().toLowerCase())
          .filter(Boolean);

        if (keywords.length > 0) {
          filteredItems = filteredItems.filter((item) => {
            const label = (item.label || item.name || "").toString().toLowerCase();
            const description = (item.description || "").toString().toLowerCase();
            return keywords.some((kw) => label.includes(kw) || description.includes(kw));
          });
        }
      }

      return filteredItems;
    },

    _filterItemsBySelectedGene: function(items, inputEl) {
      if (!Array.isArray(items) || !inputEl || !inputEl.length) {
        return [];
      }

      const instanceEl = inputEl.closest(".fdf-instance");
      const geneInput = instanceEl.find("[name='gene_search']").first();
      if (!geneInput.length) {
        return [];
      }

      const geneItemData = geneInput.data("item-data") || {};
      const selectedGeneLabel = (geneInput.data("selected-label") || "").toString().trim();
      const rawGeneValue = (geneInput.val() || "").toString().trim();
      const valueParts = rawGeneValue.split("—");
      const inferredGeneFromValue = valueParts.length > 1
        ? valueParts[valueParts.length - 1].trim()
        : rawGeneValue;

      const rawGeneSymbol = (geneItemData.symbol || selectedGeneLabel || inferredGeneFromValue || "").toString().trim();
      const geneSymbol = this._extractGeneSymbolCandidate(rawGeneSymbol) || rawGeneSymbol;
      const geneName = (geneItemData.name || "").toString().trim();

      if (!geneSymbol && !geneName) {
        return items;
      }

      const escapedGeneSymbol = geneSymbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const symbolPattern = geneSymbol ? new RegExp(`^${escapedGeneSymbol}(<|$)`, "i") : null;
      const geneSymbolLower = geneSymbol.toLowerCase();
      const geneNameLower = geneName.toLowerCase();

      const strictMatches = items.filter((item) => {
        const alleleSymbol = (getNestedValue(item, "fields.symbol", "") || "").toString().trim();
        const alleleName = (getNestedValue(item, "fields.name", "") || "").toString().trim();

        if (symbolPattern && symbolPattern.test(alleleSymbol)) {
          return true;
        }

        const alleleSymbolLower = alleleSymbol.toLowerCase();
        const alleleNameLower = alleleName.toLowerCase();

        if (geneSymbolLower && alleleSymbolLower.startsWith(geneSymbolLower)) {
          return true;
        }

        if (geneNameLower && alleleNameLower.startsWith(geneNameLower)) {
          return true;
        }

        return false;
      });

      if (strictMatches.length > 0) {
        return strictMatches;
      }

      if (geneSymbolLower) {
        const containsMatches = items.filter((item) => {
          const alleleSymbol = (getNestedValue(item, "fields.symbol", "") || "").toString().trim().toLowerCase();
          return alleleSymbol.includes(geneSymbolLower);
        });

        if (containsMatches.length > 0) {
          return containsMatches;
        }

        return items;
      }

      return items;
    },

    // `resolvedApiKey` should be the api the selection actually came from
    // (field.api_by_taxon can route different organisms to different apis
    // with different mapper.id/mapper.scheme shapes); it defaults to the
    // field's static `api`/`search_api` for fields that don't vary by taxon.
    _getControlledSubjectRuleForField: function(field, resolvedApiKey) {
      if (!field || !field.output || field.output.path !== "subjects") {
        return null;
      }

      const tpl = field.output.tpl;
      if (!tpl || typeof tpl !== "object") {
        return null;
      }

      const apiKey = resolvedApiKey || field.api || field.search_api;
      const mapper = this.schema?.apis?.[apiKey]?.mapper;

      let scheme = "";
      const schemeTpl = tpl.subjectScheme;
      if (typeof schemeTpl === "string") {
        if (schemeTpl === "$scheme") {
          scheme = mapper?.scheme || "";
        } else if (!schemeTpl.startsWith("$")) {
          scheme = schemeTpl;
        }
      }

      const requireValueUri = Object.prototype.hasOwnProperty.call(tpl, "valueURI");

      let requireHttpUri = false;
      if (requireValueUri && typeof tpl.valueURI === "string") {
        if (tpl.valueURI.startsWith("http://") || tpl.valueURI.startsWith("https://")) {
          requireHttpUri = true;
        } else if (tpl.valueURI === "$id" || tpl.valueURI === "$value") {
          const mapperId = mapper?.id;
          if (typeof mapperId === "string" && (mapperId.startsWith("http://") || mapperId.startsWith("https://"))) {
            requireHttpUri = true;
          }
        }
      }

      return {
        scheme,
        requireValueUri,
        requireHttpUri,
      };
    },

    _validateControlledApiSelection: function(instanceEl, section, field) {
      const errors = [];
      if (field.type !== "api_search") {
        return errors;
      }

      const fieldInput = instanceEl.find(`[name="${field.id}"]`).first();
      if (fieldInput.length === 0) {
        return errors;
      }

      const enteredValue = (fieldInput.val() || "").toString().trim();
      if (!enteredValue) {
        return errors;
      }

      // Prefer the api actually used for this selection (stored at click
      // time); fall back to resolving it from the current organism when
      // that data isn't available (e.g. a manually-typed value).
      const storedApiKey = (fieldInput.data("selected-api-key") || "").toString().trim();
      const resolvedApiKey = storedApiKey || this._resolveApiKeyForInput(field.api || field.search_api, fieldInput);
      const rule = this._getControlledSubjectRuleForField(field, resolvedApiKey);
      if (!rule) {
        return errors;
      }

      const selectedId = (fieldInput.data("selected-id") || "").toString().trim();

      if (!selectedId) {
        // No API selection: this is a manually-typed value. Only block it
        // when the field doesn't explicitly allow manual entry as a fallback.
        if (rule.requireValueUri && !field.allow_manual) {
          errors.push(`${field.label}: This service is temporarily unavailable. Please try again later.`);
        }
        return errors;
      }

      if (rule.requireHttpUri && !(selectedId.startsWith("http://") || selectedId.startsWith("https://"))) {
        errors.push(`${field.label}: selected identifier must be a valid URL.`);
      }

      return errors;
    },

    _clearValidationUI: function() {
      this.container.find(".fdf-field-error").remove();
      this.container.find(".fdf-validation-alert").remove();
      this.container.find(".fdf-invalid").removeClass("fdf-invalid");
    },

    _unlockSubmitButtons: function() {
      const form = this.container.closest('form');
      if (form.length > 0) {
        form.find("button[type='submit'], input[type='submit']")
          .prop('disabled', false)
          .removeClass('disabled');
      }
    },

    _getCreatorNameFromInstance: function(instanceEl) {
      const nameTypeInput = instanceEl.find(`[name="nameType"]`);
      const nameType = (nameTypeInput.val() || '').toString().trim();

      if (nameType === "Personal") {
        const givenNameInput = instanceEl.find(`[name="given_name"]`);
        const familyNameInput = instanceEl.find(`[name="family_name"]`);
        const givenName = (givenNameInput.val() || '').toString().trim();
        const familyName = (familyNameInput.val() || '').toString().trim();
        return `${givenName} ${familyName}`.trim();
      } else if (nameType === "Organizational") {
        const orgInput = instanceEl.find(`[name="organization_name"]`);
        return (orgInput.val() || '').toString().trim();
      }

      return '';
    },

    _getCreatorNameTypeFromInstance: function(instanceEl) {
      const nameTypeInput = instanceEl.find(`[name="nameType"]`);
      return (nameTypeInput.val() || '').toString().trim();
    },

    _getCreatorIdentityFromInstance: function(instanceEl) {
      const nameType = this._getCreatorNameTypeFromInstance(instanceEl);
      const givenName = (instanceEl.find(`[name="given_name"]`).val() || '').toString().trim();
      const familyName = (instanceEl.find(`[name="family_name"]`).val() || '').toString().trim();
      const organizationName = (instanceEl.find(`[name="organization_name"]`).val() || '').toString().trim();
      const creatorName = this._getCreatorNameFromInstance(instanceEl);

      return {
        creator_name: creatorName,
        nameType,
        givenName,
        familyName,
        organization_name: organizationName,
        identityPresent: Boolean(givenName || familyName || organizationName || creatorName)
      };
    },

    _addFieldError: function(instanceEl, field, message) {
      const fieldName = field.id;
      const fieldInputs = instanceEl.find(`[name="${fieldName}"]`);
      let formGroup = fieldInputs.first().closest('.form-group');

      if (formGroup.length === 0) {
        formGroup = instanceEl;
      }

      formGroup.find('.fdf-field-error').remove();

      if (fieldInputs.length > 0) {
        fieldInputs.addClass('fdf-invalid');
      }

      formGroup.append(`<div class="fdf-field-error" style="color:#d9534f; margin-top:4px; font-size:12px;">${message}</div>`);
    },

    _getFieldValueForValidation: function(instanceEl, field) {
      const fieldInputs = instanceEl.find(`[name="${field.id}"]`);

      if (fieldInputs.length === 0) {
        return null;
      }

      if (field.type === 'checkbox_group') {
        return fieldInputs.filter(':checked').map(function() { return $(this).val(); }).get();
      }

      if (field.type === 'multi_select') {
        return fieldInputs.val() || [];
      }

      if (field.type === 'preset_or_search') {
        const selectVal = fieldInputs.val();
        const searchInput = instanceEl.find('.fdf-search-input').first();
        return {
          selectValue: selectVal,
          selectedId: searchInput.data('selected-id') || '',
          typedValue: (searchInput.val() || '').trim()
        };
      }

      return (fieldInputs.val() || '').toString().trim();
    },

    _validateRequiredField: function(instanceEl, field) {
      const value = this._getFieldValueForValidation(instanceEl, field);

      if (field.type === 'checkbox_group') {
        return Array.isArray(value) && value.length > 0;
      }

      if (field.type === 'multi_select') {
        return Array.isArray(value) && value.length > 0;
      }

      if (field.type === 'preset_or_search') {
        if (!value || !value.selectValue) return false;
        if (value.selectValue === '__OTHER__') {
          if (field.allow_manual) {
            return !!(value.selectedId || value.typedValue);
          }
          return !!value.selectedId;
        }
        return true;
      }

      return value !== null && value !== undefined && String(value).trim() !== '';
    },

    _validateVocabularyField: function(instanceEl, field) {
      const errors = [];
      const value = this._getFieldValueForValidation(instanceEl, field);

      if (field.type === 'select') {
        const allowed = (field.options || []).map(opt => String(opt.value));
        if (value && !allowed.includes(String(value))) {
          errors.push(`${field.label}: value is not in the allowed options.`);
        }
      }

      if (field.type === 'checkbox_group') {
        const allowed = new Set((field.options || []).map(opt => String(opt.value)));
        const invalid = (Array.isArray(value) ? value : []).filter(v => !allowed.has(String(v)));
        if (invalid.length > 0) {
          errors.push(`${field.label}: invalid option(s): ${invalid.join(', ')}.`);
        }
      }

      if (field.type === 'multi_select' && field.vocabulary) {
        const vocabItems = this.schema.vocabularies?.[field.vocabulary]?.items || [];
        const allowed = new Set(vocabItems.map(item => String(item.id)));
        const selected = Array.isArray(value) ? value : [];
        const invalid = selected.filter(v => !allowed.has(String(v)));
        if (invalid.length > 0) {
          errors.push(`${field.label}: value does not follow the configured vocabulary.`);
        }
      }

      if (field.type === 'preset_or_search' && value && value.selectValue) {
        const vocabItems = this.schema.vocabularies?.[field.vocabulary]?.items || [];
        const allowed = new Set(vocabItems.map(item => String(item.id)));

        if (value.selectValue !== '__OTHER__' && !allowed.has(String(value.selectValue))) {
          errors.push(`${field.label}: selected value is not in the configured vocabulary.`);
        }

        if (value.selectValue === '__OTHER__' && !field.allow_manual && !value.selectedId) {
          errors.push(`${field.label}: please pick a valid result from the controlled vocabulary search.`);
        }
      }

      return errors;
    },

    _validatePatternField: function(instanceEl, field) {
      const errors = [];
      if (!field.pattern) {
        return errors;
      }

      const value = this._getFieldValueForValidation(instanceEl, field);
      if (!value) {
        return errors;
      }

      try {
        const regex = new RegExp(field.pattern);
        if (!regex.test(String(value))) {
          errors.push(`${field.label}: invalid format.`);
        }
      } catch (e) {
        // Silently ignore invalid regex patterns
      }

      return errors;
    },

    validateFDFForm: function() {
      this._clearValidationUI();

      const allMessages = [];

      this.schema.sections.forEach((section) => {
        const sectionDiv = this.container.find(`[data-section-id="${section.id}"]`);
        if (sectionDiv.length === 0 || !sectionDiv.is(':visible')) {
          return;
        }

        const instances = sectionDiv.find('.fdf-instance');
        instances.each((idx, el) => {
          const instanceEl = $(el);

          (section.fields || []).forEach((field) => {
            const fieldInputs = instanceEl.find(`[name="${field.id}"]`);
            if (fieldInputs.length === 0) {
              return;
            }

            const fieldGroup = fieldInputs.first().closest('.form-group');
            if (fieldGroup.length > 0 && !fieldGroup.is(':visible')) {
              return;
            }

            if (field.required) {
              const ok = this._validateRequiredField(instanceEl, field);
              if (!ok) {
                const message = `${field.label}: required field.`;
                this._addFieldError(instanceEl, field, message);
                allMessages.push(`[${section.title}] ${message}`);
              }
            }

            const vocabErrors = this._validateVocabularyField(instanceEl, field);
            vocabErrors.forEach((msg) => {
              this._addFieldError(instanceEl, field, msg);
              allMessages.push(`[${section.title}] ${msg}`);
            });

            const patternErrors = this._validatePatternField(instanceEl, field);
            patternErrors.forEach((msg) => {
              this._addFieldError(instanceEl, field, msg);
              allMessages.push(`[${section.title}] ${msg}`);
            });

            const controlledErrors = this._validateControlledApiSelection(instanceEl, section, field);
            controlledErrors.forEach((msg) => {
              this._addFieldError(instanceEl, field, msg);
              allMessages.push(`[${section.title}] ${msg}`);
            });
          });
        });
      });

      if (allMessages.length > 0) {
        const uniqueMessages = [...new Set(allMessages)];
        const html = `
          <div class="fdf-validation-alert alert alert-error" style="margin-bottom:12px;">
            <strong>${_("FDF validation failed.")}</strong>
            <ul style="margin-top:8px; margin-bottom:0;">
              ${uniqueMessages.map(msg => `<li>${msg}</li>`).join('')}
            </ul>
          </div>
        `;
        this.container.prepend(html);
        this._unlockSubmitButtons();
        return false;
      }

      return true;
    },

    renderForm: function () {
      if (!this.schema.sections || !this.schema.sections.length) {
        this.container.append(`<p>${_("No sections found in schema.")}</p>`);
        return;
      }

      this.schema.sections.forEach((section) => {
        const isRepeatable = section.repeatable;

        const sectionEl = $(`
          <div class="fdf-section" data-section-id="${section.id}" style="margin-bottom:20px;">
            <h3>${section.icon || ""} ${section.title || _("Section")}</h3>
            <div class="fdf-fields"></div>
          </div>
        `);

        if (section.condition) sectionEl.hide();

        const fieldsContainer = sectionEl.find(".fdf-fields");
        const minInstanceCount = isRepeatable ? this.getMinInstanceCount(section) : 1;

        if (section.fields && section.fields.length) {
          const buildInstance = (index = 0) => {
            const instanceEl = $(
              "<div class='fdf-instance' style='padding:10px; border:1px solid #ddd; margin-bottom:10px; border-radius:5px;'></div>"
            );

            section.fields.forEach((field) => {
              const prefillValue = this.getPrefillValue(field, section, index);
              let fieldHtml = this.buildField(field, index, prefillValue, {
                readOnly: false,
              });
              instanceEl.append(fieldHtml);
            });

            if (isRepeatable && index >= minInstanceCount) {
              const removeBtn = $(
                `<button type="button" class="btn btn-sm btn-danger" style="margin-top:10px;">- ${_("Remove")}</button>`
              );
              removeBtn.on("click", () => instanceEl.remove());
              instanceEl.append(removeBtn);
            }

            return instanceEl;
          };

          const instanceCount = isRepeatable ? this.getInstanceCount(section) : 1;
          for (let i = 0; i < instanceCount; i += 1) {
            fieldsContainer.append(buildInstance(i));
          }

          if (isRepeatable) {
            const addBtn = $(
              `<button type="button" class="btn btn-sm btn-primary" style="margin-top:5px; margin-bottom:10px;">+ ${_("Add")}</button>`
            );
            addBtn.on("click", () => {
              const newInstance = buildInstance(fieldsContainer.children(".fdf-instance").length);
              fieldsContainer.append(newInstance);
              this._applyFieldVisibility(newInstance);
            });
            sectionEl.append(addBtn);
          }
        }

        this.container.append(sectionEl);
      });
    },

    _getSectionPrefillEntries: function(section) {
      if (!this.prefillData || !section || !section.output || section.output.mode !== "collect_object" || !section.output.path) {
        return [];
      }

      const list = getNestedValue(this.prefillData, section.output.path, []);
      if (section.id === "contributors") {
        return this._getContributorPrefillEntries(list);
      }

      return Array.isArray(list) ? list : [];
    },

    _getSectionPrefillEntry: function(section, index) {
      const entries = this._getSectionPrefillEntries(section);
      return Array.isArray(entries) ? entries[index] || null : null;
    },

    bindConditions: function () {
      const self = this;
      this.schema.sections.forEach((section) => {
        if (!section.condition) return;

        if (section.condition.type === "checkbox_includes") {
          const fieldId = section.condition.field_id;
          const value = section.condition.value;

          $(document).on("change", `input[name="${fieldId}"]`, () => {
            const checkedValues = $(`input[name="${fieldId}"]:checked`)
              .map(function () {
                return this.value;
              })
              .get();

            if (checkedValues.includes(value)) {
              $(`[data-section-id="${section.id}"]`).slideDown();
            } else {
              $(`[data-section-id="${section.id}"]`).slideUp();
            }
          });
        }
        
        // Handle organism_trigger conditions (for strain section)
        if (section.condition.type === "organism_trigger") {
          const trigger = section.condition.trigger;
          
          // Listen for changes on organism select/preset fields
          $(document).on("change", "select[name='organism_choice']", function() {
            self._evaluateOrganismTrigger(section, trigger);
          });
          
          // Also listen to search input for __OTHER__ selections
          $(document).on("input", "select[name='organism_choice'] + .fdf-search-input", function() {
            setTimeout(() => self._evaluateOrganismTrigger(section, trigger), 100);
          });
        }
      });

      // Clear organism-dependent fields when organism changes
      $(document).on("change", "select[name='organism_choice']", function() {
        self._clearOrganismDependentFields();
      });
      $(document).on("input", "select[name='organism_choice'] + .fdf-search-input", function() {
        setTimeout(() => self._clearOrganismDependentFields(), 150);
      });
    },

    _getFieldMetadata: function(fieldId) {
      if (!this.schema || !this.schema.sections) {
        return null;
      }
      for (const section of this.schema.sections) {
        if (section.fields) {
          for (const field of section.fields) {
            if (field.id === fieldId) {
              return field;
            }
          }
        }
      }
      return null;
    },

    _clearDependentFields: function(fieldId, instanceEl) {
      const field = this._getFieldMetadata(fieldId);
      if (!field) return;

      // Clear fields that depend on this field
      if (Array.isArray(field.clear_dependent_fields)) {
        field.clear_dependent_fields.forEach(depFieldId => {
          const depField = instanceEl.find("[name='" + depFieldId + "']").first();
          if (depField.length) {
            depField.val("").trigger("change");
            depField.siblings(".fdf-search-input").val("").removeData("selected-id").removeData("selected-label");
          }
        });
      }

      // Clear fields that display data from this field
      if (field.update_display_field) {
        instanceEl.find("[name='" + field.update_display_field + "']").val("");
      }
    },

    _updateDependentFields: function(fieldId, instanceEl, mappedExtra) {
      const field = this._getFieldMetadata(fieldId);
      if (!field) return;

      this._applyBoundDependentFields(fieldId, instanceEl, mappedExtra);
    },

    // Generic propagation for fields declared via `dependent_on_field` +
    // `bind_to` (e.g. mutationType_display depends on allele_search and
    // binds to "consequenceType || geneMutationType"; xenopus_line_type
    // depends on genetic_background and binds to "lineType"). Any field in
    // the schema can opt into this by declaring those two properties — no
    // field id or provider-specific branch needed here. `bind_to` may list
    // several candidate keys separated by "||", tried in order, matching
    // the fallback convention used throughout the schema's own templates.
    _applyBoundDependentFields: function(sourceFieldId, instanceEl, mappedExtra) {
      if (!this.schema || !Array.isArray(this.schema.sections) || !mappedExtra) return;

      this.schema.sections.forEach((section) => {
        (section.fields || []).forEach((depField) => {
          if (depField.dependent_on_field !== sourceFieldId || !depField.bind_to) return;

          const depInputEl = instanceEl.find("[name='" + depField.id + "']").first();
          if (!depInputEl.length) return;

          const candidateKeys = String(depField.bind_to).split("||").map((k) => k.trim()).filter(Boolean);
          let boundValue = "";
          for (const key of candidateKeys) {
            const val = mappedExtra[key];
            if (val !== undefined && val !== null && String(val).trim() !== "") {
              boundValue = String(val).trim();
              break;
            }
          }
          if (!boundValue) return;

          if (depInputEl.is("select")) {
            const hasOption = depInputEl.find("option").filter(function() {
              return $(this).val() === boundValue;
            }).length > 0;
            if (hasOption) {
              depInputEl.val(boundValue).trigger("change");
            }
          } else {
            depInputEl.val(boundValue);
          }
        });
      });
    },

    _resolveTemplateExpression: function(template, item) {
      if (!template || typeof template !== "string") return "";

      const isSingleWrapper = /^\s*\{\{[^{}]+\}\}\s*$/.test(template);
      const expr = isSingleWrapper ? template.slice(2, -2).trim() : template;

      // Split on "||" and try each path in order (fallback behavior)
      const paths = String(expr).split("||").map(p => p.trim()).filter(Boolean);
      for (const path of paths) {
        const value = getNestedValue(item, path, "");
        if (value !== null && value !== undefined && String(value).trim() !== "") {
          return value;
        }
      }

      // If single wrapper, return empty. Otherwise process remaining templates in string
      if (isSingleWrapper) {
        return "";
      }

      // For complex templates, replace all {{...}} patterns
      return template.replace(/\{\{([^}]+)\}\}/g, (match, exprInner) => {
        const pathsInner = exprInner.split("||").map(p => p.trim()).filter(Boolean);
        for (const path of pathsInner) {
          const val = getNestedValue(item, path, "");
          if (val !== null && val !== undefined && String(val).trim() !== "") {
            return String(val);
          }
        }
        return "";
      });
    },

    _clearFieldValue: function(fieldName, containerEl) {
      const selector = "[name='" + fieldName + "']";
      const inputs = containerEl ? containerEl.find(selector) : $(selector);

      inputs.each(function() {
        const $input = $(this);
        if ($input.hasClass("fdf-api-input")) {
          $input.val("").removeAttr("data-selected-id").removeAttr("data-selected-label");
          $input.closest(".fdf-api-input-wrapper").nextAll(".xrefs-display").remove();
        } else if ($input.is("select")) {
          $input.val("").trigger("change");
        } else {
          $input.val("");
        }
        $input.siblings(".fdf-search-input").val("").removeData("selected-id").removeData("selected-label");
      });
    },

    _clearOrganismDependentFields: function () {
      const self = this;
      if (!this.schema || !this.schema.sections) {
        return;
      }

      // Find all fields marked as organism_dependent
      const fieldsToClean = [];
      const secondaryClears = {}; // Track dependent field relationships

      this.schema.sections.forEach(section => {
        if (section.fields) {
          section.fields.forEach(field => {
            if (field.organism_dependent === true) {
              fieldsToClean.push(field.id);
              if (Array.isArray(field.clear_dependent_fields)) {
                secondaryClears[field.id] = field.clear_dependent_fields;
              }
            }
          });
        }
      });

      // Clear all organism-dependent fields
      fieldsToClean.forEach(fieldId => {
          self._clearFieldValue(fieldId);
      });

      // Clear secondary dependent fields (e.g. xenopus_line_type when genetic_background is cleared)
      for (const parentFieldId in secondaryClears) {
        secondaryClears[parentFieldId].forEach(childFieldId => {
            self._clearFieldValue(childFieldId);
        });
      }

      // Trigger change on first gene field to re-evaluate visibility of dependent fields
        $("[name='" + FIELD_NAMES.GENE + "'].fdf-api-input").first().trigger("change");
    },

    _applyFieldVisibility: function (scopeEl) {
      const self = this;
      if (this._isApplyingFieldVisibility) {
        return;
      }

      const scope = scopeEl && scopeEl.length ? scopeEl : this.container;
      this._isApplyingFieldVisibility = true;

      const allFields = this.schema.sections.flatMap(section => section.fields || []);

      allFields.forEach(field => {
        if (!field.visible_if) return;

        const controllerName = field.visible_if.field;
        const expectedValue = field.visible_if.value;
        const requireNotEmpty = Boolean(field.visible_if.not_empty);
        const requireChecked = Boolean(field.visible_if.checked);
        const taxonIn = Array.isArray(field.visible_if.taxon_in)
          ? field.visible_if.taxon_in.map((value) => String(value))
          : [];
        const taxonNotIn = Array.isArray(field.visible_if.taxon_not_in)
          ? field.visible_if.taxon_not_in.map((value) => String(value))
          : [];

        const targets = scope.find(`[name='${field.id}']`).closest(".form-group");
        if (!targets.length) return;

        targets.each(function () {
          const target = $(this);
          const instanceEl = target.closest(".fdf-instance");
          const sectionEl = target.closest(".fdf-section");
          const lookupRoot = instanceEl.length ? instanceEl : sectionEl;
          const controller = lookupRoot.find(`[name='${controllerName}']`).first();

          if (!controller.length) {
            target.hide();
            return;
          }

          const currentValueRaw = controller.val();
          const currentValue = currentValueRaw !== undefined && currentValueRaw !== null
            ? String(currentValueRaw).trim()
            : "";

          let shouldShow = false;
          if (requireChecked) {
            shouldShow = controller.is(":checked");
          } else if (requireNotEmpty) {
            shouldShow = currentValue !== "";
          } else {
            shouldShow = currentValueRaw === expectedValue;
          }

          const selectedTaxonId = String(self._getOrganismTaxonId() || "");
          if (taxonIn.length > 0 && !taxonIn.includes(selectedTaxonId)) {
            shouldShow = false;
          }
          if (taxonNotIn.length > 0 && taxonNotIn.includes(selectedTaxonId)) {
            shouldShow = false;
          }

          if (shouldShow) {
            const primaryInput = target.find(`[name='${field.id}']`).first();
            if (
              primaryInput.length &&
              field.default !== undefined &&
              field.default !== null &&
              String(primaryInput.val() || "").trim() === ""
            ) {
              primaryInput.val(field.default);
            }
            target.show();
          } else {
            target.hide();
            target.find("input, select, textarea").each(function () {
              const el = $(this);
              if (el.is(":checkbox") || el.is(":radio")) {
                if (el.prop("checked")) {
                  el.prop("checked", false).trigger("change");
                }
              } else {
                if (el.val()) {
                  el.val("").trigger("change");
                }
              }
            });
          }
        });
      });

      this._isApplyingFieldVisibility = false;

      if (!this._fieldVisibilityBound) {
        this._fieldVisibilityBound = true;
        this.container.on("change.fdfVisibility input.fdfVisibility", "input, select, textarea", function () {
          const changedInput = $(this);
          const instanceEl = changedInput.closest(".fdf-instance");
          self._applyFieldVisibility(instanceEl.length ? instanceEl : null);
        });
      }
    },
    
    _evaluateOrganismTrigger: function(section, trigger) {
      // Get selected organism from preset or search
      const organismSelect = $(`select[name='organism_choice']`);
      const selectedValue = organismSelect.val();
      
      if (!selectedValue || selectedValue === "") {
        $(`[data-section-id="${section.id}"]`).slideUp();
        return;
      }
      
      // Check if it's a preset with triggers
      const vocab = this.schema.vocabularies?.organism_presets;
      const preset = vocab?.items?.find(item => item.id === selectedValue);
      
      if (preset && preset.triggers && preset.triggers.includes(trigger)) {
        $(`[data-section-id="${section.id}"]`).slideDown();
      } else if (selectedValue === "__OTHER__") {
        // For __OTHER__, check if a search result was selected
        const searchInput = organismSelect.siblings(".fdf-search-input");
        const selectedId = searchInput.data("selected-id");
        
        // If a specific organism was searched/selected, we might still want to show strain
        // For now, hide it for __OTHER__ unless we have more context
        $(`[data-section-id="${section.id}"]`).slideUp();
      } else {
        $(`[data-section-id="${section.id}"]`).slideUp();
      }
    },

    evalConditions: function () {
      // Evaluate all conditional sections based on current form state
      // This is called after rendering to show/hide sections for pre-filled values
      this.schema.sections.forEach((section) => {
        if (!section.condition) return;

        if (section.condition.type === "checkbox_includes") {
          const fieldId = section.condition.field_id;
          const value = section.condition.value;
          const checkedValues = $(`input[name="${fieldId}"]:checked`)
            .map(function () {
              return this.value;
            })
            .get();


          if (checkedValues.includes(value)) {
            $(`[data-section-id="${section.id}"]`).show();
          } else {
            $(`[data-section-id="${section.id}"]`).hide();
          }
        }
        
        // Evaluate organism_trigger conditions
        if (section.condition.type === "organism_trigger") {
          const trigger = section.condition.trigger;
          const organismSelect = $(`select[name='organism_choice']`);
          const selectedValue = organismSelect.val();
          
          if (!selectedValue || selectedValue === "") {
            $(`[data-section-id="${section.id}"]`).hide();
            return;
          }
          
          // Check if it's a preset with triggers
          const vocab = this.schema.vocabularies?.organism_presets;
          const preset = vocab?.items?.find(item => item.id === selectedValue);
          
          if (preset && preset.triggers && preset.triggers.includes(trigger)) {
            $(`[data-section-id="${section.id}"]`).show();
          } else {
            $(`[data-section-id="${section.id}"]`).hide();
          }
        }
      });
    },

    buildField: function (field, index = 0, prefillValue = null, renderOptions = {}) {
      let html = "";
      const fieldId = `${field.id}_${index}`;
      const fieldName = `${field.id}${field.repeatable ? "[]" : ""}`;
      const isReadOnly = Boolean(renderOptions && renderOptions.readOnly);
      const disabledAttr = isReadOnly ? "disabled" : "";
      
      // Convert prefillValue based on field type
      let value = '';
      let apiSelectedId = '';
      let apiSelectedLabel = '';
      let apiDisplayValue = '';
      
      // For multi_select and checkbox_group, keep arrays as arrays
      if ((field.type === 'multi_select' || field.type === 'checkbox_group') && Array.isArray(prefillValue)) {
        value = prefillValue;
      }
      // For preset_or_search, keep object {id, label} as-is if present.
      // `id` is optional here: a manually-typed / no-URI value (e.g. a
      // vocabulary-less "Other" entry) still comes back as {label, id:
      // undefined, ...} from getPrefillValue, and must still be recognized
      // as an object so it isn't JSON.stringify'd into the HTML value attr.
      else if (field.type === 'preset_or_search' && prefillValue && typeof prefillValue === 'object' && prefillValue.label) {
        value = prefillValue;
      }
      // For other types, convert to appropriate type
      else if (prefillValue !== null && prefillValue !== undefined) {
        if (typeof prefillValue === 'object') {
          // For api_search fields with object values, try to extract display value
          if (field.type === 'api_search') {
            // If it's a wrapped object from wrap_array mode (ORCID/ROR)
            if (prefillValue.nameIdentifier) {
              // ORCID format with {nameIdentifier: "..."}
              value = prefillValue.nameIdentifier;
              apiSelectedId = prefillValue.nameIdentifier;
              apiSelectedLabel = prefillValue.nameIdentifier;
            } 
            // ROR format might be {affiliation: "..." } with nested structure
            else if (prefillValue.affiliation) {
              // Prefer the persisted ROR identifier when available.
              const affiliationLabel = typeof prefillValue.affiliation === 'string'
                ? prefillValue.affiliation
                : (prefillValue.affiliation && prefillValue.affiliation.name) || '';
              const affiliationId = (prefillValue.affiliationIdentifier || prefillValue.id || '').toString().trim();

              if (affiliationLabel) {
                value = affiliationLabel;
                apiSelectedLabel = affiliationLabel;
              }

              if (affiliationId) {
                apiSelectedId = affiliationId;
              } else if (affiliationLabel) {
                // Fallback only if no identifier exists.
                apiSelectedId = affiliationLabel;
              }
            }
            // For gene_search/chem_search result objects with label and id
            else if (prefillValue.label && prefillValue.id) {
              value = prefillValue.label;
              apiSelectedId = prefillValue.id;
              apiSelectedLabel = prefillValue.label;
            }
            else if (prefillValue.display && prefillValue.id) {
              // If it's an API response object with 'display' property
              value = prefillValue.display;
              apiSelectedId = prefillValue.id;
              apiSelectedLabel = prefillValue.display;
            }
            // If it's a result with 'matched-name' and 'id'
            else if (prefillValue['matched-name'] && prefillValue.id) {
              value = prefillValue['matched-name'];
              apiSelectedId = prefillValue.id;
              apiSelectedLabel = prefillValue['matched-name'];
            }
            // If it's a ROR result with 'name' and 'id'
            else if (prefillValue.name && prefillValue.id) {
              value = prefillValue.name;
              apiSelectedId = prefillValue.id;
              apiSelectedLabel = prefillValue.name;
            }
            // Fallback: try to use id if exists
            else if (prefillValue.id) {
              value = prefillValue.id;
              apiSelectedId = prefillValue.id;
              apiSelectedLabel = prefillValue.id;
            }
            // Last fallback: stringify
            else {
              const stringified = JSON.stringify(prefillValue);
              value = stringified.length > 100 ? stringified.substring(0, 100) + "..." : stringified;
            }
          } else {
            // For other object types, try to extract sensible value
            value = typeof prefillValue === 'string' ? prefillValue : JSON.stringify(prefillValue);
          }
        } else {
          value = String(prefillValue);
          if (field.type === 'api_search' && (value.startsWith('http://') || value.startsWith('https://'))) {
            apiSelectedId = value;
            apiSelectedLabel = value;
          }
        }
      }
      
      switch (field.type) {
        case "text":
          const textValue = value !== "" ? value : (field.default || "");
          html = `
            <div class="form-group">
              <label for="${fieldId}">${this._formatFieldLabel(field)}</label>
              <input type="text" class="form-control" id="${fieldId}" name="${fieldName}" value="${textValue}" placeholder="${field.placeholder || ""}" ${field.required ? "required" : ""} ${disabledAttr}/>
              ${field.help ? `<small class="form-text text-muted">${field.help}</small>` : ""}
            </div>
          `;
          break;

        case "number":
          html = `
            <div class="form-group">
              <label for="${fieldId}">${this._formatFieldLabel(field)}</label>
              <input type="number" class="form-control" id="${fieldId}" name="${fieldName}" placeholder="${field.placeholder || ""}" 
                min="${field.min || ""}" max="${field.max || ""}" value="${value !== "" ? value : (field.default || "")}" ${field.required ? "required" : ""} ${disabledAttr}/>
              ${field.help ? `<small class="form-text text-muted">${field.help}</small>` : ""}
            </div>
          `;
          break;

        case "textarea":
          html = `
            <div class="form-group">
              <label for="${fieldId}">${this._formatFieldLabel(field)}</label>
              <textarea class="form-control" id="${fieldId}" name="${fieldName}" rows="${field.rows || 3}" placeholder="${field.placeholder || ""}" ${field.required ? "required" : ""} ${disabledAttr}>${value !== "" ? value : (field.default || "")}</textarea>
              ${field.help ? `<small class="form-text text-muted">${field.help}</small>` : ""}
            </div>
          `;
          break;

        case "select":
          const options = field.options || [];
          html = `
            <div class="form-group">
              <label for="${fieldId}">${this._formatFieldLabel(field)}</label>
              <select class="form-control" id="${fieldId}" name="${fieldName}" ${field.required ? "required" : ""} ${disabledAttr}>
                ${options
                  .map(
                    (o) =>
                      `<option value="${o.value}" ${
                        o.value === (value !== "" ? value : field.default) ? "selected" : ""
                      }>${o.label}</option>`
                  )
                  .join("")}
              </select>
            </div>
          `;
          break;

        case "checkbox_group":
          const checkedValues = Array.isArray(value) ? value : value ? [value] : [];
          if (field.id === 'intervention_types') {
          }
          html = `
            <div class="form-group">
              <label>${this._formatFieldLabel(field)}</label>
              <div>
                ${(field.options || [])
                  .map(
                    (opt) => {
                      const isChecked = checkedValues.includes(opt.value);
                      if (field.id === 'intervention_types') {
                      }
                      return `
                  <div class="checkbox">
                    <label>
                      <input type="checkbox" name="${fieldName}" value="${opt.value}" ${
                        isChecked ? "checked" : ""
                      } ${disabledAttr}>
                      ${opt.emoji || ""} ${opt.label}
                    </label>
                  </div>
                `;
                    }
                  )
                  .join("")}
              </div>
            </div>
          `;
          break;

        case "multi_select": {
          const vocab = this.schema.vocabularies?.[field.vocabulary];
          const items = vocab?.items || [];
          const selectedValues = Array.isArray(value) ? value : value ? [value] : [];

          if (field.id === 'contributor_roles') {
          }

          html = `
            <div class="form-group">
              <label>${this._formatFieldLabel(field)}</label>
              <select class="form-control" multiple name="${fieldName}" ${field.required ? "required" : ""} ${disabledAttr}>
                ${items
                  .map(
                    (item) => {
                      const isSelected = selectedValues.includes(item.id);
                      if (field.id === 'contributor_roles' && isSelected) {
                      }
                      return `<option value="${item.id}" ${
                        isSelected ? "selected" : ""
                      }>${item.label}</option>`;
                    }
                  )
                  .join("")}
              </select>
              ${field.help ? `<small class="form-text text-muted">${field.help}</small>` : ""}
            </div>
          `;
          break;
        }

        case "preset_or_search": {
            const vocab = this.schema.vocabularies?.[field.vocabulary];
            const items = vocab?.items || [];
            
            // Handle prefill value that might be string or object {id, label}
            let searchInputValue = "";
            let searchInputId = "";
            let selectValue = value;
            
            if (value && typeof value === "object" && value.label) {
              // prefillValue is an object with a label and (optionally) an external ID;
              // a manually-entered value with no resolved ID still lands here.
              searchInputValue = value.label;
              searchInputId = value.id || "";
              selectValue = "__OTHER__";
            } else if (value && value !== "__OTHER__" && !items.some(item => item.id === value)) {
              // value might be the label text when __OTHER__ was used
              searchInputValue = value;
              selectValue = "__OTHER__";
            }

            html = `
                <div class="form-group">
                <label>${this._formatFieldLabel(field)}</label>
                <select class="form-control" id="${fieldId}" name="${fieldName}" ${field.required ? "required" : ""} ${disabledAttr}>
                        <option value="">-- Select --</option>
                        ${items.map(item => `
                            <option value="${item.id}" ${
                              item.id === selectValue ? "selected" : ""
                            }>${item.emoji || ""} ${item.display || item.label}</option>
                        `).join("")}
                    </select>
                    <input type="text" class="form-control fdf-search-input" data-api="${field.search_api || ""}" data-allow-manual="${field.allow_manual ? "true" : ""}" 
                      ${searchInputId ? `data-selected-id="${searchInputId}" data-selected-label="${searchInputValue}"` : ""}
                      placeholder="${field.placeholder || _("Search…")}" value="${searchInputValue}" 
                      style="margin-top:5px; display:${selectValue === "__OTHER__" ? "block" : "none"};" ${disabledAttr}/>
                    <div class="fdf-api-results" style="border:1px solid #ccc; display:none; max-height:150px; overflow:auto;"></div>
                </div>
            `;
            break;
        }

        case "api_search":
          // Apply field.default / field.default_label when no value has been set
          if (!apiSelectedId && !value && field.default) {
            apiSelectedId = field.default;
            apiSelectedLabel = field.default_label || field.default;
            value = apiSelectedId;
          }
          if (apiSelectedId) {
            apiDisplayValue = (apiSelectedLabel && apiSelectedLabel !== apiSelectedId)
              ? `${apiSelectedId} — ${apiSelectedLabel}`
              : apiSelectedId;
          } else {
            apiDisplayValue = value;
          }
          const hasValue = Boolean(apiSelectedId || (value && String(value).trim() !== ""));
          html = `
            <div class="form-group">
              <label>${this._formatFieldLabel(field)}</label>
              <div class="fdf-api-input-wrapper">
                <input type="text" class="form-control fdf-api-input" data-api="${field.api}" id="${fieldId}" name="${fieldName}" value="${apiDisplayValue}" ${apiSelectedId ? `data-selected-id="${apiSelectedId}" data-selected-label="${apiSelectedLabel || value}"` : ""} ${field.autofill_label_to && field.autofill_label_to.length ? `data-autofill-label-to="${field.autofill_label_to.join(',')}"` : ""} placeholder="${field.placeholder || ""}" ${(field.allow_manual && !isReadOnly) ? "" : "readonly"} ${field.required ? "required" : ""} ${disabledAttr} style="padding-right:${hasValue ? "32px" : "12px"};"/>
                <button type="button" class="fdf-clear-btn" title="Clear selection" style="display:${hasValue ? "block" : "none"}">&times;</button>
              </div>
              <div class="fdf-api-results" style="border:1px solid #ccc; display:none; max-height:150px; overflow:auto;"></div>
              ${field.help ? `<small class="form-text text-muted">${field.help}</small>` : ""}
            </div>
          `;
          break;

        default:
          html = `<p>Field type "${field.type}" not implemented yet</p>`;
      }

      return html;
    },

    getInstanceCount: function(section) {
      if (!section.repeatable) {
        return 1;
      }

      const configuredInitialCount = Number(section.initial_instances);
      const initialCount = Number.isFinite(configuredInitialCount) && configuredInitialCount >= 0
        ? Math.floor(configuredInitialCount)
        : 1;

      if (!this.prefillData) {
        return initialCount;
      }

      // Case 1: Section has output -> use collect_object mode
      if (section.output) {
        if (section.output.mode !== "collect_object" || !section.output.path) {
          return initialCount;
        }

        let list = getNestedValue(this.prefillData, section.output.path, []);
        if (section.id === "contributors") {
          list = this._getContributorPrefillEntries(list);
        }
        if (Array.isArray(list) && list.length > 0) {
          return list.length;
        }
        return initialCount;
      }

      // Case 2: Section is repeatable but has NO output
      // This means fields append to shared arrays (like "subjects")
      // Count instances by finding how many items in the output path match the template pattern
      if (section.fields && section.fields.length > 0) {
        // Find first field with output
        const firstField = section.fields.find(f => f.output && f.output.path);
        if (!firstField) return initialCount;

        const outputPath = firstField.output.path;
        const dataArray = getNestedValue(this.prefillData, outputPath, []);
        
        if (!Array.isArray(dataArray) || dataArray.length === 0) {
          return initialCount;
        }

        // If section has subject_scheme defined, filter by that (more reliable than prefix)
        if (section.subject_scheme) {
          let count = 0;
          dataArray.forEach(item => {
            if (item.subjectScheme === section.subject_scheme) {
              count++;
            }
          });
          
          // Return count (even if 0, in which case we default to 1)
          // This prevents fallback logic from counting wrong items
          return count > 0 ? count : initialCount;
        }

        // Fallback: Count items that match this section's pattern (by prefix)
        // For example, if it's "genes" section, count items where subject starts with "Gene: "
        if (firstField.output.tpl && firstField.output.tpl.subject) {
          const pattern = firstField.output.tpl.subject;
          // Extract prefix like "Gene: " from pattern like "Gene: $label"
          const dollarIndex = pattern.indexOf('$');
          const prefix = dollarIndex >= 0 ? pattern.substring(0, dollarIndex) : pattern;
          
          let count = 0;
          dataArray.forEach(item => {
            if (item.subject && item.subject.startsWith(prefix)) {
              count++;
            }
          });
          
          if (count > 0) {
            return count;
          }
        }
      }

      return initialCount;
    },

    getMinInstanceCount: function(section) {
      if (!section || !section.repeatable) {
        return 1;
      }

      const configuredMinCount = Number(section.min_instances);
      if (Number.isFinite(configuredMinCount) && configuredMinCount >= 0) {
        return Math.floor(configuredMinCount);
      }

      const configuredInitialCount = Number(section.initial_instances);
      if (Number.isFinite(configuredInitialCount) && configuredInitialCount === 0) {
        return 0;
      }

      return 1;
    },

    getTemplateValueKey: function(template) {
      const keys = Object.keys(template || {});
      for (let i = 0; i < keys.length; i += 1) {
        const key = keys[i];
        const value = template[key];
        if (typeof value === "string" && value.indexOf("$value") >= 0) {
          return key;
        }
      }
      return null;
    },

    _getContributorPrefillEntries: function(list) {
      if (!Array.isArray(list)) {
        return [];
      }

      return list
        .map((item) => this._normalizeContributorPrefillItem(item))
        .filter((item) => Boolean(item));
    },

    _normalizeContributorPrefillItem: function(item) {
      if (!item || typeof item !== "object") {
        return null;
      }

      const normalized = Object.assign({}, item);
      const fullName = String(normalized.name || "").trim();
      const contributorType = String(normalized.contributorType || "").trim();
      let nameType = String(normalized.nameType || "").trim();

      if (!nameType) {
        if (normalized.organization_name || (!fullName && (normalized.affiliation || normalized.nameIdentifiers))) {
          nameType = "Organizational";
        } else if (fullName) {
          nameType = "Personal";
        }
      }

      normalized.nameType = nameType;
      normalized.contributorType = contributorType || "Researcher";

      if (nameType === "Personal") {
        const givenName = String(normalized.givenName || "").trim();
        const familyName = String(normalized.familyName || "").trim();

        if ((!givenName || !familyName) && fullName) {
          const commaParts = fullName.split(",").map((part) => part.trim()).filter(Boolean);
          let derivedGiven = "";
          let derivedFamily = "";

          if (commaParts.length >= 2) {
            derivedFamily = commaParts[0] || "";
            derivedGiven = commaParts.slice(1).join(", ") || "";
          } else {
            const nameParts = fullName.split(/\s+/).filter(Boolean);
            if (nameParts.length >= 2) {
              derivedFamily = nameParts.pop() || "";
              derivedGiven = nameParts.join(" ");
            } else {
              derivedGiven = fullName;
            }
          }

          if (!normalized.givenName && derivedGiven) {
            normalized.givenName = derivedGiven;
          }
          if (!normalized.familyName && derivedFamily) {
            normalized.familyName = derivedFamily;
          }
        }
      }

      if (nameType === "Organizational" && !String(normalized.organization_name || "").trim() && fullName) {
        normalized.organization_name = fullName;
      }

      const identityPresent = Boolean(
        String(normalized.givenName || "").trim() ||
        String(normalized.familyName || "").trim() ||
        String(normalized.organization_name || "").trim() ||
        fullName
      );

      if (!identityPresent) {
        return null;
      }

      return normalized;
    },

    getPrefillValue: function(field, section, instanceIndex) {
      if (!this.prefillData) {
        return null;
      }

      if (!field.output && field.bind_to) {
        const sourceField = (section.fields || []).find((candidate) => {
          return candidate && candidate.output && candidate.output.obj &&
            Object.prototype.hasOwnProperty.call(candidate.output.obj, field.bind_to);
        });

        if (!sourceField || !sourceField.output || !sourceField.output.path) {
          return null;
        }

        const dataValue = getNestedValue(this.prefillData, sourceField.output.path, null);
        if (!Array.isArray(dataValue) || dataValue.length === 0) {
          return null;
        }

        const sourceTpl = sourceField.output.tpl || {};
        const sourceScheme = sourceTpl.subjectScheme && !String(sourceTpl.subjectScheme).startsWith("$")
          ? sourceTpl.subjectScheme
          : null;

        let matchingItems = dataValue;
        if (sourceScheme) {
          matchingItems = dataValue.filter((item) => item && item.subjectScheme === sourceScheme);
        }

        const selectedItem = matchingItems[instanceIndex] || null;
        if (!selectedItem || selectedItem[field.bind_to] === undefined || selectedItem[field.bind_to] === null) {
          return null;
        }
        const boundValue = selectedItem[field.bind_to];
        if (typeof boundValue === "string" && boundValue.trim().startsWith("$")) {
          return null;
        }
        return boundValue;
      }

      if (!field.output) {
        return null;
      }

      const output = field.output;

      if (section.repeatable && section.output && section.output.mode === "collect_object") {
        if (output.obj_key) {
          let list = getNestedValue(this.prefillData, section.output.path, []);
          if (section.id === "contributors") {
            list = this._getContributorPrefillEntries(list);
          }
          const item = Array.isArray(list) ? list[instanceIndex] : null;
          if (!item) {
            return null;
          }
          const value = item[output.obj_key] !== undefined ? item[output.obj_key] : null;

          // wrap_array_from_array (multi_select stored as array of mapped objects):
          // rebuild the array of vocabulary IDs from the stored objects so the
          // multi_select prefills correctly.
          if (Array.isArray(value) && output.mode === "wrap_array_from_array" && output.map) {
            const idKey = Object.keys(output.map).find((key) => {
              const tplVal = output.map[key];
              return typeof tplVal === "string" && (tplVal === "$id" || tplVal === "$value");
            });
            if (idKey) {
              const ids = value
                .map((entry) => (entry && typeof entry === "object") ? entry[idKey] : null)
                .filter((v) => v !== null && v !== undefined && v !== "");
              return ids.length > 0 ? ids : null;
            }
          }

          // If the object key contains an array with wrap_array mode, extract the value
          if (Array.isArray(value) && output.mode === "wrap_array" && output.map) {
            // The value is an array of objects created by wrap_array+map template
            // Extract the value that was stored via the template
            const hasValueKey = Object.values(output.map).some(v => v === "$value" || v === "$id");
            if (hasValueKey && value.length > 0) {
              // Return the first API result object (it will be rendered properly in buildField)
              return value[0];
            }
          }
          return value;
        }
      }

      if (!output.path) {
        return null;
      }

      const dataValue = getNestedValue(this.prefillData, output.path, null);
      
      if (dataValue === null || dataValue === undefined) {
        return null;
      }

      const mode = output.mode || "set";
      if (mode === "set" || mode === "set_int") {
        return dataValue;
      }

      if (mode === "append" || mode === "append_if" || mode === "wrap_array" || mode === "append_from_array") {
        if (!Array.isArray(dataValue)) {
          return dataValue;
        }

        // For append with vocabulary (like organism_choice with preset_or_search)
        if (mode === "append" && field.vocabulary && output.tpl) {
          
          // Build label -> ID map from vocabulary
          const vocab = this.schema.vocabularies?.[field.vocabulary];
          if (vocab && vocab.items) {
            const items = vocab.items || [];
            const labelToId = {};
            vocab.items.forEach(item => {
              labelToId[item.label.toLowerCase()] = item.id;
            });
            
            // Find which key in template was populated with $label
            const labelKeyInTemplate = Object.keys(output.tpl || {}).find(key => {
              const tplVal = output.tpl[key];
              return typeof tplVal === "string" && tplVal === "$label";
            });
            
            if (labelKeyInTemplate) {
              // For organism_choice, we need to filter by scheme to avoid matching other subjects
              let relevantItem = dataValue[0];
              if (output.tpl.subjectScheme && Array.isArray(dataValue)) {
                // Find first matching by scheme
                relevantItem = dataValue.find(item => item.subjectScheme === output.tpl.subjectScheme) || dataValue[0];
              }
              
              if (relevantItem && relevantItem[labelKeyInTemplate]) {
                const label = relevantItem[labelKeyInTemplate];
                
                // Special case: __OTHER__ means user selected/searched for a custom value
                const idKeyInTemplate = Object.keys(output.tpl || {}).find(key => {
                  const tplVal = output.tpl[key];
                  return typeof tplVal === "string" && tplVal === "$id";
                });
                if (idKeyInTemplate && relevantItem[idKeyInTemplate] === "__OTHER__") {
                  return label || "__OTHER__";
                }
                
                // If valueURI is a real ontology IRI (not in vocabulary), return object with id and label
                if (idKeyInTemplate && relevantItem[idKeyInTemplate] && 
                    relevantItem[idKeyInTemplate].startsWith("http") && 
                    !items.some(item => item.id === relevantItem[idKeyInTemplate])) {
                  return {
                    id: relevantItem[idKeyInTemplate],
                    label: label
                  };
                }
                
                // Extract just the label if it has prefix like "Strain: " 
                const labelMatch = label.match(/^[^:]*:\s*(.+)$|^(.+)$/);
                const cleanLabel = labelMatch ? (labelMatch[1] || labelMatch[2]) : label;
                const id = labelToId[cleanLabel.toLowerCase()];
                
                
                return id || null;
              }
            }
          }
        }

        // For append_from_array with vocabulary (multi_select or preset_or_search)
        if (mode === "append_from_array" && field.vocabulary) {
          // Build ID -> Label map from vocabulary
          const vocab = this.schema.vocabularies?.[field.vocabulary];
          if (!vocab || !vocab.items) {
            return dataValue;
          }

          const labelToId = {};
          vocab.items.forEach(item => {
            labelToId[item.label.toLowerCase()] = item.id;
          });

          // For other multi_select fields with append_from_array, extract labels and map to IDs
          const extractedIds = [];
          dataValue.forEach((item) => {
            // The template stores structure like {subject: "label", ...} or {contributorRole: "label", ...}
            // Find which key was populated with $label
            const labelKeyInTemplate = Object.keys(output.tpl || {}).find(key => {
              const tplVal = output.tpl[key];
              return typeof tplVal === "string" && tplVal === "$label";
            });

            if (labelKeyInTemplate && item[labelKeyInTemplate]) {
              const label = item[labelKeyInTemplate];
              const id = labelToId[label.toLowerCase()];
              if (id) {
                extractedIds.push(id);
              }
            }
          });
          return extractedIds.length > 0 ? extractedIds : null;
        }

        // For append_from_array with template (no vocabulary), extract the value from template fields
        if (mode === "append_from_array" && output.tpl && typeof output.tpl === "object") {
          // Find which key in the template was populated with $label or $value
          const valueKey = Object.keys(output.tpl).find(key => {
            const tplVal = output.tpl[key];
            return typeof tplVal === "string" && (tplVal === "$label" || tplVal === "$id" || tplVal === "$value");
          });
          
          // Extract the values that match the template
          const extractedValues = dataValue.map((item) => {
            if (typeof item === "object" && valueKey && item[valueKey]) {
              return item[valueKey];
            } else if (typeof item === "string") {
              return item;
            }
            return item;
          });
          
          return extractedValues.length > 0 ? extractedValues : null;
        }

        // For regular append mode with template (no vocabulary)
        if (output.tpl && typeof output.tpl === "object") {
          const valueKey = this.getTemplateValueKey(output.tpl);
          
          // For sections without section-level output that append subjects (repeatable OR non-repeatable)
          if (!section.output && output.tpl.subject) {
            // Extract pattern prefix like "Gene: " from pattern like "Gene: $label"
            // The part BEFORE the $ is the prefix, the part AFTER $ is the placeholder
            const pattern = output.tpl.subject;
            const dollarIndex = pattern.indexOf('$');
            const prefix = dollarIndex >= 0 ? pattern.substring(0, dollarIndex) : pattern;
            
            // Filter items that match this pattern
            // Priority: if the template itself declares a literal subjectScheme, use it
            // (e.g. gene_chromosome_location uses "GeneLocus", not the section's "GeneID")
            const tplScheme = output.tpl.subjectScheme && !output.tpl.subjectScheme.startsWith('$')
              ? output.tpl.subjectScheme : null;

            let matchingItems;
            if (tplScheme) {
              // Template has a literal subjectScheme → most precise filter
              matchingItems = dataValue.filter(item => item.subjectScheme === tplScheme);
            } else if (section.subject_scheme) {
              // If section defines a subject_scheme, filter by that
              matchingItems = dataValue.filter(item => 
                item.subjectScheme === section.subject_scheme
              );
            } else if (prefix) {
              // If there's a prefix like "Gene: ", only match items with that prefix
              matchingItems = dataValue.filter(item => 
                item.subject && item.subject.startsWith(prefix)
              );
            } else {
              // If no prefix and no scheme, match all items excluding known prefixes
              matchingItems = dataValue.filter(item => 
                item.subject && 
                !item.subject.startsWith("Gene: ") &&
                !item.subject.startsWith("Strain: ")
              );
            }
            
            // Get the item at the current instance index
            if (matchingItems.length > instanceIndex) {
              const preferred = matchingItems[instanceIndex];

              if (preferred && preferred.subject) {
                // The current schema declares no prefix (or a different one)
                // for this field, but the stored text may still carry the
                // legacy "Label: " prefix from before that field was
                // migrated. Strip whichever one actually matches.
                let stripPrefix = prefix;
                if (!stripPrefix) {
                  const legacyPrefix = LEGACY_SUBJECT_PREFIXES[field.id];
                  if (legacyPrefix && preferred.subject.startsWith(legacyPrefix)) {
                    stripPrefix = legacyPrefix;
                  }
                }

                // For plain text fields, return the raw value string (valueURI),
                // not a wrapped object (which would render as "{" in the input).
                if (field.type === "text") {
                  return preferred.valueURI !== undefined ? preferred.valueURI
                    : preferred.subject.substring(stripPrefix.length);
                }

                // For api_search / other fields, return the rich object
                const label = preferred.subject.substring(stripPrefix.length);
                return {
                  label: label,
                  id: preferred.valueURI,
                  display: label,
                  subject: preferred.subject,
                  subjectScheme: preferred.subjectScheme,
                  valueURI: preferred.valueURI
                };
              }
            }
            
            return null;
          }
          
          const matchesTemplate = (item) => {
            if (!item || typeof item !== "object") {
              return false;
            }
            return Object.keys(output.tpl).every((key) => {
              const tplVal = output.tpl[key];
              if (typeof tplVal === "string" && tplVal.indexOf("$value") >= 0) {
                return true;
              }
              return item[key] === tplVal;
            });
          };

          const preferred = section.repeatable && dataValue[instanceIndex]
            ? dataValue[instanceIndex]
            : dataValue.find(matchesTemplate) || dataValue[0];
          if (preferred && valueKey && preferred[valueKey] !== undefined) {
            return preferred[valueKey];
          }
          if (typeof preferred === "string") {
            return preferred;
          }
          return null;
        }

        if (section.repeatable && dataValue[instanceIndex] !== undefined) {
          return dataValue[instanceIndex];
        }

        return dataValue;
      }

      return null;
    },

    collectFormData: function() {
      /**
       * Collect the values of all fields in the form according to the schema's output configuration
       * Return a structured object ready to be JSON-stringified and sent to the server
       */
      const formData = {};
      const container = this.container;
      const schema = this.schema;

      schema.sections.forEach((section) => {
        const sectionDiv = container.find(`[data-section-id="${section.id}"]`);
        
        if (!section.repeatable) {
          const instance = sectionDiv.find(".fdf-instance").first();
          if (instance.length > 0) {
            section.fields.forEach((field) => {
              this.collectFieldValue(field, instance, formData, 0);
            });
          }
        } else {
          const instances = sectionDiv.find(".fdf-instance");
          
          if (section.output && section.output.mode === "collect_object") {
            const outputPath = section.output.path;
            if (!formData[outputPath]) {
              formData[outputPath] = [];
            }
            
            instances.each((index, el) => {
              const objData = {};
              const instanceEl = $(el);
              section.fields.forEach((field) => {
                this.collectObjectFieldValue(field, instanceEl, objData, index);
              });

              // Process deferred fields (fields with output.path instead of obj_key)
              if (objData._deferredFields && objData._deferredFields.length > 0) {
                objData._deferredFields.forEach((deferred) => {
                  this.collectFieldValue(deferred.field, deferred.instanceEl, formData, deferred.instanceIndex);
                });
                delete objData._deferredFields;
              }

              if (this._isMeaningfulCollectObjectEntry(section, objData)) {
                formData[outputPath].push(objData);
              }
            });
          } else {
            instances.each((index, el) => {
              section.fields.forEach((field) => {
                this.collectFieldValue(field, $(el), formData, index);
              });
            });
          }
        }
      });

      return formData;
    },

    _isMeaningfulCollectObjectEntry: function(section, objData) {
      if (!objData || typeof objData !== "object") {
        return false;
      }

      const sectionId = (section && section.id) ? String(section.id) : "";

      // Contributors must have an identity, otherwise default select values
      // (contributorType/nameType) would create empty ghost entries.
      if (sectionId === "contributors") {
        const name = String(objData.name || "").trim();
        const given = String(objData.givenName || "").trim();
        const family = String(objData.familyName || "").trim();
        return Boolean(name || given || family);
      }

      // Related identifiers must have an actual identifier.
      if (sectionId === "related_identifiers") {
        return Boolean(String(objData.relatedIdentifier || "").trim());
      }

      return Object.keys(objData).some((key) => {
        const val = objData[key];
        if (val === null || val === undefined) {
          return false;
        }
        if (typeof val === "string") {
          return Boolean(val.trim());
        }
        if (Array.isArray(val)) {
          return val.length > 0;
        }
        if (typeof val === "object") {
          return Object.keys(val).length > 0;
        }
        return true;
      });
    },

    collectObjectFieldValue: function(field, instanceEl, objData, instanceIndex) {
      /**
       * Collect the value of a field and add it to objData according to the field's output schema
       */
      if (!field.output) return;

      // Check if field has obj_key (for collect_object fields) OR path (for fields with separate output)
      const hasObjKey = field.output.obj_key !== undefined;
      const hasPath = field.output.path !== undefined;

      if (!hasObjKey && !hasPath) return;

      const fieldInput = instanceEl.find(`[name="${field.id}"]`);
      if (fieldInput.length === 0) return;

      // Do not serialize values from hidden conditional fields.
      const objectFieldWrapper = fieldInput.first().closest(".form-group");
      if (objectFieldWrapper.length > 0 && !objectFieldWrapper.is(":visible")) {
        return;
      }

      let value;
      let labelOverride = null;
      const fieldType = field.type;

      if (fieldType === "checkbox_group") {
        value = fieldInput.filter(":checked").map(function() {
          return $(this).val();
        }).get();
      } else if (fieldType === "multi_select") {
        value = fieldInput.val() || [];
      } else if (fieldType === "number") {
        const numVal = fieldInput.val();
        value = numVal ? parseInt(numVal, 10) : null;
      } else {
        value = fieldInput.val();

        // For api_search fields in collect_object mode, persist selected ID (not "id — label").
        if (field.type === "api_search") {
          const selectedId = (fieldInput.data("selected-id") || "").toString().trim();
          const selectedLabel = (fieldInput.data("selected-label") || "").toString().trim();

          if (selectedId) {
            value = selectedId;
            if (selectedLabel) {
              labelOverride = selectedLabel;
            }
          } else if (typeof value === "string" && value.includes(" — ")) {
            const [parsedId, ...labelParts] = value.split(" — ");
            const parsedLabel = labelParts.join(" — ").trim();
            if (parsedId && parsedLabel) {
              value = parsedId.trim();
              labelOverride = parsedLabel;
            }
          }
        }
      }

      if (!value && value !== 0) return;

      const objKey = field.output.obj_key;

      // Handle obj_key (normal collect_object field)
      if (hasObjKey) {
        if (field.output.mode === "wrap_array_from_array" && field.output.map && Array.isArray(value)) {
          if (!objData[objKey]) {
            objData[objKey] = [];
          }
          value.forEach((item) => {
            objData[objKey].push(this.applyTemplate(field.output.map, item, field));
          });
        } else if (field.output.mode === "wrap_array" && field.output.map) {
          if (!objData[objKey]) {
            objData[objKey] = [];
          }
          objData[objKey].push(this.applyTemplate(field.output.map, value, field, "", labelOverride));
        } else if (field.output.tpl && typeof field.output.tpl === "object") {
          objData[objKey] = this.applyTemplate(field.output.tpl, value, field, "", labelOverride);
        } else {
          objData[objKey] = value;
        }
      }
      // Handle path (field has separate output path like contributor_roles)
      else if (hasPath) {
        // Store metadata so collectFieldValue can handle it after collect_object processing
        if (!objData._deferredFields) {
          objData._deferredFields = [];
        }
        objData._deferredFields.push({
          field: field,
          value: value,
          instanceEl: instanceEl,
          instanceIndex: instanceIndex
        });
      }
    },

    // Generic, always-on: whenever a subject-producing field's selection
    // carried cross-references (any api_search field whose mapper declares
    // `xrefs`/`xref_from_extra`, via _parseXrefs/_buildXrefsFromMapper —
    // gene, allele, or any future field), persist each one as its own
    // subject entry — same label, its own subjectScheme/valueURI — so
    // DataCite gets a separate <subject> per external identifier instead
    // of only the field's single primary valueURI. `crossRefOf` records
    // which subjectScheme this identifier is attached to, so a section's
    // display_mapping.filter (which only lists the *primary* schemes it
    // cares about) still picks these up — see extract_fdf_section_data in
    // plugin.py. The "default" xref key is skipped: it just restates the
    // primary valueURI (see _buildXrefsFromMapper), not a real cross-ref.
    _emitXrefSubjects: function(targetArray, renderedValue, fieldInput, labelOverride, field) {
      if (!Array.isArray(targetArray) || !renderedValue || typeof renderedValue !== "object" || Array.isArray(renderedValue)) {
        return;
      }
      const xrefs = fieldInput.data("xrefs") || {};
      const subjectText = (labelOverride || renderedValue.subject || "").toString();
      const primaryScheme = renderedValue.subjectScheme;
      // A database name alone (e.g. "MGI") can be ambiguous once several
      // fields attach cross-references from the same provider to different
      // kinds of records (a gene vs. an allele are both looked up in MGI).
      // field.xref_concept names what *this* field's subject represents
      // ("Gene", "Allele"...) so the two stay distinguishable in the final
      // subjectScheme, without baking that concept into the provider name
      // itself (xref_catalog/mapper.xrefs labels stay reusable as-is).
      const concept = field && field.xref_concept;
      Object.entries(xrefs).forEach(([xrefKey, xref]) => {
        if (xrefKey === "default" || !xref || !xref.uri || !xref.label) return;
        // Skip the suffix if the provider's own label already ends with it
        // (e.g. "NCBI Gene" + "Gene" would otherwise read "NCBI Gene Gene").
        const alreadyHasConcept = concept &&
          xref.label.toLowerCase().endsWith(concept.toLowerCase());
        const scheme = (concept && !alreadyHasConcept) ? `${xref.label} ${concept}` : xref.label;
        targetArray.push(Object.assign({}, renderedValue, {
          subject: subjectText,
          subjectScheme: scheme,
          valueURI: xref.uri,
          crossRefOf: primaryScheme
        }));
      });
    },

    collectFieldValue: function(field, instanceEl, formData, instanceIndex) {
      /**
       * Collect the value of a field and add it to formData according to the field's output schema
       */
      if (!field.output) return;

      const fieldInput = instanceEl.find(`[name="${field.id}"]`);
      if (fieldInput.length === 0) return;

      // Do not serialize values from hidden conditional fields.
      const fieldWrapper = fieldInput.first().closest(".form-group");
      if (fieldWrapper.length > 0 && !fieldWrapper.is(":visible")) {
        return;
      }

      let value;
      let labelOverride = null;
      let extraContext = {};
      const fieldType = field.type;

      if (fieldType === "checkbox_group") {
        value = fieldInput.filter(":checked").map(function() {
          return $(this).val();
        }).get();
      } else if (fieldType === "multi_select") {
        value = fieldInput.val() || [];
      } else if (fieldType === "number") {
        const numVal = fieldInput.val();
        value = numVal ? parseInt(numVal, 10) : null;
      } else {
        value = fieldInput.val();

        // For api_search fields, keep stored ID for output while preserving label for $label
        if (field.type === "api_search") {
          const selectedId = (fieldInput.data("selected-id") || "").toString().trim();
          const selectedLabel = (fieldInput.data("selected-label") || "").toString().trim();
          const mappedExtra = fieldInput.data("mapped-extra");
          if (mappedExtra && typeof mappedExtra === "object") {
            extraContext = mappedExtra;
          }

          if (selectedId) {
            value = selectedId;
            if (selectedLabel) {
              labelOverride = selectedLabel;
            }
          } else if (typeof value === "string" && value.includes(" — ")) {
            const [parsedId, ...labelParts] = value.split(" — ");
            const parsedLabel = labelParts.join(" — ").trim();
            if (parsedId && parsedLabel) {
              value = parsedId.trim();
              labelOverride = parsedLabel;
            }
          }
        }
        
        // Special handling for preset_or_search when __OTHER__ is selected
        if (field.type === "preset_or_search" && value === "__OTHER__") {
          const searchInput = fieldInput.siblings(".fdf-search-input");
          if (searchInput.length > 0) {
            const selectedId = searchInput.data("selected-id");
            const selectedLabel = searchInput.data("selected-label");
            if (selectedId && selectedLabel) {
              value = selectedId;
              labelOverride = selectedLabel;
            } else {
              // Fallback to the input value if no selection was made
              const inputVal = searchInput.val();
              if (inputVal) {
                labelOverride = inputVal;
                value = "__OTHER__";
              }
            }
          }
        }
      }

      if (!value && value !== 0) return;

      const output = field.output;
      const path = output.path;
      const mode = output.mode || "set";
      const tpl = output.tpl;

      if (path) {
        const parts = path.split(".");
        let target = formData;
        for (let i = 0; i < parts.length - 1; i++) {
          if (!target[parts[i]]) {
            target[parts[i]] = {};
          }
          target = target[parts[i]];
        }

        const lastKey = parts[parts.length - 1];

        switch (mode) {
          case "set":
            target[lastKey] = value;
            break;
          case "set_int":
            target[lastKey] = parseInt(value, 10);
            break;
          case "append":
            if (!target[lastKey]) target[lastKey] = [];
            if (Array.isArray(target[lastKey])) {
              const creatorName = this._getCreatorNameFromInstance(instanceEl);
              const creatorNameType = this._getCreatorNameTypeFromInstance(instanceEl);
              const renderedValue = tpl ? this.applyTemplate(tpl, value, field, creatorName, labelOverride, creatorNameType, extraContext) : value;
              if (output.obj && renderedValue && typeof renderedValue === "object" && !Array.isArray(renderedValue)) {
                Object.assign(renderedValue, this.applyTemplate(output.obj, value, field, creatorName, labelOverride, creatorNameType, extraContext));
              }
              target[lastKey].push(renderedValue);
              this._emitXrefSubjects(target[lastKey], renderedValue, fieldInput, labelOverride, field);
            }
            break;
          case "append_if":
            if (!target[lastKey]) target[lastKey] = [];
            if (value) {
              const creatorName = this._getCreatorNameFromInstance(instanceEl);
              const creatorNameType = this._getCreatorNameTypeFromInstance(instanceEl);
              const renderedValue = tpl ? this.applyTemplate(tpl, value, field, creatorName, labelOverride, creatorNameType, extraContext) : value;
              if (output.obj && renderedValue && typeof renderedValue === "object" && !Array.isArray(renderedValue)) {
                Object.assign(renderedValue, this.applyTemplate(output.obj, value, field, creatorName, labelOverride, creatorNameType, extraContext));
              }
              target[lastKey].push(renderedValue);
              this._emitXrefSubjects(target[lastKey], renderedValue, fieldInput, labelOverride, field);
            }
            break;
          case "collect_object":
            break;
          case "append_from_array":
            if (!target[lastKey]) target[lastKey] = [];
            if (Array.isArray(value)) {
              value.forEach((item) => {
                target[lastKey].push(tpl ? this.applyTemplate(tpl, item, field) : item);
              });
            }
            break;
          case "wrap_array":
            if (!target[lastKey]) target[lastKey] = [];
            target[lastKey].push(this.applyTemplate(tpl, value, field));
            break;
        }
      }
    },

    applyTemplate: function(template, value, field, creatorName = "", labelOverride = null, creatorNameType = "", extraContext = {}) {
      /**
       * Applies a template to a value. The template can be a string with placeholders like $value, $id, $label, etc.
       * Templates can use $value, $label, $id, $scheme, $creator_name etc.
       */
      // If the field has a vocabulary, map ID to label for $label placeholders
      let labelValue = labelOverride || value;
      if (!labelOverride && field.vocabulary && this.schema && this.schema.vocabularies && this.schema.vocabularies[field.vocabulary]) {
        const vocab = this.schema.vocabularies[field.vocabulary];
        if (vocab.items && Array.isArray(vocab.items)) {
          const vocabItem = vocab.items.find(item => item.id === value);
          if (vocabItem) {
            labelValue = vocabItem.label;
          }
        }
      }

      const replacePlaceholders = (input) => {
        if (typeof input === "string") {
          let result = input
            .replace(/\$value/g, value)
            .replace(/\$id/g, value)
            .replace(/\$label/g, labelValue)
            .replace(/\$scheme/g, field.api && this.schema.apis[field.api]?.mapper?.scheme ? this.schema.apis[field.api].mapper.scheme : "")
            .replace(/\$mutation_type/g, (extraContext && extraContext.mutation_type) ? String(extraContext.mutation_type) : "")
            .replace(/\$creator_name/g, creatorName)
            .replace(/\$nameType/g, creatorNameType)
            .replace(/\$name/g, creatorName);

          if (extraContext && typeof extraContext === "object") {
            Object.entries(extraContext).forEach(([k, v]) => {
              const safeKey = String(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
              const token = new RegExp(`\\$${safeKey}`, "g");
              result = result.replace(token, v !== undefined && v !== null ? String(v) : "");
            });
          }

          return result;
        }
        if (Array.isArray(input)) {
          return input.map((item) => replacePlaceholders(item));
        }
        if (input && typeof input === "object") {
          const result = {};
          Object.keys(input).forEach((key) => {
            result[key] = replacePlaceholders(input[key]);
          });
          return result;
        }
        return input;
      };

      return replacePlaceholders(template);
    },

    // Declarative multi-branch id resolver: schemas can set mapper.id_candidates
    // to a list of URL templates to try in order, for APIs whose response can
    // carry the canonical identifier in different fields depending on what
    // upstream data is available for a given record (e.g. an Entrez id for
    // some organisms, an Ensembl id for others). The first candidate whose
    // placeholders all resolve to a value (and pass an optional "numeric"
    // check) wins. No API or database is known to this code.
    _resolveIdCandidates: function(itemData, candidates) {
      if (!itemData || !Array.isArray(candidates)) return "";

      for (const candidate of candidates) {
        const tpl = typeof candidate === "string" ? candidate : candidate.tpl;
        if (!tpl) continue;

        let allResolved = true;
        const resolved = tpl.replace(/\{\{([^}]+)\}\}/g, (match, path) => {
          const val = getNestedValue(itemData, path.trim(), "");
          if (val === "" || val === null || val === undefined) {
            allResolved = false;
            return "";
          }
          if (candidate.numeric && !/^\d+$/.test(String(val).trim())) {
            allResolved = false;
          }
          return String(val).trim();
        });

        if (allResolved) return resolved;
      }

      return "";
    },

    // Generic last-resort resolver: used only when neither the schema's
    // mapper.xrefs entry nor xref_catalog supplied an explicit `uri`.
    // identifiers.org natively resolves "PREFIX:accession" compact
    // identifiers (MGI:, RGD:, ZFIN:, FlyBase, WormBase, Ensembl, NCBI
    // gene, ...), so no per-database knowledge needs to live here.
    _resolveIdentifierUri: function(id) {
      if (!id) return "";

      const rawId = String(id).trim();
      if (rawId.startsWith("http://") || rawId.startsWith("https://")) {
        return rawId;
      }

      return `https://identifiers.org/${rawId}`;
    },
    
    _parseXrefs: function(itemData, xrefsConfig) {
      // Parse xrefs from API response based on schema configuration
      const xrefs = {};

      const resolvePathExpression = (expr) => {
        if (!expr) return "";
        const alternatives = String(expr)
          .split("||")
          .map((part) => part.trim())
          .filter(Boolean);
        for (const candidate of alternatives) {
          const value = getNestedValue(itemData, candidate, "");
          if (value !== null && value !== undefined && String(value).trim() !== "") {
            return String(value).trim();
          }
        }
        return "";
      };
      
      if (!xrefsConfig || !itemData) return xrefs;
      
      Object.entries(xrefsConfig).forEach(([dbKey, config]) => {
        // Check condition if present
        if (config.condition) {
          const conditionPath = config.condition.replace(/\{\{([^}]+)\}\}/g, "$1").trim();
          const conditionValue = resolvePathExpression(conditionPath);
          if (!conditionValue) return; // Skip this xref if condition not met
        }
        
        // Extract id
        let id = "";
        if (config.id) {
          id = config.id.replace(/\{\{([^}]+)\}\}/g, (match, path) => 
            resolvePathExpression(path.trim())
          );
        }
        
        // Get label
        const label = config.label || dbKey.toUpperCase();
        
        // Extract uri from config if present (supports {{placeholders}})
        let uri = "";
        if (config.uri) {
          uri = config.uri.replace(/\{\{([^}]+)\}\}/g, (match, path) => 
            resolvePathExpression(path.trim())
          );
        }
        
        if (id) {
          if (dbKey === "ncbi_gene" && !/^\d+$/.test(id) && !uri) {
            return;
          }
          xrefs[dbKey] = {
            id,
            uri: uri || this._resolveIdentifierUri(id, dbKey),
            label
          };
        }
      });
      
      return xrefs;
    },


    // Best-effort, schema-driven enrichment fetch: some apis only expose a
    // useful field (e.g. a curated mutation description) on a per-record
    // detail endpoint, not in their search-result list. When
    // mapper.detail_fetch is declared, this resolves its `url` template
    // against the selected search-result item, fetches it, and resolves
    // `detail_fetch.extra` templates against the *fetched* record (so they
    // can use nested/array-filter paths like
    // "relatedNotes.[?noteType.name=mutation_description].freeText").
    // Returns {} on any failure — this is always optional enrichment, never
    // a requirement for completing a selection.
    _fetchMapperDetailEnrichment: async function(detailFetch, itemData) {
      const resolveAgainst = (source, template) => {
        if (!template || typeof template !== "string") return "";
        return template.replace(/\{\{([^}]+)\}\}/g, (match, path) => {
          const val = getNestedValue(source, path.trim(), "");
          return val !== null && val !== undefined ? String(val) : "";
        });
      };

      const url = resolveAgainst(itemData, detailFetch.url);
      if (!url) return {};

      let detailData;
      try {
        const res = await fetch(url, {
          headers: detailFetch.headers || { Accept: "application/json" },
          credentials: detailFetch.credentials || "same-origin"
        });
        if (!res.ok) return {};
        detailData = await res.json();
      } catch (e) {
        return {};
      }

      const extraTemplates = detailFetch.extra || {};
      const enrichment = {};
      Object.entries(extraTemplates).forEach(([key, tpl]) => {
        const resolved = resolveAgainst(detailData, tpl).trim();
        if (resolved) {
          enrichment[key] = resolved;
        }
      });
      return enrichment;
    },

    // Fallback cross-reference builder for mappers that don't declare an
    // explicit `mapper.xrefs` block (see _parseXrefs above for that fully
    // declarative path). Every piece of provider-specific knowledge here
    // comes from the schema:
    //  - mapper.id, when a full URL template, becomes the item's own
    //    "default" cross-reference.
    //  - mapper.xref_from_extra names the `mapper.extra` field that holds a
    //    "PREFIX:accession" style identifier; the PREFIX is looked up in
    //    the schema's top-level `xref_catalog` to get the target
    //    database's label and URI template ({{id}} / {{id_suffix}}).
    // This function has no built-in notion of any specific API or
    // database — schemas without these fields simply get no derived xrefs.
    _buildXrefsFromMapper: function(itemData, mapperConfig) {
      const xrefs = {};
      if (!itemData || !mapperConfig) return xrefs;

      const resolveTemplate = (template) => {
        if (!template) return "";
        return template.replace(/\{\{([^}]+)\}\}/g, (match, path) => {
          return getNestedValue(itemData, path.trim(), "") || "";
        });
      };

      const mapperId = mapperConfig.id || "";
      if (mapperId.startsWith("http://") || mapperId.startsWith("https://")) {
        const resolvedUri = resolveTemplate(mapperId);
        const rawId = (itemData.id || itemData.primaryKey || "").toString().trim();
        if (resolvedUri) {
          xrefs["default"] = {
            id: rawId || resolvedUri,
            uri: resolvedUri,
            label: mapperConfig.scheme || "Identifier"
          };
        }
      }

      const extraKey = mapperConfig.xref_from_extra;
      const extraTemplate = extraKey && mapperConfig.extra && mapperConfig.extra[extraKey];
      if (extraTemplate) {
        const accession = resolveTemplate(extraTemplate).trim();
        if (accession) {
          const colonIndex = accession.indexOf(":");
          const prefix = (colonIndex > -1 ? accession.slice(0, colonIndex) : accession).toUpperCase();
          const suffix = colonIndex > -1 ? accession.slice(colonIndex + 1) : accession;
          const catalog = (this.schema && this.schema.xref_catalog) || {};
          const provider = catalog[prefix];
          if (provider && provider.uri) {
            xrefs[provider.db || prefix.toLowerCase()] = {
              id: accession,
              uri: provider.uri.replace(/\{\{id_suffix\}\}/g, suffix).replace(/\{\{id\}\}/g, accession),
              label: provider.label || prefix
            };
          }
        }
      }

      return xrefs;
    },
    
    _displayXrefs: function(input, xrefs, geneLabel) {
      // Remove any existing xrefs display
      input.closest(".fdf-api-input-wrapper").nextAll(".xrefs-display").remove();
      
      if (!xrefs || Object.keys(xrefs).length === 0) return;
      
      // Create xrefs display after the wrapper
      let xrefsHtml = '<div class="xrefs-display" style="margin-top:10px; padding:10px; background:#f9f9f9; border:1px solid #e0e0e0; border-radius:4px;">';
      xrefsHtml += '<div style="font-weight:600; margin-bottom:8px; color:#333;">🔗 Cross identifications for ' + geneLabel + ':</div>';
      xrefsHtml += '<div style="display:flex; flex-wrap:wrap; gap:8px;">';
      
      Object.entries(xrefs).forEach(([dbKey, xref]) => {
        const uri = xref.uri || this._resolveIdentifierUri(xref.id, dbKey);
        xrefsHtml += `
          <div style="display:inline-flex; align-items:center; background:white; border:1px solid #ddd; border-radius:3px; padding:4px 8px;">
            <span style="font-weight:500; color:#555; margin-right:6px;">${xref.label}:</span>
            <a href="${uri}" target="_blank" rel="noopener" style="color:#1976d2; text-decoration:none;">${xref.id}</a>
          </div>
        `;
      });
      
      xrefsHtml += '</div></div>';
      
      // Insert after the wrapper
      input.closest(".fdf-api-input-wrapper").after(xrefsHtml);
    },
  };
});
