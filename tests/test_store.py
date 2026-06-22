from dispatch_hub.store import ProfileStore
from dispatch_hub.models import Profile, Pane


def test_save_then_load_roundtrip(tmp_path):
    store = ProfileStore(tmp_path)
    prof = Profile.new("sprint", "grid", [Pane("C:/a", "Backend", "go")])
    store.save(prof)
    assert store.load("sprint") == prof


def test_save_writes_one_file_per_profile(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(Profile.new("a", "vertical", []))
    store.save(Profile.new("b", "horizontal", []))
    assert (tmp_path / "a.json").exists()
    assert (tmp_path / "b.json").exists()


def test_list_sorted_and_skips_corrupt(tmp_path, capsys):
    store = ProfileStore(tmp_path)
    store.save(Profile.new("zeta", "grid", []))
    store.save(Profile.new("alpha", "grid", []))
    (tmp_path / "broken.json").write_text("{ not json")
    names = store.list()
    assert names == ["alpha", "zeta"]          # corrupt skipped, sorted
    assert "broken" in capsys.readouterr().err  # warning emitted


def test_delete_removes_file(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(Profile.new("temp", "grid", []))
    store.delete("temp")
    assert not (tmp_path / "temp.json").exists()
