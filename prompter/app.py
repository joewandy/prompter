import difflib
import fnmatch
import os
import re
from pathlib import Path
from typing import List, Dict

import dash
import dash.exceptions
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import dcc, html, Input, Output, State, ALL
from dash._dash_renderer import _set_react_version
from dash_iconify import DashIconify

_set_react_version("18.2.0")

EXTENSION_PRESETS = {
    "None": ".py, .js, .ts, .html, .css, .json",
    "Academic Code": ".py, .ipynb, .r, .csv, .txt",
    "Android (Kotlin/Java)": ".kt, .java, .xml",
    "Backend (General)": ".py, .js, .ts, .java, .c, .cpp, .cs, .go, .php",
    "Bioinformatics": ".py, .ipynb, .r, .csv, .tsv, .txt",
    "Data Science": ".py, .ipynb, .r, .csv, .tsv, .txt",
    "Django": ".py, .html, .css, .js",
    "Frontend (JS/TS)": ".html, .css, .js, .ts, .json",
    "Machine Learning": ".py, .ipynb, .csv, .txt",
    "React": ".js, .jsx, .ts, .tsx, .json, .html, .css",
    "VueJS": ".html, .css, .vue, .js, .ts, .json",
    "Angular": ".html, .css, .ts, .json",
    "iOS (Swift)": ".swift, .h, .m, .mm, .plist",
    "Performance Optimization": ".py, .js, .ts, .html, .css, .json",
}

BASE_EXCLUSIONS = {
    ".git",
    ".gitignore",
    ".pycache",
    "pycache",
    "__pycache__",
    "node_modules",
    ".ipynb_checkpoints",
}

PRESET_EXCLUSION_MAP = {
    "Django": {"venv", "migrations"},
    "Machine Learning": {"venv", ".ipynb_checkpoints"},
    "Frontend (JS/TS)": {"node_modules"},
    "Backend (General)": {"venv", "node_modules"},
    "VueJS": {"node_modules"},
    "Angular": {"node_modules"},
    "React": {"node_modules"},
    "iOS (Swift)": {"Pods"},
    "Android (Kotlin/Java)": {"build", ".gradle"},
    "Data Science": {"venv", ".ipynb_checkpoints"},
}

PROMPT_LIBRARY = {
    "None (No Template)": "",
    "Academic Code": "Check academic code correctness. If needed, propose short fixes.",
    "Bioinformatics": "Make succinct improvements for bioinformatics data processing or analysis.",
    "Bug Fix / Debug": "You are a specialized debugging model. Identify and fix any bugs succinctly.",
    "Database Schema Advice": "Suggest best-practice improvements for database-related code.",
    "ML Model Tuning": "Optimize the ML code or pipeline with short recommended changes.",
    "Performance Optimization": "Optimize the code or architecture concisely for better performance.",
    "Refactoring": "Refactor the code for clarity and maintainability.",
    "Security Audit": "Review code for security issues. Provide short, direct mitigations.",
    "Testing Strategy": "Propose a concise testing strategy for the given code or system.",
}


class LLMUpdateParser:
    """
    A dedicated parser class to handle the specified output format:
    file: path/to/file.ext
    --- START CODE ---
    ...
    --- END CODE ---
    """

    def parse_response(self, text: str) -> (List[Dict[str, str]], str):
        lines = text.splitlines()
        blocks = []
        error_message = ""

        current_file = None
        current_code = []
        expecting_start = False
        in_code_block = False

        for idx, line in enumerate(lines):
            line_stripped = line.strip()

            # Detect 'file:'
            if line_stripped.lower().startswith("file:"):
                # If we were still in a code block, that means we didn't see '--- END CODE ---'
                if in_code_block:
                    error_message = f"Missing '--- END CODE ---' before starting new file block at line {idx+1}"
                    return [], error_message

                parts = line_stripped.split(":", 1)
                if len(parts) < 2:
                    error_message = f"Invalid file line at line {idx+1}"
                    return [], error_message

                filename = parts[1].strip()
                current_file = filename
                current_code = []
                expecting_start = True
                in_code_block = False
                continue

            if expecting_start:
                if line_stripped == "--- START CODE ---":
                    expecting_start = False
                    in_code_block = True
                else:
                    error_message = (
                        f"Expected '--- START CODE ---' after file line for file '{current_file}' "
                        f"but got '{line_stripped}' at line {idx+1}"
                    )
                    return [], error_message
                continue

            if in_code_block:
                if line_stripped == "--- END CODE ---":
                    # End of this file's code block
                    blocks.append(
                        {
                            "filename": current_file,
                            "new_content": "\n".join(current_code),
                        }
                    )
                    in_code_block = False
                    current_file = None
                    current_code = []
                else:
                    current_code.append(line)
                continue

        # If we never saw '--- END CODE ---' for some block
        if in_code_block:
            error_message = f"Missing '--- END CODE ---' for file '{current_file}'"
            return [], error_message

        return blocks, error_message


