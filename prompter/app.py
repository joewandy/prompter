import os
import fnmatch
import time
import streamlit as st
from pathlib import Path
from typing import List, Dict, Optional

############################################
# 1. PROMPT LIBRARY (TEMPLATES + Examples) #
############################################
# Expanded library for various software/web dev, ML, research, and bioinformatics tasks
PROMPT_LIBRARY = {
    "None (No Template)": "",
    "Web Development Bug Fix": (
        "You are a skilled web developer focusing on debugging issues in front-end or back-end.\n"
        "Identify the root cause of the bug, then propose a fix.\n"
        "If reflection is enabled, revisit your fix to ensure it's robust.\n"
    ),
    "Backend Refactoring (Microservices)": (
        "You are an expert in microservices architecture.\n"
        "Refactor the provided codebase to improve modularity and clarity.\n"
        "Address any code smells or poor design patterns.\n"
    ),
    "Machine Learning Model Improvement": (
        "You specialize in ML model refinement.\n"
        "Look for opportunities to enhance model performance (regularization, hyperparameter tuning, etc.).\n"
        "If reflection is enabled, double-check for data leakage or training instability.\n"
    ),
    "Data Analysis / Visualization": (
        "You are a data scientist focusing on analysis and visualization.\n"
        "Suggest better ways to structure data, create plots, or derive insights.\n"
        "Consider performance on large datasets.\n"
    ),
    "Academic Research Support": (
        "You assist in academic research coding tasks.\n"
        "Pay attention to reproducibility, clarity, and references to relevant literature.\n"
        "If reflection is enabled, ensure the final code follows best research practices.\n"
    ),
    "Bioinformatics Workflow": (
        "You are a bioinformatics specialist.\n"
        "Look for ways to streamline data preprocessing, analysis pipelines (e.g. FASTQ processing,\n"
        "genome assembly scripts, or protein structure code).\n"
        "Check for reproducibility and software dependencies.\n"
    ),
}

###########################################
# 2. HELPER FUNCTIONS FOR FILE MANAGEMENT #
###########################################
def should_exclude(path: str, exclude_patterns: List[str]) -> bool:
    """
    Checks if a given directory or file path should be excluded
    based on the exclude_patterns list.
    """
    for pattern in exclude_patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        if fnmatch.fnmatch(path, pattern):
            return True
        if pattern in path.split(os.sep):
            return True
    return False

def display_folder_tree(
    folder_path: str,
    base_folder: str,
    selected_files: List[str],
    extensions: List[str],
    exclude_patterns: List[str],
    skip_hidden: bool,
    level: int = 0
):
    """
    Recursively displays the folder structure (indentation-based) and
    creates a checkbox for each file with a matching extension.
    Those checkboxes are *checked by default*.
    """
    items = sorted(os.listdir(folder_path))
    for item in items:
        full_item_path = os.path.join(folder_path, item)

        # Skip hidden if desired
        if skip_hidden and item.startswith('.'):
            continue

        # Check exclusion patterns
        if should_exclude(full_item_path, exclude_patterns):
            continue

        indent = " " * (level * 2)

        if os.path.isdir(full_item_path):
            # Just show the directory with indentation
            st.write(f"{indent}📁 **{item}**")
            # Recurse
            display_folder_tree(
                folder_path=full_item_path,
                base_folder=base_folder,
                selected_files=selected_files,
                extensions=extensions,
                exclude_patterns=exclude_patterns,
                skip_hidden=skip_hidden,
                level=level + 1
            )
        else:
            # Check extension
            if any(item.lower().endswith(ext) for ext in extensions):
                rel_path = os.path.relpath(full_item_path, base_folder)
                label = f"{indent}📄 {item}"
                checked = st.checkbox(label, value=True, key=full_item_path)
                if checked:
                    if rel_path not in selected_files:
                        selected_files.append(rel_path)

def read_file_in_chunks(
    full_path: str,
    chunk_size_lines: int,
    max_file_size_mb: Optional[float] = None
) -> List[str]:
    """
    Reads a file in line-based chunks, respecting an optional
    maximum file size limit for truncation. Returns a list of chunk strings.
    """
    try:
        file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
        if max_file_size_mb and file_size_mb > max_file_size_mb:
            # Entire file is too large -> Truncate
            # We'll read first ~100 KB so we at least get some context
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(1024 * 100)
            return [content + f"\n<!-- File truncated, exceeded {max_file_size_mb} MB -->"]
        else:
            # Read in chunks by line
            chunks = []
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                current_lines = []
                line_count = 0
                for line in f:
                    current_lines.append(line)
                    line_count += 1
                    if line_count >= chunk_size_lines:
                        chunks.append("".join(current_lines))
                        current_lines = []
                        line_count = 0
                # Remainder
                if current_lines:
                    chunks.append("".join(current_lines))
            return chunks
    except Exception as e:
        return [f"<!-- Could not read file: {e} -->"]

