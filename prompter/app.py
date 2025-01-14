import os
import streamlit as st
from pathlib import Path
from typing import List, Dict, Optional
import time


def collect_source_files(
        folder_path: str,
        extensions: List[str],
        callback=None,
        skip_hidden: bool = True,
        max_file_size_mb: Optional[float] = None
) -> List[Dict[str, str]]:
    """
    Collects source files from the specified folder and its subfolders based on the given extensions.
    Optionally skips hidden directories/files and enforces a max file size limit.

    Args:
        folder_path (str): Path to the folder.
        extensions (List[str]): List of file extensions to include.
        callback (function, optional): Function to update progress. Defaults to None.
        skip_hidden (bool, optional): Whether to skip hidden directories and files. Defaults to True.
        max_file_size_mb (float, optional): Maximum allowed file size in MB to read fully.
            If a file exceeds this size, it will be truncated or skipped. Defaults to None.

    Returns:
        List[Dict[str, str]]: List of dictionaries containing 'filename' and 'content'.
    """
    source_files = []
    total_files = 0

    # Clean and standardize extensions (ensure leading dot)
    cleaned_extensions = []
    for ext in extensions:
        ext = ext.strip().lower()
        if not ext.startswith('.'):
            ext = '.' + ext
        cleaned_extensions.append(ext)

    # First, count total files to process for progress tracking
    for root, dirs, files in os.walk(folder_path):
        if skip_hidden:
            # Filter out hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if skip_hidden and file.startswith('.'):
                continue
            if any(file.lower().endswith(e) for e in cleaned_extensions):
                total_files += 1

    if total_files == 0:
        return source_files  # No files to process

    processed_files = 0

    # Process each file
    for root, dirs, files in os.walk(folder_path):
        if skip_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if skip_hidden and file.startswith('.'):
                continue
            if any(file.lower().endswith(e) for e in cleaned_extensions):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, folder_path)

                file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
                content = ""
                try:
                    if max_file_size_mb and file_size_mb > max_file_size_mb:
                        # Option: skip or read only a snippet.
                        # Here, we choose to truncate:
                        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read(1024 * 100)  # Read first ~100 KB
                            content += f"\n<!-- File truncated because it exceeded {max_file_size_mb} MB -->"
                    else:
                        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                except Exception as e:
                    content = f'<!-- Could not read file: {e} -->'

                source_files.append({
                    'filename': relative_path,
                    'content': content
                })

                processed_files += 1
                if callback:
                    progress = int((processed_files / total_files) * 100)
                    callback(progress)
                # Optional: time.sleep to simulate work
                # time.sleep(0.05)
    return source_files


def get_language_extension(filename: str) -> str:
    """
    Maps file extensions to language identifiers for syntax highlighting.

    Args:
        filename (str): Name of the file.

    Returns:
        str: Language identifier.
    """
    ext = Path(filename).suffix.lower()
    mapping = {
        '.py': 'python',
        '.js': 'javascript',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.go': 'go',
        '.php': 'php',
        '.html': 'html',
        '.css': 'css',
        '.ts': 'typescript',
        '.swift': 'swift',
        '.kt': 'kotlin',
    }
    return mapping.get(ext, '')


def generate_prompt(source_files: List[Dict[str, str]], problem_description: str) -> str:
    """
    Generates a prompt by compiling source files and problem description.

    Args:
        source_files (List[Dict[str, str]]): List of source files with filenames and contents.
        problem_description (str): Description of the problem.

    Returns:
        str: Compiled prompt.
    """
    prompt = "I need assistance with the following project files:\n\n"
    for file in source_files:
        language = get_language_extension(file['filename'])
        prompt += f"### File: {file['filename']}\n"
        if language:
            prompt += f"```{language}\n{file['content']}\n```\n\n"
        else:
            prompt += f"```\n{file['content']}\n```\n\n"
    prompt += f"### Problem Description\n{problem_description}"
    return prompt


def main():
    """
    The main Streamlit app for generating a ChatGPT prompt from source files.
    """
    st.set_page_config(page_title="ChatGPT Prompt Generator", layout="wide")
    st.title("📝 ChatGPT Prompt Generator")

    st.markdown("""
    This application allows you to generate a comprehensive prompt for ChatGPT by 
    compiling source files from a specified folder along with a problem description.
    """)

    # Sidebar for inputs
    st.sidebar.header("Configuration")

    folder_path = st.sidebar.text_input(
        "Folder Path",
        value="",
        placeholder="Enter the path to your project folder"
    )
    extensions_input = st.sidebar.text_input(
        "File Extensions",
        value=".py, .js, .java, .c, .cpp, .cs, .rb, .go, .php, .html, .css, .json, .md",
        placeholder="e.g., .py, .js, .java"
    )

    skip_hidden = st.sidebar.checkbox("Skip Hidden Files/Folders", value=True)
    max_file_size = st.sidebar.number_input(
        "Max File Size (MB, 0 for unlimited)",
        min_value=0.0,
        value=0.0
    )

    st.sidebar.markdown("""
    ---
    **Instructions**:
    1. Enter the path to the folder containing your source files.
    2. Specify the file extensions to include, separated by commas.
    3. Enter a description of the problem you're encountering.
    4. (Optional) Set whether to skip hidden files/folders and set a max file size limit if desired.
    5. Click "Generate Prompt" to compile the prompt.
    """)

    # Main content
    problem_description = st.text_area(
        "Problem Description",
        height=200,
        placeholder="Describe the issue you're facing here..."
    )

    generate_button = st.button("Generate Prompt")

    if generate_button:
        if not folder_path or not os.path.isdir(folder_path):
            st.error("Please enter a valid folder path.")
            return

        # Clean up the extensions input
        if not extensions_input.strip():
            st.error("Please specify at least one file extension.")
            return

        problem_desc_input = problem_description.strip()
        if not problem_desc_input:
            warn_placeholder = st.warning(
                "You haven't entered a problem description. Proceed without it?"
            )
            proceed = st.button("Proceed Anyway")
            if not proceed:
                return

        # Now we have everything we need, proceed
        extensions = [ext.strip() for ext in extensions_input.split(',') if ext.strip()]

        with st.spinner("Collecting source files..."):
            progress_bar = st.progress(0)

            def update_progress(pct):
                progress_bar.progress(pct)
                time.sleep(0.01)

            # If user sets max_file_size to 0, treat it as unlimited
            max_size = max_file_size if max_file_size > 0 else None

            source_files = collect_source_files(
                folder_path=folder_path,
                extensions=extensions,
                callback=update_progress,
                skip_hidden=skip_hidden,
                max_file_size_mb=max_size
            )

        if not source_files:
            st.info("No source files found with the specified extensions.")
        else:
            prompt = generate_prompt(source_files, problem_desc_input)
            st.success("Prompt generated successfully!")
            st.text_area("Generated Prompt", prompt, height=400)
            st.download_button(
                label="Download Prompt",
                data=prompt,
                file_name="chatgpt_prompt.txt",
                mime="text/plain"
            )

    st.markdown("""
    ---
    **Note**: Including the entire content of all source files may result in a very large prompt. 
    Ensure that the total size does not exceed ChatGPT's token limits (e.g., GPT-4 can handle up to 
    ~8,000 tokens). If you encounter issues, consider selectively including only the relevant files 
    or sections, or using the size limit feature above.
    """)


if __name__ == "__main__":
    main()