def generate_side_by_side_diff(original: str, new_content: str, filename: str) -> str:
    if not original and not new_content:
        return f"File '{filename}' is empty both before and after."
    diff_html = difflib.HtmlDiff(wrapcolumn=80).make_table(
        original.splitlines(),
        new_content.splitlines(),
        fromdesc=f"a/{filename}",
        todesc=f"b/{filename}",
    )
    return diff_html


def is_hidden_or_excluded(path: str, exclusion_list: List[str]) -> bool:
    p = Path(path)
    if any(part.startswith(".") for part in p.parts):
        return True
    for pattern in exclusion_list:
        if pattern in p.parts:
            return True
        if fnmatch.fnmatch(path, f"*{pattern}*"):
            return True
    return False


def add_all_files(
    folder_path: str,
    base_path: str,
    extensions: List[str],
    exclusion_list: List[str],
    selected_files: List[str],
):
    for root, dirs, files in os.walk(folder_path):
        if is_hidden_or_excluded(root, exclusion_list):
            dirs[:] = []
            continue
        dirs[:] = [
            d
            for d in dirs
            if not is_hidden_or_excluded(os.path.join(root, d), exclusion_list)
        ]
        for file in files:
            full_file_path = os.path.join(root, file)
            if is_hidden_or_excluded(full_file_path, exclusion_list):
                continue
            if any(file.lower().endswith(ext) for ext in extensions):
                rel_path = os.path.relpath(full_file_path, base_path)
                if rel_path not in selected_files:
                    selected_files.append(rel_path)


def read_entire_file(full_path: str) -> str:
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"<!-- Could not read file: {e} -->"


def read_selected_files(
    folder_path: str, selected_files: List[str]
) -> List[Dict[str, str]]:
    base_folder_name = os.path.basename(folder_path.rstrip("/"))
    source_files = []
    for rel_path in selected_files:
        full_path = os.path.join(folder_path, rel_path)
        display_path = f"{base_folder_name}/{rel_path}"
        content = read_entire_file(full_path)
        if not content.strip():
            continue
        source_files.append(
            {
                "filename": rel_path,
                "display_path": display_path,
                "content": content,
            }
        )
    return source_files


def get_language_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".go": "go",
        ".php": "php",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".ipynb": "python",
        ".csv": "",
        ".txt": "",
        ".vue": "html",
        ".swift": "swift",
        ".kt": "kotlin",
        ".xml": "xml",
        ".r": "r",
    }
    return mapping.get(ext, "")


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

mantine_theme = {
    "fontFamily": "Inter, sans-serif",
    "primaryColor": "indigo",
    "defaultRadius": "sm",
}