def read_selected_files(
    folder_path: str,
    selected_files: List[str],
    chunk_size_lines: int,
    max_file_size_mb: Optional[float] = None
) -> List[Dict[str, str]]:
    """
    Reads selected files. If chunking is enabled (chunk_size_lines > 0),
    each chunk is stored as a separate entry with "filename" appended with chunk index.
    """
    source_files = []
    for rel_path in selected_files:
        full_path = os.path.join(folder_path, rel_path)
        # Read in chunks
        chunks = read_file_in_chunks(full_path, chunk_size_lines, max_file_size_mb)
        if len(chunks) == 1:
            # Only one chunk => normal single file
            source_files.append({
                'filename': rel_path,
                'content': chunks[0]
            })
        else:
            # Multiple chunks => label them
            for i, c in enumerate(chunks, start=1):
                chunk_label = f"{rel_path} (CHUNK {i})"
                source_files.append({
                    'filename': chunk_label,
                    'content': c
                })
    return source_files

######################################
# 3. PROMPT GENERATION & FORMATTING  #
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
        '.csv': '',          # plain text
        # Add more mappings if needed
    }
    return mapping.get(ext, '')

def generate_prompt(
    source_files: List[Dict[str, str]],
    problem_description: str,
    template_text: str,
    reflection_enabled: bool,
    step_by_step_instructions: bool,
    num_solutions: int
) -> str:
    """
    Generates a multi-part prompt that includes:
      1. An optional template from the library (like bug fix, refactoring, etc.).
      2. Step-by-step instructions (if enabled).
      3. Code chunks from all selected files.
      4. User's problem description.
      5. Reflection stage (if enabled).
      6. Request for multiple solutions (if num_solutions > 1).
    """
    prompt_parts = []

    # Start with any chosen template
    if template_text.strip():
        prompt_parts.append(template_text.strip())

    # If step-by-step is enabled, we add a structured instruction section
    if step_by_step_instructions:
        prompt_parts.append(
            "### Step-by-Step Instructions\n"
            "1. Understand the code context from the selected files.\n"
            "2. Address the user's specific problem or goal.\n"
            "3. Provide your proposed solution(s)."
        )

    # If multiple solutions requested
    if num_solutions > 1:
        prompt_parts.append(
            f"### Multiple Solutions\n"
            f"Please provide **{num_solutions} distinct solutions** if possible. "
            "Explain your reasoning briefly for each approach."
        )

    # Include code
    prompt_parts.append("### Selected Project Files\n")
    for file_info in source_files:
        language = get_language_extension(file_info['filename'])
        chunk_title = f"File: {file_info['filename']}"
        if language:
            code_block = f"```{language}\n{file_info['content']}\n```"
        else:
            code_block = f"```\n{file_info['content']}\n```"
        prompt_parts.append(f"**{chunk_title}**\n{code_block}\n")

    # The user's problem or question
    prompt_parts.append("### Problem Description")
    final_problem_desc = problem_description.strip() if problem_description.strip() else "No specific description provided."
    prompt_parts.append(final_problem_desc)

    # If reflection is enabled, add reflection stage
    if reflection_enabled:
        reflection_text = (
            "### Reflection Stage\n"
            "After proposing your solution(s), reflect on them:\n"
            " - Check for undefined variables or missing imports.\n"
            " - Ensure it meets the user's needs.\n"
            " - If you see any mistakes, correct them and finalize your solution."
        )
        prompt_parts.append(reflection_text)

    final_prompt = "\n\n".join(prompt_parts).strip()
    return final_prompt

