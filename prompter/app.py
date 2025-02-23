import os
import fnmatch
from pathlib import Path
from typing import List, Dict

import dash
from dash import dcc, html, Input, Output, State, ALL, no_update
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from dash._dash_renderer import _set_react_version

_set_react_version("18.2.0")

EXTENSION_PRESETS = {
    "None": ".py, .js, .ts, .html, .css, .json",
    "Django": ".py, .html, .css, .js",
    "Machine Learning": ".py, .ipynb, .csv, .txt",
    "Frontend (JS/TS)": ".html, .css, .js, .ts, .json",
    "Backend (General)": ".py, .js, .ts, .java, .c, .cpp, .cs, .go, .php",
    "VueJS": ".html, .css, .vue, .js, .ts, .json",
    "Angular": ".html, .css, .ts, .json",
    "React": ".js, .jsx, .ts, .tsx, .json, .html, .css",
    "iOS (Swift)": ".swift, .h, .m, .mm, .plist",
    "Android (Kotlin/Java)": ".kt, .java, .xml",
    "Data Science": ".py, .ipynb, .r, .csv, .tsv, .txt",
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
    "Bug Fix / Debug": "You are a specialized debugging model. Identify and fix any bugs succinctly.",
    "Performance Optimization": "Optimize the code or architecture concisely for better performance.",
    "Security Audit": "Review code for security issues. Provide short, direct mitigations.",
    "Refactoring": "Refactor the code for clarity and maintainability.",
    "Database Schema Advice": "Suggest best-practice improvements for database-related code.",
    "ML Model Tuning": "Optimize the ML code or pipeline with short recommended changes.",
    "Bioinformatics": "Make succinct improvements for bioinformatics data processing or analysis.",
    "Academic Code": "Check academic code correctness. If needed, propose short fixes.",
    "Testing Strategy": "Propose a concise testing strategy for the given code or system.",
}

def is_hidden_or_excluded(path: str, exclusion_list: List[str]) -> bool:
    p = Path(path)
    if any(part.startswith('.') for part in p.parts):
        return True
    for pattern in exclusion_list:
        if pattern in p.parts:
            return True
        if fnmatch.fnmatch(path, f"*{pattern}*"):
            return True
    return False

def add_all_files(folder_path: str, base_path: str, extensions: List[str], exclusion_list: List[str], selected_files: List[str]):
    for root, dirs, files in os.walk(folder_path):
        if is_hidden_or_excluded(root, exclusion_list):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not is_hidden_or_excluded(os.path.join(root, d), exclusion_list)]
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
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"<!-- Could not read file: {e} -->"

def read_selected_files(folder_path: str, selected_files: List[str]) -> List[Dict[str, str]]:
    base_folder_name = os.path.basename(folder_path.rstrip("/"))
    source_files = []
    for rel_path in selected_files:
        full_path = os.path.join(folder_path, rel_path)
        display_path = f"{base_folder_name}/{rel_path}"
        content = read_entire_file(full_path)
        if not content.strip():
            continue
        source_files.append({
            'filename': rel_path,
            'display_path': display_path,
            'content': content,
        })
    return source_files

def get_language_extension(filename: str) -> str:
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
        '.ipynb': 'python',
        '.csv': '',
        '.txt': '',
        '.vue': 'html',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.xml': 'xml',
        '.r': 'r',
    }
    return mapping.get(ext, '')

