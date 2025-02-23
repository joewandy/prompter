import os
import streamlit as st
from pathlib import Path
from typing import List, Dict

##########################
# 1. EXTENSION PRESETS   #
##########################
EXTENSION_PRESETS = {
    "None": "",
    "Django": ".py, .html, .css, .js",
    "Machine Learning": ".py, .ipynb, .csv, .txt",
    "Frontend (JS/TS)": ".html, .css, .js, .ts, .json",
    "Backend (General)": ".py, .js, .ts, .java, .c, .cpp, .cs, .go, .php",
}

#############################
# 2. EXCLUSION PRESET LISTS #
#############################
# You can adjust these to suit typical project structures.
# They will be combined with a base exclusion (below) depending on user's choice.
EXCLUSION_PRESETS = {
    "None": [],
    "Django": ["migrations"],               # Example for Django
    "Machine Learning": [".ipynb_checkpoints"],  # Common hidden notebook checkpoints
    "Frontend (JS/TS)": ["node_modules"],   # Common for JS projects
    "Backend (General)": ["node_modules", "venv"]  # Generic example
}

###############################
# 3. BASE EXCLUSIONS & HIDDEN #
###############################
BASE_EXCLUDES = [".git", "__pycache__", ".venv"]  # Always excluded by default

############################################
# 4. PROMPT LIBRARY (Minimal / Expandable) #
############################################
# Short, direct instructions for reasoning models.
PROMPT_LIBRARY = {
    "None (No Template)": "",
    "Bug Fix / Debug": (
        "You are a specialized debugging model. Identify the root cause of any bug and propose a succinct fix."
    ),
    "Performance Optimization": (
        "Optimize the code or architecture for performance improvements, providing a direct, concise approach."
    ),
    "Security Audit": (
        "Review the code for security vulnerabilities. Summarize issues and propose short solutions."
    ),
    "Refactoring for Clarity": (
        "Refactor the code to improve readability and maintainability. Provide clear, concise recommendations."
    ),
    "Database Schema Advice": (
        "Review relevant DB schemas or data models. Suggest a concise plan that aligns with best practices."
    ),
    "ML Model Tuning": (
        "Evaluate the ML code or pipeline. Recommend hyperparameter or structural changes to improve performance. Keep it direct."
    ),
    "Bioinformatics Pipeline": (
        "You are a bioinformatics expert. Suggest succinct improvements for data processing or analysis pipelines."
    ),
    "Academic Code Snippet": (
        "Check the provided academic or research code for correctness and clarity. If needed, propose short fixes."
    ),
    "Testing Strategy": (
        "Propose a concise testing strategy for the given code or system. Outline relevant test cases briefly."
    ),
}

###########################################
# 5. HELPER FUNCTIONS FOR FILE MANAGEMENT #
###########################################
def should_skip_hidden(item_path: str) -> bool:
    """
    Return True if the file or folder is hidden (begins with '.'),
    or any parent folder is hidden.
    """
    base_name = os.path.basename(item_path)
    if base_name.startswith('.'):
        return True
    # Check parents for hidden directories
    return any(part.startswith('.') for part in Path(item_path).parts)

def should_exclude_path(item_path: str, exclude_list: List[str]) -> bool:
    """
    Return True if item_path matches any of the folders in exclude_list.
    Matching logic: if the exclude token appears in the path's parts.
    """
    parts = Path(item_path).parts
    for ex in exclude_list:
        ex = ex.strip()
        if ex and ex in parts:
            return True
    return False

def display_folder_files(
    folder_path: str,
    base_folder: str,
    selected_files: List[str],
    extensions: List[str],
    exclude_list: List[str],
    level: int = 0
):
    """
    Recursively displays the folder structure (indentation-based) and
    creates a checkbox for each file with a matching extension.
    Skips hidden files/folders and any that match exclude_list.
    """
    try:
        items = sorted(os.listdir(folder_path))
    except FileNotFoundError:
        st.error("Folder not found. Please verify your folder path.")
        return

    for item in items:
        full_item_path = os.path.join(folder_path, item)

        # Skip hidden files/folders
        if should_skip_hidden(full_item_path):
            continue

        # Skip excluded folders/files
        if should_exclude_path(full_item_path, exclude_list):
            continue

        if os.path.isdir(full_item_path):
            indent = " " * (level * 2)
            st.write(f"{indent}📁 **{item}**")
            display_folder_files(
                folder_path=full_item_path,
                base_folder=base_folder,
                selected_files=selected_files,
                extensions=extensions,
                exclude_list=exclude_list,
                level=level + 1
            )
        else:
            # Check extension
            if any(item.lower().endswith(ext) for ext in extensions):
                indent = " " * (level * 2)
                rel_path = os.path.relpath(full_item_path, base_folder)
                label = f"{indent}📄 {item}"
                checked = st.checkbox(label, value=True, key=full_item_path)
                if checked:
                    if rel_path not in selected_files:
                        selected_files.append(rel_path)

def read_entire_file(full_path: str) -> str:
    """
    Read an entire file into a single string.
    """
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"<!-- Could not read file: {e} -->"

def read_selected_files(
    folder_path: str,
    selected_files: List[str]
) -> List[Dict[str, str]]:
    """
    Reads each selected file in full and returns a list of dicts.
    """
    source_files = []
    for rel_path in selected_files:
        full_path = os.path.join(folder_path, rel_path)
        content = read_entire_file(full_path)
        source_files.append({
            'filename': rel_path,
            'content': content
        })
    return source_files

