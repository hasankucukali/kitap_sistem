from flask import Flask, render_template, request, redirect, session
import psycopg2
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "secret123"

# 🔥 DATABASE
def get_db():
    url = os.environ.get("DATABASE_URL")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return psycopg2.connect(url)


# 🔐 LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    hata = ""

    if request.method == "POST":
        kullanici = request.form["kullanici"]
        sifre = request.form["sifre"]

        if kullanici == "admin" and sifre == "1234":
            session["login"] = True
            return redirect("/")
        else:
            hata = "Hatalı giriş"

    return render_template("login.html", hata=hata)


# 🚪 LOGOUT



# 🔒 LOGIN KONTROL
def kontrol():
    if "login" not in session:
        return redirect("/login")


# 🏠 ANA SAYFA
@app.route("/")
def home():
    if "login" not in session:
        return redirect("/login")
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# 📦 STOK
@app.route("/stok")
def stok():
    q = request.args.get("q")

    con = get_db()
    cur = con.cursor()

    if q:
        cur.execute("""
            SELECT barkod, ad, yazar, fiyat, stok 
            FROM kitaplar
            WHERE 
                barkod ILIKE %s OR 
                ad ILIKE %s OR 
                yazar ILIKE %s
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
    if "login" not in session:
        return redirect("/login")

    mesaj = ""

    if request.method == "POST":
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
            cur.execute("UPDATE kitaplar SET stok = stok + %s WHERE barkod=%s", (stok, barkod))
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

    return render_template("ekle.html", mesaj=mesaj)


# 📥 CSV / EXCEL YÜKLE
@app.route("/excel_yukle", methods=["POST"])
def excel_yukle():
    if "login" not in session:
        return redirect("/login")

    file = request.files["file"]

    filename = file.filename.lower()

    if filename.endswith(".csv"):
        df = pd.read_csv(file, sep=';', encoding='utf-8-sig')
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip().str.lower()
    df = df.fillna(0)

    con = get_db()
    cur = con.cursor()

    for _, row in df.iterrows():
        barkod = str(row["barkod"]).replace(".0", "").strip()

        if barkod == "":
            continue

        ad = str(row["ad"])
        yazar = str(row["yazar"])
        fiyat = float(row["fiyat"])
        stok = int(row["stok"])

        cur.execute("SELECT * FROM kitaplar WHERE barkod=%s", (barkod,))
        var = cur.fetchone()

        if var:
            cur.execute("UPDATE kitaplar SET stok = stok + %s WHERE barkod=%s", (stok, barkod))
        else:
            cur.execute(
                "INSERT INTO kitaplar (barkod, ad, yazar, fiyat, stok) VALUES (%s,%s,%s,%s,%s)",
                (barkod, ad, yazar, fiyat, stok)
            )

    con.commit()
    cur.close()
    con.close()

    return redirect("/stok")


# 💰 SATIŞ
@app.route("/satis", methods=["GET", "POST"])
def satis():
    if "login" not in session:
        return redirect("/login")

    if "sepet" not in session:
        session["sepet"] = []

    mesaj = ""

    if request.method == "POST":
        barkod = request.form["barkod"]

        con = get_db()
        cur = con.cursor()

        cur.execute("SELECT ad, fiyat FROM kitaplar WHERE barkod=%s", (barkod,))
        urun = cur.fetchone()

        cur.close()
        con.close()

        if urun:
            bulundu = False

            for i in session["sepet"]:
                if i["barkod"] == barkod:
                    i["adet"] += 1
                    bulundu = True

            if not bulundu:
                session["sepet"].append({
                    "barkod": barkod,
                    "ad": urun[0],
                    "fiyat": urun[1],
                    "adet": 1
                })
        else:
            mesaj = "Ürün yok"

    session.modified = True

    toplam = sum(i["adet"] * i["fiyat"] for i in session["sepet"])

    return render_template("satis.html", sepet=session["sepet"], toplam=toplam, mesaj=mesaj)


# ➕ ➖ ❌
@app.route("/arttir/<barkod>")
def arttir(barkod):
    for i in session["sepet"]:
        if i["barkod"] == barkod:
            i["adet"] += 1
    session.modified = True
    return redirect("/satis")


@app.route("/azalt/<barkod>")
def azalt(barkod):
    for i in session["sepet"]:
        if i["barkod"] == barkod and i["adet"] > 1:
            i["adet"] -= 1
    session.modified = True
    return redirect("/satis")


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
    session.modified = True

    return redirect("/stok")


if __name__== "__main__":
    app.run(debug=True)
