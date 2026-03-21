import csv
from pathlib import Path
from typing import Iterable

from path_utils import get_repo_paths


VILLAGES = [
    ("Sundarpur", "Nagpur Rural", "Maharashtra"),
    ("Nirmalgaon", "Wardha", "Maharashtra"),
    ("Lakshmipur", "Sehore", "Madhya Pradesh"),
    ("Devnagar", "Bhopal Rural", "Madhya Pradesh"),
    ("Riverbend", "Raipur", "Chhattisgarh"),
]

VOLUNTEERS = [
    {
        "person_id": "VOL-001",
        "user_id": "mock-volunteer-uuid",
        "name": "Test Volunteer",
        "email": "volunteer@test.com",
        "phone": "1234567890",
        "skills": "digital literacy;teaching;excel training;household survey",
        "text": "Teaches digital literacy workshops, helps residents learn spreadsheets, and runs household surveys for village planning.",
        "willingness_eff": 0.91,
        "willingness_bias": 0.76,
        "availability": "immediately available",
        "home_location": "Nirmalgaon",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-002",
        "user_id": "vol-sam-uuid",
        "name": "Skilled Sam",
        "email": "sam@test.com",
        "phone": "2345678901",
        "skills": "plumbing;construction;handpump repair and maintenance;pump maintenance",
        "text": "Repairs handpumps, handles plumbing maintenance, and supports small construction fixes for public water infrastructure.",
        "willingness_eff": 0.93,
        "willingness_bias": 0.73,
        "availability": "immediately available",
        "home_location": "Sundarpur",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-003",
        "user_id": "vol-alice-uuid",
        "name": "Electrician Alice",
        "email": "alice@test.com",
        "phone": "3456789012",
        "skills": "electrical work;pump wiring;safety checks;field maintenance",
        "text": "Handles electrical repairs, pump wiring, and field safety checks for village repair works.",
        "willingness_eff": 0.84,
        "willingness_bias": 0.61,
        "availability": "generally available",
        "home_location": "Devnagar",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-004",
        "user_id": "vol-farida-uuid",
        "name": "Farida Khan",
        "email": "farida@test.com",
        "phone": "4567890123",
        "skills": "healthcare;public health outreach;community mobilization;awareness campaigns",
        "text": "Supports public health outreach, awareness campaigns, and community mobilization for urgent village needs.",
        "willingness_eff": 0.78,
        "willingness_bias": 0.58,
        "availability": "generally available",
        "home_location": "Lakshmipur",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-005",
        "user_id": "vol-mohan-uuid",
        "name": "Mohan Verma",
        "email": "mohan@test.com",
        "phone": "5678901234",
        "skills": "water quality assessment;sanitation issue mapping;sample collection;reporting",
        "text": "Performs water quality assessment, sanitation issue mapping, sample collection, and field reporting.",
        "willingness_eff": 0.87,
        "willingness_bias": 0.66,
        "availability": "immediately available",
        "home_location": "Riverbend",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-006",
        "user_id": "vol-reena-uuid",
        "name": "Reena Das",
        "email": "reena@test.com",
        "phone": "6789012345",
        "skills": "gis and remote sensing;data analysis and reporting;mapping;survey design",
        "text": "Uses GIS, mapping, and data analysis for field surveys, reporting, and civic planning tasks.",
        "willingness_eff": 0.83,
        "willingness_bias": 0.63,
        "availability": "generally available",
        "home_location": "Nirmalgaon",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-007",
        "user_id": "vol-kavya-uuid",
        "name": "Kavya Patel",
        "email": "kavya@test.com",
        "phone": "7890123456",
        "skills": "road repair;masonry;culvert repair;drainage design and de-silting",
        "text": "Handles drainage repair, masonry, culvert repair, and road patching for civic works.",
        "willingness_eff": 0.74,
        "willingness_bias": 0.54,
        "availability": "generally available",
        "home_location": "Devnagar",
        "availability_status": "available",
    },
    {
        "person_id": "VOL-008",
        "user_id": "vol-bharat-uuid",
        "name": "Bharat Singh",
        "email": "bharat@test.com",
        "phone": "8901234567",
        "skills": "agriculture;drip and sprinkler irrigation setup;watershed management;soil testing",
        "text": "Works on irrigation setup, watershed management, soil testing, and agriculture advisory visits.",
        "willingness_eff": 0.69,
        "willingness_bias": 0.48,
        "availability": "rarely available",
        "home_location": "Sundarpur",
        "availability_status": "busy",
    },
]

