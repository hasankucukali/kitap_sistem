from flask import Flask, render_template, request, redirect, session
import psycopg2
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "secret123"

# 🔥 DATABASE BAĞLANTI
def get_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))


# 🏠 ANA SAYFA
@app.route("/")
def home():
    return render_template("index.html")


# 📦 STOK
@app.route("/stok")
def stok():
    q = request.args.get("q", "")

    con = get_db()
    cur = con.cursor()

    if q:
        cur.execute("""
            SELECT barkod, ad, yazar, fiyat, stok 
            FROM kitaplar 
            WHERE ad ILIKE %s OR yazar ILIKE %s OR barkod ILIKE %s
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        cur.execute("SELECT barkod, ad, yazar, fiyat, stok FROM kitaplar")

    rows = cur.fetchall()

    cur.close()
    con.close()

    return render_template("stok.html", kitaplar=rows)

# ➕ ÜRÜN EKLE
@app.route("/ekle", methods=["GET", "POST"])
def ekle():
    mesaj = ""

    if request.method == "POST":
        try:
            barkod = request.form["barkod"]
            ad = request.form["ad"]
            yazar = request.form["yazar"]
            fiyat = float(request.form["fiyat"])
            stok = int(request.form["stok"])

            con = get_db()
            cur = con.cursor()

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


# 📥 EXCEL YÜKLE
@app.route("/excel_yukle", methods=["POST"])
def excel_yukle():
    try:
        file = request.files["file"]

        df = pd.read_excel(file)

        con = get_db()
        cur = con.cursor()

        for _, row in df.iterrows():
            barkod = str(row["barkod"])
            ad = row["ad"]
            yazar = row["yazar"]
            fiyat = float(row["fiyat"])
            stok = int(row["stok"])

            cur.execute("SELECT * FROM kitaplar WHERE barkod=%s", (barkod,))
            var = cur.fetchone()

            if var:
                cur.execute(
                    "UPDATE kitaplar SET stok = stok + %s WHERE barkod=%s",
                    (stok, barkod)
                )
            else:
                cur.execute(
                    "INSERT INTO kitaplar (barkod, ad, yazar, fiyat, stok) VALUES (%s,%s,%s,%s,%s)",
                    (barkod, ad, yazar, fiyat, stok)
                )

        con.commit()
        cur.close()
        con.close()

        return redirect("/stok")

    except Exception as e:
        return "HATA: " + str(e)


# 💰 SATIŞ
@app.route("/satis", methods=["GET", "POST"])
def satis():
    mesaj = ""

    if "sepet" not in session:
        session["sepet"] = []

    if request.method == "POST":
        barkod = request.form["barkod"]

        con = get_db()
        cur = con.cursor()

        cur.execute("SELECT ad, fiyat, stok FROM kitaplar WHERE barkod=%s", (barkod,))
        urun = cur.fetchone()

        cur.close()
        con.close()

        if urun:
            bulundu = False

            for i in session["sepet"]:
                if i["barkod"] == barkod:
                    i["adet"] += 1
                    bulundu = True
                    break

            if not bulundu:
                session["sepet"].append({
                    "barkod": barkod,
                    "ad": urun[0],
                    "fiyat": urun[1],
                    "adet": 1
                })
        else:
            mesaj = "Ürün bulunamadı"

    toplam = sum(i["adet"] * i["fiyat"] for i in session["sepet"])
    session.modified = True

    return render_template("satis.html", sepet=session["sepet"], toplam=toplam, mesaj=mesaj)


# ➕ ARTIR
@app.route("/arttir/<barkod>")
def arttir(barkod):
    for i in session["sepet"]:
        if i["barkod"] == barkod:
            i["adet"] += 1
            break

    session.modified = True
    return redirect("/satis")


# ➖ AZALT
@app.route("/azalt/<barkod>")
def azalt(barkod):
    for i in session["sepet"]:
        if i["barkod"] == barkod and i["adet"] > 1:
            i["adet"] -= 1
        

    session.modified = True
    return redirect("/satis")


# ❌ SİL
@app.route("/sil/<barkod>")
def sil(barkod):
    session["sepet"] = [i for i in session["sepet"] if i["barkod"] != barkod]
    

    session.modified = True
    return redirect("/satis")


# ✅ SATIŞ TAMAMLA
@app.route("/tamamla")
def tamamla():
    con = get_db()
    cur = con.cursor()

    for i in session["sepet"]:
        cur.execute(
            "UPDATE kitaplar SET stok = stok - %s WHERE barkod=%s AND stok >= %s",
            (i["adet"], i["barkod"], i["adet"])
        )

    con.commit()
    cur.close()
    con.close()

    session["sepet"] = []

    return redirect("/stok")


# 🚀 ÇALIŞTIRMA
if __name__ == "__main__":
    app.run(debug=True)
