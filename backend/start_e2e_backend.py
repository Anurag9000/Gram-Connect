import os

import uvicorn

import api_server
from generate_canonical_dataset import main as generate_canonical_dataset
from m3_trainer import TrainingConfig, train_model


def ensure_model() -> str:
    model_path = str((api_server.PATHS.runtime_dir / "canonical_model.pkl").resolve())
    if not os.path.exists(model_path):
        train_model(
            TrainingConfig(
                proposals=api_server.DEFAULT_PROPOSALS_CSV,
                people=api_server.DEFAULT_PEOPLE_CSV,
                pairs=api_server.DEFAULT_PAIRS_CSV,
                out=model_path,
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                village_locations=api_server.DEFAULT_VILLAGE_LOCATIONS,
                village_distances=api_server.DEFAULT_DISTANCE_CSV,
            )
        )
    return model_path


def main() -> None:
    generate_canonical_dataset()
    api_server.reset_runtime_state()
    api_server.recommender_service.set_model_path(ensure_model())
    uvicorn.run(api_server.app, host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