PROPOSALS = [
    {
        "proposal_id": "PROB-001",
        "title": "Broken Handpump Near School",
        "text": "Urgent broken handpump near the primary school in Sundarpur. The pump is not drawing water and nearby families need immediate repair support.",
        "village": "Sundarpur",
        "village_address": "Near Primary School",
        "category": "infrastructure",
        "status": "in_progress",
        "seed_assignees": "VOL-002;VOL-003",
        "visual_tags": '["broken pump","infrastructure damage"]',
        "has_audio": "false",
    },
    {
        "proposal_id": "PROB-002",
        "title": "Digital Literacy Camp",
        "text": "Need digital literacy classes in Nirmalgaon to help women self-help groups use smartphones, forms, and spreadsheets for records.",
        "village": "Nirmalgaon",
        "village_address": "Panchayat Hall",
        "category": "digital",
        "status": "pending",
        "seed_assignees": "",
        "visual_tags": '["digital literacy","education"]',
        "has_audio": "false",
    },
    {
        "proposal_id": "PROB-003",
        "title": "Water Contamination Survey",
        "text": "Villagers in Riverbend reported possible water contamination after heavy rain. A field survey, sample collection, and awareness visit are needed.",
        "village": "Riverbend",
        "village_address": "Ward 4 Riverbank",
        "category": "health",
        "status": "pending",
        "seed_assignees": "",
        "visual_tags": '["water pollution","sanitation issue"]',
        "has_audio": "true",
    },
    {
        "proposal_id": "PROB-004",
        "title": "Drainage Repair Near Market",
        "text": "Main market lane in Devnagar has blocked drainage and damaged paving. Repair and de-silting work are required before monsoon flooding worsens.",
        "village": "Devnagar",
        "village_address": "Main Market Lane",
        "category": "infrastructure",
        "status": "completed",
        "seed_assignees": "VOL-007",
        "visual_tags": '["drainage","road repair"]',
        "has_audio": "false",
    },
    {
        "proposal_id": "PROB-005",
        "title": "Irrigation Audit",
        "text": "Farmers in Lakshmipur need an irrigation audit and advisory on drip system repair, soil testing, and water conservation planning.",
        "village": "Lakshmipur",
        "village_address": "South Fields",
        "category": "others",
        "status": "pending",
        "seed_assignees": "",
        "visual_tags": '["agriculture","irrigation"]',
        "has_audio": "false",
    },
    {
        "proposal_id": "PROB-006",
        "title": "School WASH Inspection",
        "text": "School WASH inspection in Sundarpur needs water quality assessment, sanitation review, and student hygiene awareness support.",
        "village": "Sundarpur",
        "village_address": "Government School",
        "category": "education",
        "status": "pending",
        "seed_assignees": "",
        "visual_tags": '["education","sanitation issue"]',
        "has_audio": "false",
    },
]

SCHEDULE_ROWS = [
    {
        "person_id": "VOL-002",
        "start": "2026-03-19T09:00:00",
        "end": "2026-03-19T13:00:00",
    },
    {
        "person_id": "VOL-006",
        "start": "2026-03-20T14:00:00",
        "end": "2026-03-20T18:00:00",
    },
]

