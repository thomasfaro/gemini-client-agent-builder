import os
import shutil
import subprocess
import sys


def main():
    """
    Prepares and links the Airship skills repository for use with the Gemini CLI.

    This script creates a temporary, flattened directory structure that is compatible
    with Gemini's skill discovery mechanism, and then uses the `gemini skills link`
    command to make them available.
    """
    # Script lives in tools/ — repo root is one level up
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_skills_dir = os.path.join(repo_root, 'skills')
    build_dir = os.path.join(repo_root, 'gemini_build')
    target_skills_dir = os.path.join(build_dir, 'skills')

    if not os.path.isdir(source_skills_dir):
        print(f"Error: Source skills directory not found at {source_skills_dir}")
        sys.exit(1)

    # 1. Clean and create the temporary build directory
    print(f"Creating a fresh build directory at {build_dir}...")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(target_skills_dir)

    # 2. Flatten the skill structure
    print("Scanning for skills and restructuring...")
    skill_count = 0
    for root, dirs, files in os.walk(source_skills_dir):
        if 'SKILL.md' in files:
            skill_name = os.path.basename(root)
            source_dir = root
            target_dir = os.path.join(target_skills_dir, skill_name)

            print(f"  - Found skill: {skill_name}")
            shutil.copytree(source_dir, target_dir)
            skill_count += 1
            # Prevent walking into subdirectories of an already-found skill
            dirs[:] = []

    # 3. Package AUTHENTICATION.md as its own skill
    auth_md_path = os.path.join(source_skills_dir, 'AUTHENTICATION.md')
    if os.path.exists(auth_md_path):
        print("  - Found AUTHENTICATION.md, packaging as a skill...")
        auth_skill_dir = os.path.join(target_skills_dir, 'AUTHENTICATION')
        os.makedirs(auth_skill_dir)
        frontmatter = (
            "---\n"
            "name: authentication\n"
            "metadata:\n"
            "  category: api\n"
            "description: Airship API authentication methods including OAuth (recommended),"
            " Bearer token, and Basic auth. Use when setting up API credentials, requesting"
            " OAuth tokens, or configuring authentication for any Airship API integration.\n"
            "---\n\n"
        )
        with open(auth_md_path, 'r') as f:
            auth_content = f.read()
        with open(os.path.join(auth_skill_dir, 'SKILL.md'), 'w') as f:
            f.write(frontmatter + auth_content)
        skill_count += 1
    else:
        print(
            "Warning: AUTHENTICATION.md not found at the root of the skills directory."
        )

    if skill_count == 0:
        print("Error: No skills with SKILL.md files were found.")
        sys.exit(1)

    print(f"\nSuccessfully processed {skill_count} skills.")

    # 4. Link the resulting directory with Gemini
    link_path = os.path.abspath(target_skills_dir)
    print(f"\nRunning 'gemini skills link' on the temporary directory: {link_path}")

    try:
        subprocess.run(
            ['gemini', 'skills', 'link', '--consent', link_path],
            check=True
        )
        print("\n✅ Gemini skills linked successfully!")

    except FileNotFoundError:
        print("\nError: 'gemini' command not found.")
        print("Please ensure the Gemini CLI is installed and in your system's PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("\nError: 'gemini skills link' command failed.")
        print("Please check the output above for the error message from the Gemini CLI.")
        sys.exit(1)


if __name__ == '__main__':
    main()
