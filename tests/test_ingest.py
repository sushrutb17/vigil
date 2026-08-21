from pipeline.ingest import normalize_row, split_multi


def test_split_multi_normalizes_empty_values() -> None:
    assert split_multi(" A ; ; B ") == ("A", "B")
    assert split_multi("") == ()


def test_normalize_row_maps_required_fields_and_facets() -> None:
    report = normalize_row(
        {
            "acn_num_ACN": "1234567",
            "Report 1_Narrative": "A concise report.",
            "Events_Anomaly": "Loss of Control; Weather",
            "Person 1.7_Human Factors": "Confusion",
            "Report 2_Narrative": "Second reporter.",
        }
    )
    assert report.acn == "1234567"
    assert report.anomaly_labels == ("Loss of Control", "Weather")
    assert report.human_factors == ("Confusion",)
    assert report.second_narrative == "Second reporter."