def generate_prompt(source_files: List[Dict[str, str]], problem_description: str, template_text: str, prompt_position: str) -> str:
    code_section = ["## Relevant Code"]
    for file_info in source_files:
        language = get_language_extension(file_info['filename'])
        if language:
            code_block = f"\n{file_info['content']}\n"
        else:
            code_block = f"\n{file_info['content']}\n"
        code_section.append(
            f"**File: {file_info['display_path']}**\n{code_block}"
        )
    code_block_str = "\n\n".join(code_section).strip()

    tmpl = template_text.strip()
    prob = problem_description.strip()

    # If no template and no problem description, just return the code section
    if not tmpl and not prob:
        return code_block_str

    if prompt_position == "After Template":
        return (f"{tmpl}\n\n{code_block_str}\n\n## Problem\n{prob}").strip()
    elif prompt_position == "Top Combined":
        combined = (tmpl + "\n\n" + prob).strip()
        return (combined + "\n\n" + code_block_str).strip()
    else:  # "Top Separate"
        template_block = f"## Template\n{tmpl}"
        problem_block = f"## Problem\n{prob}"
        return (template_block + "\n\n" + problem_block + "\n\n" + code_block_str).strip()

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
                    checked=True
                ),
                DashIconify(icon="akar-icons:file", width=18),
                dmc.Text(file_path.name, size="sm")
            ],
            gap=5,
            align="center",
            wrap="nowrap",
            style={"paddingTop": "5px", "marginLeft": "15px"}
        )

    def build_folder_row(self, folder_path: Path):
        folder_checkbox = dmc.Checkbox(
            id={"type": "folder_checkbox", "index": str(folder_path)},
            size="sm",
            checked=True
        )
        folder_icon = DashIconify(icon="akar-icons:folder", width=18)
        folder_name = dmc.Text(folder_path.name, size="sm")
        folder_control = dmc.AccordionControl(
            dmc.Group([folder_icon, folder_name], gap=5, align="center", wrap="nowrap")
        )
        return dmc.Group(
            [folder_checkbox, folder_control],
            gap=10,
            align="center",
            wrap="nowrap"
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
                [folder_row, dmc.AccordionPanel(children=children)],
                value=str(path)
            )
        ]

    def render(self) -> dmc.Accordion:
        tree_items = self.build_tree(self.filepath)
        return dmc.Accordion(
            children=tree_items,
            multiple=True,
            value=self.folders_expanded,
            variant="contained",
            style={"height": "600px", "overflowY": "auto"}
        )

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

mantine_theme = {
    "fontFamily": "Inter, sans-serif",
    "primaryColor": "indigo",
    "defaultRadius": "sm"
}

