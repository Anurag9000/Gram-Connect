from datetime import datetime, timedelta

def get_mock_problems():
    return [
        {
            "id": "problem-1",
            "villager_id": "villager-1",
            "title": "Broken Well Pump",
            "description": "The main well pump is broken and needs repair.",
            "category": "infrastructure",
            "village_name": "Test Village",
            "status": "pending",
            "lat": 21.1458,
            "lng": 79.0882,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "villager-1", 
                "full_name": "Submitted by Coordinator", 
                "email": "anon@test.com", 
                "role": "villager", 
                "created_at": datetime.now().isoformat(), 
                "phone": None 
            },
            "matches": []
        },
        {
            "id": "problem-2",
            "villager_id": "villager-2",
            "title": "Digital Literacy Class",
            "description": "Need someone to teach basic computer skills to children.",
            "category": "digital",
            "village_name": "Other Village",
            "status": "in_progress",
            "lat": 21.1610,
            "lng": 79.0720,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "villager-2", 
                "full_name": "Submitted by Coordinator", 
                "email": "jane@test.com", 
                "role": "villager", 
                "created_at": datetime.now().isoformat(), 
                "phone": None 
            },
            "matches": [
                {
                    "id": "match-1",
                    "problem_id": "problem-2",
                    "volunteer_id": "vol-1",
                    "assigned_at": datetime.now().isoformat(),
                    "completed_at": None,
                    "notes": "Assigned to Test Volunteer",
                    "volunteers": {
                        "id": "vol-1",
                        "user_id": "mock-volunteer-uuid",
                        "skills": ["Teaching", "Digital Literacy"],
                        "availability_status": "available",
                        "created_at": datetime.now().isoformat(),
                        "profiles": { 
                            "id": "mock-volunteer-uuid", 
                            "full_name": "Test Volunteer", 
                            "email": "volunteer@test.com", 
                            "role": "volunteer", 
                            "created_at": datetime.now().isoformat(), 
                            "phone": "1234567890" 
                        }
                    }
                }
            ]
        }
    ]

def get_mock_volunteers():
    return [
        {
            "id": "vol-1",
            "user_id": "mock-volunteer-uuid",
            "skills": ["Teaching", "Digital Literacy", "Web Development"],
            "availability_status": "available",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-volunteer-uuid", 
                "full_name": "Test Volunteer", 
                "email": "volunteer@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "1234567890" 
            }
        },
        {
            "id": "vol-2",
            "user_id": "mock-vol-2-uuid",
            "skills": ["Plumbing", "Construction"],
            "availability_status": "available",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-vol-2-uuid", 
                "full_name": "Skilled Sam", 
                "email": "sam@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "2345678901" 
            }
        },
        {
            "id": "vol-3",
            "user_id": "mock-vol-3-uuid",
            "skills": ["Electrical Work", "Plumbing"],
            "availability_status": "available",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-vol-3-uuid", 
                "full_name": "Electrician Alice", 
                "email": "alice@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "3456789012" 
            }
        },
        {
            "id": "vol-4",
            "user_id": "mock-vol-4-uuid",
            "skills": ["Agriculture", "Healthcare"],
            "availability_status": "busy",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-vol-4-uuid", 
                "full_name": "Doctor Dave", 
                "email": "dave@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "4567890123" 
            }
        }
    ]

def get_mock_volunteer_tasks():
    return [
        {
            "id": 'task-1',
            "title": 'Broken Well Pump',
            "village": 'Gram Puram',
            "location": 'Near Primary School',
            "status": 'assigned',
            "description": 'The handle of the hand-pump is broken. Needs basic welding or part replacement.',
            "assigned_at": (datetime.now() - timedelta(days=2)).isoformat(),
        }
    ]
