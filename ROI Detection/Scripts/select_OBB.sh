#!/bin/bash

# Define input arguments
DATA_DIR="../Data/All"
TRAIN_DIR="../data/OBB/train"
VAL_DIR="../data/OBB/val"
TRAIN_PERCENT=0.8
VAL_PERCENT=0.2
MAX_IMAGES=100

python random_select.py $DATA_DIR $TRAIN_DIR $VAL_DIR $TRAIN_PERCENT $VAL_PERCENT $MAX_IMAGES