RUNTIME_PROFILES = [
    {
        "id": "mock-coordinator-uuid",
        "email": "coordinator@test.com",
        "full_name": "Test Coordinator",
        "phone": "0987654321",
        "role": "coordinator",
    },
    {
        "id": "mock-volunteer-uuid",
        "email": "volunteer@test.com",
        "full_name": "Test Volunteer",
        "phone": "1234567890",
        "role": "volunteer",
    },
]

POSITIVE_RULES = {
    "PROB-001": {"VOL-002", "VOL-003"},
    "PROB-002": {"VOL-001", "VOL-006"},
    "PROB-003": {"VOL-004", "VOL-005", "VOL-006"},
    "PROB-004": {"VOL-007", "VOL-002"},
    "PROB-005": {"VOL-008", "VOL-006"},
    "PROB-006": {"VOL-001", "VOL-005", "VOL-004"},
}

DISTANCE_MATRIX = {
    ("Sundarpur", "Nirmalgaon"): (18, 35),
    ("Sundarpur", "Lakshmipur"): (42, 82),
    ("Sundarpur", "Devnagar"): (28, 54),
    ("Sundarpur", "Riverbend"): (61, 110),
    ("Nirmalgaon", "Lakshmipur"): (37, 73),
    ("Nirmalgaon", "Devnagar"): (24, 48),
    ("Nirmalgaon", "Riverbend"): (55, 100),
    ("Lakshmipur", "Devnagar"): (16, 33),
    ("Lakshmipur", "Riverbend"): (34, 67),
    ("Devnagar", "Riverbend"): (29, 56),
}


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def build_pairs() -> list[dict]:
    rows: list[dict] = []
    for proposal in PROPOSALS:
        proposal_id = proposal["proposal_id"]
        positives = POSITIVE_RULES[proposal_id]
        for volunteer in VOLUNTEERS:
            label = 1 if volunteer["person_id"] in positives else 0
            rows.append(
                {
                    "proposal_id": proposal_id,
                    "person_id": volunteer["person_id"],
                    "label": label,
                }
            )
    return rows


def build_distances() -> list[dict]:
    rows: list[dict] = []
    for (village_a, village_b), (distance_km, travel_time_min) in DISTANCE_MATRIX.items():
        rows.append(
            {
                "village_a": village_a,
                "village_b": village_b,
                "distance_km": distance_km,
                "travel_time_min": travel_time_min,
            }
        )
    return rows


def main() -> None:
    data_dir = get_repo_paths().data_dir

    _write_csv(
        data_dir / "people.csv",
        [
            "person_id",
            "user_id",
            "name",
            "email",
            "phone",
            "skills",
            "text",
            "willingness_eff",
            "willingness_bias",
            "availability",
            "home_location",
            "availability_status",
        ],
        VOLUNTEERS,
    )
    _write_csv(
        data_dir / "proposals.csv",
        [
            "proposal_id",
            "title",
            "text",
            "village",
            "village_address",
            "category",
            "status",
            "seed_assignees",
            "visual_tags",
            "has_audio",
        ],
        PROPOSALS,
    )
    _write_csv(
        data_dir / "pairs.csv",
        ["proposal_id", "person_id", "label"],
        build_pairs(),
    )
    _write_csv(
        data_dir / "village_locations.csv",
        ["village_name", "district_placeholder", "state_placeholder"],
        [
            {
                "village_name": village_name,
                "district_placeholder": district,
                "state_placeholder": state,
            }
            for village_name, district, state in VILLAGES
        ],
    )
    _write_csv(
        data_dir / "village_distances.csv",
        ["village_a", "village_b", "distance_km", "travel_time_min"],
        build_distances(),
    )
    _write_csv(
        data_dir / "schedule.csv",
        ["person_id", "start", "end"],
        SCHEDULE_ROWS,
    )
    _write_csv(
        data_dir / "runtime_profiles.csv",
        ["id", "email", "full_name", "phone", "role"],
        RUNTIME_PROFILES,
    )
    print(f"Wrote canonical dataset to {data_dir}")


if __name__ == "__main__":
    main()
