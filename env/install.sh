#!/bin/bash

ENV_NAME="dental-landmarks"
ENV_FILE="environment.yml"

function check_conda() {
    if ! command -v conda >/dev/null 2>&1; then
        echo "Error: Conda is not installed or not in PATH." >&2
        echo "Please install Anaconda or Miniconda before proceeding."
        exit 1
    fi
}

function ensure_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "Error: Cannot find '$ENV_FILE' in $(pwd)." >&2
        return 1
    fi
    return 0
}

function create_env() {
    ensure_env_file || return 1
    echo "Creating or updating conda environment '$ENV_NAME'..."
    if conda env list | grep -q "$ENV_NAME"; then
        echo "Environment '$ENV_NAME' exists. Updating..."
        if conda env update -f "$ENV_FILE" -n "$ENV_NAME" --prune; then
            echo "Environment '$ENV_NAME' updated successfully."
        else
            echo "Error: Environment update failed." >&2
            return 2
        fi
    else
        if conda env create -f "$ENV_FILE" -n "$ENV_NAME"; then
            echo "Environment '$ENV_NAME' created successfully."
        else
            echo "Error: Environment creation failed." >&2
            return 2
        fi
    fi
}

function remove_env() {
    echo "Removing conda environment '$ENV_NAME'..."
    if conda env remove -n "$ENV_NAME"; then
        echo "Environment '$ENV_NAME' removed successfully."
    else
        echo "Error: Failed to remove environment or environment not found." >&2
        return 3
    fi
}

function reinstall_env() {
    remove_env
    if [ $? -ne 0 ]; then
        echo "Reinstall aborted due to removal failure." >&2
        return 4
    fi
    create_env
}

function menu() {
    while true; do
        echo ""
        echo "Please select an action:"
        echo "1. Install environment"
        echo "2. Uninstall environment"
        echo "3. Reinstall environment"
        echo "4. Exit"
        read -r -p "Enter choice [1-4]: " choice
        case "$choice" in
            1)
                create_env
                ;;
            2)
                remove_env
                ;;
            3)
                reinstall_env
                ;;
            4)
                echo "Exiting."
                exit 0
                ;;
            *)
                echo "Invalid input. Please enter a number from 1 to 4."
                ;;
        esac
    done
}

check_conda
menu
