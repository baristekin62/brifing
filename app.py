"""ÖZEN GROSS Brifing Yönetim Paneli — Flask Web Uygulaması

D:\\BRIFING içindeki tüm brifing yapılandırmasını yönetir:
  - Sorgular: ekle, düzenle, sil, aç/kapat, sırala
  - SMTP profilleri
  - ERP bağlantısı
  - Alıcılar / rapor başlığı
  - Brifingi çalıştır + önizle

Çalıştırma:  python app.py
"""

import base64
import json
import os
import re
import subprocess
import sys
from functools import wraps
from pathlib import Path

import pyodbc
from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for

import run_briefing as rb

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
META_FILE = BASE_DIR / "queries_meta.json"
QUERIES_DIR = BASE_DIR / "queries"
OUTPUT_DIR = BASE_DIR / "output"

app = Flask(__name__)
app.secret_key = "OZEN-BRIFING-SECRET-KEY-CHANGE-ME"


@app.template_filter("datetime_tr")
def datetime_tr(ts):
    from datetime import datetime
    try:
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(ts)


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    return {"queries": []}


def save_manifest(meta: dict) -> None:
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_kpis(request) -> list:
    """Formdan KPI listesini okur: kpi_label[], kpi_column[], kpi_row[]. Boş olanları atlar."""
    labels = request.form.getlist("kpi_label")
    columns = request.form.getlist("kpi_column")
    rows = request.form.getlist("kpi_row")
    kpis = []
    for i, label in enumerate(labels):
        label = (label or "").strip()
        col = (columns[i] if i < len(columns) else "").strip()
        if not label or not col:
            continue
        try:
            row = int(rows[i]) if i < len(rows) and rows[i].strip() else 0
        except ValueError:
            row = 0
        kpis.append({"label": label, "column": col, "row": row})
    return kpis


def _parse_summary(request) -> dict:
    """Formdan günlük özet yapılandırmasını okur. Boşsa {} döner.

    Alanlar: summary_totals (virgüllü kolon adları), summary_ratio_num,
    summary_ratio_den, summary_ratio_label, summary_delta (on/off).
    """
    totals = [c.strip() for c in request.form.get("summary_totals", "").split(",") if c.strip()]
    ratio_num = request.form.get("summary_ratio_num", "").strip()
    ratio_den = request.form.get("summary_ratio_den", "").strip()
    ratio_label = request.form.get("summary_ratio_label", "").strip()
    delta = request.form.get("summary_delta") == "on"

    scfg = {}
    if totals:
        scfg["totals"] = totals
    if ratio_num and ratio_den:
        scfg["ratio_num"] = ratio_num
        scfg["ratio_den"] = ratio_den
        if ratio_label:
            scfg["ratio_label"] = ratio_label
    if delta:
        scfg["delta"] = True
    return scfg


_WEEK_DAYS = ("PZT", "SAL", "ÇAR", "PER", "CUM", "CMT", "PAZ")
_ENG_DAYS = {"PZT": "MON", "SAL": "TUE", "ÇAR": "WED", "PER": "THU", "CUM": "FRI", "CMT": "SAT", "PAZ": "SUN"}


def _parse_week_days(raw: str) -> list:
    """'PZT,ÇAR' veya 'MON,WED' gibi değerleri ENG gün kodlarına çevirir."""
    out = []
    for part in (raw or "").replace(";", ",").split(","):
        p = part.strip().upper()
        if not p:
            continue
        if p in _ENG_DAYS:
            out.append(_ENG_DAYS[p])
        elif p in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"):
            out.append(p)
    return out


def _parse_month_day(raw) -> int:
    try:
        return max(1, min(31, int(raw or 1)))
    except (TypeError, ValueError):
        return 1


def _decode_secret(value: str) -> str:
    if not value:
        return ""
    if isinstance(value, str) and value.startswith("ENV:"):
        return rb._resolve_secret(value[4:].strip())
    if isinstance(value, str) and value.startswith("ENC:"):
        try:
            return base64.b64decode(value[4:].encode("utf-8")).decode("utf-8")
        except Exception:
            return value
    return value


def _encode_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("ENC:"):
        return value
    return "ENC:" + base64.b64encode(value.encode("utf-8")).decode("utf-8")


# ─── Güvenlik ─────────────────────────────────────────────────────────────

# Master şifre (19811203) — SHA-256 hash olarak koda gömülüdür.
# Kullanıcı adı config.json'daki admin_username'dir; şifre bu hash ile doğrulanır.
MASTER_PASSWORD_HASH = "38e73cc04c39de52ecec6135ffd1e8578cebe3c92e6e24b888863d2581de7e92"


