# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Module 4: Testing and Documentation'
copyright = '2026, Dawna Jones Proskourine'
author = 'Dawna Jones Proskourine'
release = '1.0'

import os
import sys
sys.path.insert(0, os.path.abspath("."))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc']

# Mock external packages so autodoc works without them installed (e.g. on RTD)
autodoc_mock_imports = [
    'llama_cpp',
    'huggingface_hub',
    'psycopg',
    'psycopg.cursor',
    'flask',
    'bs4',
]

templates_path = ['website/_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['website/_static']
