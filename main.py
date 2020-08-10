from flask import (
    Flask, 
    render_template, 
    request, 
    session, 
    redirect,
    jsonify,
)
from flask_cors import CORS
from db import DB, from_env
import os, json, uuid

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db = DB(from_env('CONF'))

def notes_to_dict(notes):
    res = {}
    for note in notes:
        res[note.id] = {
            'body': note.get('body'),
            'date': str(note.get('date'))
        }
    return res

def escape(text):
    for sym, rep in {
        '`': '|bt|',
        '<': '|lt|',
        '>': '|gt|',
    }.items():
        text = text.replace(sym, rep)
    return text
def unescape(text):
    for sym, rep in {v:k for k,v in {
        '`': '|bt|',
        '<': '|lt|',
        '>': '|gt|',
    }.items()}.items():
        text = text.replace(sym, rep)
    return text

@app.before_request
def app_check_loggedin():
    if request.path.split('/')[-1] in ['signup', 'login']:
        if session.get('user'):
            return redirect('/notes')

@app.route('/')
def app_index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def app_signup():
    if request.method == 'GET':
        return render_template('signup.html', reason=None)
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('signup.html', reason='missing_field')

        if db.get_user(username):
            return render_template('signup.html', reason='username_exists')

        user = db.users.document(username)
        user.set({'password':db.hash(password)})
        session['user'] = user.id
        return redirect('/notes')

@app.route('/login', methods=['GET', 'POST'])
def app_login():
    if request.method == 'GET':
        return render_template('login.html', reason=None)
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('login.html', reason='missing_field')
        
        user = db.get_user(username)
        if not user:
            return render_template('login.html', reason='no_user')
        
        if not db.hash(password) == user.get().get('password'):
            return render_template('login.html', reason='bad_pass')
        
        session['user'] = user.id
        return redirect('/notes')

@app.route('/logout')
def app_logout():
    if session.get('user'):
        del session['user']
    return redirect('/')

@app.route('/delete/account', methods=['GET', 'POST'])
def app_delete_account():
    if request.method == 'GET':
        return render_template('delete.html')
    
    user = db.get_user(session.get('user'))
    password = request.form.get('password')
    if user.get().get('password') == db.hash(password):
        user.delete()
        return redirect('/logout')
    return redirect('/login')

@app.route('/delete/note', methods=['POST'])
def app_delete_note():
    user = db.get_user(session.get('user'))
    note = request.json.get('id')
    if not user: return redirect('/login')
    if not note: return 'none'
    doc = user.collection('notes').document(note)
    if not doc.get().exists: return 'gone'
    doc.delete()
    return 'ok'

@app.route('/notes', methods=['GET', 'POST'])
def app_notes():
    username = session.get('user')
    if not username:
        return redirect('/login')
    
    user = db.get_user(username)
    notes = user.collection('notes')

    if request.method == 'GET':
        notesd = notes_to_dict(notes.get())
        notesj = escape(json.dumps(notesd))
        return render_template('notes.html', user=user, notes=notesd, notesj=notesj)
    elif request.method == 'POST':
        notesd = request.json
        ts = db.date()

        for note, body in notesd.items():
            while type(body) == dict:
                body = body['body']
            doc = notes.document(note);
            nd = {'body': body, 'date': ts}
            doc.set(nd)
        return 'ok'

@app.route('/makelink', methods=['POST'])
def app_makelink():
    user = db.get_user(session.get('user'))
    if not user:
        return render_template('error.html', msg='You are not logged in. Please create an account or log in to yours', redir='/')
    noteid = request.json.get('id')
    render = request.json.get('render', False)
    note = user.collection('notes').document(noteid)
    if not note.get().exists:
        return render_template('error.html', msg='A note with that title does not exist. Make sure to save your notes before creating a link', redir='/notes')
    
    uid = str(uuid.uuid4()).replace('-','')
    link = db.links.document(uid)
    link.set({
        'path': note,
        'render': render,
        'user': user.id,
    })
    return jsonify({'url':f'/link/{uid}'})

@app.route('/link/<uid>')
def app_link(uid):
    link = db.links.document(uid).get()
    if not link.exists:
        return '', 404
    note = link.get('path').get()
    if not note.exists:
        return render_template('error.html', msg='This note has been deleted', redir='/#')
    raw = note.get('body')
    if link.get('render'):
        return render_template('render.html', raw=unescape(raw))
    else:
        return unescape(raw)

@app.route('/demo')
def app_demo():
    return render_template('demo.html', demo=open('demo.md','r').read())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)