def _check_master(password: str) -> bool:
    import hashlib
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest() == MASTER_PASSWORD_HASH


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = load_config()
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == cfg.get("admin_username", "admin") and _check_master(p):
            session["admin_logged_in"] = True
            return redirect(url_for("index"))
        flash("Kullanıcı adı veya şifre hatalı!", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Ana sayfa ────────────────────────────────────────────────────────────


@app.route("/")
@login_required
def index():
    cfg = load_config()
    meta = load_manifest()
    queries = meta.get("queries", [])
    active_count = sum(1 for q in queries if q.get("enabled", True))

    reports = []
    if OUTPUT_DIR.exists():
        html_files = sorted(OUTPUT_DIR.glob("brifing_*.html"), reverse=True)[:10]
        for f in html_files:
            excel = OUTPUT_DIR / (f.stem + ".xlsx")
            reports.append({
                "file": f.name,
                "excel": excel.name if excel.exists() else None,
                "time": f.stat().st_mtime,
            })

    return render_template(
        "index.html",
        cfg=cfg,
        queries=queries,
        active_count=active_count,
        reports=reports,
    )


# ─── Sorgu yönetimi ───────────────────────────────────────────────────────


@app.route("/queries")
@login_required
def queries_list():
    meta = load_manifest()
    queries = sorted(meta.get("queries", []), key=lambda q: (q.get("order", 999), q.get("file", "")))
    return render_template("queries.html", queries=queries)


@app.route("/queries/new", methods=["GET", "POST"])
@login_required
def query_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        sql = request.form.get("sql", "").strip()
        filename = request.form.get("filename", "").strip()

        if not title or not sql:
            flash("Başlık ve SQL zorunludur.", "danger")
            return render_template("query_edit.html", q=None, is_new=True)

        if not filename:
            filename = re.sub(r"[^\w]", "_", title.lower()).strip("_") + ".sql"
        if not filename.endswith(".sql"):
            filename += ".sql"
        # Başa numara ekle
        filename = re.sub(r"^\d+_", "", filename)

        meta = load_manifest()
        existing_orders = [q.get("order", 0) for q in meta.get("queries", [])]
        next_order = (max(existing_orders, default=0) + 1)

        fpath = QUERIES_DIR / filename
        if fpath.exists():
            # çakışan ad varsa sayı ekle
            i = 2
            while fpath.exists():
                fpath = QUERIES_DIR / f"{Path(filename).stem}_{i}.sql"
                i += 1

        fpath.write_text(sql, encoding="utf-8")
        meta.setdefault("queries", []).append({
            "file": fpath.name,
            "title": title,
            "enabled": request.form.get("enabled") == "on",
            "order": next_order,
            "kpis": _parse_kpis(request),
            "summary": _parse_summary(request),
        })
        save_manifest(meta)
        flash(f"'{title}' sorgusu eklendi.", "success")
        return redirect(url_for("queries_list"))
    return render_template("query_edit.html", q=None, is_new=True)


@app.route("/queries/edit/<filename>", methods=["GET", "POST"])
@login_required
def query_edit(filename):
    meta = load_manifest()
    entry = next((q for q in meta.get("queries", []) if q.get("file") == filename), None)
    if not entry:
        flash("Sorgu bulunamadı.", "danger")
        return redirect(url_for("queries_list"))

    fpath = QUERIES_DIR / filename
    sql = fpath.read_text(encoding="utf-8") if fpath.exists() else ""

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        sql = request.form.get("sql", "").strip()
        if not title or not sql:
            flash("Başlık ve SQL zorunludur.", "danger")
            return render_template("query_edit.html", q=entry, sql=sql, is_new=False)

        entry["title"] = title
        entry["enabled"] = request.form.get("enabled") == "on"
        entry["order"] = int(request.form.get("order", entry.get("order", 1)))
        entry["kpis"] = _parse_kpis(request)
        entry["summary"] = _parse_summary(request)
        fpath.write_text(sql, encoding="utf-8")
        save_manifest(meta)
        flash(f"'{title}' güncellendi.", "success")
        return redirect(url_for("queries_list"))

    return render_template("query_edit.html", q=entry, sql=sql, is_new=False)


@app.route("/queries/test", methods=["POST"])
@login_required
def query_test():
    """Panelden tek sorguyu ERP'de çalıştırıp sonucu JSON olarak döndürür."""
    sql = request.form.get("sql", "").strip()
    if not sql:
        return jsonify({"ok": False, "error": "SQL boş."})
    try:
        cfg = load_config()
        erp_profile = rb.get_active_erp_profile(cfg)
        conn_str = rb.build_erp_conn_str(erp_profile)
        conn = pyodbc.connect(conn_str, timeout=30)
        conn.timeout = 30
        try:
            res = rb.run_sql_query(conn, sql, timeout_sec=60)
            rows = []
            for r in res.get("rows", [])[:50]:
                rows.append([rb.value_to_str(v) for v in r])
            return jsonify({
                "ok": True,
                "success": res.get("success", True),
                "error": res.get("error"),
                "columns": res.get("columns", []),
                "rows": rows,
                "row_count": res.get("row_count", 0),
                "duration_ms": res.get("duration_ms", 0),
            })
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/queries/delete/<filename>", methods=["POST"])
@login_required
def query_delete(filename):
    meta = load_manifest()
    meta["queries"] = [q for q in meta.get("queries", []) if q.get("file") != filename]
    save_manifest(meta)
    fpath = QUERIES_DIR / filename
    if fpath.exists():
        try:
            fpath.unlink()
        except Exception:
            pass
    flash("Sorgu silindi.", "success")
    return redirect(url_for("queries_list"))


@app.route("/queries/toggle/<filename>", methods=["POST"])
@login_required
def query_toggle(filename):
    meta = load_manifest()
    for q in meta.get("queries", []):
        if q.get("file") == filename:
            q["enabled"] = not q.get("enabled", True)
    save_manifest(meta)
    return redirect(url_for("queries_list"))


@app.route("/queries/move/<filename>/<direction>", methods=["POST"])
@login_required
def query_move(filename, direction):
    meta = load_manifest()
    queries = sorted(meta.get("queries", []), key=lambda q: (q.get("order", 999), q.get("file", "")))
    idx = next((i for i, q in enumerate(queries) if q.get("file") == filename), None)
    if idx is None:
        return redirect(url_for("queries_list"))
    other = idx - 1 if direction == "up" else idx + 1
    if 0 <= other < len(queries):
        queries[idx]["order"], queries[other]["order"] = queries[other]["order"], queries[idx]["order"]
        save_manifest({"queries": queries})
    return redirect(url_for("queries_list"))


# ─── SMTP yönetimi ────────────────────────────────────────────────────────


@app.route("/smtp")
@login_required
def smtp_list():
    cfg = load_config()
    source = rb._resolve_path(BASE_DIR, cfg.get("smtp_profiles_source", ""))
    data = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"profiles": []}
    return render_template("smtp.html", profiles=data.get("profiles", []), source=str(source))


