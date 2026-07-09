# apkdownloader

# 🤖 ربات تلگرام دانلود APK از گوگل‌پلی

رباتی پایتونی که لینک گوگل‌پلی رو می‌گیره، نسخه‌های مختلف APK (بر اساس معماری ARM و نسخه اندروید) رو به صورت **دکمه‌های شیشه‌ای (Inline Keyboard)** نشون می‌ده و بعد از انتخاب کاربر، فایل APK رو مستقیم از Google Play دانلود و در تلگرام می‌فرسته.

## ✨ امکانات

- 📲 پشتیبانی از معماری‌های `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86`
- 📱 نمایش همزمان `minSdk` و `targetSdk` به همراه نسخه اندروید
- 🔍 جستجوی برنامه‌ها داخل گوگل‌پلی با `/search`
- 📦 دانلود مستقیم APK از خود Google Play (نه منابع واسط)
- 🎛 دکمه‌های شیشه‌ای برای انتخاب سریع معماری
- 🔒 محدودسازی کاربران مجاز (اختیاری)
- 🐳 آماده استقرار روی VPS / Render / Railway / هر پلتفرم Docker

## 📁 ساختار پروژه

```
telegram-apk-bot/
├── bot.py                  # ربات تلگرام (هندلرها + دکمه‌های شیشه‌ای)
├── play_downloader.py      # wrapper روی gpapi برای ارتباط با Google Play
├── get_aas_token.py        # اسکریپت کمکی برای دریافت AAS Token
├── config.py               # بارگذاری متغیرهای محیطی
├── requirements.txt
├── .env.example            # نمونه فایل تنظیمات
├── Dockerfile              # استقرار با Docker
├── render.yaml             # استقرار روی Render.com
├── start.sh                # اجرای محلی
└── README.md
```

## 🚀 راه‌اندازی

### ۱) پیش‌نیازها

- پایتون ۳.۱۰ یا بالاتر
- یک **اکانت گوگل** (پیشنهاد: یک اکانت پرکاربرد نسازید، یک اکانت disposable بسازید)
- فعال بودن **Two-Factor Authentication (2FA)** روی اکانت گوگل
- یک **App Password** (۱۶ کاراکتری) از این آدرس:
  https://myaccount.google.com/apppasswords

### ۲) دریافت AAS Token

AAS Token (Google Services Framework login token) کلید احراز هویت ربات با Google Play است.

```bash
# نصب وابستگی‌ها
pip install -r requirements.txt

# اجرای اسکریپت دریافت توکن
python get_aas_token.py
```

اسکریپت از شما ایمیل و App Password را می‌خواهد و سپس AAS Token را چاپ می‌کند. مقدار را کپی کنید.

> ⚠️ **نکته امنیتی:** اگر گوگل اکانت شما را به عنوان «سuspicious» علامت بزند، ممکن است نیاز باشد یک بار از یک مرورگر معمولی به google.com لاگین کنید و سپس دوباره تلاش کنید.

### ۳) تنظیم متغیرها

فایل `.env` بسازید (از روی `.env.example`):

```bash
cp .env.example .env
```

و مقادیر را پر کنید:

```env
BOT_TOKEN=123456789:ABCdef...        # توکن ربات از @BotFather
GOOGLE_EMAIL=you@gmail.com
GOOGLE_AAS_TOKEN=ya29.xxxxx           # از مرحله قبل
ANDROID_DEVICE_CODENAME=hero2lte
ALLOWED_USER_IDS=11111111,22222222    # شناسه تلگرام کاربران مجاز (اختیاری)
```