############################
# 4. STREAMLIT MAIN APP    #
############################
def main():
    st.set_page_config(page_title="Advanced ChatGPT Prompt Generator", layout="wide")
    st.title("📝 Advanced ChatGPT Prompt Generator")

    st.markdown("""
    This application integrates multiple **prompt engineering best practices**:
    - **Prompt Library**: Reuse well-crafted templates for software/web dev, ML, academic research, bioinformatics, etc.
    - **Step-by-Step Instructions** (Mishra et al. 2022, Wei et al. 2022): Encourage structured reasoning.
    - **Multiple Solutions** (Wang et al. 2022): Generating several drafts can improve correctness via self-consistency.
    - **Reflection Technique** (Madaan et al. 2023): The model critiques its own solution to catch errors.
    - **Chunking Large Files**: Splits big files into smaller parts to avoid token limit issues.

    For more background:
    - [Chain-of-Thought Prompting Elicits Reasoning](https://arxiv.org/abs/2201.11903)
    - [Self-Refine: Iterative Refinement with Natural Language Feedback](https://arxiv.org/abs/2303.17651)
    - [Self-Consistency Improves Chain of Thought Reasoning](https://arxiv.org/abs/2203.11171)
    """)

    # --- Sidebar Config ---
    st.sidebar.header("Configuration")

    folder_path = st.sidebar.text_input(
        "Folder Path",
        value="",
        placeholder="Enter path to your project folder"
    )
    extensions_input = st.sidebar.text_input(
        "File Extensions",
        value=".py, .js, .ts, .html, .css, .java, .c, .cpp, .cs, .rb, .go, .php, .json, .ipynb, .csv",
        placeholder="Comma-separated, e.g., .py, .js, .ts",
        help="These are the extensions we'll scan for in your folder."
    )

    skip_hidden = st.sidebar.checkbox(
        "Skip Hidden Files/Folders",
        value=True,
        help="If checked, items starting with '.' will be ignored."
    )

    exclude_input = st.sidebar.text_input(
        "Exclude Patterns",
        value=".git, node_modules, venv, .DS_Store",
        placeholder="Comma-separated patterns (e.g. node_modules, venv)"
    )

    max_file_size = st.sidebar.number_input(
        "Max File Size (MB, 0 for unlimited)",
        min_value=0.0,
        value=0.0,
        help="If a file exceeds this size, we'll truncate it to ~100KB. 0 = no limit."
    )

    chunk_size_lines = st.sidebar.number_input(
        "Chunk Size (lines, 0 to disable chunking)",
        min_value=0,
        value=0,
        help="If > 0, we split each file into chunks of this many lines."
    )

    # Prompt library
    st.sidebar.subheader("Prompt Library")
    template_options = list(PROMPT_LIBRARY.keys())
    selected_template_key = st.sidebar.selectbox(
        "Choose a Prompt Template",
        template_options,
        index=0
    )
    chosen_template_text = PROMPT_LIBRARY.get(selected_template_key, "")

    # Additional advanced settings
    step_by_step_instructions = st.sidebar.checkbox(
        "Step-by-Step Instructions",
        value=True,
        help="Adds a structured list of steps in the prompt."
    )
    reflection_enabled = st.sidebar.checkbox(
        "Reflection Stage",
        value=True,
        help="Requests the model to review its own solution for mistakes."
    )
    num_solutions = st.sidebar.slider(
        "Number of Solutions",
        min_value=1,
        max_value=3,
        value=1,
        help="If more than 1, the model is prompted to provide multiple distinct answers."
    )

    # Main content
    if not folder_path or not os.path.isdir(folder_path):
        st.warning("Please enter a valid folder path above.")
        st.stop()

    # Convert extension string to a list, ensuring each has a leading dot
    extensions = []
    for ext in extensions_input.split(','):
        e = ext.strip().lower()
        if e and not e.startswith('.'):
            e = '.' + e
        if e:
            extensions.append(e)

    # Prepare exclusion patterns
    exclusion_patterns = []
    if exclude_input.strip():
        exclusion_patterns = [pat.strip() for pat in exclude_input.split(',') if pat.strip()]

    st.header("Select Files")
    with st.expander("📁 Folder Browser (collapsed by default)", expanded=False):
        selected_files = []
        display_folder_tree(
            folder_path=folder_path,
            base_folder=folder_path,
            selected_files=selected_files,
            extensions=extensions,
            exclude_patterns=exclusion_patterns,
            skip_hidden=skip_hidden,
            level=0
        )
    st.markdown(f"**{len(selected_files)} file(s) selected**")

    # Text area for the user's problem description
    problem_description = st.text_area(
        "Problem Description",
        height=150,
        placeholder="Describe your issue, goal, or question here..."
    )

    # Generate button
    generate_button = st.button("Generate Prompt")

    if generate_button:
        if not selected_files:
            st.error("No files selected. Please select at least one.")
            st.stop()

        st.info("Reading selected files...")
        max_size = max_file_size if max_file_size > 0 else None
        effective_chunk_size = chunk_size_lines if chunk_size_lines > 0 else 999999999

        source_files = read_selected_files(
            folder_path=folder_path,
            selected_files=selected_files,
            chunk_size_lines=effective_chunk_size,
            max_file_size_mb=max_size
        )

        final_prompt = generate_prompt(
            source_files=source_files,
            problem_description=problem_description,
            template_text=chosen_template_text,
            reflection_enabled=reflection_enabled,
            step_by_step_instructions=step_by_step_instructions,
            num_solutions=num_solutions
        )

        st.success("Prompt generated successfully!")
        st.text_area("Generated Prompt", final_prompt, height=400)
        st.download_button(
            label="Download Prompt",
            data=final_prompt,
            file_name="chatgpt_prompt.txt",
            mime="text/plain"
        )

    st.markdown("""
    ---
    **References and Further Reading**  
    - [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models (Wei et al. 2022)](https://arxiv.org/abs/2201.11903)  
    - [Self-Refine: Iterative Refinement with Natural Language Feedback (Madaan et al. 2023)](https://arxiv.org/abs/2303.17651)  
    - [Self-Consistency Improves Chain of Thought Reasoning (Wang et al. 2022)](https://arxiv.org/abs/2203.11171)
    """)

if __name__ == "__main__":
    main()
