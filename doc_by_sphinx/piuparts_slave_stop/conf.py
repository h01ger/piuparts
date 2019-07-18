# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Project information -----------------------------------------------------

project = 'Piuparts'
copyright = ''
author = ''

# The short X.Y version
version = ''
# The full version, including alpha/beta/rc tags
release = '0.98'

# source_suffix = ['.rst', '.md']
source_suffix = '.txt'

# The master toctree document.
master_doc = 'index'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'piupartsdoc'

# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'piuparts_slave_stop',
        'stop all running piuparts-slaves on a host\n', '', 8)
]