@app.route("/smtp/edit/<pid>", methods=["GET", "POST"])
@login_required
def smtp_edit(pid):
    cfg = load_config()
    source = rb._resolve_path(BASE_DIR, cfg.get("smtp_profiles_source", ""))
    data = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"profiles": []}
    prof = next((p for p in data["profiles"] if p.get("id") == pid), None)
    if not prof:
        flash("SMTP profili bulunamadı.", "danger")
        return redirect(url_for("smtp_list"))

    if request.method == "POST":
        new_pass = request.form.get("password", "")
        if new_pass:
            prof["password_enc"] = _encode_secret(new_pass)
        prof["name"] = request.form.get("name", prof.get("name", ""))
        prof["host"] = request.form.get("host", "")
        prof["port"] = int(request.form.get("port", 587))
        prof["use_ssl"] = request.form.get("use_ssl") == "on"
        prof["use_tls"] = request.form.get("use_tls") == "on"
        prof["use_auth"] = request.form.get("use_auth") == "on"
        prof["username"] = request.form.get("username", "")
        prof["from_address"] = request.form.get("from_address", "")
        prof["display_name"] = request.form.get("display_name", "")
        prof["reply_to"] = request.form.get("reply_to", "")
        prof["timeout_sec"] = int(request.form.get("timeout_sec", 15))
        prof["is_default"] = request.form.get("is_default") == "on"
        source.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        flash("SMTP profili güncellendi.", "success")
        return redirect(url_for("smtp_list"))

    prof["decoded_password"] = _decode_secret(prof.get("password_enc", ""))
    return render_template("smtp_edit.html", prof=prof)


