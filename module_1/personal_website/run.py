from flask import Flask
import pages

# create an application factory to scale my flask project.
# it initializes the app and then returns it
def create_app():
    app = Flask(__name__)
    # create blueprints that I register in my application factory
    # connect the pages blueprint with the flask project
    app.register_blueprint(pages.bp)
    return app

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080, debug=True)