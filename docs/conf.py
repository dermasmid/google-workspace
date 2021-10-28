import os
import sys

sys.path.insert(0, os.path.abspath("../"))

from google_workspace import __version__


version = __version__
project = "Google Workspace"
copyright = "2021, Cheskel Twersky"
author = "Cheskel Twersky"


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
]

templates_path = ["_templates"]


exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

copybutton_prompt_text = "$ "


html_theme = "sphinx_rtd_theme"