app.layout = dmc.MantineProvider(
    theme=mantine_theme,
    children=dbc.Container(
        [
            html.H2("🔎 Prompter for Reasoning Models", style={"color": "#2c3e50"}),
            html.P(
                "Welcome to the 🏆 ultimate prompter solution for your coding projects. "
                "This interactive multi-tab application is designed to gather code snippets "
                "from your entire project, letting you quickly assemble an entire prompt. "
                "Use it to highlight relevant sections of your code to guide your reasoning model. "
                "Additional features are in the pipeline to enhance your developer experience. "
                "Whether you need debugging support, performance tuning, or code reviews, "
                "our prompter streamlines the process by consolidating your code context "
                "and problem statements all in one place. Stay tuned for more updates!"
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        "Select Project Folder", style={"backgroundColor": "#eaf2f8"}
                    ),
                    dbc.CardBody(
                        [
                            dbc.Label("Folder Path"),
                            dbc.Input(
                                id="folder-path",
                                type="text",
                                placeholder="Enter path to your folder",
                            ),
                        ]
                    ),
                ],
                style={
                    "marginTop": "25px",
                    "border": "none",
                    "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)",
                },
            ),
            dbc.Card(
                [
                    dbc.CardBody(
                        [
                            dbc.Tabs(
                                [
                                    dbc.Tab(
                                        label="Prompter",
                                        children=[
                                            html.Br(),
                                            html.P(
                                                "This tab is your main interface to gather and assemble code from the specified "
                                                "folder or directory. You can select which files to include, preview your choices, "
                                                "and generate a complete prompt. Perfect for debugging sessions, code reviews, or "
                                                "any scenario needing a thorough code context for your reasoning model. "
                                                "Just point to your folder, pick file extensions, and you're ready to go! 🚀"
                                            ),
                                            dbc.Card(
                                                [
                                                    dbc.CardHeader(
                                                        "🛠️ Configuration",
                                                        style={
                                                            "backgroundColor": "#eaf2f8"
                                                        },
                                                    ),
                                                    dbc.CardBody(
                                                        [
                                                            dbc.Row(
                                                                [
                                                                    dbc.Col(
                                                                        [
                                                                            html.H5(
                                                                                "Configuration"
                                                                            ),
                                                                            dbc.Label(
                                                                                "Extension Preset"
                                                                            ),
                                                                            dcc.Dropdown(
                                                                                id="extension-preset",
                                                                                options=[
                                                                                    {
                                                                                        "label": k,
                                                                                        "value": k,
                                                                                    }
                                                                                    for k in sorted(
                                                                                        EXTENSION_PRESETS.keys()
                                                                                    )
                                                                                ],
                                                                                value="None",
                                                                            ),
                                                                            html.Br(),
                                                                            dbc.Label(
                                                                                "File Extensions"
                                                                            ),
                                                                            dbc.Input(
                                                                                id="file-extensions",
                                                                                type="text",
                                                                                placeholder=".py, .js, .ts",
                                                                            ),
                                                                            html.Br(),
                                                                            dbc.Label(
                                                                                "Current Exclusion List"
                                                                            ),
                                                                            dbc.Input(
                                                                                id="exclusions-field",
                                                                                type="text",
                                                                                placeholder=".git, .gitignore, .pycache",
                                                                            ),
                                                                            html.Br(),
                                                                            dbc.Label(
                                                                                "Prompt Template (Optional)"
                                                                            ),
                                                                            dcc.Dropdown(
                                                                                id="prompt-template",
                                                                                options=[
                                                                                    {
                                                                                        "label": k,
                                                                                        "value": k,
                                                                                    }
                                                                                    for k in sorted(
                                                                                        PROMPT_LIBRARY.keys()
                                                                                    )
                                                                                ],
                                                                                value="None (No Template)",
                                                                            ),
                                                                            html.Br(),
                                                                            dbc.Alert(
                                                                                id="alert-no-files",
                                                                                color="danger",
                                                                                is_open=False,
                                                                            ),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                    dbc.Col(
                                                                        [
                                                                            html.H5(
                                                                                "File/Folder Tree"
                                                                            ),
                                                                            dbc.Alert(
                                                                                "Enter a valid folder path to see contents.",
                                                                                id="folder-warning",
                                                                                color="warning",
                                                                                is_open=True,
                                                                            ),
                                                                            html.Div(
                                                                                id="selected-count",
                                                                                children="0 file(s) selected",
                                                                                style={
                                                                                    "marginTop": "15px"
                                                                                },
                                                                            ),
                                                                            html.Div(
                                                                                id="filetree_div"
                                                                            ),
                                                                        ],
                                                                        md=8,
                                                                    ),
                                                                ],
                                                                style={
                                                                    "marginTop": "25px"
                                                                },
                                                            ),
                                                        ]
                                                    ),
                                                ],
                                                style={
                                                    "marginTop": "25px",
                                                    "border": "none",
                                                    "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)",
                                                },
                                            ),
                                            dbc.Card(
                                                [
                                                    dbc.CardHeader(
                                                        "✏️ Prompt Generation",
                                                        style={
                                                            "backgroundColor": "#fcf0e6"
                                                        },
                                                    ),
                                                    dbc.CardBody(
                                                        [
                                                            dmc.Paper(
                                                                p="md",
                                                                style={
                                                                    "marginTop": "30px"
                                                                },
                                                                children=[
                                                                    dbc.Row(
                                                                        [
                                                                            dbc.Col(
                                                                                [
                                                                                    html.H4(
                                                                                        "Describe Your Task or Question"
                                                                                    ),
                                                                                    dcc.Textarea(
                                                                                        id="problem-description",
                                                                                        style={
                                                                                            "width": "100%",
                                                                                            "height": "200px",
                                                                                        },
                                                                                    ),
                                                                                ],
                                                                                md=6,
                                                                            ),
                                                                            dbc.Col(
                                                                                [
                                                                                    html.H4(
                                                                                        "Additional Information"
                                                                                    ),
                                                                                    dcc.Textarea(
                                                                                        id="additional-info",
                                                                                        style={
                                                                                            "width": "100%",
                                                                                            "height": "200px",
                                                                                        },
                                                                                    ),
                                                                                ],
                                                                                md=6,
                                                                            ),
                                                                        ]
                                                                    ),
                                                                    html.Br(),
                                                                    dbc.Row(
                                                                        [
                                                                            dbc.Col(
                                                                                [
                                                                                    html.H4(
                                                                                        "Constraints / Warnings"
                                                                                    ),
                                                                                    dcc.Textarea(
                                                                                        id="constraints-warnings",
                                                                                        style={
                                                                                            "width": "100%",
                                                                                            "height": "200px",
                                                                                        },
                                                                                    ),
                                                                                ],
                                                                                md=6,
                                                                            ),
                                                                            dbc.Col(
                                                                                [
                                                                                    html.H4(
                                                                                        "Output Format"
                                                                                    ),
                                                                                    dcc.Textarea(
                                                                                        id="output-format",
                                                                                        style={
                                                                                            "width": "100%",
                                                                                            "height": "200px",
                                                                                        },
                                                                                        value='file: path/to/file.ext\n--- START CODE ---\n<entire new content for that file>\n--- END CODE ---\n\nRepeat the above block for each file changed.\n\nExample:\nfile: src/main.py\n--- START CODE ---\ndef my_function():\n    print("Hello World!")\n--- END CODE ---\n\nfile: requirements.txt\n--- START CODE ---\nrequests==2.25.1\nnumpy==1.20.0\n--- END CODE ---',
                                                                                    ),
                                                                                ],
                                                                                md=6,
                                                                            ),
                                                                        ]
                                                                    ),
                                                                    html.Br(),
                                                                    dbc.Row(
                                                                        [
                                                                            dbc.Col(
                                                                                [
                                                                                    dbc.Button(
                                                                                        "Generate Prompt",
                                                                                        id="generate-button",
                                                                                        color="primary",
                                                                                        style={
                                                                                            "margin-right": "10px"
                                                                                        },
                                                                                    ),
                                                                                    dbc.Button(
                                                                                        "Copy Prompt",
                                                                                        id="copy-prompt-btn",
                                                                                        color="secondary",
                                                                                        style={
                                                                                            "margin-right": "10px"
                                                                                        },
                                                                                    ),
                                                                                    html.Span(
                                                                                        id="download-link-container",
                                                                                        style={
                                                                                            "marginLeft": "10px"
                                                                                        },
                                                                                    ),
                                                                                ],
                                                                                width=12,
                                                                            ),
                                                                        ]
                                                                    ),
                                                                    html.Br(),
                                                                    dbc.Row(
                                                                        [
                                                                            dbc.Col(
                                                                                [
                                                                                    html.H4(
                                                                                        "Generated Prompt"
                                                                                    ),
                                                                                    dcc.Textarea(
                                                                                        id="final-prompt-output",
                                                                                        style={
                                                                                            "width": "100%",
                                                                                            "height": "300px",
                                                                                        },
                                                                                        readOnly=False,
                                                                                    ),
                                                                                    dcc.Store(
                                                                                        id="dummy-store",
                                                                                        data="",
                                                                                    ),
                                                                                ],
                                                                                width=12,
                                                                            ),
                                                                        ]
                                                                    ),
                                                                ],
                                                            ),
                                                        ]
                                                    ),
                                                ],
                                                style={
                                                    "marginTop": "25px",
                                                    "border": "none",
                                                    "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)",
                                                },
                                            ),
                                        ],
                                    ),
                                    dbc.Tab(
                                        label="Apply LLM Updates",
                                        children=[
                                            html.Br(),
                                            html.H4("Paste LLM Response Below"),
                                            dbc.Textarea(
                                                id="llm-response-input",
                                                style={
                                                    "width": "100%",
                                                    "height": "200px",
                                                },
                                                placeholder="Paste LLM's updated code blocks here (following the specified format)",
                                            ),
                                            html.Br(),
                                            dbc.Button(
                                                "Generate Diffs",
                                                id="generate-diffs-btn",
                                                color="primary",
                                            ),
                                            html.Br(),
                                            html.Br(),
                                            dbc.Alert(
                                                id="apply-feedback",
                                                color="info",
                                                is_open=False,
                                            ),
                                            dcc.Store(
                                                id="parsed-changes-store", data=[]
                                            ),
                                            dcc.Store(id="backups-store", data=[]),
                                            html.Div(id="diffs-output"),
                                            html.Br(),
                                            dbc.Button(
                                                "Apply Changes",
                                                id="apply-changes-btn",
                                                color="danger",
                                            ),
                                            html.Br(),
                                            html.Br(),
                                            html.Hr(),
                                            html.H5("Restore from Backup"),
                                            dcc.Dropdown(
                                                id="backup-select-dropdown",
                                                placeholder="Select a file to restore...",
                                                options=[],
                                                value=None,
                                                style={"width": "300px"},
                                            ),
                                            html.Br(),
                                            dbc.Button(
                                                "Restore Selected Backup",
                                                id="restore-backup-btn",
                                                color="secondary",
                                            ),
                                            html.Br(),
                                            html.Br(),
                                        ],
                                    ),
                                ]
                            )
                        ]
                    )
                ],
                style={
                    "marginTop": "25px",
                    "border": "none",
                    "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)",
                },
            ),
        ],
        fluid=True,
    ),
)