######################################
# 6. PROMPT GENERATION & FORMATTING  #
######################################
def get_language_extension(filename: str) -> str:
    """
    Maps file extensions to language identifiers for syntax highlighting.
    """
    ext = Path(filename).suffix.lower()
    mapping = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.go': 'go',
        '.php': 'php',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.ipynb': 'python',  # Jupyter notebooks considered Python
        '.csv': '',
        '.txt': '',
    }
    return mapping.get(ext, '')

def generate_prompt(
    source_files: List[Dict[str, str]],
    problem_description: str,
    template_text: str
) -> str:
    """
    Generates a streamlined prompt for a reasoning model:
      - Optionally starts with a template
      - Includes the relevant code
      - States the user's question or task
    """
    prompt_parts = []

    # Template (if any)
    if template_text.strip():
        prompt_parts.append(template_text.strip())

    # Include code context
    prompt_parts.append("## Relevant Code")
    for file_info in source_files:
        language = get_language_extension(file_info['filename'])
        if language:
            code_block = f"```{language}\n{file_info['content']}\n```"
        else:
            code_block = f"```\n{file_info['content']}\n```"
        prompt_parts.append(f"**File: {file_info['filename']}**\n{code_block}\n")

    # User's problem
    prompt_parts.append("## Task or Question")
    final_problem_desc = problem_description.strip() if problem_description.strip() else "No specific description provided."
    prompt_parts.append(final_problem_desc)

    final_prompt = "\n\n".join(prompt_parts).strip()
    return final_prompt

############################
# 7. STREAMLIT MAIN APP    #
############################
def main():
    st.set_page_config(page_title="Prompter for Reasoning Models", layout="wide")
    st.title("🔎 Prompter for Reasoning Models")

    # Usage instructions (condensed into a paragraph)
    st.markdown("""
    **Welcome to Prompter** – a lightweight tool for assembling concise, direct prompts for OpenAI _reasoning models_ like **o1** or **o3-mini**. Choose a folder, select relevant files, optionally pick an extension preset or template, then provide a brief description of your question. After generating, copy the output into your reasoning model’s interface. By keeping prompts short and unambiguous, and letting the model do its own internal reasoning, you'll often see more accurate results.
    """)

    st.sidebar.header("Configuration")

    # Folder path input
    folder_path = st.sidebar.text_input(
        "Folder Path",
        value="",
        placeholder="Enter path to your project folder"
    )

    # Extension Preset
    preset_label = st.sidebar.selectbox(
        "Extension Preset",
        list(EXTENSION_PRESETS.keys()),
        index=0
    )
    preset_extensions = EXTENSION_PRESETS[preset_label]

    # Extension override
    extensions_input = st.sidebar.text_input(
        "File Extensions (override or add to preset)",
        value=preset_extensions,
        placeholder="Comma-separated e.g. .py, .js, .ts"
    )

    # Exclusion preset combination
    base_excludes = BASE_EXCLUDES.copy()
    preset_exclusions = EXCLUSION_PRESETS.get(preset_label, [])
    combined_exclusions = list(set(base_excludes + preset_exclusions))

    # Display / override exclusion
    exclusion_str = ", ".join(combined_exclusions)
    user_exclusion_input = st.sidebar.text_input(
        "Excluded Folders (override below)",
        value=exclusion_str
    )
    # Convert user override into list
    final_exclusions = [ex.strip() for ex in user_exclusion_input.split(',') if ex.strip()]

    # Prompt Template (Optional)
    st.sidebar.subheader("Prompt Template (Optional)")
    template_options = list(PROMPT_LIBRARY.keys())
    selected_template_key = st.sidebar.selectbox(
        "Choose a Template",
        template_options,
        index=0
    )
    chosen_template_text = PROMPT_LIBRARY.get(selected_template_key, "")

    # Validate folder
    if not folder_path or not os.path.isdir(folder_path):
        st.warning("Please enter a valid folder path above.")
        st.stop()

    # Convert extension string to a list
    extensions = []
    for ext in extensions_input.split(','):
        e = ext.strip().lower()
        if e and not e.startswith('.'):
            e = '.' + e
        if e:
            extensions.append(e)

    st.header("Select Files")
    with st.expander("Folder Browser (hidden + excluded folders skipped)", expanded=True):
        selected_files = []
        display_folder_files(
            folder_path=folder_path,
            base_folder=folder_path,
            selected_files=selected_files,
            extensions=extensions,
            exclude_list=final_exclusions
        )

    st.markdown(f"**{len(selected_files)} file(s) selected**")

    problem_description = st.text_area(
        "Describe Your Task or Question",
        height=150,
        placeholder="e.g., Summarize this code or find potential bugs..."
    )

    generate_button = st.button("Generate Prompt")

    if generate_button:
        if not selected_files:
            st.error("No files selected. Please select at least one.")
            return

        source_files = read_selected_files(
            folder_path=folder_path,
            selected_files=selected_files
        )

        final_prompt = generate_prompt(
            source_files=source_files,
            problem_description=problem_description,
            template_text=chosen_template_text
        )

        st.success("Prompt generated successfully!")
        st.text_area(
            "Generated Prompt (copy/paste into your o-series model)",
            final_prompt,
            height=400
        )
        st.download_button(
            label="Download Prompt",
            data=final_prompt,
            file_name="reasoning_prompt.txt",
            mime="text/plain"
        )

if __name__ == "__main__":
    main()
