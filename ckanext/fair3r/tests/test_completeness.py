from ckanext.fair3r.lib.fdf.completeness import compute_completeness

SCHEMA = {
    "sections": [
        {
            "id": "title_section",
            "title": "Title",
            "fields": [
                {
                    "id": "year",
                    "label": "Year",
                    "required": True,
                    "output": {"path": "publication_year", "mode": "set"},
                },
                {
                    "id": "keywords",
                    "label": "Keywords",
                    "required": False,
                    "output": {"path": "keywords", "mode": "set"},
                },
            ],
        },
        {
            "id": "organism_section",
            "title": "Organism",
            "fields": [
                {
                    "id": "strain",
                    "label": "Strain",
                    "required": True,
                    "output": {"path": "strain", "mode": "set"},
                },
                {
                    "id": "strain_note",
                    "label": "Strain note (only for a specific strain)",
                    "required": True,
                    "visible_if": {"field": "strain", "value": "special"},
                    "output": {"path": "strain_note", "mode": "set"},
                },
            ],
        },
        {
            "id": "treatment_section",
            "title": "Treatment",
            "condition": {"type": "equals", "field_id": "kind", "value": "treated"},
            "fields": [
                {
                    "id": "protocol",
                    "label": "Protocol",
                    "required": True,
                    "output": {"path": "protocol", "mode": "set"},
                },
            ],
        },
        {
            "id": "creators",
            "title": "Creators",
            "output": {"mode": "collect_object", "path": "creators"},
            "initial_instances": 1,
            "fields": [
                {
                    "id": "family_name",
                    "label": "Family name",
                    "required": True,
                    "output": {"obj_key": "family_name"},
                },
                {
                    "id": "orcid",
                    "label": "ORCID",
                    "required": False,
                    "output": {"obj_key": "orcid"},
                },
            ],
        },
    ],
}

PKG_COMPLETE = {
    "title": "T",
    "notes": "N",
    "tags": [{"name": "x"}],
    "license_id": "cc-by",
}
PKG_EMPTY = {}


def _fdf(**kwargs):
    return kwargs


def test_empty_dataset_scores_zero_and_is_red():
    result = compute_completeness(SCHEMA, _fdf(), PKG_EMPTY)
    assert result["score"] == 0
    assert result["band"] == "red"


def test_inactive_section_is_not_counted():
    # treatment_section is only active when kind == "treated"
    fdf = _fdf(kind="other")
    labels = [
        label for _, label, _ in compute_completeness(SCHEMA, fdf, PKG_EMPTY)["missing"]
    ]
    assert "Protocol" not in labels


def test_active_section_required_field_is_counted_as_missing():
    fdf = _fdf(kind="treated")
    labels = [
        label for _, label, _ in compute_completeness(SCHEMA, fdf, PKG_EMPTY)["missing"]
    ]
    assert "Protocol" in labels


def test_conditional_field_is_ignored_when_its_rule_is_false():
    fdf = _fdf(strain="wildtype")
    labels = [
        label for _, label, _ in compute_completeness(SCHEMA, fdf, PKG_EMPTY)["missing"]
    ]
    assert "Strain note (only for a specific strain)" not in labels


def test_conditional_field_counts_when_its_rule_is_true():
    fdf = _fdf(strain="special")
    labels = [
        label for _, label, _ in compute_completeness(SCHEMA, fdf, PKG_EMPTY)["missing"]
    ]
    assert "Strain note (only for a specific strain)" in labels


def test_required_fields_weigh_more_than_optional():
    # Only the optional "keywords" filled, against a fully empty schema.
    only_optional = compute_completeness(SCHEMA, _fdf(keywords=["a"]), PKG_EMPTY)[
        "score"
    ]
    only_required = compute_completeness(
        SCHEMA, _fdf(publication_year=2025), PKG_EMPTY
    )["score"]
    assert only_required > only_optional


def test_repeatable_section_checks_each_item():
    fdf = _fdf(creators=[{"family_name": "Doe"}, {"family_name": ""}])
    missing = compute_completeness(SCHEMA, fdf, PKG_EMPTY)["missing"]
    assert ("Creators", "Family name", True) in missing


def test_empty_repeatable_section_with_min_instances_counts_required_missing():
    missing = compute_completeness(SCHEMA, _fdf(creators=[]), PKG_EMPTY)["missing"]
    assert ("Creators", "Family name", True) in missing


def test_base_fields_count():
    base_only = compute_completeness(SCHEMA, _fdf(), PKG_COMPLETE)
    assert base_only["score"] > 0
    assert not any(section == "CKAN" for section, _, _ in base_only["missing"])