class FileTree:
    """
    We'll store all folder paths so we can expand them by default.
    """

    def __init__(self, filepath: Path, exclusions: List[str], extensions: List[str]):
        self.filepath = filepath
        self.exclusions = exclusions
        self.extensions = extensions
        self.folders_expanded = []

    def flatten(self, input_list):
        return [item for sublist in input_list for item in sublist]

    def build_file(self, file_path: Path):
        return dmc.Group(
            [
                dmc.Checkbox(
                    id={"type": "file_checkbox", "index": str(file_path)},
                    size="sm",
                    checked=True,
                ),
                DashIconify(icon="akar-icons:file", width=18),
                dmc.Text(file_path.name, size="sm"),
            ],
            gap=5,
            align="center",
            wrap="nowrap",
            style={"paddingTop": "5px", "marginLeft": "15px"},
        )

    def build_folder_row(self, folder_path: Path):
        folder_checkbox = dmc.Checkbox(
            id={"type": "folder_checkbox", "index": str(folder_path)},
            size="sm",
            checked=True,
        )
        folder_icon = DashIconify(icon="akar-icons:folder", width=18)
        folder_name = dmc.Text(folder_path.name, size="sm")
        folder_control = dmc.AccordionControl(
            dmc.Group([folder_icon, folder_name], gap=5, align="center", wrap="nowrap")
        )
        return dmc.Group(
            [folder_checkbox, folder_control], gap=10, align="center", wrap="nowrap"
        )

    def build_tree(self, path: Path):
        if is_hidden_or_excluded(str(path), self.exclusions):
            return []
        if path.is_file():
            if any(path.name.lower().endswith(ext) for ext in self.extensions):
                return [self.build_file(path)]
            else:
                return []
        self.folders_expanded.append(str(path))

        items = sorted(list(path.iterdir()), key=lambda x: x.name)
        children = self.flatten([self.build_tree(child) for child in items])
        folder_row = self.build_folder_row(path)
        return [
            dmc.AccordionItem(
                [folder_row, dmc.AccordionPanel(children=children)], value=str(path)
            )
        ]

    def render(self) -> dmc.Accordion:
        tree_items = self.build_tree(self.filepath)
        return dmc.Accordion(
            children=tree_items,
            multiple=True,
            value=self.folders_expanded,
            variant="contained",
            style={"height": "400px", "overflowY": "auto"},
        )


