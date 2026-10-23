from ckanext.fair3r.lib.fdf.summary import summary_lines

SCHEMA = {
    "sections": [
        {
            "id": "interventions",
            "title": "Experimental Interventions",
            "fields": [
                {
                    "id": "intervention_types",
                    "type": "checkbox_group",
                    "options": [{"value": "GENE", "label": "Genetic Modification"}],
                    "output": {"path": "experimentalInterventions"},
                }
            ],
            "display_mapping": {
                "source": ["experimentalInterventions"],
                "labels": {"experimentalInterventions": "Interventions"},
            },
        },
        {
            "id": "genes",
            "title": "Involved Genes",
            "display_mapping": {
                "source": ["subjects"],
                "filter": {"subjectScheme": ["geneAccessionId", "alleleAccessionId"]},
                "labels": {"geneAccessionId": "Gene", "alleleAccessionId": "Allele"},
            },
        },
        {
            "id": "disease",
            "title": "Disease Model",
            "display_mapping": {
                "source": "subjects",
                "filter": {"subjectScheme": ["MONDO", "DOID", "UPHENO"]},
                "labels": {"UPHENO": "Phenotype"},
            },
        },
    ]
}


def test_labels_come_from_the_schema():
    fdf = {
        "experimentalInterventions": ["GENE"],
        "subjects": [
            {"subject": "Apoe", "subjectScheme": "geneAccessionId"},
            {
                "subject": "Apoe",
                "subjectScheme": "MGI Gene",
                "crossRefOf": "geneAccessionId",
            },
            {"subject": "Gene: Lep", "subjectScheme": "geneAccessionId"},
            {"subject": "Rett syndrome", "subjectScheme": "MONDO"},
            {"subject": "cystic fibrosis", "subjectScheme": "DOID"},
            {"subject": "abnormal gait", "subjectScheme": "UPHENO"},
            {"subject": "something", "subjectScheme": "NewScheme"},
        ],
    }

    assert summary_lines(SCHEMA, fdf) == [
        ("Interventions", ["Genetic Modification"]),
        # cross-reference left out, pre-3.0.4 "Gene: " prefix stripped
        ("Gene", ["Apoe", "Lep"]),
        # no label for MONDO/DOID: the section title
        ("Disease Model", ["Rett syndrome", "cystic fibrosis"]),
        ("Phenotype", ["abnormal gait"]),
        # no section claims it: kept, under its scheme name
        ("NewScheme", ["something"]),
    ]


def test_without_schema_subjects_go_under_their_scheme():
    fdf = {"subjects": [{"subject": "Mus musculus", "subjectScheme": "NCBITaxon"}]}

    assert summary_lines({}, fdf) == [("NCBITaxon", ["Mus musculus"])]


def test_subjects_only_leaves_other_answers_out():
    fdf = {
        "experimentalInterventions": ["GENE"],
        "subjects": [{"subject": "Apoe", "subjectScheme": "geneAccessionId"}],
    }

    assert summary_lines(SCHEMA, fdf, subjects_only=True) == [("Gene", ["Apoe"])]
