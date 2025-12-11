import shutil
import os
from pathlib import Path


def transfer_files(source_dirs, destination_dir):
    """
    Transfer all files from source directories to destination directory
    """
    # Create destination directory if it doesn't exist
    Path(destination_dir).mkdir(parents=True, exist_ok=True)

    transferred_files = []

    for source_dir in source_dirs:
        source_path = Path(source_dir)

        if source_path.exists():
            print(f"Processing {source_dir}...")

            # Walk through all files and subdirectories
            for item in source_path.rglob('*'):
                if item.is_file():
                    # Create relative path to maintain directory structure
                    relative_path = item.relative_to(source_path)
                    dest_file = Path(destination_dir) / source_path.name / relative_path

                    # Create parent directories if needed
                    dest_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    shutil.copy2(item, dest_file)
                    transferred_files.append(str(dest_file))
                    print(f"  Transferred: {item} -> {dest_file}")

            # Remove the source directory after transfer
            shutil.rmtree(source_path)
            print(f"  Removed source directory: {source_dir}")
        else:
            print(f"Directory not found: {source_dir}")

    return transferred_files


# Define source directories and destination
source_directories = [
    "../data/processed/",
    "../results/",
    "../notebooks/config/"
]

destination_directory = "../archive/"  # Change this to your preferred destination

# Transfer files
print("Starting file transfer...")
transferred = transfer_files(source_directories, destination_directory)

print(f"\nTransfer complete! {len(transferred)} files transferred to {destination_directory}")