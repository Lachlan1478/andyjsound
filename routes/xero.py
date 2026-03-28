import os
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from models.database import db, XeroOrder, Equipment, XeroToken, StockMovement
from services import xero_service
from datetime import datetime

bp = Blueprint("xero", __name__, url_prefix="/xero")


def _client_id():
    return os.environ.get("XERO_CLIENT_ID", "")


def _client_secret():
    return os.environ.get("XERO_CLIENT_SECRET", "")


def _redirect_uri():
    return os.environ.get("XERO_REDIRECT_URI", "http://localhost:5050/xero/callback")


@bp.route("/")
def index():
    token = XeroToken.query.first()
    orders = XeroOrder.query.order_by(XeroOrder.invoice_date.desc()).limit(50).all()
    return render_template("xero.html", token=token, orders=orders)


@bp.route("/connect")
def connect():
    if not _client_id() or _client_id() == "YOUR_XERO_CLIENT_ID":
        flash("Xero credentials not configured. Add your XERO_CLIENT_ID and XERO_CLIENT_SECRET to the .env file, then restart the app.", "warning")
        return redirect(url_for("xero.index"))

    state = secrets.token_urlsafe(16)
    session["xero_state"] = state
    auth_url = xero_service.get_auth_url(_client_id(), _redirect_uri(), state)
    return redirect(auth_url)


@bp.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        flash(f"Xero authorisation failed: {error}", "error")
        return redirect(url_for("xero.index"))

    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("xero_state"):
        flash("Invalid OAuth state. Please try connecting again.", "error")
        return redirect(url_for("xero.index"))

    try:
        token_data = xero_service.exchange_code_for_token(code, _client_id(), _client_secret(), _redirect_uri())
        tenants = xero_service.get_tenants(token_data["access_token"])

        if not tenants:
            flash("No Xero organisations found.", "error")
            return redirect(url_for("xero.index"))

        # Use first tenant
        tenant = tenants[0]
        xero_service.save_token(token_data, tenant["tenantId"], tenant.get("tenantName", ""))
        flash(f"Connected to Xero: {tenant.get('tenantName', 'Unknown Org')}", "success")
    except Exception as e:
        flash(f"Failed to connect to Xero: {str(e)}", "error")

    return redirect(url_for("xero.index"))


@bp.route("/disconnect", methods=["POST"])
def disconnect():
    token = XeroToken.query.first()
    if token:
        db.session.delete(token)
        db.session.commit()
    flash("Disconnected from Xero.", "info")
    return redirect(url_for("xero.index"))


@bp.route("/sync", methods=["POST"])
def sync():
    """Pull purchase orders / bills from Xero and upsert into local DB."""
    token = xero_service.get_valid_token(_client_id(), _client_secret())
    if not token:
        flash("Not connected to Xero. Please connect first.", "error")
        return redirect(url_for("xero.index"))

    try:
        invoices = xero_service.fetch_invoices(token.access_token, token.tenant_id, invoice_type="ACCPAY")
        synced = 0

        for inv in invoices:
            inv_number = inv.get("InvoiceNumber", inv.get("InvoiceID", ""))
            contact_name = inv.get("Contact", {}).get("Name", "Unknown")

            inv_date = None
            due_date = None
            raw_date = inv.get("Date", "")
            if raw_date:
                try:
                    ts = int(raw_date.replace("/Date(", "").replace(")/", "").split("+")[0]) / 1000
                    inv_date = datetime.utcfromtimestamp(ts)
                except Exception:
                    pass

            raw_due = inv.get("DueDate", "")
            if raw_due:
                try:
                    ts = int(raw_due.replace("/Date(", "").replace(")/", "").split("+")[0]) / 1000
                    due_date = datetime.utcfromtimestamp(ts)
                except Exception:
                    pass

            for line in inv.get("LineItems", []):
                desc = line.get("Description", "")
                qty = int(line.get("Quantity", 0))
                unit_price = float(line.get("UnitAmount", 0))
                item_code = line.get("ItemCode", "")

                if qty <= 0:
                    continue

                # Try to match to local equipment by xero_item_code or name
                equipment = None
                if item_code:
                    equipment = Equipment.query.filter_by(xero_item_code=item_code).first()
                if not equipment and desc:
                    equipment = Equipment.query.filter(Equipment.name.ilike(f"%{desc[:30]}%")).first()

                # Check if order already synced
                existing = XeroOrder.query.filter_by(
                    xero_invoice_id=inv.get("InvoiceID", ""),
                    item_description=desc,
                ).first()

                if existing:
                    existing.quantity_ordered = qty
                    existing.unit_price = unit_price
                    existing.contact_name = contact_name
                else:
                    order = XeroOrder(
                        xero_invoice_id=inv.get("InvoiceID", ""),
                        invoice_number=inv_number,
                        contact_name=contact_name,
                        equipment_id=equipment.id if equipment else None,
                        item_description=desc,
                        quantity_ordered=qty,
                        quantity_received=0,
                        unit_price=unit_price,
                        status="pending",
                        invoice_date=inv_date,
                        due_date=due_date,
                    )
                    db.session.add(order)
                    synced += 1

        db.session.commit()
        flash(f"Xero sync complete. {synced} new order lines imported.", "success")
    except Exception as e:
        flash(f"Sync failed: {str(e)}", "error")

    return redirect(url_for("xero.index"))


@bp.route("/demo-sync", methods=["POST"])
def demo_sync():
    """Load demo data for testing without a real Xero connection."""
    demo_items = [
        ("INV-0042", "Audio House UK", "QSC K12.2 Active Speaker", 4, 899.00),
        ("INV-0043", "Soundcraft Pro", "Soundcraft Signature 22 Mixer", 2, 649.00),
        ("INV-0043", "Soundcraft Pro", "Shure SM58 Microphone", 10, 99.00),
        ("INV-0044", "Elation Systems", "Elation ELAR 108 LED PAR", 6, 245.00),
        ("INV-0044", "Elation Systems", "XLR Cable 10m", 20, 18.50),
    ]

    synced = 0
    for inv_num, contact, desc, qty, price in demo_items:
        existing = XeroOrder.query.filter_by(invoice_number=inv_num, item_description=desc).first()
        if not existing:
            equipment = Equipment.query.filter(Equipment.name.ilike(f"%{desc[:20]}%")).first()
            order = XeroOrder(
                xero_invoice_id=f"DEMO-{inv_num}-{desc[:10]}",
                invoice_number=inv_num,
                contact_name=contact,
                equipment_id=equipment.id if equipment else None,
                item_description=desc,
                quantity_ordered=qty,
                quantity_received=0,
                unit_price=price,
                status="pending",
                invoice_date=datetime.utcnow(),
            )
            db.session.add(order)
            synced += 1

    db.session.commit()
    flash(f"Demo sync loaded {synced} sample order lines.", "success")
    return redirect(url_for("xero.index"))
