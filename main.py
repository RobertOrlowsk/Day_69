from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)

# Gravatar:
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy()
db.init_app(app)


# CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = relationship('User', back_populates='posts')
    img_url = db.Column(db.String(250), nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # author_id = Column(db.Integer, db.ForeignKey('authors.id')) definiuje klucz obcy w tabeli User,
    # który łączy tę tabelę z tabelą authors za pomocą kolumny id.

    comment = relationship('Comment', back_populates='parent_post')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    # BlogPost
    posts = relationship('BlogPost', back_populates='author')
    # Comment
    comments = relationship('Comment', back_populates='author')


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    # USER
    author = relationship('User', back_populates='comments')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # BLOGPOST
    parent_post = relationship('BlogPost', back_populates='comment')
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))


with app.app_context():
    db.create_all()


# DECORATOR ADMIN_ONLY ( SHORT: if current_user.get_id() != 1 or not current_user.is_authenticated: ... )
def admin_only(fun):
    @wraps(fun)
    def wrapped(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        else:
            return fun(*args, **kwargs)

    return wrapped


@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegisterForm()

    if register_form.validate_on_submit():

        check_user = User.query.filter_by(email=register_form.email.data).first()
        print(check_user)
        if check_user:
            flash('user with this email exist, try to login.')
            return redirect(url_for('login'))

        new_user = User(
            email=register_form.email.data,
            name=register_form.name.data,
            password=generate_password_hash(register_form.password.data, method='pbkdf2:sha256', salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=register_form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        email = login_form.email.data
        passwd = login_form.password.data

        get_user = User.query.filter_by(email=email).first()

        if not get_user or not check_password_hash(get_user.password, passwd):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))
        else:
            login_user(get_user)
            print(f'welcome {current_user.name}, {User.get_id(current_user)}')
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        print(f"Goodbye!: {current_user.name}")
        logout_user()  # LOGOUT USER, CLEAN UP!
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)

    if comment_form.validate_on_submit():
        new_comment = Comment(
            text=comment_form.comment.data,
            author_id=current_user.id,
            post_id=requested_post.id
        )
        db.session.add(new_comment)
        db.session.commit()

    get_comments = db.session.execute(db.Select(Comment).where(Comment.post_id == post_id))
    comments = get_comments.scalars().all()
    return render_template("post.html", post=requested_post, form=comment_form, comments=comments)


@app.route("/new-post", methods=["GET", "POST"])
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)

    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)

    if current_user.get_id() != '1' or not current_user.is_authenticated:
        print('Only admin can delete posts', current_user.get_id())
        return redirect(url_for('get_all_posts'))

    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
