"""Configuration for the GapFill model workflow."""

import os
from pathlib import Path

ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
DATA_DIR = ROOT_DIR / "data"
LINE_ART_DIR = DATA_DIR / "line_art"
COLORED_DIR = DATA_DIR / "colored"
PATCH_DATA_DIR = ROOT_DIR / "patches" / "all"
REGION_ANALYSIS_OUTPUT_DIR = ROOT_DIR / "region_analysis"
REGION_ANALYSIS_CSV_PATH = REGION_ANALYSIS_OUTPUT_DIR / "nearest_same_color_analysis.csv"
MODEL_SAVE_DIR = ROOT_DIR / "saved_models"
DEFAULT_MODEL_DIR = MODEL_SAVE_DIR / "gapfill"
BEST_MODEL_PATH = DEFAULT_MODEL_DIR / "checkpoints" / "best_model.pth"

for directory in [DATA_DIR, LINE_ART_DIR, COLORED_DIR, PATCH_DATA_DIR, MODEL_SAVE_DIR]:
    directory.mkdir(exist_ok=True, parents=True)


TRAIN_VAL_SPLIT = 0.8  # Fraction of source images assigned to training; the remainder is used for validation.
PATCH_SIZE = 32
BATCH_SIZE = 64
NUM_WORKERS = 8
USE_HDF5 = True
REGION_SIZE_THRESHOLD = 10

LEARNING_RATE = 1e-4
WEIGHT_DECAY = 1e-5
NUM_EPOCHS = 100
EARLY_STOPPING_PATIENCE = 15
SAVE_INTERVAL = 10
