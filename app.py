from flask import Flask, render_template, request, redirect, session
import psycopg2
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = "secret123"

# DB BAĞLANTI
def get_db():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    return psycopg2.connect(DATABASE_URL)

# TABLO OLUŞTUR
def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS kitaplar(
        id SERIAL PRIMARY KEY,
        barkod TEXT UNIQUE,
        ad TEXT,
        yazar TEXT,
        fiyat REAL,
        stok INTEGER
    )
    """)

    con.commit()
    cur.close()
    con.close()

init_db()

# ANA
@app.route("/")
def home():
    return redirect("/stok")

# STOK + ARAMA
@app.route("/stok")
def stok():
    try:
        con = get_db()
        cur = con.cursor()

        cur.execute("SELECT barkod, ad, yazar, fiyat, stok FROM kitaplar")
        rows = cur.fetchall()

        cur.close()
        con.close()

        return render_template("stok.html", kitaplar=rows)

    except Exception as e:
        return "HATA: " + str(e)
# EKLE
@app.route("/ekle", methods=["GET","POST"])
def ekle():
    mesaj = ""

    if request.method == "POST":
        try:
            barkod = request.form.get("barkod")
            ad = request.form.get("ad")
            yazar = request.form.get("yazar")
            fiyat = request.form.get("fiyat")
            stok = request.form.get("stok")

            if not barkod or not ad:
                return render_template("ekle.html", mesaj="Barkod ve ad zorunlu")

            fiyat = float(fiyat or 0)
            stok = int(stok or 0)

            con = get_db()
            cur = con.cursor()

            # VAR MI KONTROL
            cur.execute("SELECT * FROM kitaplar WHERE barkod=%s", (barkod,))
            var = cur.fetchone()

            if var:
                cur.execute(
                    "UPDATE kitaplar SET stok = stok + %s WHERE barkod=%s",
                    (stok, barkod)
                )
                mesaj = "Stok artırıldı"
            else:
                cur.execute(
                    "INSERT INTO kitaplar (barkod, ad, yazar, fiyat, stok) VALUES (%s,%s,%s,%s,%s)",
                    (barkod, ad, yazar, fiyat, stok)
                )
                mesaj = "Ürün eklendi"

            con.commit()
            cur.close()
            con.close()

        except Exception as e:
            mesaj = "Hata: " + str(e)

    return render_template("ekle.html", mesaj=mesaj)
# EXCEL YÜKLE
@app.route("/excel", methods=["GET","POST"])
def excel():
    mesaj = ""

    if request.method == "POST":
        file = request.files["file"]
        df = pd.read_excel(file)

        con = get_db()
        cur = con.cursor()

        for _, row in df.iterrows():
            barkod = str(row[0])
            ad = str(row[1])
            yazar = str(row[2])
            fiyat = float(row[3])
            stok = int(row[4])

            cur.execute("SELECT * FROM kitaplar WHERE barkod=%s", (barkod,))
            var = cur.fetchone()

            if var:
                cur.execute("UPDATE kitaplar SET stok = stok + %s WHERE barkod=%s",
                            (stok, barkod))
            else:
                cur.execute("""
                INSERT INTO kitaplar (barkod, ad, yazar, fiyat, stok)
                VALUES (%s,%s,%s,%s,%s)
                """, (barkod, ad, yazar, fiyat, stok))

        con.commit()
        cur.close()
        con.close()

        mesaj = "Excel yüklendi"

    return render_template("excel.html", mesaj=mesaj)

# SATIŞ
@app.route("/satis", methods=["GET","POST"])
def satis():
    mesaj = ""

    if request.method == "POST":
        barkod = request.form["barkod"]

        con = get_db()
        cur = con.cursor()

        cur.execute("SELECT ad, fiyat, stok FROM kitaplar WHERE barkod=%s", (barkod,))
        kitap = cur.fetchone()

        cur.close()
        con.close()

        if not kitap:
            mesaj = "Ürün yok"
        elif kitap[2] <= 0:
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
                    "ad": kitap[0],
                    "fiyat": kitap[1],
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
    try:
        con = get_db()
        cur = con.cursor()

        sepet = session.get("sepet", [])

        if not sepet:
            return redirect("/satis")

        for i in sepet:
            barkod = i["barkod"]
            adet = int(i["adet"])

            cur.execute("""
            UPDATE kitaplar 
            SET stok = stok - %s 
            WHERE barkod = %s
            """, (adet, barkod))

        con.commit()   # 💥 EN ÖNEMLİ

        toplam = sum(i["adet"] * i["fiyat"] for i in sepet)

        session["son_satis"] = sepet
        session["toplam"] = toplam
        session["sepet"] = []

        cur.close()
        con.close()

        return redirect("/fis")

    except Exception as e:
        return "HATA: " + str(e)
# FİŞ
@app.route("/fis")
def fis():
    satis = session.get("son_satis", [])
    toplam = session.get("toplam", 0)
    return render_template("fis.html", satis=satis, toplam=toplam)

if __name__ == "__main__":
    app.run()
