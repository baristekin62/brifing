"""ÖZEN Brifing İçgörü Katmanı — Kural Tabanlı Özet + Anomali Tespiti

LLM gerektirmez; sorgu sonuçlarından:
  - Her bölüm için Türkçe yönetici özeti (toplam, ortalama, en iyi/en kötü)
  - Genel günlük brifing özeti
  - Geçmiş kayıtlarla karşılaştırmalı anomali uyarıları (sapma % > eşik)

Geçmiş veri D:\\BRIFING\\history\\<YYYY-MM-DD>.json olarak saklanır.

Kullanım:
    from insights import build_insights
    summary_html, anomalies = build_insights(cfg, query_results)
"""

import json
import statistics
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HISTORY_DIR = BASE_DIR / "history"


# ─── Sayısal yardımcılar ───────────────────────────────────────────────────


def _num(value):
    """Sayıya çevirir; sayı değilse None döner."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        v = value.strip().replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return None
    return None


_DATE_KEYWORDS = ("tarih", "date", "gun", "gün", "saat", "time", "tarihi")
_RATIO_KEYWORDS = ("oran", "yüzde", "yuzde", "ratio", "pct", "ort", "ortalama", "adet/personel", "fark_orani")


def _is_date_col(name: str) -> bool:
    n = str(name).strip().lower()
    return any(k in n for k in _DATE_KEYWORDS)


def _is_ratio_col(name: str) -> bool:
    n = str(name).strip().lower()
    return any(k in n for k in _RATIO_KEYWORDS)


def _is_total_row(row) -> bool:
    """GENEL TOPLAM / TOPLAM gibi toplam satırını tespit eder."""
    for v in row:
        if v is None:
            continue
        s = str(v).strip().upper()
        if "GENEL TOPLAM" in s or "TOPLAM" == s or s == "TOTAL":
            return True
    return False


def _fmt(value, decimal: bool = True) -> str:
    """Türkçe sayı formatı: 18.235,79 (nokta binlik, virgül ondalık)."""
    if value is None:
        return "-"
    f = float(value)
    if decimal:
        s = f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        s = f"{f:,.0f}".replace(",", ".")
    return s


# ─── KPI çözümleme ─────────────────────────────────────────────────────────


def _resolve_value(q: dict, kpi: dict):
    if not q.get("success"):
        return None
    columns = q.get("columns", [])
    rows = q.get("rows", [])
    col_name = str(kpi.get("column", "")).strip().lower()
    col_idx = None
    for i, c in enumerate(columns):
        if str(c).strip().lower() == col_name:
            col_idx = i
            break
    if col_idx is None:
        return None
    row_idx = int(kpi.get("row", 0))
    if row_idx < len(rows):
        return rows[row_idx][col_idx]
    return None


def _find_col(columns: list, name) -> int:
    """Kolon adını (case-insensitive) bulur; yoksa -1."""
    target = str(name or "").strip().lower()
    for i, c in enumerate(columns):
        if str(c).strip().lower() == target:
            return i
    return -1


def _split_rows(q: dict):
    """Sorgu satırlarını toplam satırı ve detay satırları olarak ayırır."""
    rows = q.get("rows", [])
    total_row = None
    detail = []
    for r in rows:
        if _is_total_row(r):
            total_row = r
        else:
            detail.append(r)
    return total_row, detail


def _col_total(q: dict, col_name, total_row=None, detail=None) -> float:
    """Bir kolonun toplam değerini döndürür (GENEL TOPLAM satırı varsa onu kullanır)."""
    columns = q.get("columns", [])
    ci = _find_col(columns, col_name)
    if ci == -1:
        return None
    if total_row is not None and ci < len(total_row):
        v = _num(total_row[ci])
        if v is not None:
            return v
    if detail is None:
        _, detail = _split_rows(q)
    vals = []
    for r in detail:
        if ci < len(r):
            v = _num(r[ci])
            if v is not None:
                vals.append(v)
    return sum(vals) if vals else None


def _query_metrics(q: dict) -> list:
    """Sorgudan takip edilebilir metrikleri çıkarır: [{label, value}].

    Öncelik: sorguya özel 'summary' yapılandırması → manifest KPI'ları
    → tek satırlık özet sorgularda tüm sayısal sütunlar
    → çok satırlı sorgularda sayısal sütunların toplamı (GENEL TOPLAM satırı çift sayılmaz).
    """
    if not q.get("success"):
        return []
    metrics = []

    scfg = q.get("summary") or {}
    total_row, detail = _split_rows(q)
    if scfg:
        # Tanımlı toplam kolonları
        for cname in scfg.get("totals", []):
            val = _col_total(q, cname, total_row, detail)
            if val is not None:
                metrics.append({"label": f"{cname} (Toplam)", "value": round(val, 2)})
        # Tanımlı oran (pay/payda)
        num = scfg.get("ratio_num")
        den = scfg.get("ratio_den")
        if num and den:
            nv = _col_total(q, num, total_row, detail)
            dv = _col_total(q, den, total_row, detail)
            if nv is not None and dv:
                metrics.append({
                    "label": scfg.get("ratio_label") or f"{num}/{den}",
                    "value": round(nv / dv * 100.0, 2),
                })
        return metrics

    for kpi in q.get("kpis", []):
        label = kpi.get("label") or kpi.get("column")
        if not label:
            continue
        val = _num(_resolve_value(q, kpi))
        if val is not None:
            metrics.append({"label": str(label), "value": val})
    if not metrics and len(q.get("rows", [])) == 1:
        row = q["rows"][0]
        for ci, c in enumerate(q["columns"]):
            if ci < len(row):
                val = _num(row[ci])
                if val is not None:
                    metrics.append({"label": str(c), "value": val})
    if not metrics:
        # Çok satırlı sorgu: tarih ve oran sütunları hariç sayısal sütunların toplamı
        rows = q.get("rows", [])
        columns = q.get("columns", [])
        for ci, c in enumerate(columns):
            if _is_date_col(str(c)) or _is_ratio_col(str(c)):
                continue
            vals = []
            for r in rows:
                if _is_total_row(r):
                    continue
                if ci < len(r):
                    v = _num(r[ci])
                    if v is not None:
                        vals.append(v)
            if vals:
                metrics.append({"label": f"{c} (Toplam)", "value": sum(vals)})
    return metrics


# ─── Geçmiş kayıt ──────────────────────────────────────────────────────────


def save_history(query_results: list, day: date = None) -> Path:
    """Bugünün metriklerini history/<tarih>.json olarak kaydeder."""
    day = day or date.today()
    metrics = []
    for q in query_results:
        for m in _query_metrics(q):
            metrics.append({
                "query": q.get("title", "?"),
                "label": m["label"],
                "value": round(m["value"], 2),
            })
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    fpath = HISTORY_DIR / f"{day.isoformat()}.json"
    fpath.write_text(json.dumps({"date": day.isoformat(), "metrics": metrics},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return fpath


def load_history(days_back: int = 30) -> list:
    """Son N günün kayıtlarını (bugün hariç) döndürür."""
    if not HISTORY_DIR.exists():
        return []
    today = date.today()
    out = []
    for d in range(days_back, 0, -1):
        fpath = HISTORY_DIR / f"{(today - timedelta(days=d)).isoformat()}.json"
        if fpath.exists():
            try:
                out.append(json.loads(fpath.read_text(encoding="utf-8")))
            except Exception:
                pass
    return out


# ─── Anomali tespiti ───────────────────────────────────────────────────────


def detect_anomalies(query_results: list, threshold_pct: float = 20.0,
                     days_back: int = 7) -> list:
    """Bugünkü metrikleri son N günün ortalamasıyla karşılaştırır.

    Sapma |değer - ortalama| / ortalama > eşik ise anomali döner.
    En az 3 gün geçmiş veri olmalı.
    """
    history = load_history(days_back)
    if len(history) < 3:
        return []
    # (query, label) -> [değerler]
    past = {}
    for day in history:
        for m in day.get("metrics", []):
            key = (m.get("query"), m.get("label"))
            past.setdefault(key, []).append(m.get("value"))

    anomalies = []
    for q in query_results:
        title = q.get("title", "?")
        for m in _query_metrics(q):
            vals = past.get((title, m["label"]), [])
            if len(vals) < 3:
                continue
            try:
                avg = statistics.mean(vals)
            except (statistics.StatisticsError, TypeError):
                continue
            if avg == 0:
                continue
            pct = (m["value"] - avg) / avg * 100.0
            if abs(pct) >= threshold_pct:
                direction = "artış" if pct > 0 else "düşüş"
                anomalies.append({
                    "query": title,
                    "label": m["label"],
                    "current": m["value"],
                    "avg": avg,
                    "pct": pct,
                    "direction": direction,
                })
    anomalies.sort(key=lambda a: abs(a["pct"]), reverse=True)
    return anomalies


def _anomaly_html(anomalies: list) -> str:
    if not anomalies:
        return ""
    items = ""
    for a in anomalies[:8]:
        icon = "📈" if a["pct"] > 0 else "📉"
        color = "#b91c1c" if a["pct"] < 0 else "#b45309"
        items += (
            f"<div class='anom-item'><span class='anom-icon'>{icon}</span>"
            f"<span>{a['query']} — <strong>{a['label']}</strong>: "
            f"<span style='color:{color}'>{_fmt(a['current'])}</span> "
            f"vs ortalama {_fmt(a['avg'])} ({a['pct']:+.1f}%)</span></div>"
        )
    return f"<div class='anom-box'><h3>🚨 Anomali Uyarıları</h3>{items}</div>"


# ─── Kural tabanlı bölüm özeti ─────────────────────────────────────────────


def build_section_summary(q: dict, prev_values: dict = None) -> str:
    """Tek sorgu sonucundan Türkçe, iş anlamlı özet cümle üretir.

    queries_meta.json'daki 'summary' yapılandırmasına uyar:
      totals:      toplamı gösterilecek kolonlar (GENEL TOPLAM satırı varsa onu kullanır)
      ratio_num/ratio_den/ratio_label: pay/payda yüzdesi
      delta:       önceki rapora göre artış/azalış (%) — prev_values ile karşılaştırır
    Yapılandırma yoksa akıllı varsayılan (toplam + en yüksek) uygulanır.
    """
    if not q.get("success"):
        return ""
    columns = q.get("columns", [])
    rows = q.get("rows", [])
    if not rows or not columns:
        return ""

    title = q.get("title", "")
    scfg = q.get("summary") or {}
    total_row, detail = _split_rows(q)

    if scfg:
        parts = []
        # Toplamlar
        for cname in scfg.get("totals", []):
            val = _col_total(q, cname, total_row, detail)
            if val is not None:
                s = f"**{cname}**: {_fmt(val)}"
                if scfg.get("delta") and prev_values:
                    prev = prev_values.get((title, f"{cname} (Toplam)"))
                    if prev is not None:
                        s += _delta_text(val, prev)
                parts.append(s)
        # Oran
        num = scfg.get("ratio_num")
        den = scfg.get("ratio_den")
        if num and den:
            nv = _col_total(q, num, total_row, detail)
            dv = _col_total(q, den, total_row, detail)
            if nv is not None and dv:
                pct = nv / dv * 100.0
                label = scfg.get("ratio_label") or "Oran"
                s = f"**{label}**: %{_fmt(pct)}"
                if scfg.get("delta") and prev_values:
                    plabel = scfg.get("ratio_label") or f"{num}/{den}"
                    prev = prev_values.get((title, plabel))
                    if prev is not None:
                        s += _delta_text(pct, prev)
                parts.append(s)
        if parts:
            return f"**{title}:** " + "; ".join(parts) + "."
        return ""

    # ── Akıllı varsayılan (summary yapılandırması yok) ──
    # Sayısal sütun indeksleri (tarih ve oran sütunları hariç)
    num_cols = []
    for ci, c in enumerate(columns):
        if _is_date_col(str(c)) or _is_ratio_col(str(c)):
            continue
        if ci < len(rows[0]):
            v = _num(rows[0][ci])
            if v is not None:
                num_cols.append(ci)

    parts = []
    if q.get("kpis"):
        for kpi in q["kpis"]:
            label = kpi.get("label") or kpi.get("column")
            val = _num(_resolve_value(q, kpi))
            if val is not None:
                parts.append(f"**{label}**: {_fmt(val)}")
    elif len(rows) == 1:
        row = rows[0]
        for ci in num_cols:
            parts.append(f"**{columns[ci]}**: {_fmt(_num(row[ci]))}")
    elif num_cols:
        main_col = num_cols[0]
        if total_row is not None and main_col < len(total_row):
            tv = _num(total_row[main_col])
            if tv is not None:
                parts.append(f"**{columns[main_col]}** toplam: {_fmt(tv)}")
        elif detail:
            vals = [_num(r[main_col]) for r in detail]
            vals = [v for v in vals if v is not None]
            if vals:
                parts.append(f"**{columns[main_col]}** toplam: {_fmt(sum(vals))}")
        pool = detail if detail else rows
        if pool:
            best = None
            for r in pool:
                v = _num(r[main_col]) if main_col < len(r) else None
                if v is not None and (best is None or v > best[0]):
                    best = (v, r)
            if best is not None:
                name = _row_name(columns, best[1])
                if name and name not in ("—", ""):
                    parts.append(f"En yüksek: {name} ({_fmt(best[0])})")

    if not parts:
        return ""
    return f"**{title}:** " + "; ".join(parts) + "."


def _delta_text(current: float, prev: float) -> str:
    """Önceki değere göre artış/azalış metni üretir."""
    if prev == 0:
        return ""
    pct = (current - prev) / abs(prev) * 100.0
    if abs(pct) < 0.05:
        return f" (önceki rapora göre aynı)"
    arrow = "▲" if pct > 0 else "▼"
    color = "#b91c1c" if pct > 0 else "#15803d"
    return f" (önceki rapora göre <span style='color:{color}'>{arrow} {abs(pct):.1f}%</span>)"


def _row_name(columns, row) -> str:
    """Satırın isim değerini bulur (ilk metin sütunundan)."""
    for ci, c in enumerate(columns):
        if ci < len(row):
            v = row[ci]
            if v is not None and _num(v) is None and str(v).strip():
                return str(v).strip()
    return "—"


def _prev_values_map(history: list) -> dict:
    """Geçmiş kayıtlardan (query, label) -> değer eşlemesi üretir. En yakın gün öncelikli."""
    out = {}
    for day in sorted(history, key=lambda h: h.get("date", ""), reverse=True):
        for m in day.get("metrics", []):
            key = (m.get("query"), m.get("label"))
            out.setdefault(key, m.get("value"))
    return out


def build_daily_summary(query_results: list, prev_values: dict = None) -> str:
    """Tüm bölümlerin özet cümlelerini birleştirip genel özet metni üretir."""
    lines = []
    for q in query_results:
        s = build_section_summary(q, prev_values)
        if s:
            lines.append(s)
    if not lines:
        return ""
    return "\n".join(lines)


# ─── Genel HTML üretimi ────────────────────────────────────────────────────


def build_insights(cfg: dict, query_results: list) -> str:
    """Rapor üstüne eklenecek içgörü HTML'ini üretir (özet + anomali)."""
    anomalies = detect_anomalies(
        query_results,
        threshold_pct=float(cfg.get("insights", {}).get("anomaly_threshold_pct", 20)),
        days_back=int(cfg.get("insights", {}).get("anomaly_days_back", 7)),
    )
    anom_html = _anomaly_html(anomalies)
    history = load_history(int(cfg.get("insights", {}).get("anomaly_days_back", 7)))
    prev_values = _prev_values_map(history)
    summary = build_daily_summary(query_results, prev_values)
    summary_html = ""
    if summary:
        items = "".join(
            f"<div class='insight-item'>{_md_inline(line)}</div>" for line in summary.split("\n")
        )
        summary_html = f"<div class='insight-box'><h3>🧠 Günlük Özet</h3>{items}</div>"
    return anom_html + summary_html


def _md_inline(text: str) -> str:
    """**bold** işaretlerini <strong> yapar; HTML escape yapar.

    _delta_text'in ürettiği güvenli <span> etiketleri (renkli ok) escape'ten
    önce yer tutucuya alınıp sonunda geri konur — ham HTML görünmez.
    """
    import html as _html
    import re as _re
    src = str(text)
    spans = []
    def _keep(m):
        spans.append(m.group(0))
        return f"\x00span{len(spans)-1}\x00"
    src = _re.sub(r"<span[^>]*>.*?</span>", _keep, src)
    escaped = _html.escape(src)
    out = []
    i = 0
    while True:
        j = escaped.find("**", i)
        if j == -1:
            out.append(escaped[i:])
            break
        k = escaped.find("**", j + 2)
        if k == -1:
            out.append(escaped[i:])
            break
        out.append(escaped[i:j])
        out.append("<strong>" + escaped[j + 2:k] + "</strong>")
        i = k + 2
    result = "".join(out)
    for idx, sp in enumerate(spans):
        result = result.replace(f"\x00span{idx}\x00", sp)
    return result


if __name__ == "__main__":
    print("İçgörü katmanı hazır. Geçmiş kayıt sayısı:", len(load_history(30)))
