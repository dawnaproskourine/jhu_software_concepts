# Description

This assignment teaches the fundamentals of website construction. This is a personal developer website
that includes a biography, contact information/links, and details about the Python projects.

This project uses Flask, a micro web framework written in Python. We also use HTML and cascading style sheets (CSS) to
describe how HTML elements are to be displayed. The output is a functional personal website that includes details about
Dawna, her projects, and contact information.

This project uses blueprints in pages.py. Flask's blueprint helps organize application into modular reusable components. 
It lets you group related routes, templates, and static files together. To use blueprints: first create a blueprint, then
define routes inside the blueprint and finally register the blueprint inside the main application.  

In this project, we define three routes: home, contact and projects. Each of them returns a rendered template to indicate 
what page is active. Templates are HTML files with the capability of rendering dynamic content sent over from the Flask 
views. For this, Flask uses the Jinja template engine. With Jinja, we can embed Python-like expressions into templates 
to create dynamic web content. For example, we can use loops, conditionals, and variables directly in the templates. 
Further, Jinja supports template inheritance allowing for the creation of a base template which is extended into child 
templates. This promotes code reuse and a consistent layout across different pages in the website.

In this project, the Jinja base template is called base.html which contains the main HTML structure of the web pages. 
It is extended by three child HTMLs: contact, home and projects.

To improve user-experience, we have included a navigation menu which is displayed on every page in the top right hand 
corner. This is done by including _navigation.html into base.html via a {% include%} tag. Included templates are partials
that contain a portion of the full HTML code. We indicate that _navigation.html is meant to be included by prefixing it 
with an underscore sign. Since all three of the child HTML extends base.html, we didn't need to make any further changes 
to make the navigation bar appear due to template inheritance.

Furthermore, we have added styling using Cascading Style Sheets. As is common, we have added CSS file styles.css into static/
directory. The CSS declarations ensure that the web elements are properly spaced and sized making the website look 
organized and convenient to navigate. The color scheme for the links provides a visual cue to users about active and 
clickable elements.  The font style and size contribute to readability. The overall layout including left aligned text 
vs right-aligned image makes for a clean and modern look. We also reference the CSS file in base.html taking advantage 
of Jinja inheritance properties

# Installation

```
pip install -r requirements.txt
```

# Execution and usage

```
python3 run.py
```

# Used technology

* Flask
* Python 3.14

# References
 * https://realpython.com/flask-project/
 * https://stackoverflow.com/questions/11287150/css-making-text-align-left-and-justify-at-same-time
 * https://www.geeksforgeeks.org/html/html-img-align-attribute/
 * https://realpython.com/readme-python-project/