@app.callback(
    Output("file-extensions", "value"),
    Output("exclusions-field", "value"),
    Input("extension-preset", "value"),
)
def sync_fields_with_preset(preset_label):
    if preset_label not in EXTENSION_PRESETS:
        preset_label = "None"
    preset_extensions = EXTENSION_PRESETS[preset_label]
    base_exclusion_set = set(BASE_EXCLUSIONS)
    if preset_label in PRESET_EXCLUSION_MAP:
        base_exclusion_set = base_exclusion_set.union(
            PRESET_EXCLUSION_MAP[preset_label]
        )

    excl_text = ", ".join(sorted(list(base_exclusion_set)))
    return preset_extensions, excl_text


@app.callback(
    Output("folder-warning", "is_open"),
    Output("filetree_div", "children"),
    Input("folder-path", "value"),
    Input("file-extensions", "value"),
    Input("exclusions-field", "value"),
    prevent_initial_call=True,
)
def update_file_tree(folder_path, file_ext_string, exclusion_string):
    if not folder_path or not os.path.isdir(folder_path):
        return True, ""

    extensions = []
    for ext in file_ext_string.split(","):
        e = ext.strip().lower()
        if e and not e.startswith("."):
            e = "." + e
        if e:
            extensions.append(e)

    user_excl_clean = set()
    if exclusion_string.strip():
        for x in exclusion_string.split(","):
            x2 = x.strip()
            if x2:
                user_excl_clean.add(x2)

    tree_obj = FileTree(
        filepath=Path(folder_path),
        exclusions=sorted(list(user_excl_clean)),
        extensions=extensions,
    )
    return False, tree_obj.render()


