
import yaml
import os
from flask import *
os.path.dirname(".")
parent_dir = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(parent_dir,"config.yml")) as f:
    config = yaml.safe_load(f)

app = Flask(__name__)

@app.route('/')
def url_categories():
    template = "main.html"
    if config["use_dynamic_js"]:
        template = "dynamic.html"
    return render_template(
        template
        )

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=False)