app.layout = dmc.MantineProvider(
    theme=mantine_theme,
    children=dbc.Container([
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
                dbc.CardHeader("Select Project Folder", style={"backgroundColor": "#eaf2f8"}),
                dbc.CardBody([
                    dbc.Label("Folder Path"),
                    dbc.Input(id="folder-path", type="text", placeholder="Enter path to your folder"),
                ]),
            ],
            style={"marginTop": "25px", "border": "none", "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)"}
        ),

        dbc.Card(
            [
                dbc.CardBody(
                    [
                        dbc.Tabs([
                            dbc.Tab(label="Prompter", children=[
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
                                        dbc.CardHeader("🛠️ Configuration", style={"backgroundColor": "#eaf2f8"}),
                                        dbc.CardBody(
                                            [
                                                dbc.Row([
                                                    dbc.Col([
                                                        html.H5("Configuration"),
                                                        dbc.Label("Extension Preset"),
                                                        dcc.Dropdown(
                                                            id="extension-preset",
                                                            options=[{"label": k, "value": k} for k in EXTENSION_PRESETS.keys()],
                                                            value="None"
                                                        ),
                                                        html.Br(),

                                                        dbc.Label("File Extensions"),
                                                        dbc.Input(id="file-extensions", type="text", placeholder=".py, .js, .ts"),
                                                        html.Br(),

                                                        dbc.Label("Current Exclusion List"),
                                                        dbc.Input(id="exclusions-field", type="text", placeholder=".git, .gitignore, .pycache"),
                                                        html.Br(),

                                                        dbc.Label("Prompt Template (Optional)"),
                                                        dcc.Dropdown(
                                                            id="prompt-template",
                                                            options=[{"label": k, "value": k} for k in PROMPT_LIBRARY.keys()],
                                                            value="None (No Template)"
                                                        ),
                                                        html.Br(),

                                                        dbc.Label("Prompt Position"),
                                                        dbc.RadioItems(
                                                            id="prompt-position",
                                                            options=[
                                                                {"label": "After Template", "value": "After Template"},
                                                                {"label": "Top Combined", "value": "Top Combined"},
                                                                {"label": "Top Separate", "value": "Top Separate"},
                                                            ],
                                                            value="After Template"
                                                        ),
                                                        html.Br(),
                                                        dbc.Alert(id="alert-no-files", color="danger", is_open=False),
                                                    ], md=4),

                                                    dbc.Col([
                                                        html.H5("File/Folder Tree"),
                                                        dbc.Alert(
                                                            "Enter a valid folder path to see contents.",
                                                            id="folder-warning",
                                                            color="warning",
                                                            is_open=True
                                                        ),
                                                        html.Div(
                                                            id="selected-count",
                                                            children="0 file(s) selected",
                                                            style={"marginTop": "15px"}
                                                        ),
                                                        html.Div(id='filetree_div'),
                                                    ], md=8),
                                                ], style={"marginTop": "25px"}),
                                            ]
                                        ),
                                    ],
                                    style={"marginTop": "25px", "border": "none", "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)"}
                                ),

                                dbc.Card(
                                    [
                                        dbc.CardHeader("✏️ Prompt Generation", style={"backgroundColor": "#fcf0e6"}),
                                        dbc.CardBody(
                                            [
                                                dmc.Paper(
                                                    p="md",
                                                    style={"marginTop": "30px"},
                                                    children=[
                                                        dmc.Group(
                                                            [
                                                                dbc.Button("Generate Prompt", id="generate-button", color="primary"),
                                                                dbc.Button("Copy Prompt", id="copy-prompt-btn", color="secondary"),
                                                                html.Span(id="download-link-container")
                                                            ],
                                                            gap="sm"
                                                        ),
                                                        html.Br(),
                                                        dbc.Row([
                                                            dbc.Col([
                                                                html.H4("Describe Your Task or Question"),
                                                                dcc.Textarea(
                                                                    id="problem-description",
                                                                    style={"width": "100%", "height": "300px"},
                                                                )
                                                            ], md=6),
                                                            dbc.Col([
                                                                html.H4("Generated Prompt"),
                                                                dcc.Textarea(
                                                                    id="final-prompt-output",
                                                                    style={"width": "100%", "height": "300px"},
                                                                    readOnly=True
                                                                ),
                                                                dcc.Store(id="dummy-store", data="")
                                                            ], md=6)
                                                        ])
                                                    ]
                                                ),
                                            ]
                                        ),
                                    ],
                                    style={"marginTop": "25px", "border": "none", "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)"}
                                ),
                            ]),
                            dbc.Tab(label="Other Feature (Coming Soon)", children=[
                                html.Br(),
                                html.H2("Another feature will go here in the future!"),
                                html.P(
                                    "We're planning additional functionalities to further enhance your experience. "
                                    "Stay tuned for more updates and improvements in upcoming versions!"
                                )
                            ])
                        ])
                    ]
                )
            ],
            style={"marginTop": "25px", "border": "none", "boxShadow": "0 1px 2px 0 rgba(0,0,0,0.2)"}
        )
    ], fluid=True)
)

@app.callback(
    Output("file-extensions", "value"),
    Output("exclusions-field", "value"),
    Input("extension-preset", "value")
)
def sync_fields_with_preset(preset_label):
    if preset_label not in EXTENSION_PRESETS:
        preset_label = "None"
    preset_extensions = EXTENSION_PRESETS[preset_label]
    base_exclusion_set = set(BASE_EXCLUSIONS)
    if preset_label in PRESET_EXCLUSION_MAP:
        base_exclusion_set = base_exclusion_set.union(PRESET_EXCLUSION_MAP[preset_label])

    excl_text = ", ".join(sorted(list(base_exclusion_set)))
    return preset_extensions, excl_text

