from flask import Flask, request, render_template, session, redirect, flash, url_for, jsonify
from flask_session import Session
from werkzeug.utils import secure_filename
from datetime import date
import re
import cv2
import os
import mysql.connector
from mysql.connector import Error
from collections import defaultdict
import hashlib

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super secret key')

# Fungsi untuk membuat koneksi ke database
def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            port='3306',
            database='db_sistem_pakar',
            user='root',
            password=''
        )
        if connection.is_connected():
            print("Berhasil terhubung ke database")
            return connection
    except Error as e:
        print(f"Kesalahan saat menghubungkan ke MySQL: {e}")
        return None

# Membangun koneksi ke database
connection = create_connection()
if connection:
    cursor = connection.cursor(dictionary=True) 
else:
    print("Gagal terhubung ke database")

@app.route("/dashboard", methods=['GET', 'POST'])
def index():
    if 'loggedin' in session:
        try:
            cursor.execute("SELECT id, name, kecerdasan, percentage, rekomen, tanggal_test FROM result ORDER BY id DESC")
            results = cursor.fetchall()
            print("Results from database:", results)
        except Exception as e:
            print(f"Error fetching data from database: {e}")
            return "Failed to retrieve data from the database", 500
        
        return render_template('index.html', results=results)
    return redirect(url_for('login'))