@app.callback(
    Output({"type": "file_checkbox", "index": ALL}, "checked"),
    Output({"type": "folder_checkbox", "index": ALL}, "checked"),
    Input({"type": "folder_checkbox", "index": ALL}, "checked"),
    State({"type": "folder_checkbox", "index": ALL}, "id"),
    State({"type": "folder_checkbox", "index": ALL}, "checked"),
    State({"type": "file_checkbox", "index": ALL}, "id"),
    State({"type": "file_checkbox", "index": ALL}, "checked"),
    State("folder-path", "value"),
    State("file-extensions", "value"),
    State("exclusions-field", "value"),
    prevent_initial_call=True,
)
def toggle_folder_files(
    folder_check_values,
    folder_ids,
    old_folder_check_values,
    file_ids,
    file_check_values,
    folder_path,
    file_ext_string,
    exclusion_string,
):
    if not folder_path or not os.path.isdir(folder_path):
        return file_check_values, old_folder_check_values

    def get_subfolders_abs(base_abs_path, exclusion_list, collected_abs):
        for root, dirs, _files in os.walk(base_abs_path):
            if is_hidden_or_excluded(root, exclusion_list):
                dirs[:] = []
                continue
            for d in dirs:
                full_dir = os.path.join(root, d)
                if not is_hidden_or_excluded(full_dir, exclusion_list):
                    collected_abs.add(os.path.abspath(full_dir))

    extensions = []
    for ext in file_ext_string.split(","):
        e = ext.strip().lower()
        if e and not e.startswith("."):
            e = "." + e
        if e:
            extensions.append(e)

    user_excl_clean = set()
    if exclusion_string.strip():
        for x in exclusion_string.split(","):
            x2 = x.strip()
            if x2:
                user_excl_clean.add(x2)

    new_file_states = list(file_check_values)
    new_folder_states = list(old_folder_check_values)

    for f_val, f_id in zip(folder_check_values, folder_ids):
        folder_abs = os.path.abspath(f_id["index"])
        all_subfolders_abs = set()
        all_subfolders_abs.add(folder_abs)
        get_subfolders_abs(folder_abs, list(user_excl_clean), all_subfolders_abs)

        for idx, (fld_id, fld_state) in enumerate(zip(folder_ids, new_folder_states)):
            if fld_id["index"]:
                fld_abs = os.path.abspath(fld_id["index"])
                if fld_abs in all_subfolders_abs:
                    new_folder_states[idx] = f_val

        subfiles = []
        for subf in all_subfolders_abs:
            add_all_files(
                subf, folder_path, extensions, list(user_excl_clean), subfiles
            )
        for idx, (this_file_id, old_val_file) in enumerate(
            zip(file_ids, new_file_states)
        ):
            if this_file_id["index"]:
                rel_path = os.path.relpath(this_file_id["index"], folder_path)
                if rel_path in subfiles:
                    new_file_states[idx] = f_val

    return new_file_states, new_folder_states


@app.callback(
    Output("selected-count", "children"),
    Input({"type": "file_checkbox", "index": ALL}, "checked"),
    prevent_initial_call=True,
)
def count_selected_files(file_check_values):
    if not file_check_values:
        return "0 file(s) selected"
    return f"{sum(bool(v) for v in file_check_values)} file(s) selected"


