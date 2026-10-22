from ckanext.fair3r.lib import actions


def test_xenbase_line_enrichment_stops_at_the_time_budget(monkeypatch):
    now = iter(range(0, 1000, 10))
    monkeypatch.setattr(actions.time, "monotonic", lambda: next(now))
    fetched = []

    def fake_fetch(line_id, cache=None):
        fetched.append(line_id)
        return {"line_type": "transgenic"}

    monkeypatch.setattr(actions, "_fetch_xenbase_line_metadata", fake_fetch)
    items = [{"lineId": str(i)} for i in range(5)]

    actions._enrich_xenbase_lines(items)

    # budget 15 s, clock moves 10 s per check: only the first line fits
    assert fetched == ["0"]
    assert items[0]["line_type"] == "transgenic"
    assert "line_type" not in items[1]
