#!/usr/bin/env python

from flask import Flask
app = Flask(__name__)

@app.route('/vk-users/<int:post_id>')
def show_post(post_id):
    # show the post with the given id, the id is an integer
    return 'Post %d' % post_id

@app.route("/")
def hello():
    return "Hello World!"

if __name__ == "__main__":
    app.run(debug=True)
