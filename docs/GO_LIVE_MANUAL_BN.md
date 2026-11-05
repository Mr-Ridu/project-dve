# সাইট লাইভ করার ম্যানুয়াল (cPanel — SSH ছাড়া)

এই ম্যানুয়ালটা এমন একজনের জন্য যিনি cPanel চালাতে পারেন, কিন্তু SSH বা coding জানেন না। সব কাজ cPanel-এর বাটনে হবে।

**আগে জেনে নিন:** হোস্টিংয়ে Python **3.10 বা তার বেশি** (3.12 সবচেয়ে ভালো) এবং SSL (https) আছে কি না। না থাকলে হোস্টিং সাপোর্টকে বলুন। ডাটাবেস হিসেবে **SQLite3** ডিফল্ট — আলাদা ডাটাবেস বানাতে হবে না। পরে চাইলে MySQL-এ নেওয়া যাবে (ধাপ ৪)।

---

## ধাপ ১ — কোডের জিপ বানান (নিজের কম্পিউটারে)

1. প্রজেক্ট ফোল্ডারে ঢুকুন।
2. `static/css/app.css` ফাইলটা আছে কি না দেখুন। না থাকলে ডেভেলপারকে `npm run build:css` চালাতে বলুন।
3. এই ফোল্ডার/ফাইলগুলো **বাদ দিয়ে** বাকি সব সিলেক্ট করুন:

   `.venv`, `node_modules`, `.git`, `db.sqlite3`, `.env`, `staticfiles`, `media`, `__pycache__`

4. সিলেক্ট করা ফাইলগুলোতে right-click → **Send to → Compressed (zipped) folder**। নাম দিন `site.zip`।

> `cpanel_setup.py`, `manage.py`, `passenger_wsgi.py`, `templates`, `static` — এগুলো জিপে অবশ্যই থাকবে।

---

## ধাপ ২ — cPanel-এ Python Application তৈরি

cPanel → **Software** → **Setup Python App** → **Create Application**

| ঘর | যা দিতে হবে |
|---|---|
| Python version | `3.12` (না থাকলে 3.10–3.13-এর মধ্যে highest) |
| Application root | `apps/tmt` |
| Application URL | আপনার ডোমেইন (যেমন `example.com`) |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

**Create** চাপুন। cPanel নিজে একটা ফোল্ডার ও virtualenv বানাবে।

---

## ধাপ ৩ — কোড আপলোড

1. cPanel → **File Manager** → `/home/YOUR-CPANEL-USER/apps/tmt` ফোল্ডারে যান।
2. **Upload** → `site.zip` আপলোড করুন।
3. জিপটার উপর right-click → **Extract**।
4. নিশ্চিত করুন `manage.py`, `cpanel_setup.py`, `passenger_wsgi.py` সরাসরি `apps/tmt`-এর ভেতরে আছে (আরেকটা ফোল্ডারের ভেতরে নয়)।
5. cPanel নিজের একটা `passenger_wsgi.py` বানিয়ে থাকলে আমাদের ফাইলটা দিয়ে **Overwrite** করুন।

> কোড কখনো `public_html`-এর ভেতরে রাখবেন না।
>
> `public_html`-এ আগের সাইটের `static` ফোল্ডার থাকলে তার নাম বদলে রাখুন (যেমন `static-old`)। না হলে নতুন CSS/ছবি পুরোনো ফাইলের সাথে মিশে যাবে।

---

## ধাপ ৪ — ডাটাবেস (এখন SQLite3)

এই সাইট এখন **SQLite3** দিয়ে চলবে। cPanel-এ কোনো ডাটাবেস বা ডাটাবেস ইউজার বানাতে হবে না, কোনো পাসওয়ার্ডও লাগবে না।

- ডেটা থাকবে: `/home/cpuser/apps/tmt/db.sqlite3`
- ফাইলটা `public_html`-এর বাইরে, তাই ওয়েব থেকে কেউ খুলতে পারবে না।
- সেটআপ স্ক্রিপ্ট নিজেই ফাইলটা বানায় ও সব টেবিল তৈরি করে।
- `.env`-এ `DB_ENGINE=sqlite` লিখুন; ডাটাবেসের আর কিছু লাগবে না।

### পরে MySQL-এ নিতে চাইলে (অপশন)

MySQL-এর সাপোর্ট কোডে আছে। কিন্তু SQLite-তে আসল ডেটা (ইউজার/টিউটোরিয়াল) জমার পরে MySQL-এ নিলে ডেটা কপি করতে হয় — সেটা ডেভেলপারের কাজ। তাই যদি শুরুতেই MySQL চান, সেটআপের **আগে** এটা করুন:

1. cPanel → **Databases** → **MySQL Databases**
2. **Create New Database** → `tmt`; **Add New User** → `tmt` + শক্ত পাসওয়ার্ড; **Add User To Database** → **ALL PRIVILEGES**
3. Character set **utf8mb4** রাখুন (না হলে হোস্টিং সাপোর্টকে বলুন)
4. `.env`-এ `DB_ENGINE=sqlite`-এর বদলে যোগ করুন:

```env
DB_ENGINE=mysql
DB_NAME=cpuser_tmt
DB_USER=cpuser_tmt
DB_PASSWORD=এখানে-ডাটাবেস-পাসওয়ার্ড
DB_HOST=localhost
DB_PORT=3306
```

5. `cpanel_setup.py` Run করুন।

---

## ধাপ ৫ — `.env` ফাইল

File Manager → `apps/tmt` → **+ File** → নাম `.env` → **Create** → right-click → **Edit**।

নিচের লেখাটা বসিয়ে নিজের তথ্য দিন:

```env
DJANGO_SECRET_KEY=
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DB_ENGINE=sqlite
DJANGO_STATIC_ROOT=/home/cpuser/public_html/static
DJANGO_MEDIA_ROOT=/home/cpuser/public_html/media
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=আপনার-ইমেইল
DJANGO_SUPERUSER_PASSWORD=একটা-শক্ত-পাসওয়ার্ড
```

**অবশ্যই বদলান:** `example.com`, `cpuser`, ইমেইল, অ্যাডমিন পাসওয়ার্ড।

- `DB_ENGINE=sqlite` মানে ডাটাবেস ফাইল `apps/tmt/db.sqlite3`-এ থাকবে। আলাদা কিছু লাগবে না; চাইলে `DJANGO_DB_PATH` দিয়ে ফাইলের জায়গা বদলানো যায়।
- `DJANGO_SECRET_KEY` খালি রাখলে সেটআপ স্ক্রিপ্ট নিজে একটা বানিয়ে `.env`-এ লিখে দেবে।
- `.env` কখনো `public_html`-এ রাখবেন না, কারো সাথে শেয়ার করবেন না।
- ফাইলটার permission থাকলে **600** করুন (right-click → Change Permissions)।

---

## ধাপ ৬ — এক ক্লিকে বাকি সব

cPanel → **Setup Python App** → আপনার অ্যাপের ডান পাশে → **Run Python script**

লিখুন:

```
cpanel_setup.py
```

(পুরো path চাইলে: `/home/cpuser/apps/tmt/cpanel_setup.py`)

**Run** চাপুন। স্ক্রিপ্টটা নিজে থেকে:

1. Python প্যাকেজ ইনস্টল করে
2. ডাটাবেস টেবিল তৈরি/আপডেট করে (`migrate`) — SQLite হলে `db.sqlite3` নিজেই বানায়
3. ক্যাশ টেবিল বানায়
4. CSS/ছবি `public_html/static`-এ কপি করে (`collectstatic`)
5. আপনার অ্যাডমিন অ্যাকাউন্ট বানায়
6. অ্যাপ restart করে

শেষে **DONE** দেখবেন।

### Run Python script না থাকলে

cPanel → **Terminal** (এটা ব্রাউজারের টার্মিনাল, SSH নয়):

```bash
source /home/cpuser/virtualenv/apps/tmt/3.12/bin/activate
python /home/cpuser/apps/tmt/cpanel_setup.py
```

Terminal-ও না থাকলে হোস্টিং সাপোর্টকে বলুন এই কমান্ডটা একবার চালাতে:

```bash
/home/cpuser/virtualenv/apps/tmt/3.12/bin/python /home/cpuser/apps/tmt/cpanel_setup.py
```

> `3.12` এর জায়গায় আপনার Python version folder-এর নাম দিন।

---

## ধাপ ৭ — প্রথম পরীক্ষা

| কী খুলবেন | কী দেখা উচিত |
|---|---|
| `https://example.com/` | নতুন হোমপেজ, ইন্ডাস্ট্রিয়াল ছবি |
| `https://example.com/products/` | পাঁচ সেক্টরের পেজ |
| `https://example.com/tutorials/` | টিউটোরিয়াল লাইব্রেরি |
| `https://example.com/admin/` | অ্যাডমিন লগইন |
| `https://example.com/static/css/app.css` | CSS ফাইল খোলে |

তারপর:

1. `/accounts/register/` দিয়ে একটা টেস্ট অ্যাকাউন্ট খুলুন।
2. `/dashboard/` → **Users** → অ্যাকাউন্টটা **Approve** করুন।
3. ওই অ্যাকাউন্টে লগইন করে `/tutorials/` দেখুন।