@app.callback(
    Output("folder-warning", "is_open"),
    Output("filetree_div", "children"),
    Input("folder-path", "value"),
    Input("file-extensions", "value"),
    Input("exclusions-field", "value"),
    prevent_initial_call=True
)
def update_file_tree(folder_path, file_ext_string, exclusion_string):
    if not folder_path or not os.path.isdir(folder_path):
        return True, ""

    extensions = []
    for ext in file_ext_string.split(","):
        e = ext.strip().lower()
        if e and not e.startswith('.'):
            e = '.' + e
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
        extensions=extensions
    )
    return False, tree_obj.render()

@app.callback(
    Output({"type": "file_checkbox", "index": ALL}, "checked"),
    Input({"type": "folder_checkbox", "index": ALL}, "checked"),
    State({"type": "folder_checkbox", "index": ALL}, "id"),
    State({"type": "file_checkbox", "index": ALL}, "id"),
    State({"type": "file_checkbox", "index": ALL}, "checked"),
    State("folder-path", "value"),
    State("file-extensions", "value"),
    State("exclusions-field", "value"),
    prevent_initial_call=True
)
def toggle_folder_files(folder_check_values, folder_ids, file_ids, file_check_values,
                        folder_path, file_ext_string, exclusion_string):
    if not folder_path or not os.path.isdir(folder_path):
        return file_check_values

    extensions = []
    for ext in file_ext_string.split(","):
        e = ext.strip().lower()
        if e and not e.startswith('.'):
            e = '.' + e
        if e:
            extensions.append(e)

    user_excl_clean = set()
    if exclusion_string.strip():
        for x in exclusion_string.split(","):
            x2 = x.strip()
            if x2:
                user_excl_clean.add(x2)

    new_states = list(file_check_values)
    for f_val, f_id in zip(folder_check_values, folder_ids):
        folder_str = f_id["index"]
        subfiles = []
        add_all_files(folder_str, folder_path, extensions, list(user_excl_clean), subfiles)
        for idx, (this_file_id, old_val) in enumerate(zip(file_ids, file_check_values)):
            if this_file_id["index"]:
                rel_path = os.path.relpath(this_file_id["index"], folder_path)
                if rel_path in subfiles:
                    new_states[idx] = f_val

    return new_states

@app.callback(
    Output("selected-count", "children"),
    Input({"type": "file_checkbox", "index": ALL}, "checked"),
    prevent_initial_call=True
)
def count_selected_files(file_check_values):
    if not file_check_values:
        return "0 file(s) selected"
    return f"{sum(bool(v) for v in file_check_values)} file(s) selected"

@app.callback(
    Output("final-prompt-output", "value"),
    Output("alert-no-files", "is_open"),
    Output("download-link-container", "children"),
    Input("generate-button", "n_clicks"),
    State("folder-path", "value"),
    State("problem-description", "value"),
    State("prompt-template", "value"),
    State("prompt-position", "value"),
    State({"type": "file_checkbox", "index": ALL}, "id"),
    State({"type": "file_checkbox", "index": ALL}, "checked")
)
def generate_final_prompt(n_clicks,
                          folder_path,
                          problem_description,
                          template_key,
                          prompt_position,
                          file_ids,
                          file_checked):
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
        template_text=chosen_template_text,
        prompt_position=prompt_position
    )

    # Ensure we properly encode special chars so the entire final prompt is included
    final_prompt_encoded = final_prompt.replace("\n", "%0A").replace("#", "%23")

    download_link = dbc.Button(
        "Download Prompt",
        id="download-btn",
        href="data:text/plain;charset=utf-8," + final_prompt_encoded,
        download="reasoning_prompt.txt",
        external_link=True,
        color="secondary"
    )
    return final_prompt, False, download_link

# Clientside callback for "Copy Prompt"
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
    prevent_initial_call=True
)

server = app.server

if __name__ == "__main__":
    app.run_server(debug=True)
