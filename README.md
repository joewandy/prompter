# 🔎 Prompter for Reasoning Models

Prompter is an interactive web application tailored specifically for reasoning models like O3-mini, O1, and O1 Pro. It's designed to simplify the creation of structured prompts by enabling quick selection and assembly of relevant code snippets directly pasted from your web browser, without requiring API integration.

---

## 🚀 Features

- **Interactive File Explorer**: Quickly navigate your project folders to select relevant files for your prompts.
- **Automatic Prompt Assembly**: Easily combine code snippets, problem statements, constraints, and specified output formats into comprehensive prompts.
- **Preset-Based Filtering**: Effortlessly filter files using presets tailored for common tasks, including Machine Learning, Django, Frontend development, and Bioinformatics.
- **Prompt Templates**: Utilize pre-defined templates optimized for debugging, refactoring, optimization, security auditing, and more.
- **Integrated Diff Viewer (In Progress)**: Visualize proposed code changes clearly with a built-in side-by-side diff viewer.
- **Direct Code Updates (In Progress)**: Seamlessly apply suggested updates directly to your files, with automatic backups to ensure safety.

---

## 🛠 Installation

Install using [Poetry](https://python-poetry.org/):

```bash
git clone https://github.com/joewandy/prompter.git
cd prompter
poetry install
```

Run the app within the Poetry environment:

```bash
poetry run python prompter/app.py
```

---

## 🎯 Quick Start

After starting the app, access it at:

```
http://localhost:8051
```

---

## 📂 Directory Structure

```
prompter/
├── app.py               # Main Dash application
├── pyproject.toml       # Poetry configuration
├── README.md            # Project documentation (this file)
```

---

## 🔧 Dependencies

Key dependencies include:
- Dash
- Dash Bootstrap Components
- Dash Mantine Components
- Dash Iconify

See the full list in `pyproject.toml`.

---

## 📝 Usage

1. **Enter Folder Path**: Specify your project directory.
2. **Configure File Selection**: Use presets or manually define file extensions and exclusions.
3. **Generate Prompt**: Provide your problem statement, constraints, and output format.
4. **Apply Updates** *(in progress)*: Paste updates from your reasoning model directly into Prompter.

---

## 🌟 Contributing

Contributions are welcome! Submit issues or pull requests directly on GitHub.

---

## 📄 License

This project is open-source under the MIT License.