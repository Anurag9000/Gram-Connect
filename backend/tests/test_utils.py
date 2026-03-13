from datetime import datetime

import utils


def test_parse_schedule_csv_aggregates_hours_and_skips_invalid_rows(tmp_path):
    schedule_csv = tmp_path / "schedule.csv"
    schedule_csv.write_text(
        "\n".join(
            [
                "person_id,start,end",
                "p1,2026-01-01T10:00:00,2026-01-01T12:00:00",
                "p1,2026-01-02T10:00:00,2026-01-02T11:30:00",
                "p2,invalid,2026-01-02T11:30:00",
                "p3,2026-01-03T12:00:00,2026-01-03T11:00:00",
            ]
        ),
        encoding="utf-8",
    )

    schedule = utils.parse_schedule_csv(str(schedule_csv))

    assert sorted(schedule) == ["p1"]
    assert len(schedule["p1"]["intervals"]) == 2
    assert schedule["p1"]["week_hours"][(2026, 1)] == 3.5


def test_split_hours_by_week_splits_across_week_boundary():
    start = datetime(2025, 12, 28, 23, 0, 0)
    end = datetime(2025, 12, 29, 2, 0, 0)

    hours = utils.split_hours_by_week(start, end)

    assert hours[(2025, 52)] == 1.0
    assert hours[(2026, 1)] == 2.0
