import os
import shutil


# Fix directory structure - move folders from notebook directory to root
def fix_directory_structure():
    """
    Move project folders from notebook directory to root directory
    """

    # Get current working directory (should be in notebooks folder)
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")

    # Get parent directory (root of repo)
    parent_dir = os.path.dirname(current_dir)
    print(f"Parent directory (root): {parent_dir}")

    # Folders that should be in root directory
    folders_to_move = [
        "data",
        "results",
        "models",
        "docs",
        "scripts"
    ]

    # Files that should be in root directory
    files_to_move = [
        "requirements.txt",
        "README.md",
        "CHECKLIST.md",
        ".gitignore"
    ]

    print("\n=== Moving Folders ===")
    for folder in folders_to_move:
        source_path = os.path.join(current_dir, folder)
        dest_path = os.path.join(parent_dir, folder)

        if os.path.exists(source_path):
            if os.path.exists(dest_path):
                print(f"⚠️  {folder} already exists in root. Merging contents...")
                # Merge contents
                for item in os.listdir(source_path):
                    src_item = os.path.join(source_path, item)
                    dst_item = os.path.join(dest_path, item)
                    if os.path.isdir(src_item):
                        if not os.path.exists(dst_item):
                            shutil.move(src_item, dst_item)
                        else:
                            print(f"   Subdirectory {item} already exists, skipping")
                    else:
                        shutil.move(src_item, dst_item)
                # Remove empty source folder
                try:
                    os.rmdir(source_path)
                    print(f"✅ Merged {folder} to root directory")
                except:
                    print(f"⚠️  Could not remove {source_path} (may not be empty)")
            else:
                shutil.move(source_path, dest_path)
                print(f"✅ Moved {folder} to root directory")
        else:
            print(f"❌ {folder} not found in notebook directory")

    print("\n=== Moving Files ===")
    for file in files_to_move:
        source_path = os.path.join(current_dir, file)
        dest_path = os.path.join(parent_dir, file)

        if os.path.exists(source_path):
            if os.path.exists(dest_path):
                print(f"⚠️  {file} already exists in root. Backing up and replacing...")
                backup_path = dest_path + ".backup"
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                shutil.move(dest_path, backup_path)

            shutil.move(source_path, dest_path)
            print(f"✅ Moved {file} to root directory")
        else:
            print(f"❌ {file} not found in notebook directory")

    print("\n=== Directory Structure Fixed! ===")
    print("Your project structure should now be:")
    print("repo-root/")
    print("├── data/")
    print("├── results/")
    print("├── models/")
    print("├── docs/")
    print("├── scripts/")
    print("├── notebooks/  (your notebook files)")
    print("├── requirements.txt")
    print("├── README.md")
    print("└── CHECKLIST.md")

    print(f"\nNext steps:")
    print(f"1. Navigate to your root directory: cd {parent_dir}")
    print(f"2. Continue running notebooks from notebooks/ folder")
    print(f"3. All paths in notebooks will now work correctly")


if __name__ == "__main__":
    fix_directory_structure()