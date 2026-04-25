import uvicorn

from env_loader import load_local_env

load_local_env()

import api_server
from demo_bootstrap import ensure_canonical_dataset, ensure_trained_model


def ensure_model() -> str:
    model_path = str((api_server.PATHS.runtime_dir / "canonical_model.pkl").resolve())
    return ensure_trained_model(
        model_path=model_path,
        proposals=api_server.DEFAULT_PROPOSALS_CSV,
        people=api_server.DEFAULT_PEOPLE_CSV,
        pairs=api_server.DEFAULT_PAIRS_CSV,
        village_locations=api_server.DEFAULT_VILLAGE_LOCATIONS,
        village_distances=api_server.DEFAULT_DISTANCE_CSV,
        force=True,
    )


def main() -> None:
    ensure_canonical_dataset()
    api_server.reset_runtime_state()
    api_server.recommender_service.set_model_path(ensure_model())
    uvicorn.run(api_server.app, host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
