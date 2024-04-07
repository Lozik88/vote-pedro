from flask import *

app = Flask(__name__)

@app.route('/')
def url_categories():
    return render_template(
        "main.html"
        )

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=False)
