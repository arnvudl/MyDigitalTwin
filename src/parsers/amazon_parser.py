"""
MyDigitalTwin — Parser Amazon
================================
Lit les CSV Amazon et produit des DataFrames propres,
anonymisés et prêts pour PySpark.

Fichiers traités :
    Order History.csv           → orders.csv
    Digital Content Orders.csv  → digital_orders.csv
    Refund Details.csv          → refunds.csv
    Returns Status.csv          → returns.csv

Fichiers ignorés :
    Retail.TransactionalInvoicing.*.pdf  → factures PDF non parsables
    Delivery Photos.csv                  → liens photos inutiles

Colonnes supprimées (confidentialité) :
    Billing Address, Shipping Address    → contiennent ton adresse réelle
    Carrier Name & Tracking Number       → inutile analytiquement
    Gift Recipient/Sender                → données tierces

Usage:
    python amazon_parser.py --input ./data/raw/AMAZON --output ./data/processed/amazon
"""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    """Corrige le double encodage UTF-8 présent dans les exports Amazon."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_val(val: str) -> str:
    """Nettoie une valeur CSV : strip, fix encoding, remplace 'Not Available'."""
    if not val:
        return ""
    val = val.strip().strip('"')
    if val in ("Not Available", "Not Applicable", "N/A", ""):
        return ""
    return fix_encoding(val)


def ts_to_iso(date_str: str) -> str:
    """Normalise une date Amazon en ISO 8601."""
    if not date_str:
        return ""
    date_str = date_str.strip().strip('"')
    for fmt in [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return date_str


def to_float(val: str) -> str:
    """Convertit une valeur numérique, gère les formats avec apostrophe."""
    if not val:
        return ""
    val = val.strip().strip("'\"")
    try:
        return str(round(float(val), 2))
    except ValueError:
        return ""


def categorize_product(name: str) -> str:
    """
    Catégorise un produit Amazon à partir de son nom.
    Utile pour l'analyse des centres d'intérêt.
    """
    name_lower = name.lower()
    categories = {
        "Électronique": ["câble", "usb", "chargeur", "batterie", "écouteur", "casque",
                         "clavier", "souris", "hub", "adaptateur", "hdmi", "ssd",
                         "ram", "carte", "raspberry", "arduino", "led", "lampe",
                         "trépied", "selfie", "caméra", "webcam", "microphone"],
        "Vêtements": ["t-shirt", "chemise", "pantalon", "jean", "veste", "chaussure",
                      "sneaker", "pull", "sweat", "short", "chaussette", "slip"],
        "Livres": ["livre", "book", "roman", "guide", "manuel", "atlas"],
        "Sport": ["sport", "fitness", "yoga", "musculation", "vélo", "running",
                  "basketball", "football", "tennis", "natation"],
        "Musique / DJ": ["dj", "vinyle", "platine", "mixeur", "controller", "cdj",
                         "Pioneer", "rekordbox", "traktor", "serato", "studio"],
        "Jeux vidéo": ["jeu", "game", "gaming", "manette", "console", "playstation",
                       "xbox", "nintendo", "switch", "ps4", "ps5"],
        "Cuisine": ["cuisine", "casserole", "poêle", "couteau", "planche",
                    "mixeur", "blender", "café", "thé"],
        "Beauté / Santé": ["shampooing", "crème", "soin", "vitamines", "complément",
                           "brosse", "rasoir", "parfum", "déodorant"],
        "Maison": ["lampe", "cadre", "coussin", "rideau", "étagère", "boîte",
                   "rangement", "nettoyage", "aspirateur"],
        "Abonnement": ["prime", "abonnement", "membership", "subscription"],
    }
    for category, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return category
    return "Autre"


def read_csv_safe(path: Path) -> list:
    """Lit un CSV Amazon avec gestion d'encodage robuste."""
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception:
            continue
    print(f"  [!] Impossible de lire : {path.name}")
    return []


def write_csv(rows: list, path: Path) -> int:
    """Écrit une liste de dicts en CSV propre."""
    if not rows:
        print(f"  [~] Vide — {path.name}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [✓] {path.name:<40} {len(rows):>5} lignes")
    return len(rows)


# ══════════════════════════════════════════════════════════════════════════════
# PARSERS
# ══════════════════════════════════════════════════════════════════════════════

