from flask import Blueprint, render_template, request

#create an instance of blueprint and name it bp. The first argument is the name of the blueprint.
#Use this name to identify this particular plueprint in the flask project
bp = Blueprint("pages", __name__)

#next, define three routes: home, contact and projects. each of them returns a string to indicate what page is active
@bp.route("/")
def home():
    return render_template("pages/home.html")

@bp.route("/contact")
def contact():
    return render_template("pages/contact.html")

@bp.route("/projects")
def projects():
    return render_template("pages/projects.html")