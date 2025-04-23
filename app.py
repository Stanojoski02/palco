from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tajna_lozinka'

DATABASE_URL = "postgresql://palco_user:vmMGliTqLu1tcyuZwr1mPARQC731xDkL@dpg-d04jb4buibrs73b5aac0-a.oregon-postgres.render.com/palco_db"

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL)''')

        cur.execute('''CREATE TABLE IF NOT EXISTS branches (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL)''')

        cur.execute('''CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            regular_price REAL,
            discount_price REAL,
            description TEXT,
            branch_id INTEGER REFERENCES branches(id))''')

        cur.execute("SELECT COUNT(*) FROM branches")
        if cur.fetchone()['count'] == 0:
            cur.executemany("INSERT INTO branches (name, address) VALUES (%s, %s)", [
                ('Пет Шоп Палчо бр. 1', 'ул.Киро Крстев бр. 1'),
                ('Пет Шоп Палчо бр. 2', 'ул. Пионерска бр. 11'),
                ('Пет Шоп Палчо бр. 3', 'ул. Илинденска бр. 13')
            ])

        cur.execute("SELECT COUNT(*) FROM users WHERE username = %s", ('adminpalco',))
        if cur.fetchone()['count'] == 0:
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)",
                        ('adminpalco', 'adminpalco123'))

        conn.commit()
        conn.close()
    except Exception as e:
        print("Грешка при иницијализација:", e)

@app.context_processor
def inject_date():
    return {'current_date': datetime.now().strftime('%d.%m.%Y')}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash('Најави се прво.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def home():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM branches")
    branches = cur.fetchall()
    conn.close()
    return render_template('home.html', branches=branches)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session['user'] = user['username']
            return redirect(url_for('product_list'))
        else:
            flash("Неточни податоци.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/products')
def product_list():
    branch_id = request.args.get('branch_id')
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM branches")
    branches = cur.fetchall()
    branch_name = "сите подружници"

    if branch_id:
        cur.execute("SELECT name FROM branches WHERE id = %s", (branch_id,))
        b = cur.fetchone()
        if b:
            branch_name = b['name']
        cur.execute("""
            SELECT products.*, branches.name AS branch_name
            FROM products
            JOIN branches ON products.branch_id = branches.id
            WHERE branch_id = %s
        """, (branch_id,))
    else:
        cur.execute("""
            SELECT products.*, branches.name AS branch_name
            FROM products
            JOIN branches ON products.branch_id = branches.id
        """)

    products = cur.fetchall()
    conn.close()
    return render_template('products.html', products=products, branches=branches, branch_name=branch_name)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM branches")
    branches = cur.fetchall()

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        regular_price = float(request.form.get('regular_price') or 0)
        discount_price = float(request.form.get('discount_price') or 0)
        description = request.form.get('description')
        branch_id = int(request.form['branch_id'])

        cur.execute("""
            INSERT INTO products (name, price, regular_price, discount_price, description, branch_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, price, regular_price, discount_price, description, branch_id))

        conn.commit()
        conn.close()
        return redirect(url_for('product_list'))

    return render_template('add_product.html', branches=branches)

@app.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()

    cur.execute("SELECT * FROM branches")
    branches = cur.fetchall()

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        regular_price = float(request.form.get('regular_price') or 0)
        discount_price = float(request.form.get('discount_price') or 0)
        description = request.form.get('description')
        branch_id = int(request.form['branch_id'])

        cur.execute("""
            UPDATE products SET name=%s, price=%s, regular_price=%s, discount_price=%s, description=%s, branch_id=%s
            WHERE id=%s
        """, (name, price, regular_price, discount_price, description, branch_id, product_id))

        conn.commit()
        conn.close()
        return redirect(url_for('product_list'))

    return render_template('edit_product.html', product=product, branches=branches)

@app.route('/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('product_list'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=10000, debug=True)
