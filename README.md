# يوزر بوت Telethon لتنزيل ورفع فيديوهات يوتيوب

مشروع يوزر بوت (Telethon) يقوم بتنزيل فيديوهات YouTube عبر `yt-dlp` ورفعها إلى تيليجرام حتى 2GB، مع عرض تقدم التحميل والرفع وتنظيف الملفات تلقائياً.

## المتطلبات
- Python 3.9+
- حساب تيليجرام (User) وليس بوت Bot
- الحصول على `API_ID` و`API_HASH` من موقع تيليجرام: https://my.telegram.org
- وجود `ffmpeg` على النظام (ضروري للدمج والتحويل من yt-dlp)

### تثبيت ffmpeg على أوبونتو/ديبيان
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

## الإعداد
```bash
cd yt_telethon_userbot
cp .env.example .env
# عدّل قيم API_ID و API_HASH داخل .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## التشغيل لأول مرة (تسجيل الجلسة)
```bash
python main.py
```
- سيطلب منك رقم هاتف تيليجرام والكود لمرة واحدة لإنشاء جلسة `SESSION_NAME` (افتراضيًا userbot.session).

## الاستخدام داخل تيليجرام
أرسل (كيوزر) في أي دردشة رسالة من حسابك الشخصي (ليس كبوت):

- تنزيل ورفع فيديو:
```
.yt <url> [--res 360|480|720|1080]
```
أمثلة:
```
.yt https://www.youtube.com/watch?v=XXXXXXXX
.yt https://youtu.be/XXXXXXXX --res 480
```
- الشرط: الحجم النهائي يجب أن لا يتجاوز 2GB (يمكن ضبطه من `.env`). إذا تجاوز الحجم سيتم إيقاف العملية مع اقتراح اختيار دقة أقل.

- يتم رفع الفيديو كـ Video يدعم المشاهدة المباشرة (streaming) مع العنوان والرابط، ويُحذف الملف المحلي تلقائيًا بعد الرفع.

## تحديثات مفيدة
- لتغيير مجلد التحميل عدّل `DOWNLOAD_DIR` في `.env`.
- لتغيير الحد الأقصى للحجم عدّل `MAX_FILE_SIZE_GB` في `.env`.

## التشغيل عبر Docker (اختياري)
```bash
docker build -t yt-telethon-userbot .
docker run --name yt-userbot --env-file .env -v $(pwd)/downloads:/app/downloads -it yt-telethon-userbot
```

## ملاحظات
- هذا يوزر بوت: يتفاعل مع رسائل حسابك (outgoing). لا يحتاج إنشاء بوت BotFather.
- يدعم فيديو واحد في كل أمر. قوائم التشغيل تُتجاهَل افتراضيًا.