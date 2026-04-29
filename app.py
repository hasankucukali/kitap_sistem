from flask import Flask, render_template, request, redirect, session
import sqlite3
import pandas as pd

app = Flask(__name__)
app.secret_key = "secret123"

def get_db():
    con = sqlite3.connect("kitap.db")
    con.row_factory = sqlite3.Row
    return con

# DB
with get_db() as con:
    con.execute("""
    CREATE TABLE IF NOT EXISTS kitaplar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barkod TEXT UNIQUE,
        ad TEXT,
        yazar TEXT,
        fiyat REAL,
        stok INTEGER
    )
    """)

# ANA
@app.route("/")
def home():
    return redirect("/stok")

# STOK + ARAMA
@app.route("/stok")
def stok():
    q = request.args.get("q", "")
    con = get_db()
    kitaplar = con.execute("""
    SELECT * FROM kitaplar 
    WHERE ad LIKE ? OR yazar LIKE ? OR barkod LIKE ?
    """, ('%'+q+'%','%'+q+'%','%'+q+'%')).fetchall()
    return render_template("stok.html", kitaplar=kitaplar)

# EKLE
@app.route("/ekle", methods=["GET","POST"])
def ekle():
    mesaj = ""
    if request.method == "POST":
        barkod = request.form["barkod"]
        ad = request.form["ad"]
        yazar = request.form["yazar"]
        fiyat = float(request.form["fiyat"])
        stok = int(request.form["stok"])

        con = get_db()
        var = con.execute("SELECT * FROM kitaplar WHERE barkod=?", (barkod,)).fetchone()

        if var:
            con.execute("UPDATE kitaplar SET stok = stok + ? WHERE barkod=?", (stok, barkod))
            mesaj = "Stok artırıldı"
        else:
            con.execute("INSERT INTO kitaplar VALUES (NULL,?,?,?,?,?)",
                        (barkod, ad, yazar, fiyat, stok))

            mesaj = "Ürün eklendi"

        con.commit()

    return render_template("ekle.html", mesaj=mesaj)

# EXCEL
@app.route("/excel", methods=["GET","POST"])
def excel():
    mesaj = ""
    if request.method == "POST":
        file = request.files["file"]
        df = pd.read_excel(file)

        con = get_db()

        for _, row in df.iterrows():
            barkod = str(row[0])
            ad = str(row[1])
            yazar = str(row[2])
            fiyat = float(row[3])
            stok = int(row[4])

            var = con.execute("SELECT * FROM kitaplar WHERE barkod=?", (barkod,)).fetchone()

            if var:
                con.execute("UPDATE kitaplar SET stok = stok + ? WHERE barkod=?", (stok, barkod))
            else:
                con.execute("INSERT INTO kitaplar VALUES (NULL,?,?,?,?,?)",
                            (barkod, ad, yazar, fiyat, stok))

        con.commit()
        mesaj = "Excel yüklendi"

    return render_template("excel.html", mesaj=mesaj)

# SATIŞ
@app.route("/satis", methods=["GET","POST"])
def satis():
    mesaj = ""

    if request.method == "POST":
        barkod = request.form["barkod"]

        con = get_db()
        kitap = con.execute("SELECT * FROM kitaplar WHERE barkod=?", (barkod,)).fetchone()

        if not kitap:
            mesaj = "Ürün yok"
        elif kitap["stok"] <= 0:
            mesaj = "Stok yok"
        else:
            if "sepet" not in session:
                session["sepet"] = []

            bulundu = False
            for i in session["sepet"]:
                if i["barkod"] == barkod:
                    i["adet"] += 1
                    bulundu = True

            if not bulundu:
                session["sepet"].append({
                    "barkod": barkod,
                    "ad": kitap["ad"],
                    "fiyat": kitap["fiyat"],
                    "adet": 1
                })

            session.modified = True

    sepet = session.get("sepet", [])
    toplam = sum(i["adet"] * i["fiyat"] for i in sepet)

    return render_template("satis.html", mesaj=mesaj, sepet=sepet, toplam=toplam)

# + ARTTIR
@app.route("/arttir/<barkod>")
def arttir(barkod):
    for i in session.get("sepet", []):
        if i["barkod"] == barkod:
            i["adet"] += 1
    session.modified = True
    return redirect("/satis")

# - AZALT
@app.route("/azalt/<barkod>")
def azalt(barkod):
    yeni = []
    for i in session.get("sepet", []):
        if i["barkod"] == barkod:
            i["adet"] -= 1
            if i["adet"] > 0:
                yeni.append(i)
        else:
            yeni.append(i)
    session["sepet"] = yeni
    session.modified = True
    return redirect("/satis")

# SİL
@app.route("/sil/<barkod>")
def sil(barkod):
    session["sepet"] = [i for i in session["sepet"] if i["barkod"] != barkod]
    session.modified = True
    return redirect("/satis")

# TAMAMLA + FİŞ
@app.route("/tamamla")
def tamamla():
    con = get_db()
    sepet = session.get("sepet", [])

    for i in sepet:
        con.execute("UPDATE kitaplar SET stok = stok - ? WHERE barkod=?",
                    (i["adet"], i["barkod"]))

    con.commit()

    toplam = sum(i["adet"] * i["fiyat"] for i in sepet)

    session["son_satis"] = sepet
    session["toplam"] = toplam
    session["sepet"] = []

    return redirect("/fis")

# FİŞ
@app.route("/fis")
def fis():
    satis = session.get("son_satis", [])
    toplam = session.get("toplam", 0)
    return render_template("fis.html", satis=satis, toplam=toplam)

app.run(debug=True)