@app.route("/register", methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        alamat = request.form['alamat']
        instansi = request.form['instansi']
        role = request.form.get('role', 0)
        if phone.startswith('0'):
            phone = '+62' + phone[1:]
        else:
            phone = '+62' + phone
        # Validasi kata sandi
        if len(password) < 8 or not re.search("[a-z]", password) or not re.search("[A-Z]", password) or not re.search("[0-9]", password) or not re.search("[*&#%@-]", password):
            flash('Password harus minimal 8 karakter dan mengandung huruf besar, huruf kecil, angka, dan karakter spesial (*, &, #, %, @, -).')
            return render_template('register.html',  name=name, email=email, phone=phone, alamat=alamat, instansi=instansi)
            # return redirect(url_for('register'))
        password = hashlib.sha256(password.encode()) 
        password = password.hexdigest()
        try:
            connection = create_connection()
            if connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute('INSERT INTO user (name, email, password, phone, alamat, instansi, role) VALUES (%s, %s, %s, %s, %s, %s, %s)', (name, email, password, phone, alamat, instansi, role))
                connection.commit()

                cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
                account = cursor.fetchone()

                cursor.close()
                connection.close()

                if account:
                    session['loggedin'] = True
                    session['email'] = account['email']
                    session['name'] = account['name']
                    session['role'] = role
                    flash('Berhasil Melakukan Register!!!')
                    return redirect(url_for('panduan'))
                else:
                    flash('Akun tidak ditemukan setelah registrasi.')
            else:
                flash('Gagal terhubung ke database.')
        except Error as e:
            msg = f'Kesalahan saat mendaftar: {e}'
            flash(msg)
            return redirect(url_for('register'))
    return render_template('register.html', msg=msg)

@app.route("/", methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        password = hashlib.sha256(password.encode()) 
        password = password.hexdigest()
        cursor.execute('SELECT * FROM user WHERE email = %s AND password = %s', (email, password))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['email'] = account['email']
            session['name'] = account['name']
            session['role'] = account['role']
            if account['role'] == '1':
                return redirect(url_for('index'))
            else:
                return redirect(url_for('panduan'))
        else:
            msg = 'Email atau kata sandi salah!'
    return render_template('login.html', msg=msg)

@app.route("/tes")
def tes():
    connection = create_connection()
    if connection and connection.is_connected():
        cursor.execute("SELECT * FROM testing")
        data = cursor.fetchall()
        if connection:
            curso = connection.cursor(dictionary=True)
            curso.execute('SELECT name, email, phone, alamat, instansi FROM user WHERE email = %s', (session['email'],))
            user_data = curso.fetchone()
            curso.close()
            connection.close()
            if user_data:
                return render_template('tes.html', data=data, nama=user_data['name'], user_data=user_data)
    else:
        return "Tidak bisa terhubung ke database"

@app.route('/submit-data', methods=['POST'])
def submit_data():
    data = request.get_json()
    
    print("Data received from view:", data)
    
    grouped_data = defaultdict(list)
    for item in data:
        grouped_data[item['id_kecerdasan']].append(item)
    
    results = {}
    
    for id_kecerdasan, items in grouped_data.items():
        if not items:
            continue
        
        first_item = items[0]
        combined_result = 1.0
        
        if first_item['kondisi'] is not None and first_item['cf_pakar'] is not None:
            combined_result = float(first_item['kondisi']) * float(first_item['cf_pakar'])
        
        for item in items[1:]:
            if item['kondisi'] is not None and item['cf_pakar'] is not None:
                kondisi = float(item['kondisi'])
                cf_pakar = float(item['cf_pakar'])
                
                combined_result = combined_result + kondisi * cf_pakar * (1 - combined_result)
        
        print(f"Intermediate result for id_kecerdasan={id_kecerdasan}: {combined_result}")
        
        percentage = combined_result * 100
        results[id_kecerdasan] = percentage
    
    highest_result = max(results.items(), key=lambda x: x[1])
    highest_id_kecerdasan, highest_percentage = highest_result
    
    print(f"Results: {results}")
    print(f"Highest: id_kecerdasan={highest_id_kecerdasan}, percentage={highest_percentage}")
    session['highest_percentage'] = highest_percentage
    
    cursor.execute("SELECT * FROM kecerdasan WHERE id = %s", (highest_id_kecerdasan,))
    kecerdasan_data = cursor.fetchone()

    if kecerdasan_data:
        session['kecerdasan_data'] = {
            'nm_kecerdasan': kecerdasan_data.get('nm_kecerdasan'),
            'deskripsi': kecerdasan_data.get('deskripsi'),
            'pekerjaan': kecerdasan_data.get('pekerjaan')
        }
        print(session.get('kecerdasan_data'))
    else:
        print("Error: kecerdasan_data is empty")

    return redirect(url_for('tes2'), code=302)

@app.route('/tes2', methods=['GET'])
def tes2():
    connection = create_connection()
    if not connection:
        return "Gagal menghubungkan ke database", 500

    kecerdasan_data = session.get('kecerdasan_data')
    highest_percentage = session.get('highest_percentage')
    
    if kecerdasan_data:
        nama_cerdas = kecerdasan_data.get('nm_kecerdasan')
        deskripsi = kecerdasan_data.get('deskripsi')
        pekerjaan = kecerdasan_data.get('pekerjaan')
        highest_percentage = round(highest_percentage, 2)
        
        name = session.get('name')
        tanggal_test = date.today() 
        
        # Pengecekan entri yang sudah ada
        check_query = """
            SELECT COUNT(*) as count FROM result
            WHERE name = %s AND kecerdasan = %s
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(check_query, (name, nama_cerdas))
        result_count = cursor.fetchone()['count']
        
        if result_count == 0:
            insert_query = """
                INSERT INTO result (name, kecerdasan, percentage, rekomen, tanggal_test)
                VALUES (%s, %s, %s, %s, %s)
            """
            try:
                cursor.execute(insert_query, (
                    name,
                    nama_cerdas,
                    highest_percentage,
                    pekerjaan,
                    tanggal_test
                ))
                connection.commit()
            except Exception as e:
                print(f"Error inserting data: {e}")
                connection.rollback()
                cursor.close()
                connection.close()
                return "Gagal menyisipkan data ke dalam database", 500
        
        cursor.execute('SELECT name, email, phone, alamat, instansi FROM user WHERE email = %s', (session['email'],))
        user_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if user_data:
            return render_template('tes2.html', nama=nama_cerdas, deskripsi=deskripsi, pekerjaan=pekerjaan, percentage=highest_percentage, naman=session['name'], user_data=user_data)
    else:
        return "Error: kecerdasan_data tidak ditemukan dalam session", 404


@app.route('/identitas', methods=['GET', 'POST'])
def identitas():
    msg=''
    if request.method == 'POST':
        nama = request.form['nama']
        telepon = request.form['telepon']
        alamat = request.form['alamat']
        sekolah = request.form['sekolah']
        try:
            cursor.execute('INSERT INTO identitas (nama, no_hp, alamat, asal_instansi) VALUES (%s, %s, %s, %s)', (nama, telepon, alamat, sekolah))
            connection.commit()
            session['loggedin'] = True
            session['nama'] = nama
            return redirect(url_for('panduan'))
        except Error as e:
            msg = f'Kesalahan saat mengisi data diri: {e}'
    return render_template('datadiri.html', msg=msg)

@app.route("/masuk",methods=['GET','POST'])
def masuk():
    msg=''
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        cursor.execute('SELECT * FROM user WHERE email=%s AND password=%s',(email,password))
        record = cursor.fetchone()
        if record:
            session['loggedin']= True
            session['email']= record[1]
            return redirect(url_for('panduan'))
        else:
            msg='Incorrect email/password.Try again!'
    return render_template('login.html',msg=msg)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    return redirect(url_for('login'))

@app.route("/datadiri")
def datadiri():
    if not session.get('loggedin'):
        return redirect(url_for('masuk'))
    return render_template('datadiri.html', email=session['email'])

@app.route('/panduan')
def panduan():
    if not session.get('loggedin'):
        return redirect(url_for('datadiri'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT name, email, phone, alamat, instansi FROM user WHERE email = %s', (session['email'],))
        user_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if user_data:
            return render_template('panduan.html', nama=user_data['name'], user_data=user_data)
        else:
            flash('Data pengguna tidak ditemukan.')
            return redirect(url_for('datadiri'))
    else:
        flash('Gagal terhubung ke database.')
        return redirect(url_for('datadiri'))

@app.route('/terimakasih', methods=['GET'])
def terimakasih():
    connection = create_connection()
    if connection and connection.is_connected():
        if connection:
            curso = connection.cursor(dictionary=True)
            curso.execute('SELECT name, email, phone, alamat, instansi FROM user WHERE email = %s', (session['email'],))
            user_data = curso.fetchone()
            curso.close()
            connection.close()
            if user_data:
                return render_template('terimakasih.html', nama=user_data['name'], user_data=user_data)
    else:
        return "Tidak bisa terhubung ke database"

if __name__ == '__main__':
	app.run(debug = True)