@app.route("/smtp/test/<pid>", methods=["POST"])
@login_required
def smtp_test(pid):
    cfg = load_config()
    source = rb._resolve_path(BASE_DIR, cfg.get("smtp_profiles_source", ""))
    data = json.loads(source.read_text(encoding="utf-8"))
    prof = next((p for p in data["profiles"] if p.get("id") == pid), None)
    if not prof:
        return jsonify({"success": False, "error": "Profil bulunamadı"})
    result = rb.send_email_via_smtp  # placeholder değil, gerçek test aşağıda
    import smtplib
    try:
        server = rb.smtp_connect(prof)
        server.quit()
        return jsonify({"success": True, "message": "SMTP bağlantısı başarılı"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── ERP yönetimi ─────────────────────────────────────────────────────────


@app.route("/erp")
@login_required
def erp_list():
    cfg = load_config()
    source = rb._resolve_path(BASE_DIR, cfg.get("erp_connection_source", ""))
    data = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"profiles": []}
    return render_template("erp.html", profiles=data.get("profiles", []), active_id=data.get("active_profile_id"), source=str(source))


@app.route("/erp/edit/<pid>", methods=["GET", "POST"])
@login_required
def erp_edit(pid):
    cfg = load_config()
    source = rb._resolve_path(BASE_DIR, cfg.get("erp_connection_source", ""))
    data = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"profiles": []}
    prof = next((p for p in data["profiles"] if p.get("profile_id") == pid), None)
    if not prof:
        flash("ERP profili bulunamadı.", "danger")
        return redirect(url_for("erp_list"))

    if request.method == "POST":
        new_pass = request.form.get("password", "")
        if new_pass:
            prof["password_encrypted"] = new_pass
        prof["profile_name"] = request.form.get("profile_name", prof.get("profile_name", ""))
        prof["server"] = request.form.get("server", "")
        prof["database"] = request.form.get("database", "")
        prof["username"] = request.form.get("username", "")
        prof["driver"] = request.form.get("driver", "ODBC Driver 17 for SQL Server")
        prof["encrypt"] = request.form.get("encrypt") == "on"
        prof["trust_server_certificate"] = request.form.get("trust_server_certificate") == "on"
        prof["is_active"] = request.form.get("is_active") == "on"
        if request.form.get("make_active") == "on":
            data["active_profile_id"] = pid
            for p in data["profiles"]:
                p["is_active"] = (p["profile_id"] == pid)
        source.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        flash("ERP profili güncellendi.", "success")
        return redirect(url_for("erp_list"))

    return render_template("erp_edit.html", prof=prof)