# Colonnes à supprimer (confidentialité + inutilité analytique)
ORDERS_DROP = {
    "Billing Address", "Carrier Name & Tracking Number",
    "Gift Message", "Gift Recipient Contact", "Gift Sender Name",
    "Item Serial Number", "Product Condition", "Purchase Order Number",
    "Ship Date", "Shipment Item Subtotal Tax", "Shipment Status",
    "Shipping Address", "Shipping Option", "Unit Price Tax", "Currency"
}

DIGITAL_KEEP = {
    "Order Date", "Order ID", "Order Status", "Product Name",
    "Price", "Price Currency Code", "Transaction Amount",
    "Subscription Order Type", "Fulfillment Status",
    "Delivery Status", "Marketplace"
}

REFUND_KEEP = {
    "Creation Date", "Currency", "Order ID", "Payment Status",
    "Quantity", "Refund Amount", "Refund Date",
    "Reversal Reason", "Reversal Status", "Website"
}

RETURNS_KEEP = {
    "Return Date", "Order ID", "Order Date", "Title",
    "Quantity", "Return Reason", "Status", "ASIN"
}


def parse_orders(path: Path) -> list:
    """
    Order History.csv
    Colonnes sensibles supprimées, montants normalisés,
    catégorie produit ajoutée automatiquement.
    """
    rows_raw = read_csv_safe(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        product_name = clean_val(r.get("Product Name", ""))
        order_date = ts_to_iso(r.get("Order Date", ""))

        rows.append({
            "asin": clean_val(r.get("ASIN", "")),
            "order_id": clean_val(r.get("Order ID", "")),
            "order_date": order_date,
            "order_month": order_date[:7] if order_date else "",
            "order_year": order_date[:4] if order_date else "",
            "order_status": clean_val(r.get("Order Status", "")),
            "quantity": clean_val(r.get("Original Quantity", "")),
            "product_name": product_name,
            "category": categorize_product(product_name),
            "unit_price": to_float(r.get("Unit Price", "")),
            "total_amount": to_float(r.get("Total Amount", "")),
            "total_discounts": to_float(r.get("Total Discounts", "").lstrip("'")),
            "shipping_charge": to_float(r.get("Shipping Charge", "")),
            "payment_method": clean_val(r.get("Payment Method Type", "")),
            "website": clean_val(r.get("Website", "")),
            "platform": "amazon",
        })
    return rows


def parse_digital_orders(path: Path) -> list:
    """
    Digital Content Orders.csv
    On garde uniquement les colonnes analytiquement pertinentes.
    Abonnements Prime identifiés séparément.
    """
    rows_raw = read_csv_safe(path)
    if not rows_raw:
        return []

    rows = []
    seen_orders = set()  # Dédupliquer (chaque commande a 2 lignes Tax + Price)

    for r in rows_raw:
        order_id = clean_val(r.get("Order ID", ""))
        component = clean_val(r.get("Component Type", ""))

        # On ne garde qu'une ligne par commande (Price Amount, pas Tax)
        key = f"{order_id}_{component}"
        if key in seen_orders or component == "Tax":
            continue
        seen_orders.add(key)

        product_name = clean_val(r.get("Product Name", ""))
        order_date = ts_to_iso(r.get("Order Date", ""))

        rows.append({
            "order_id": order_id,
            "order_date": order_date,
            "order_month": order_date[:7] if order_date else "",
            "order_year": order_date[:4] if order_date else "",
            "order_status": clean_val(r.get("Order Status", "")),
            "product_name": product_name,
            "category": categorize_product(product_name),
            "price": to_float(r.get("Price", "")),
            "transaction_amount": to_float(r.get("Transaction Amount", "")),
            "subscription_type": clean_val(r.get("Subscription Order Type", "")),
            "fulfillment_status": clean_val(r.get("Fullfilment Status", r.get("Fulfillment Status", ""))),
            "marketplace": clean_val(r.get("Marketplace", "")),
            "platform": "amazon",
            "type": "digital",
        })
    return rows


def parse_refunds(path: Path) -> list:
    """
    Refund Details.csv
    """
    rows_raw = read_csv_safe(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        creation_date = ts_to_iso(r.get("Creation Date", ""))
        rows.append({
            "order_id": clean_val(r.get("Order ID", "")),
            "creation_date": creation_date,
            "refund_date": ts_to_iso(r.get("Refund Date", "")),
            "refund_month": creation_date[:7] if creation_date else "",
            "quantity": clean_val(r.get("Quantity", "")),
            "refund_amount": to_float(r.get("Refund Amount", "")),
            "reversal_reason": clean_val(r.get("Reversal Reason", "")),
            "reversal_status": clean_val(r.get("Reversal Status", "")),
            "payment_status": clean_val(r.get("Payment Status", "")),
            "website": clean_val(r.get("Website", "")),
            "platform": "amazon",
            "type": "refund",
        })
    return rows


def parse_returns(path: Path) -> list:
    """
    Returns Status.csv
    """
    rows_raw = read_csv_safe(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        return_date = ts_to_iso(
            r.get("Return Date", r.get("Order Date", ""))
        )
        rows.append({
            "order_id": clean_val(r.get("Order ID", "")),
            "asin": clean_val(r.get("ASIN", "")),
            "return_date": return_date,
            "return_month": return_date[:7] if return_date else "",
            "product_name": fix_encoding(r.get("Title", r.get("Product Name", ""))),
            "quantity": clean_val(r.get("Quantity", "")),
            "return_reason": clean_val(r.get("Return Reason", "")),
            "status": clean_val(r.get("Status", "")),
            "platform": "amazon",
            "type": "return",
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Parser Amazon — MyDigitalTwin")
    ap.add_argument("--input", required=True, help="Dossier racine AMAZON")
    ap.add_argument("--output", default="./data/processed/amazon")
    args = ap.parse_args()

    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 55}")
    print(f"  MyDigitalTwin — Parser Amazon")
    print(f"  Source : {root}")
    print(f"  Sortie : {out}")
    print(f"{'=' * 55}\n")

    stats = {}

    # ── Commandes physiques ──────────────────────────────────────────────────
    print("📦 Commandes physiques")
    p = root / "Your Orders" / "Your Amazon Orders" / "Order History.csv"
    if p.exists():
        orders = parse_orders(p)
        stats["orders"] = write_csv(orders, out / "orders.csv")

        # Stats rapides
        if orders:
            total_spent = sum(float(r["total_amount"]) for r in orders if r["total_amount"])
            cats = {}
            for r in orders:
                cats[r["category"]] = cats.get(r["category"], 0) + 1
            top_cat = max(cats, key=cats.get) if cats else "—"
            years = sorted(set(r["order_year"] for r in orders if r["order_year"]))
            print(f"     Période       : {years[0] if years else '?'} → {years[-1] if years else '?'}")
            print(f"     Total dépensé : {total_spent:.2f} EUR")
            print(f"     Top catégorie : {top_cat} ({cats.get(top_cat, 0)} commandes)")
    else:
        print(f"  [!] Fichier introuvable : {p}")

    # ── Commandes digitales ──────────────────────────────────────────────────
    print("\n💻 Commandes digitales (abonnements, livres, films…)")
    p = root / "Your Orders" / "Your Amazon Orders" / "Digital Content Orders.csv"
    if p.exists():
        stats["digital"] = write_csv(parse_digital_orders(p), out / "digital_orders.csv")
    else:
        print(f"  [!] Fichier introuvable : {p}")

    # ── Remboursements ───────────────────────────────────────────────────────
    print("\n💸 Remboursements")
    p = root / "Your Orders" / "Your Returns & Refunds" / "Refund Details.csv"
    if p.exists():
        stats["refunds"] = write_csv(parse_refunds(p), out / "refunds.csv")
    else:
        print(f"  [!] Fichier introuvable : {p}")

    # ── Retours ─────────────────────────────────────────────────────────────
    print("\n🔄 Retours")
    p = root / "Your Orders" / "Your Returns & Refunds" / "Returns Status.csv"
    if p.exists():
        stats["returns"] = write_csv(parse_returns(p), out / "returns.csv")
    else:
        print(f"  [!] Fichier introuvable : {p}")

    # ── Résumé ───────────────────────────────────────────────────────────────
    total = sum(v for v in stats.values() if v)
    print(f"\n{'─' * 55}")
    print(f"  Total : {total:,} lignes dans {len(stats)} fichiers")
    print(f"  Sortie: {out}")
    print(f"{'─' * 55}")


if __name__ == "__main__":
    main()
