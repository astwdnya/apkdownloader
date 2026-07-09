# 🤖 ربات تلگرام دانلود APK از Uptodown

رباتی پایتونی که با **Telethon** ساخته شده و لینک گوگل‌پلی / Uptodown / نام پکیج رو می‌گیره، نسخه‌های مختلف APK رو به صورت **دکمه‌های شیشه‌ای (Inline Keyboard)** نشون می‌ده و بعد از انتخاب کاربر، فایل APK رو مستقیم از **Uptodown** دانلود و در تلگرام می‌فرسته.

## ✨ امکانات

- 🆓 **بدون نیاز به اکانت گوگل** — بدون AAS Token، بدون App Password
- 📲 APK یونیورسال (روی همه معماری‌ها: arm64-v8a, armeabi-v7a, x86_64, x86)
- 📅 انتخاب بین نسخه‌های مختلف (آخرین نسخه + نسخه‌های قدیمی‌تر)
- 🔍 جستجوی برنامه‌ها داخل Uptodown با `/search`
- 🔗 پشتیبانی از لینک‌های گوگل‌پلی (ربات خودش اسم برنامه را استخراج می‌کند)
- 🔗 پشتیبانی از لینک‌های مستقیم Uptodown
- 🔒 محدودسازی کاربران مجاز (اختیاری)
- 🚀 مبتنی بر **Telethon** (سریع‌تر و سبک‌تر از Bot API، حد آپلود ۲ گیگابایت)
- 🐳 آماده استقرار روی VPS / Render / Docker

## 📁 ساختار پروژه

```
telegram-apk-bot/
├── bot.py                  # ربات تلگرام (Telethon + دکمه‌های شیشه‌ای)
├── uptodown_downloader.py  # دانلود APK از uptodown.com
├── config.py               # بارگذاری متغیرهای محیطی
├── requirements.txt
├── .env.example            # نمونه فایل تنظیمات
├── Dockerfile              # استقرار با Docker
├── render.yaml             # استقرار روی Render.com
├── run_bot.bat             # لانچر ویندوز (دابل‌کلیک)
├── start.sh                # لانچر لینوکس
└── README.md
```

## 🚀 راه‌اندازی

### ۱) پیش‌نیازها