> **লগইন কাজ না করলে:** প্রোডাকশনে cookie Secure থাকে, তাই **https** ছাড়া লগইন হবে না। আগে ধাপ ৮ করুন।

---

## ধাপ ৮ — HTTPS চালু

1. cPanel → **Security** → **SSL/TLS Status** → **Run AutoSSL**
2. `https://example.com/` খুলে তালা (🔒) দেখুন।
3. HTTPS ঠিক হওয়ার **পরে** চাইলে `.env`-এ যোগ করুন:

```env
DJANGO_HSTS_SECONDS=31536000
```

তারপর `cpanel_setup.py` আবার চালান। HTTPS ঠিক হওয়ার আগে HSTS দেবেন না।

---

## ধাপ ৯ — পরে সাইট আপডেট করলে

1. শুধু বদলানো ফাইলগুলো File Manager দিয়ে আপলোড/Overwrite করুন।
2. `cpanel_setup.py` আবার Run করুন (নতুন database change বা CSS থাকলে দরকার)।
3. ব্রাউজারে **Ctrl + F5** দিন।

`.env` বা ডাটাবেস ফাইল (`db.sqlite3`) কখনো আপলোড করবেন না। ব্যাকআপের জন্য ডাউনলোড করবেন।

---

## ধাপ ১০ — সমস্যা হলে

| সমস্যা | কারণ / সমাধান |
|---|---|
| সাইট 500 | `.env`-এ `DJANGO_SECRET_KEY` / `DJANGO_ALLOWED_HOSTS` নেই, বা `apps/tmt` ফোল্ডারে লেখার permission নেই। `.env` ঠিক করে আবার Run করুন। |
| `database is locked` | একসাথে অনেক লেখা হচ্ছে (SQLite)। কিছুক্ষণ পরে চেষ্টা করুন; বারবার হলে MySQL-এ যাওয়া ভালো। |
| ডাটাবেস ফাইল তৈরি হচ্ছে না | File Manager-এ `apps/tmt` ফোল্ডারের permission 755/775 করুন, তারপর আবার Run করুন। |
| সাইট 503 / পুরোনো পেজ | Setup Python App → **Restart**। পুরোনো `public_html/index.html` বা `.htaccess` থাকলে সরান/নাম বদলান। |
| CSS/ছবি আসছে না | `.env`-এ `DJANGO_STATIC_ROOT` ঠিক আছে? `cpanel_setup.py` আবার চালান। |
| লগইন করে আবার লগআউট হয়ে যাচ্ছে | HTTPS নেই। AutoSSL চালু করুন। |
| `Table 'django_cache' doesn't exist` | `cpanel_setup.py` আবার চালান। |
| ভিডিও চলে না | Bunny Stream-এর key সেট নেই, বা tutorial Published নয়। ডেভেলপারকে দেখান। |
| কিছুই ঠিক হচ্ছে না | Setup Python App → **Logs**; ওখানে error-এর শেষ লাইনগুলো ডেভেলপারকে পাঠান। |

---

## ধাপ ১১ — ব্যাকআপ

মাসে অন্তত একবার:

1. cPanel → **Files** → **Backup Wizard** → **Backup**
2. **Home Directory** ডাউনলোড করুন।
3. File Manager → `apps/tmt` → `db.sqlite3` ডাউনলোড করুন (সাইটে কম কাজ চলার সময়)।
4. `.env` ফাইলটা আলাদা নিরাপদ জায়গায় রাখুন।

MySQL ব্যবহার করলে: **phpMyAdmin** → আপনার ডাটাবেস → **Export** → Go।

Backup Wizard না থাকলে: File Manager দিয়ে `public_html` ও `apps/tmt` ফোল্ডার ডাউনলোড করুন।

ফাইলগুলো নিজের কম্পিউটারে/Google Drive-এ রাখুন। শুধু হোস্টিংয়ের ব্যাকআপের উপর ভরসা করবেন না।

---

## প্রথম দিনের চেকলিস্ট

- [ ] Python app তৈরি
- [ ] কোড আপলোড
- [ ] ডাটাবেস: SQLite3 (কিছু করতে হবে না; চাইলে MySQL)
- [ ] `.env` তৈরি
- [ ] `cpanel_setup.py` Run → DONE
- [ ] হোম, Products, Tutorials, Admin খোলা
- [ ] AutoSSL → HTTPS
- [ ] টেস্ট অ্যাকাউন্ট → Approve → Tutorial দেখা
- [ ] Home Directory + `db.sqlite3` + `.env` ব্যাকআপ
- [ ] `.env` থেকে `DJANGO_SUPERUSER_PASSWORD` লাইনটা মুছে ফেলা (পাসওয়ার্ড আলাদা জায়গায় লিখে রাখুন)