def test_score_bands_follow_thresholds():
    everything = _fdf(
        publication_year=2025,
        keywords=["a"],
        strain="special",
        strain_note="x",
        kind="treated",
        protocol="p",
        creators=[{"family_name": "Doe", "orcid": "0000-0001-0000-0001"}],
    )
    full = compute_completeness(SCHEMA, everything, PKG_COMPLETE)
    assert full["score"] == 100
    assert full["band"] == "green"
    assert full["missing"] == []


CHECKED_SCHEMA = {
    "sections": [
        {
            "id": "genes",
            "title": "Genes",
            "output": {"mode": "collect_object", "path": "subjects"},
            "initial_instances": 1,
            "fields": [
                {
                    "id": "cross_species_gene",
                    "label": "Cross-species gene",
                    "type": "checkbox_group",
                    "output": {"obj_key": "cross"},
                },
                {
                    "id": "transgene_origin",
                    "label": "Transgene origin species",
                    "required": False,
                    "visible_if": {"field": "cross_species_gene", "checked": True},
                    "output": {"obj_key": "origin"},
                },
                {
                    "id": "gene_search",
                    "label": "Gene",
                    "required": True,
                    "output": {"obj_key": "gene"},
                },
                {
                    "id": "allele",
                    "label": "Allele",
                    "required": False,
                    "visible_if": {"field": "gene_search", "not_empty": True},
                    "output": {"obj_key": "allele"},
                },
            ],
        },
    ],
}


def test_checkbox_group_is_never_counted_as_missing():
    fdf = {"subjects": [{"gene": "Apoe"}]}
    labels = [
        label
        for _, label, _ in compute_completeness(CHECKED_SCHEMA, fdf, PKG_EMPTY)[
            "missing"
        ]
    ]
    assert "Cross-species gene" not in labels


def test_checked_rule_hides_field_when_checkbox_unticked():
    fdf = {"subjects": [{"gene": "Apoe", "cross": False}]}
    labels = [
        label
        for _, label, _ in compute_completeness(CHECKED_SCHEMA, fdf, PKG_EMPTY)[
            "missing"
        ]
    ]
    assert "Transgene origin species" not in labels


def test_checked_rule_shows_field_when_checkbox_ticked():
    fdf = {"subjects": [{"gene": "Apoe", "cross": True}]}
    labels = [
        label
        for _, label, _ in compute_completeness(CHECKED_SCHEMA, fdf, PKG_EMPTY)[
            "missing"
        ]
    ]
    assert "Transgene origin species" in labels


def test_not_empty_rule_hides_field_until_controller_is_filled():
    fdf = {"subjects": [{"cross": False}]}
    labels = [
        label
        for _, label, _ in compute_completeness(CHECKED_SCHEMA, fdf, PKG_EMPTY)[
            "missing"
        ]
    ]
    assert "Allele" not in labels


SUBJECT_SCHEMA = {
    "sections": [
        {
            "id": "genes",
            "title": "Genes",
            "subject_scheme": "geneAccessionId",
            "fields": [
                {
                    "id": "gene_search",
                    "label": "Gene",
                    "required": True,
                    "output": {
                        "path": "subjects",
                        "mode": "append",
                        "tpl": {"subject": "$label", "subjectScheme": "$scheme"},
                    },
                },
                {
                    "id": "mutation_type",
                    "label": "Mutation Type",
                    "required": False,
                    "output": {
                        "path": "subjects",
                        "mode": "append_if",
                        "tpl": {
                            "subject": "$value",
                            "subjectScheme": "geneMutationType",
                        },
                    },
                },
            ],
        },
    ],
}


def test_subject_field_is_filled_only_by_its_own_scheme():
    fdf = {"subjects": [{"subject": "Apoe", "subjectScheme": "geneAccessionId"}]}
    labels = [
        label
        for _, label, _ in compute_completeness(SUBJECT_SCHEMA, fdf, PKG_EMPTY)[
            "missing"
        ]
    ]
    assert "Mutation Type" in labels


def test_subject_field_counts_when_its_scheme_is_present():
    fdf = {
        "subjects": [
            {"subject": "Apoe", "subjectScheme": "geneAccessionId"},
            {"subject": "KO", "subjectScheme": "geneMutationType"},
        ]
    }
    labels = [
        label
        for _, label, _ in compute_completeness(SUBJECT_SCHEMA, fdf, PKG_EMPTY)[
            "missing"
        ]
    ]
    assert "Mutation Type" not in labels
