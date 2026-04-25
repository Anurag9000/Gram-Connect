from pathlib import Path

import path_utils


def test_resolve_model_path_defaults_to_runtime_bundle(monkeypatch, tmp_path):
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    monkeypatch.setattr(
        path_utils,
        "get_repo_paths",
        lambda: path_utils.RepoPaths(
            repo_root=tmp_path,
            backend_dir=fake_backend,
            data_dir=tmp_path / "data",
            runtime_dir=fake_backend / "runtime_data",
        ),
    )

    assert path_utils.resolve_model_path() == str((fake_backend / "runtime_data" / "canonical_model.pkl").resolve())


def test_resolve_people_csv_prefers_existing_repo_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GRAM_CONNECT_PEOPLE_CSV", raising=False)

    fake_backend = tmp_path / "backend"
    fake_data = tmp_path / "data"
    fake_backend.mkdir()
    fake_data.mkdir()
    bundled = fake_backend / "people_2.csv"
    bundled.write_text("person_id,name,text\np1,Alice,skills\n", encoding="utf-8")

    monkeypatch.setattr(
        path_utils,
        "get_repo_paths",
        lambda: path_utils.RepoPaths(
            repo_root=tmp_path,
            backend_dir=fake_backend,
            data_dir=fake_data,
            runtime_dir=fake_backend / "runtime_data",
        ),
    )

    assert path_utils.resolve_people_csv() == str(bundled.resolve())


def test_ensure_runtime_dir_creates_directory(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "backend" / "runtime_data"
    monkeypatch.setattr(
        path_utils,
        "get_repo_paths",
        lambda: path_utils.RepoPaths(
            repo_root=tmp_path,
            backend_dir=tmp_path / "backend",
            data_dir=tmp_path / "data",
            runtime_dir=runtime_dir,
        ),
    )

    created = path_utils.ensure_runtime_dir()
    assert Path(created).is_dir()