- پایتون ۳.۱۰ یا بالاتر
- یک ربات تلگرام (توکن از [@BotFather](https://t.me/BotFather))

### ۲) تنظیم متغیرها

فایل `.env` بسازید (از روی `.env.example`):

```bash
cp .env.example .env
```

و این مقادیر را پر کنید:

```env
# Telegram / Telethon
API_ID=2040
API_HASH=b18441a1ff607e10a989891a5462e627
BOT_TOKEN=123456789:ABCdef...        # توکن ربات از @BotFather
SESSION_NAME=apk_bot

# Access control
ALLOWED_USER_IDS=                    # اختیاری - IDs کاربران مجاز

# Uptodown
UPTODOWN_LANG=en
MAX_VERSIONS=8
LOG_LEVEL=INFO
```

> برای پیدا کردن Telegram User ID خود، به ربات [@userinfobot](https://t.me/userinfobot) پیام بدهید.

### ۳) اجرا

#### 🪟 روی ویندوز

۱. پایتون ۳.۱۰+ را از https://www.python.org/downloads/windows/ نصب کنید
   - ⚠️ حتماً تیک **"Add Python to PATH"** را در زمان نصب بزنید

۲. پوشه پروژه را در File Explorer باز کنید

۳. روی فایل **`run_bot.bat`** دابل‌کلیک کنید

#### 🐧 روی Linux / macOS

```bash
python bot.py
# یا
./start.sh
```

> 💡 **نکته:** در اولین اجرا، Telethon فایل `apk_bot.session` را می‌سازد. این فایل session تلگرام است و نیازی به لاگین مجدد در اجراهای بعدی نیست.

#### 🐳 اجرا با Docker

```bash
docker build -t telegram-apk-bot .
docker run -d --env-file .env --name apk-bot telegram-apk-bot
```

#### ☁️ استقرار روی Render.com

1. پروژه را به GitHub پوش کنید
2. در Render: **New → Blueprint → انتخاب ریپو**
3. Render فایل `render.yaml` را شناسایی می‌کند
4. متغیرهای محیطی را در پنل Render وارد کنید
5. Deploy کنید

#### 🖥️ استقرار روی VPS (با systemd)

```bash
scp -r telegram-apk-bot/ user@vps:/opt/
ssh user@vps

cd /opt/telegram-apk-bot
pip install -r requirements.txt

sudo tee /etc/systemd/system/apk-bot.service > /dev/null <<'EOF'
[Unit]
Description=Telegram APK Bot (Uptodown)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram-apk-bot
EnvironmentFile=/opt/telegram-apk-bot/.env
ExecStart=/usr/bin/python3 /opt/telegram-apk-bot/bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now apk-bot
sudo systemctl status apk-bot
```

## 🎮 نحوه استفاده

### روش ۱: ارسال لینک گوگل‌پلی
```
https://play.google.com/store/apps/details?id=com.whatsapp
```
ربات اسم برنامه را از گوگل‌پلی استخراج می‌کند و در Uptodown جستجو می‌کند.

### روش ۲: ارسال لینک مستقیم Uptodown
```
https://whatsapp-messenger.en.uptodown.com/android
```

### روش ۳: ارسال نام پکیج
```
com.whatsapp
```

### روش ۴: جستجوی آزاد
```
/search whatsapp messenger
```
یا فقط کلمه‌ای را بفرستید (مثلاً `whatsapp`) تا ربات آن را جستجو کند.

### جریان کار:
1. ربات لیست برنامه‌های منطبق را به صورت دکمه‌های شیشه‌ای نشان می‌دهد
2. روی برنامه مورد نظر ضربه بزنید
3. ربات لیست نسخه‌ها (آخرین نسخه + نسخه‌های قدیمی‌تر) را نشان می‌دهد
4. روی نسخه دلخواه ضربه بزنید → ربات APK را دانلود و ارسال می‌کند

## 🆚 چرا Uptodown به جای گوگل‌پلی؟

| ویژگی | Uptodown | Google Play (gpapi) |
|---|---|---|
| نیاز به اکانت گوگل | ❌ | ✅ (ضروری) |
| نیاز به AAS Token | ❌ | ✅ (دریافت سختی دارد) |
| نیاز به App Password | ❌ | ✅ |
| ریسک مسدود شدن اکانت | ❌ | ✅ (بالا) |
| نسخه‌های قدیمی | ✅ | ❌ |
| پشتیبانی از منطقه‌های مختلف | ✅ | محدود |
| نصب ساده | ✅ | پیچیده |

## 🔧 نکات فنی

### معماری APK
Uptodown معمولاً برنامه‌های App Bundle را به صورت یک APK یونیورسال تک‌فایلی بازنشر می‌کند که روی همه معماری‌ها (arm64-v8a, armeabi-v7a, x86_64, x86) کار می‌کند. به همین دلیل به جای دکمه‌های معماری، دکمه‌های **نسخه** ارائه می‌شود.

### محدودیت‌ها
- حجم فایل APK نباید از **۲ گیگابایت** (حد تلگرام) بیشتر باشد
- برای برنامه‌های پولی معمولاً نسخه رایگان در Uptodown نیست
- برخی برنامه‌های منطقه‌ای ممکن است در Uptodown موجود نباشند

### زبان Uptodown
به طور پیش‌فرض از سایت انگلیسی (`en.uptodown.com`) استفاده می‌شود. می‌توانید در `.env`:
```env
UPTODOWN_LANG=es    # اسپانیایی
UPTODOWN_LANG=de    # آلمانی
UPTODOWN_LANG=fr    # فرانسوی
```

## 🛠 رفع اشکال

| مشکل | راه‌حل |
|---|---|
| `ConnectionError` | اینترنت/VPN را بررسی کنید |
| `Empty search results` | نام انگلیسی برنامه را امتحان کنید |
| فایل دانلود نمی‌شود | نسخه دیگری را امتحان کنید (ممکن است نسخه حذف شده باشد) |
| `SessionStartError` | فایل `apk_bot.session` را پاک کنید و دوباره اجرا کنید |
| `callback_data too long` | نام برنامه خیلی بلند است؛ ربات خودکار آن را کوتاه می‌کند |
| دکمه‌ها کار نمی‌کنند | ربات را ری‌استارت کنید (session cache پاک می‌شود) |

## 📜 مجوز

MIT License — استفاده آزاد.

## ⚠️ هشدار

این پروژه صرفاً برای اهداف آموزشی و راحتی شخصی است. دانلود خودکار APK از Uptodown ممکن است **خلاف ToS** باشد. مسئولیت استفاده با شماست. نویسنده هیچ مسئولیتی در قبال مسدود شدن اکانت یا IP شما ندارد.