@app.route("/erp/test/<pid>", methods=["POST"])
@login_required
def erp_test(pid):
    cfg = load_config()
    source = rb._resolve_path(BASE_DIR, cfg.get("erp_connection_source", ""))
    data = json.loads(source.read_text(encoding="utf-8"))
    prof = next((p for p in data["profiles"] if p.get("profile_id") == pid), None)
    if not prof:
        return jsonify({"success": False, "error": "Profil bulunamadı"})
    try:
        conn = rb.pyodbc.connect(rb.build_erp_conn_str(prof))
        cur = conn.cursor()
        cur.execute("SELECT DB_NAME()")
        db = cur.fetchone()[0]
        conn.close()
        return jsonify({"success": True, "message": f"ERP bağlantısı başarılı ({db})"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── Genel ayarlar ────────────────────────────────────────────────────────


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    cfg = load_config()
    if request.method == "POST":
        cfg["recipients"] = {
            "to": [x.strip() for x in request.form.get("to", "").replace(";", ",").split(",") if x.strip()],
            "cc": [x.strip() for x in request.form.get("cc", "").replace(";", ",").split(",") if x.strip()],
            "bcc": [x.strip() for x in request.form.get("bcc", "").replace(";", ",").split(",") if x.strip()],
        }
        cfg["subject_template"] = request.form.get("subject_template", cfg.get("subject_template", ""))
        cfg["report_title"] = request.form.get("report_title", cfg.get("report_title", ""))
        cfg["send_email"] = request.form.get("send_email") == "on"
        cfg["save_output"] = request.form.get("save_output") == "on"
        cfg["send_time"] = request.form.get("send_time", cfg.get("send_time", "08:00"))
        cfg["send_time_enabled"] = request.form.get("send_time_enabled") == "on"
        # İçgörü ayarları
        ins = cfg.setdefault("insights", {})
        ins["enabled"] = request.form.get("insights_enabled") == "on"
        ins["save_history"] = request.form.get("insights_save_history") == "on"
        try:
            ins["anomaly_threshold_pct"] = float(request.form.get("anomaly_threshold_pct", 20))
        except (TypeError, ValueError):
            ins["anomaly_threshold_pct"] = 20
        try:
            ins["anomaly_days_back"] = max(3, int(request.form.get("anomaly_days_back", 7)))
        except (TypeError, ValueError):
            ins["anomaly_days_back"] = 7
        # Güvenlik
        new_user = request.form.get("admin_username", "").strip()
        if new_user:
            cfg["admin_username"] = new_user
        save_config(cfg)
        flash("Ayarlar kaydedildi.", "success")
        return redirect(url_for("settings"))

    schedule_info = get_schedule_info()
    installed_tasks = {t["profile_id"]: t for t in schedule_info.get("tasks", []) if t.get("profile_id") is not None}
    profile_data = load_profiles()
    return render_template("settings.html", cfg=cfg, schedule=schedule_info,
                           profiles=profile_data.get("profiles", []), installed_tasks=installed_tasks)


@app.route("/profile/<pid>/time", methods=["POST"])
@login_required
def profile_save_time(pid):
    data = load_profiles()
    prof = next((p for p in data["profiles"] if p.get("id") == pid), None)
    if not prof:
        flash("Profil bulunamadı.", "danger")
        return redirect(url_for("settings"))
    new_time = request.form.get("send_time", "")
    if ":" in new_time:
        prof["send_time"] = new_time
        freq = request.form.get("schedule_frequency", "daily").lower()
        if freq not in ("daily", "weekly", "monthly"):
            freq = "daily"
        prof["schedule_frequency"] = freq
        if freq == "weekly":
            prof["schedule_week_days"] = _parse_week_days(request.form.get("schedule_week_days", "")) or ["MON"]
            prof.pop("schedule_month_day", None)
        elif freq == "monthly":
            try:
                prof["schedule_month_day"] = max(1, min(31, int(request.form.get("schedule_month_day", 1))))
            except ValueError:
                prof["schedule_month_day"] = 1
            prof.pop("schedule_week_days", None)
        else:
            prof.pop("schedule_week_days", None)
            prof.pop("schedule_month_day", None)
        save_profiles(data)
        periyot = {"daily": "her gün", "weekly": "haftalık", "monthly": "aylık"}.get(freq, "her gün")
        flash(f"'{prof['name']}' gönderim saati güncellendi ({periyot} · {new_time}). Görevi yeniden kurun.", "success")
    else:
        flash("Geçersiz saat.", "danger")
    return redirect(url_for("settings"))


@app.route("/schedule/install", methods=["POST"])
@login_required
def schedule_install():
    cfg = load_config()
    result = install_schedule(cfg)
    if result.get("success"):
        flash(result.get("message", "Zamanlama kuruldu."), "success")
    else:
        flash(result.get("error", "Zamanlama kurulamadı."), "danger")
    return redirect(url_for("settings"))


@app.route("/schedule/uninstall", methods=["POST"])
@login_required
def schedule_uninstall():
    result = uninstall_schedule()
    if result.get("success"):
        flash(result.get("message", "Zamanlama kaldırıldı."), "success")
    else:
        flash(result.get("error"), "danger")
    return redirect(url_for("settings"))


@app.route("/schedule/install/<pid>", methods=["POST"])
@login_required
def schedule_install_profile(pid):
    data = load_profiles()
    prof = next((p for p in data["profiles"] if p.get("id") == pid), None)
    if not prof:
        flash("Profil bulunamadı.", "danger")
        return redirect(url_for("settings"))
    result = install_one_profile(prof)
    if result.get("success"):
        flash(result.get("message"), "success")
    else:
        flash(result.get("error"), "danger")
    return redirect(url_for("settings"))


@app.route("/schedule/uninstall/<pid>", methods=["POST"])
@login_required
def schedule_uninstall_profile(pid):
    result = uninstall_one_profile(pid)
    if result.get("success"):
        flash(result.get("message"), "success")
    else:
        flash(result.get("error"), "danger")
    return redirect(url_for("settings"))


# ─── Zamanlama (Windows Görev Zamanlayıcı) ────────────────────────────────

TASK_PREFIX = "OZEN_Gunluk_Brifing"


def _task_name(profile_id: str = None) -> str:
    if profile_id:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", profile_id)
        return f"{TASK_PREFIX}_{safe}"
    return TASK_PREFIX


def _task_profile_id(task_name: str) -> str:
    """Görev adından profil ID'sini çıkarır; genel görevse None."""
    task_name = task_name.lstrip("\\")
    if task_name == TASK_PREFIX:
        return None
    prefix = TASK_PREFIX + "_"
    if task_name.startswith(prefix):
        return task_name[len(prefix):]
    return None


def get_schedule_info() -> dict:
    """Görev zamanlayıcıda mevcut kayıtları adı + saatiyle listeler."""
    import csv as _csv
    from io import StringIO

    tasks = []
    try:
        out = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        rows = list(_csv.reader(StringIO(out.stdout)))
        for row in rows:
            if not row:
                continue
            name = row[0]
            if TASK_PREFIX not in name:
                continue
            task_time = ""
            if len(row) > 1:
                m = re.search(r"(\d{2}:\d{2})", row[1])
                task_time = m.group(1) if m else ""
            tasks.append({
                "name": name,
                "profile_id": _task_profile_id(name),
                "time": task_time,
            })
    except Exception:
        pass
    return {"installed": len(tasks) > 0, "tasks": tasks}


def _task_script_path(profile_id: str = None) -> Path:
    if profile_id:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", profile_id)
        return BASE_DIR / f"run_scheduled_{safe}.bat"
    return BASE_DIR / "run_scheduled.bat"


def _ensure_task_script(profile_id: str = None) -> Path:
    bat = _task_script_path(profile_id)
    py = sys.executable
    arg = f' --profile "{profile_id}"' if profile_id else ""
    script = (
        f'@echo off\r\n'
        f'cd /d "{BASE_DIR}"\r\n'
        f'"{py}" "run_briefing.py"{arg}\r\n'
    )
    bat.write_text(script, encoding="ascii")
    return bat


def _schedule_args(prof: dict) -> tuple:
    """Profilden schtasks /SC ... /D ... /ST ... parametrelerini üretir.

    Periyotlar:
      - daily  : her gün (varsayılan)
      - weekly : schedule_week_days (örn. ['MON','WED']) haftanın belirli günleri
      - monthly: schedule_month_day (1-31) ayın belirli günü
    """
    freq = (prof.get("schedule_frequency") or "daily").lower()
    if freq == "weekly":
        days = prof.get("schedule_week_days") or ["MON"]
        day_str = ",".join(days)
        return ["/SC", "WEEKLY", "/D", day_str.upper()]
    if freq == "monthly":
        try:
            md = int(prof.get("schedule_month_day") or 1)
        except (TypeError, ValueError):
            md = 1
        return ["/SC", "MONTHLY", "/D", str(md)]
    return ["/SC", "DAILY"]


def install_one_profile(prof: dict) -> dict:
    """Tek bir profili kendi gönderim saati ve periyoduyla zamanlar."""
    try:
        pid = prof.get("id")
        if not pid:
            return {"success": False, "error": "Profil ID yok."}
        send_time = prof.get("send_time", "08:00")
        if ":" not in send_time:
            send_time = "08:00"
        hour, minute = send_time.split(":")[:2]
        bat = _ensure_task_script(pid)
        cmd = [
            "schtasks", "/Create", "/F", "/TN", _task_name(pid),
            "/TR", str(bat),
        ] + _schedule_args(prof) + [
            "/ST", f"{hour}:{minute}",
            "/RL", "LIMITED",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        if out.returncode == 0 or "already" in out.stderr.lower() or "zaten" in out.stderr.lower():
            periyot = prof.get("schedule_frequency") or "daily"
            return {"success": True, "message": f"'{pid}' için görev kuruldu: {periyot} · {send_time}."}
        return {"success": False, "error": out.stderr.strip() or out.stdout.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uninstall_one_profile(profile_id: str) -> dict:
    """Tek bir profilin görevini kaldırır."""
    try:
        tn = _task_name(profile_id)
        out = subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", tn],
            capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if out.returncode == 0:
            return {"success": True, "message": f"'{profile_id}' görevi kaldırıldı."}
        return {"success": False, "error": out.stderr.strip() or out.stdout.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def install_schedule(cfg: dict) -> dict:
    """Tüm aktif profilleri (veya profil yoksa varsayılanı) zamanlar."""
    try:
        data = load_profiles()
        profiles = [p for p in data.get("profiles", []) if p.get("enabled", True)]
        installed = []

        if profiles:
            for prof in profiles:
                result = install_one_profile(prof)
                if result.get("success"):
                    installed.append(f"{prof.get('id')}@{prof.get('send_time', '08:00')}")
            return {"success": True, "message": f"Zamanlama kuruldu: {', '.join(installed)}."}

        # Profil yok: genel ayar saatiyle tek görev
        send_time = cfg.get("send_time", "08:00")
        if ":" not in send_time:
            send_time = "08:00"
        hour, minute = send_time.split(":")[:2]
        bat = _ensure_task_script()
        cmd = [
            "schtasks", "/Create", "/F", "/TN", TASK_PREFIX,
            "/TR", str(bat), "/SC", "DAILY",
            "/ST", f"{hour}:{minute}",
            "/RL", "LIMITED",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        if out.returncode == 0 or "already" in out.stderr.lower() or "zaten" in out.stderr.lower():
            return {"success": True, "message": f"Zamanlama kuruldu: her gün {send_time}."}
        return {"success": False, "error": out.stderr.strip() or out.stdout.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uninstall_schedule() -> dict:
    """Tüm ÖZEN brifing görevlerini kaldırır."""
    removed = 0
    try:
        out = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in out.stdout.splitlines():
            if TASK_PREFIX in line:
                tn = line.split(",")[0].strip('"')
                subprocess.run(
                    ["schtasks", "/Delete", "/F", "/TN", tn],
                    capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                removed += 1
        return {"success": True, "message": f"Zamanlama kaldırıldı ({removed} görev)."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Brifing çalıştır ─────────────────────────────────────────────────────


# ─── Brifing Profilleri ───────────────────────────────────────────────────


def load_profiles() -> dict:
    f = BASE_DIR / "briefing_profiles.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"profiles": []}


def save_profiles(data: dict) -> None:
    (BASE_DIR / "briefing_profiles.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.route("/profiles")
@login_required
def profiles_list():
    meta = load_manifest()
    queries = sorted(meta.get("queries", []), key=lambda q: (q.get("order", 999), q.get("file", "")))
    data = load_profiles()
    return render_template("profiles.html", profiles=data.get("profiles", []), queries=queries)


@app.route("/profiles/new", methods=["GET", "POST"])
@login_required
def profile_new():
    meta = load_manifest()
    queries = sorted(meta.get("queries", []), key=lambda q: (q.get("order", 999), q.get("file", "")))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pid = request.form.get("id", "").strip() or "profil-" + str(int(__import__("time").time()))
        data = load_profiles()
        if any(p.get("id") == pid for p in data["profiles"]):
            flash("Bu profil ID zaten mevcut.", "danger")
            return render_template("profile_edit.html", p=None, queries=queries, is_new=True)
        profile = {
            "id": pid,
            "name": name,
            "enabled": request.form.get("enabled") == "on",
            "is_default": request.form.get("is_default") == "on",
            "to": [x.strip() for x in request.form.get("to", "").replace(";", ",").split(",") if x.strip()],
            "cc": [x.strip() for x in request.form.get("cc", "").replace(";", ",").split(",") if x.strip()],
            "bcc": [x.strip() for x in request.form.get("bcc", "").replace(";", ",").split(",") if x.strip()],
            "subject_template": request.form.get("subject_template", "ÖZEN Günlük Brifingi ({date})"),
            "send_time": request.form.get("send_time", "08:00"),
            "schedule_frequency": request.form.get("schedule_frequency", "daily"),
            "schedule_week_days": _parse_week_days(request.form.get("schedule_week_days", "")),
            "schedule_month_day": _parse_month_day(request.form.get("schedule_month_day", "1")),
            "send_email": request.form.get("send_email") == "on",
            "save_output": request.form.get("save_output") == "on",
            "query_files": request.form.getlist("query_files"),
        }
        if profile["is_default"]:
            for p in data["profiles"]:
                p["is_default"] = False
        data["profiles"].append(profile)
        save_profiles(data)
        flash(f"'{name}' profili oluşturuldu.", "success")
        return redirect(url_for("profiles_list"))
    return render_template("profile_edit.html", p=None, queries=queries, is_new=True)


@app.route("/profiles/edit/<pid>", methods=["GET", "POST"])
@login_required
def profile_edit(pid):
    meta = load_manifest()
    queries = sorted(meta.get("queries", []), key=lambda q: (q.get("order", 999), q.get("file", "")))
    data = load_profiles()
    prof = next((p for p in data["profiles"] if p.get("id") == pid), None)
    if not prof:
        flash("Profil bulunamadı.", "danger")
        return redirect(url_for("profiles_list"))
    if request.method == "POST":
        prof["name"] = request.form.get("name", "").strip()
        prof["enabled"] = request.form.get("enabled") == "on"
        prof["is_default"] = request.form.get("is_default") == "on"
        prof["to"] = [x.strip() for x in request.form.get("to", "").replace(";", ",").split(",") if x.strip()]
        prof["cc"] = [x.strip() for x in request.form.get("cc", "").replace(";", ",").split(",") if x.strip()]
        prof["bcc"] = [x.strip() for x in request.form.get("bcc", "").replace(";", ",").split(",") if x.strip()]
        prof["subject_template"] = request.form.get("subject_template", "ÖZEN Günlük Brifingi ({date})")
        prof["send_time"] = request.form.get("send_time", "08:00")
        prof["schedule_frequency"] = request.form.get("schedule_frequency", "daily")
        prof["schedule_week_days"] = _parse_week_days(request.form.get("schedule_week_days", ""))
        prof["schedule_month_day"] = _parse_month_day(request.form.get("schedule_month_day", "1"))
        prof["send_email"] = request.form.get("send_email") == "on"
        prof["save_output"] = request.form.get("save_output") == "on"
        prof["query_files"] = request.form.getlist("query_files")
        if prof["is_default"]:
            for p in data["profiles"]:
                p["is_default"] = (p["id"] == pid)
        save_profiles(data)
        flash(f"'{prof['name']}' profili güncellendi.", "success")
        return redirect(url_for("profiles_list"))
    return render_template("profile_edit.html", p=prof, queries=queries, is_new=False)


@app.route("/profiles/delete/<pid>", methods=["POST"])
@login_required
def profile_delete(pid):
    data = load_profiles()
    data["profiles"] = [p for p in data["profiles"] if p.get("id") != pid]
    save_profiles(data)
    flash("Profil silindi.", "success")
    return redirect(url_for("profiles_list"))


@app.route("/profiles/run/<pid>", methods=["POST"])
@login_required
def profile_run(pid):
    cfg = load_config()
    # Formdan açık talimat gelirse onu kullan; yoksa profilin kendi ayarı
    send_email = request.form.get("send_email")
    if send_email is None:
        data = load_profiles()
        prof = next((p for p in data["profiles"] if p.get("id") == pid), None)
        send_email = bool(prof.get("send_email", cfg.get("send_email", True))) if prof else cfg.get("send_email", True)
    else:
        send_email = send_email == "on"
    result = rb.run_briefing(cfg, send_email_flag=send_email, profile_id=pid)
    if result.get("success"):
        msg = f"'{pid}' profili üretildi: {result.get('output_file')}"
        if result.get("email"):
            msg += f" | E-posta: {'OK' if result['email'].get('success') else 'HATA ' + str(result['email'].get('error'))}"
        flash(msg, "success")
    else:
        flash(f"Üretilemedi: {result.get('error')}", "danger")
    return redirect(url_for("profiles_list"))


@app.route("/run", methods=["POST"])
@login_required
def run_briefing_now():
    cfg = load_config()
    send_email = request.form.get("send_email") == "on"
    profile_id = request.form.get("profile_id") or None
    result = rb.run_briefing(cfg, send_email_flag=send_email, profile_id=profile_id)
    if result.get("success"):
        msg = f"Brifing üretildi: {result.get('output_file')}"
        if result.get("email"):
            msg += f" | E-posta: {'✅' if result['email'].get('success') else '❌ ' + str(result['email'].get('error'))}"
        flash(msg, "success")
    else:
        flash(f"Brifing üretilemedi: {result.get('error')}", "danger")
    return redirect(url_for("index"))


@app.route("/maillog")
@login_required
def maillog():
    """E-posta teslimat takibi: son gönderimlerin listesi."""
    entries = rb.load_mail_log()
    entries = list(reversed(entries))
    total = len(entries)
    ok = sum(1 for e in entries if e.get("success"))
    return render_template("maillog.html", entries=entries, total=total, ok=ok, fail=total - ok)


@app.route("/insights/history")
@login_required
def insights_history():
    """İçgörü geçmişi: kaydedilen günlük metrikler + son anomali durumu."""
    import insights as _ins
    days = []
    history_dir = BASE_DIR / "history"
    if history_dir.exists():
        for f in sorted(history_dir.glob("*.json"), reverse=True)[:30]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                days.append(data)
            except Exception:
                continue
    return render_template("insights_history.html", days=days)


@app.route("/report/excel/<filename>")
@login_required
def report_excel(filename):
    if ".." in filename or not filename.startswith("brifing_") or not filename.endswith(".xlsx"):
        flash("Geçersiz dosya.", "danger")
        return redirect(url_for("index"))
    fpath = OUTPUT_DIR / filename
    if not fpath.exists():
        flash("Excel dosyası bulunamadı.", "danger")
        return redirect(url_for("index"))
    return send_file(fpath, as_attachment=True, download_name=filename)


@app.route("/report/<filename>")
@login_required
def report_view(filename):
    if ".." in filename or not filename.startswith("brifing_"):
        flash("Geçersiz dosya.", "danger")
        return redirect(url_for("index"))
    fpath = OUTPUT_DIR / filename
    if not fpath.exists():
        flash("Rapor bulunamadı.", "danger")
        return redirect(url_for("index"))
    return send_file(fpath)


@app.route("/report/view/<filename>")
@login_required
def report_view_page(filename):
    if ".." in filename or not filename.startswith("brifing_"):
        flash("Geçersiz dosya.", "danger")
        return redirect(url_for("index"))
    fpath = OUTPUT_DIR / filename
    if not fpath.exists():
        flash("Rapor bulunamadı.", "danger")
        return redirect(url_for("index"))
    return render_template("report_view.html", filename=filename)


@app.route("/secrets", methods=["GET", "POST"])
@login_required
def secrets_page():
    """Gizli değer yönetimi: ERP, SMTP şifreleri DPAPI ile secrets.dat'te saklanır."""
    if request.method == "POST":
        current = rb.load_secrets()
        current.update({
            "ADMIN_PASSWORD": request.form.get("admin_password", "").strip(),
            "ERP_PASSWORD": request.form.get("erp_password", "").strip(),
            "SMTP_PASSWORD": request.form.get("smtp_password", "").strip(),
        })
        rb.save_secrets(current)
        flash("Gizli değerler bu bilgisayarda şifrelenerek kaydedildi.", "success")
        return redirect(url_for("secrets_page"))
    secrets = rb.load_secrets()
    return render_template("secrets.html",
                           admin_password=secrets.get("ADMIN_PASSWORD", ""),
                           erp_password=secrets.get("ERP_PASSWORD", ""),
                           smtp_password=secrets.get("SMTP_PASSWORD", ""))


if __name__ == "__main__":
    port = load_config().get("web_port", 8080)
    print(f"ÖZEN Brifing Paneli → http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
