"""The saved watchlist loads and run_many dispatches one run per topic."""
from radar import config, topic_mode


def test_watchlist_loads_presets():
    topics = config.watchlist_topics()
    assert topics, "watchlist should not be empty"
    # The point-of-care focus is present.
    assert any("point-of-care" in t.lower() for t in topics)
    # Defaults carry a lookback window and per-source count.
    defaults = config.watchlist_defaults()
    assert "since_days" in defaults
    assert "per_source_count" in defaults


def test_run_many_dispatches_each_topic(monkeypatch):
    calls = []

    def fake_run(topic, since=None, n=None, do_llm=True, http=None, render=True):
        calls.append((topic, render))
        return {"mode": "topic", "query": topic, "count": 0, "items": [],
                "generated_at": "2026-01-01T00:00:00Z"}

    rendered = {"n": 0}

    def fake_render(runs):
        rendered["n"] = len(runs)

    monkeypatch.setattr(topic_mode, "run", fake_run)
    # render_site is imported inside run_many from radar.site; patch there.
    import radar.site as site
    monkeypatch.setattr(site, "render_site", lambda runs, out_dir=None: rendered.update(n=len(runs)))
    monkeypatch.setattr("radar.store.load_public_runs", lambda: [1, 2])

    topics = ["a", "b", "c"]
    results = topic_mode.run_many(topics, do_llm=False)
    assert [c[0] for c in calls] == topics
    # Each per-topic run is told not to render; the batch renders once at the end.
    assert all(render is False for _, render in calls)
    assert len(results) == 3
