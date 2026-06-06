# Smart Surveillance BI Prototype

Ushbu boshlang'ich prototip YouTube live video oqimida odamlar va transport
vositalarini YOLO hamda OpenCV yordamida aniqlaydi. Odamlar soni belgilangan
limitga yetganda konsolda crowd alert ko'rsatiladi.

## Ishga tushirish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Video oynasini yopish uchun `q` tugmasini bosing.

Agar YouTube bot tekshiruvi sabab oqimni bermasa, siz tizimga kirgan brauzer
nomini ko'rsating:

```bash
python app.py --cookies-from-browser chrome
```

YouTube JavaScript tekshiruvini yechish uchun kompyuterda `node` o'rnatilgan
bo'lishi kerak. Oqimni video oynasini ochmasdan tekshirish mumkin:

```bash
python app.py --cookies-from-browser chrome --check-source
```

macOS Safari cookie fayliga terminal orqali kirishni standart holatda
cheklaydi. Shu sababli ushbu prototip uchun Chrome ishlatish tavsiya etiladi.

## Screenshot olish

Live oqimdan 200 ta screenshot olish:

```bash
python capture_screenshots.py
```

Rasmlar `screenshots/` papkasiga saqlanadi.

## Parametrlar

```bash
python app.py \
  --source "https://www.youtube.com/live/Q71sLS8h9a4" \
  --threshold 20 \
  --confidence 0.35 \
  --frame-skip 2
```

`--threshold` crowd alert uchun odamlar soni limitini belgilaydi.
`--frame-skip` qiymatini oshirish CPU yuklamasini kamaytiradi.
