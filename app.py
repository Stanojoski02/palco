from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from datetime import datetime
import bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = 'tajna_lozinka'
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax'
)
DATABASE = 'database.db'
limiter = Limiter(get_remote_address, app=app)

def get_db():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print("Database connection error:", e)
        return None

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            regular_price REAL,
            discount_price REAL,
            branch_id INTEGER,
            FOREIGN KEY(branch_id) REFERENCES branches(id))''')

        cursor.execute("SELECT COUNT(*) FROM branches")
        if cursor.fetchone()[0] == 0:
            branches = [
                ('Пет Шоп Палчо бр. 1', 'ул.Киро Крстев бр. 1'),
                ('Пет Шоп Палчо бр. 2', 'ул. Пионерска бр. 11'),
                ('Пет Шоп Палчо бр. 3', 'ул. Илинденска бр. 13')
            ]
            cursor.executemany("INSERT INTO branches (name, address) VALUES (?, ?)", branches)
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

@app.context_processor
def inject_date():
    return {'current_date': datetime.now().strftime('%d.%m.%Y')}

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            flash('Најави се за да пристапиш.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def home():
    try:
        conn = get_db()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        conn.close()
        return render_template('home.html', branches=branches)
    except Exception as e:
        flash(f"Грешка при вчитување на почетна страна: {e}")
        return redirect(url_for('login'))

@limiter.limit("5 per minute")
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password'].encode('utf-8')
            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            conn.close()
            if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
                session['user'] = user['username']
                return redirect(url_for('product_list'))
            else:
                flash('Неточни податоци.')
        except Exception as e:
            flash(f"Грешка при најава: {e}")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/products')
def product_list():
    try:
        branch_id = request.args.get('branch_id')
        conn = get_db()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        branch_name = "сите подружници"

        if branch_id:
            branch = conn.execute("SELECT name FROM branches WHERE id=?", (branch_id,)).fetchone()
            if branch:
                branch_name = branch["name"]
            products = conn.execute("""
                SELECT products.*, branches.name AS branch_name
                FROM products
                JOIN branches ON products.branch_id = branches.id
                WHERE branch_id=?
            """, (branch_id,)).fetchall()
        else:
            products = conn.execute("""
                SELECT products.*, branches.name AS branch_name
                FROM products
                JOIN branches ON products.branch_id = branches.id
            """).fetchall()
        conn.close()
        return render_template('products.html', products=products, branches=branches, branch_name=branch_name)
    except Exception as e:
        flash(f"Грешка при вчитување на производи: {e}")
        return redirect(url_for('home'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    try:
        conn = get_db()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        if request.method == 'POST':
            name = request.form['name']
            price = float(request.form['price'])
            description = request.form.get('description')
            regular_price = float(request.form.get('regular_price') or 0)
            discount_price = float(request.form.get('discount_price') or 0)
            branch_id = int(request.form.get('branch_id'))
            if not name or price < 0:
                flash("Невалиден внес.")
                return redirect(url_for('add_product'))
            conn.execute("""
                INSERT INTO products (name, price, description, regular_price, discount_price, branch_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (name, price, description, regular_price, discount_price, branch_id))
            conn.commit()
            conn.close()
            return redirect(url_for('product_list'))
        return render_template('add_product.html', branches=branches)
    except Exception as e:
        flash(f"Грешка при додавање: {e}")
        return redirect(url_for('product_list'))

@app.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    try:
        conn = get_db()
        branches = conn.execute("SELECT * FROM branches").fetchall()
        if request.method == 'POST':
            name = request.form['name']
            price = float(request.form['price'])
            description = request.form.get('description')
            regular_price = float(request.form.get('regular_price') or 0)
            discount_price = float(request.form.get('discount_price') or 0)
            branch_id = int(request.form.get('branch_id'))
            if not name or price < 0:
                flash("Невалиден внес.")
                return redirect(url_for('edit_product', product_id=product_id))
            conn.execute("""
                UPDATE products SET name=?, price=?, description=?, regular_price=?, discount_price=?, branch_id=?
                WHERE id=?""",
                (name, price, description, regular_price, discount_price, branch_id, product_id))
            conn.commit()
            conn.close()
            return redirect(url_for('product_list'))
        product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        conn.close()
        return render_template('edit_product.html', product=product, branches=branches)
    except Exception as e:
        flash(f"Грешка при уредување: {e}")
        return redirect(url_for('product_list'))

@app.route('/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('product_list'))
    except Exception as e:
        flash(f"Грешка при бришење: {e}")
        return redirect(url_for('product_list'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=10000)

