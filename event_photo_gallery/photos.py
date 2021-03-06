import zipfile
from io import BytesIO
import os
import urllib
import uuid

from sqlalchemy.sql.expression import and_
from flask import request, abort, render_template, redirect, url_for,\
        current_app, send_from_directory, Blueprint, flash, send_file,\
        Response
from flask_login import current_user
from werkzeug.utils import secure_filename
from werkzeug.wsgi import FileWrapper

from .models import db, User, Photo, Comment, Category, Vote

photos = Blueprint('photos', __name__, template_folder='templates')

@photos.before_request
def check_auth():
    if not current_user.is_authenticated:
        abort(401)

def get_votes():
    categories = Category.query\
            .order_by(Category.name)\
            .join(Photo)\
            .join(Vote)\
            .filter_by(user_id=current_user.id)\
            .order_by(Vote.rank)\
            .all()
    return categories

def get_photos(page):
    return db.session.query(Photo, Vote)\
            .outerjoin(Vote, and_(Photo.id == Vote.photo_id,\
                    Vote.user_id == current_user.id))\
            .paginate(page, 27)

@photos.route('/')
def view_gallery():
    page = int(request.args.get("page", 1))
    photos = get_photos(page)
    categories = Category.query.all()
    voting_open = []
    for category in categories:
        if category.voting_enabled:
            voting_open.append(category.name)
    return render_template('pages/gallery.html', photos=photos,
            categories=categories, votes=get_votes(), voting_open=voting_open)

@photos.route('/download')
def download_photos():
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(current_app.config['UPLOADS_FOLDER']):
           for file in files:
                zipf.write(os.path.join(root, file), file)
    memory_file.seek(0)
    return Response(FileWrapper(memory_file), mimetype="application/zip",\
            direct_passthrough=True, headers = {
                'Content-Disposition': 'attachment; filename=%s.zip' %\
                (urllib.parse.quote(current_app.config['SITE_TITLE']))
                })

@photos.route('/view/<id>', methods=['GET', 'POST'])
def view_photo(id):
    photo = Photo.query.filter_by(id=id).first()
    if photo is None:
        abort(404)
    if request.method == "POST":
        if request.form['action'] == 'comment' and not photo.category.comments_enabled:
            comment = Comment(text=request.form['comment'], user_id=current_user.id)
            photo.comments.append(comment)
            db.session.add(comment)
            db.session.commit()
        elif request.form['action'] == 'vote' and photo.category.voting_enabled:
            if request.form['rank'] not in ['1', '2', '3']:
                abort(400)
            rank = request.form['rank']

            if photo.user_id == current_user.id:
                flash("Voting for own photo not allowed.")
                return redirect(url_for('photos.view_photo', id=id))

            vote = Vote.query.filter_by(user_id=current_user.id, photo_id=id).first()
            if vote:
                ''' Found an existing vote for photo by user '''
                vote.rank = rank
                flash("Your vote has been updated.")
            else:
                flash("Your vote has been cast.")
                vote = Vote(photo_id=id, user_id=current_user.id, rank=rank)
                db.session.add(vote)

            vote_query = Vote.query.filter(
                    and_(Vote.photo_id != id,\
                    Vote.user_id == current_user.id, \
                    Vote.rank == rank))\
                    .join(Vote.photo).filter(Photo.category_id == photo.category_id)
            vote = vote_query.first()
            if vote:
                ''' Found existing vote of same rank by user '''
                flash("Removing previous vote of same rank.")
                db.session.delete(vote)

            db.session.commit()
        elif request.form['action'] == 'delete':
            photo = Photo.query.filter_by(id=id).first()
            if photo:
                if current_user.id == photo.user_id or current_user.admin:
                    Vote.query.filter_by(photo_id=id).delete()
                    db.session.delete(photo)
                    db.session.commit()
                    flash('Image deleted.')
                    return redirect(url_for('photos.view_gallery'))
                else:
                    abort(403)
            else:
                abort(400)
        else:
            abort(400)

        return redirect(url_for('photos.view_photo', id=id))
    prev_photo = Photo.query.filter(id > Photo.id).order_by(Photo.id.desc()).first()
    next_photo = Photo.query.filter(id < Photo.id).first()
    prev_num = prev_photo.id if prev_photo else None
    next_num = next_photo.id if next_photo else None
    return render_template("pages/photo.html", has_next=(next_num is not None),\
            has_prev=(prev_num is not None), next_num=next_num,\
            prev_num=prev_num, photo=photo)

@photos.route('/raw/<id>')
def view_raw_photo(id):
    photo = Photo.query.filter_by(id=id).first()
    if photo is None:
        abort(404)
    return send_from_directory(current_app.config['UPLOADS_FOLDER'], photo.path)


@photos.route('/upload', methods=['POST'])
def upload():
    category = Category.query.filter_by(id=request.form["category"]).first()
    if not category or not category.uploads_enabled:
        abort(400)
    
    uploaded_photos = request.files.getlist("photo[]")
    for uploaded_photo in uploaded_photos:
        if not ('.' in uploaded_photo.filename and \
                uploaded_photo.filename.rsplit('.', 1)[1].lower() in
                current_app.config['ALLOWED_PHOTO_EXTENSIONS']):
            abort(400);

    for uploaded_photo in uploaded_photos:
        _, extension = os.path.splitext(uploaded_photo.filename)
        filename = str(uuid.uuid4())  + extension
        uploaded_photo.save(os.path.join(current_app.config['UPLOADS_FOLDER'], filename))
        photo = Photo(path=filename, user_id=current_user.id, category_id=request.form['category'])
        db.session.add(photo)
        db.session.commit()
    flash("Photo(s) uploaded.") 
    return redirect(url_for('photos.view_gallery'))