> برای پیدا کردن Telegram User ID خود، به ربات [@userinfobot](https://t.me/userinfobot) پیام بدهید.

### ۴) اجرا

#### اجرای محلی

```bash
python bot.py
# یا
./start.sh
```

#### اجرا با Docker

```bash
docker build -t telegram-apk-bot .
docker run -d --env-file .env --name apk-bot telegram-apk-bot
```

#### استقرار روی Render.com

1. پروژه را به GitHub پوش کنید
2. در Render: **New → Blueprint → انتخاب ریپو**
3. Render فایل `render.yaml` را شناسایی می‌کند
4. متغیرهای محیطی (`BOT_TOKEN`, `GOOGLE_EMAIL`, `GOOGLE_AAS_TOKEN`, ...) را در پنل Render وارد کنید
5. Deploy کنید

#### استقرار روی VPS (با systemd)

```bash
# کپی پروژه به سرور
scp -r telegram-apk-bot/ user@vps:/opt/

# روی سرور:
cd /opt/telegram-apk-bot
pip install -r requirements.txt

# ساخت سرویس systemd
sudo tee /etc/systemd/system/apk-bot.service > /dev/null <<'EOF'
[Unit]
Description=Telegram APK Bot
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

1. در تلگرام ربات خود را استارت کنید: `/start`
2. یکی از کارهای زیر را انجام دهید:
   - یک لینک گوگل‌پلی بفرستید:
     ```
     https://play.google.com/store/apps/details?id=com.whatsapp
     ```
   - فقط نام پکیج را بفرستید:
     ```
     com.whatsapp
     ```
   - جستجو کنید:
     ```
     /search telegram
     ```
3. ربات اطلاعات برنامه را همراه با **دکمه‌های شیشه‌ای** برای هر معماری نمایش می‌دهد
4. روی دکمه مورد نظر ضربه بزنید → ربات APK را دانلود و ارسال می‌کند

## 🔧 نکات فنی

### چرا به AAS Token نیاز داریم؟

گوگل‌پلی API عمومی ندارد. کتابخانه `gpapi` با شبیه‌سازی یک دستگاه اندرویدی واقعی، مستقیماً با سرورهای Google Play صحبت می‌کند. این کار نیاز به یک حساب گوگل و توکن احراز هویت دارد.

### تفاوت APK و Split APK

برنامه‌های جدید گوگل‌پلی معمولاً به صورت **App Bundle** منتشر می‌شوند که شامل:
- یک APK اصلی (base)
- چندین APK مجزا برای معماری‌های مختلف (`config.arm64_v8a`, `config.x86_64`, ...)

ربات هر کدام را به صورت جداگانه در دکمه‌های شیشه‌ای نمایش می‌دهد و کاربر می‌تواند همان را انتخاب کند. اگر فقط یک APK پایه وجود داشته باشد، گزینه «Universal» نمایش داده می‌شود.

### محدودیت‌ها

- حجم فایل APK نباید از **۲ گیگابایت** (حد تلگرام برای ربات‌ها) بیشتر باشد
- برای برنامه‌های پولی باید حساب گوگل شما آن برنامه را خریده باشد
- برای برنامه‌های منطقه‌ای ممکن است نیاز باشد `device_codename` یا `locale` را تغییر دهید
- گوگل ممکن است بعد از تعداد زیادی درخواست، موقتاً اکانت را محدود کند

### تنظیم `device_codename`

کدنیم دستگاهی که gpapi خود را به جای آن جا می‌زند. انتخاب‌های امن:

| کدنیم | دستگاه |
|---|---|
| `hero2lte` | Galaxy S7 Edge |
| `walleye` | Pixel 2 |
| `cheetsuntrusted` | Chromebook |
| `bacon` | OnePlus One |

## 🛠 رفع اشکال

| مشکل | راه‌حل |
|---|---|
| `Login failed` | App Password را دوباره بسازید |
| `403 Forbidden` | `device_codename` را عوض کنید |
| `Empty results` | اکانت گوگل را با مرورگر باز کنید و دوباره تلاش کنید |
| فایل دانلود نمی‌شود | نسخه/پکیج را چک کنید؛ برنامه ممکن است برای منطقه شما در دسترس نباشد |
| `callback_data too long` | نام پکیج خیلی بلند است؛ ربات خودکار آن را کوتاه می‌کند |

## 📜 مجوز

MIT License — استفاده آزاد. مسئول использования на свой риск.

## ⚠️ هشدار

این پروژه صرفاً برای اهداف آموزشی و راحتی شخصی است. دانلود خودکار APK از Google Play ممکن است **خلاف ToS گوگل** باشد. از اکانت گوگل اصلی خود استفاده نکنید و یک اکانت disposable بسازید. نویسنده هیچ مسئولیتی در قبال مسدود شدن اکانت گوگل شما ندارد.