def generate_prompt(
    source_files: List[Dict[str, str]],
    problem_description: str,
    constraints_warnings: str,
    output_format_text: str,
    additional_info: str,
    template_text: str,
) -> str:
    sections = []

    # Problem Statement
    prob = problem_description.strip()
    if prob:
        sections.append(
            "##BEGIN-PROBLEM-STATEMENT\n" + prob + "\n##END-PROBLEM-STATEMENT"
        )

    # Constraints / Warnings
    cw = constraints_warnings.strip()
    if cw:
        sections.append(
            "##BEGIN-CONSTRAINTS-WARNINGS\n" + cw + "\n##END-CONSTRAINTS-WARNINGS"
        )

    # Output Format
    ofmt = output_format_text.strip()
    if ofmt:
        sections.append("##BEGIN-OUTPUT-FORMAT\n" + ofmt + "\n##END-OUTPUT-FORMAT")

    # Relevant Code
    code_section = ["##BEGIN-RELEVANT-CODE"]
    for file_info in source_files:
        language = get_language_extension(file_info["filename"])
        if language:
            code_block = f"```{language}\n{file_info['content']}\n```"
        else:
            code_block = f"{file_info['content']}"
        code_section.append(
            f"###BEGIN-FILE: {file_info['display_path']}\n{code_block}\n###END-FILE"
        )
    code_section.append("##END-RELEVANT-CODE")
    sections.append("\n\n".join(code_section))

    # Additional Information
    addl = additional_info.strip()
    if addl:
        sections.append(
            "##BEGIN-ADDITIONAL-INFORMATION\n" + addl + "\n##END-ADDITIONAL-INFORMATION"
        )

    # Template (Optional)
    tmpl = template_text.strip()
    if tmpl:
        sections.append("##BEGIN-TEMPLATE\n" + tmpl + "\n##END-TEMPLATE")

    return "\n\n".join(sections).strip()


@app.callback(
    Output("final-prompt-output", "value"),
    Output("alert-no-files", "is_open"),
    Output("download-link-container", "children"),
    Input("generate-button", "n_clicks"),
    State("folder-path", "value"),
    State("problem-description", "value"),
    State("constraints-warnings", "value"),
    State("output-format", "value"),
    State("additional-info", "value"),
    State("prompt-template", "value"),
    State({"type": "file_checkbox", "index": ALL}, "id"),
    State({"type": "file_checkbox", "index": ALL}, "checked"),
)
# ----------------------------------------------------------------
# REPLACED SECTION (3 of 3): Entire generate_final_prompt callback
# ----------------------------------------------------------------
def generate_final_prompt(
    n_clicks,
    folder_path,
    problem_description,
    constraints_warnings,
    output_format_text,
    additional_info,
    template_key,
    file_ids,
    file_checked,
):
    if not n_clicks:
        return "", False, ""
    if not folder_path or not os.path.isdir(folder_path):
        return "", False, ""

    selected_files = []
    if file_ids and file_checked:
        for fid, checked in zip(file_ids, file_checked):
            if checked:
                rel_path = os.path.relpath(fid["index"], folder_path)
                selected_files.append(rel_path)

    if not selected_files:
        return "", True, ""

    source_files = read_selected_files(folder_path, selected_files)
    chosen_template_text = PROMPT_LIBRARY.get(template_key, "")
    final_prompt = generate_prompt(
        source_files=source_files,
        problem_description=problem_description or "",
        constraints_warnings=constraints_warnings or "",
        output_format_text=output_format_text or "",
        additional_info=additional_info or "",
        template_text=chosen_template_text,
    )

    final_prompt_encoded = final_prompt.replace("\n", "%0A").replace("#", "%23")
    download_link = dbc.Button(
        "Download Prompt",
        id="download-btn",
        href="data:text/plain;charset=utf-8," + final_prompt_encoded,
        download="reasoning_prompt.txt",
        external_link=True,
        color="secondary",
    )
    return final_prompt, False, download_link


app.clientside_callback(
    """
    function(n_clicks, content) {
        if(!n_clicks) return null;
        if(!content) {
            alert('No text to copy.');
            return null;
        }
        navigator.clipboard.writeText(content);
        alert('Prompt copied to clipboard!');
        return null;
    }
    """,
    Output("dummy-store", "data"),
    Input("copy-prompt-btn", "n_clicks"),
    State("final-prompt-output", "value"),
    prevent_initial_call=True,
)


@app.callback(Output("copy-prompt-btn", "style"), Input("final-prompt-output", "value"))
def hide_copy_button(prompt_text):
    if not prompt_text.strip():
        return {"display": "none"}
    return {}


@app.callback(
    Output("parsed-changes-store", "data"),
    Output("diffs-output", "children"),
    Input("generate-diffs-btn", "n_clicks"),
    State("llm-response-input", "value"),
    State("folder-path", "value"),
    prevent_initial_call=True,
)
def generate_diffs_callback(n_clicks, llm_text, folder_path):
    if not folder_path or not os.path.isdir(folder_path):
        return [], "Invalid or missing folder path."
    if not llm_text:
        return [], "No response provided."

    parser = LLMUpdateParser()
    changes, error_message = parser.parse_response(llm_text)
    if error_message:
        return [], error_message
    if not changes:
        return [], "No code blocks detected."

    diffs_display = []
    store_data = []
    for change in changes:
        filename = change["filename"]
        new_content = change["new_content"]
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            original_content = read_entire_file(file_path)
        else:
            original_content = ""

        diff_html = generate_side_by_side_diff(original_content, new_content, filename)
        store_data.append(
            {
                "filename": filename,
                "diff_html": diff_html,
                "new_content": new_content,
                "apply_selected": True,
            }
        )

        diffs_display.append(
            html.Div(
                [
                    html.H5(filename),
                    dmc.Checkbox(
                        label="Select to apply",
                        id={"type": "apply_check", "index": filename},
                        size="sm",
                        checked=True,
                    ),
                    html.Div(
                        style={
                            "overflow": "auto",
                            "border": "1px solid #ccc",
                            "marginTop": "5px",
                        },
                        children=html.Div(
                            dangerouslySetInnerHTML={"__html": diff_html}
                        ),
                    ),
                    html.Hr(),
                ]
            )
        )

    return store_data, diffs_display


@app.callback(
    Output("apply-feedback", "children"),
    Output("apply-feedback", "is_open"),
    Output("backups-store", "data"),
    Output("backup-select-dropdown", "options"),
    Input("apply-changes-btn", "n_clicks"),
    Input("restore-backup-btn", "n_clicks"),
    State("parsed-changes-store", "data"),
    State({"type": "apply_check", "index": ALL}, "checked"),
    State({"type": "apply_check", "index": ALL}, "id"),
    State("folder-path", "value"),
    State("backups-store", "data"),
    State("backup-select-dropdown", "value"),
    prevent_initial_call=True,
)
def apply_or_restore_callback(
    apply_nclicks,
    restore_nclicks,
    parsed_changes,
    check_values,
    check_ids,
    folder_path,
    current_backups,
    selected_backup_file,
):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "apply-changes-btn":
        if not folder_path or not os.path.isdir(folder_path):
            return "Invalid or missing folder path.", True, current_backups, []
        if not parsed_changes:
            return "No changes to apply.", True, current_backups, []
        if current_backups is None:
            current_backups = []

        apply_dict = {}
        for check_val, cid in zip(check_values, check_ids):
            filename = cid["index"]
            apply_dict[filename] = check_val

        applied_files = []
        for item in parsed_changes:
            fn = item["filename"]
            new_content = item["new_content"]
            if not apply_dict.get(fn, False):
                continue
            file_path = os.path.join(folder_path, fn)
            try:
                if os.path.isfile(file_path):
                    backup_file = file_path + ".bak"
                    os.rename(file_path, backup_file)
                    current_backups.append(
                        {"original_file": file_path, "backup_file": backup_file}
                    )
                dir_name = os.path.dirname(file_path)
                if dir_name and not os.path.exists(dir_name):
                    os.makedirs(dir_name, exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                applied_files.append(fn)
            except Exception as e:
                return f"Error applying changes to {fn}: {e}", True, current_backups, []

        if applied_files:
            backup_options = []
            for bk in current_backups:
                backup_options.append(
                    {
                        "label": os.path.basename(bk["backup_file"]),
                        "value": bk["backup_file"],
                    }
                )
            return (
                f"Updated/created (old versions renamed to *.bak): {', '.join(applied_files)}",
                True,
                current_backups,
                backup_options,
            )
        else:
            return (
                "No files were selected to apply changes.",
                True,
                current_backups,
                [],
            )

    elif trigger_id == "restore-backup-btn":
        if not selected_backup_file or not current_backups:
            return (
                "No backup selected or no backups available.",
                True,
                current_backups,
                [],
            )
        matched = [
            bk for bk in current_backups if bk["backup_file"] == selected_backup_file
        ]
        if not matched:
            return "Backup file not found in records.", True, current_backups, []
        backup_entry = matched[0]
        backup_file = backup_entry["backup_file"]
        original_file = backup_entry["original_file"]
        try:
            if os.path.isfile(original_file):
                os.remove(original_file)
            os.rename(backup_file, original_file)
            return (
                f"Restored backup {os.path.basename(backup_file)} → {os.path.basename(original_file)}",
                True,
                current_backups,
                [
                    {
                        "label": os.path.basename(bk["backup_file"]),
                        "value": bk["backup_file"],
                    }
                    for bk in current_backups
                ],
            )
        except Exception as e:
            return f"Error restoring backup: {e}", True, current_backups, []
    else:
        raise dash.exceptions.PreventUpdate


server = app.server

if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
