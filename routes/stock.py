from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.database import db, Equipment, StockMovement, XeroOrder
from datetime import datetime

bp = Blueprint("stock", __name__, url_prefix="/stock")


@bp.route("/receive", methods=["GET", "POST"])
def receive():
    """Mark stock as received from a Xero order or manually."""
    if request.method == "POST":
        equipment_id = int(request.form.get("equipment_id"))
        qty = int(request.form.get("quantity", 0))
        notes = request.form.get("notes", "").strip()
        reference = request.form.get("reference", "").strip()
        xero_order_id = request.form.get("xero_order_id", "")

        if qty <= 0:
            flash("Quantity must be greater than zero.", "error")
            return redirect(url_for("stock.receive"))

        item = Equipment.query.get_or_404(equipment_id)
        item.current_stock += qty

        movement = StockMovement(
            equipment_id=equipment_id,
            movement_type="received",
            quantity=qty,
            notes=notes,
            reference=reference,
            performed_by=request.form.get("performed_by", "Staff"),
        )
        db.session.add(movement)

        # Update Xero order if linked
        if xero_order_id:
            order = XeroOrder.query.get(int(xero_order_id))
            if order:
                order.quantity_received = min(
                    order.quantity_received + qty, order.quantity_ordered
                )
                order.status = (
                    "received"
                    if order.quantity_received >= order.quantity_ordered
                    else "partially_received"
                )

        db.session.commit()
        flash(f"Received {qty} × {item.name}. New stock: {item.current_stock}.", "success")
        return redirect(url_for("dashboard.index"))

    equipment = Equipment.query.order_by(Equipment.name).all()
    pending_orders = (
        XeroOrder.query.filter(XeroOrder.status != "received")
        .order_by(XeroOrder.invoice_date.desc())
        .all()
    )
    return render_template("stock_receive.html", equipment=equipment, pending_orders=pending_orders)


@bp.route("/sell", methods=["GET", "POST"])
def sell():
    """Reduce quantity when equipment is sold/dispatched to a client."""
    if request.method == "POST":
        equipment_id = int(request.form.get("equipment_id"))
        qty = int(request.form.get("quantity", 0))
        client = request.form.get("client", "").strip()
        notes = request.form.get("notes", "").strip()

        if qty <= 0:
            flash("Quantity must be greater than zero.", "error")
            return redirect(url_for("stock.sell"))

        item = Equipment.query.get_or_404(equipment_id)
        if qty > item.current_stock:
            flash(f"Insufficient stock. Available: {item.current_stock}.", "error")
            return redirect(url_for("stock.sell"))

        item.current_stock -= qty
        movement = StockMovement(
            equipment_id=equipment_id,
            movement_type="sold",
            quantity=-qty,
            notes=notes,
            reference=client,
            performed_by=request.form.get("performed_by", "Staff"),
        )
        db.session.add(movement)
        db.session.commit()
        flash(f"Dispatched {qty} × {item.name} to {client or 'client'}. Remaining: {item.current_stock}.", "success")
        return redirect(url_for("dashboard.index"))

    equipment = Equipment.query.order_by(Equipment.name).all()
    return render_template("stock_sell.html", equipment=equipment)


@bp.route("/adjust", methods=["GET", "POST"])
def adjust():
    """Manual stock adjustment (e.g. damaged, lost, counted)."""
    if request.method == "POST":
        equipment_id = int(request.form.get("equipment_id"))
        new_qty = int(request.form.get("new_quantity"))
        reason = request.form.get("reason", "Manual adjustment").strip()
        extra_notes = request.form.get("notes", "").strip()
        full_notes = f"{reason}: {extra_notes}" if extra_notes else reason

        item = Equipment.query.get_or_404(equipment_id)
        diff = new_qty - item.current_stock
        item.current_stock = new_qty

        movement = StockMovement(
            equipment_id=equipment_id,
            movement_type="adjustment",
            quantity=diff,
            notes=full_notes,
            reference="Manual count",
            performed_by=request.form.get("performed_by", "Staff"),
        )
        db.session.add(movement)
        db.session.commit()
        flash(f'Stock for "{item.name}" adjusted to {new_qty} ({"+" if diff >= 0 else ""}{diff}).', "success")
        return redirect(url_for("dashboard.index"))

    equipment = Equipment.query.order_by(Equipment.name).all()
    return render_template("stock_adjust.html", equipment=equipment)


@bp.route("/movements")
def movements():
    """Full activity log."""
    page = request.args.get("page", 1, type=int)
    movement_type = request.args.get("type", "")
    search = request.args.get("q", "")

    query = StockMovement.query
    if movement_type:
        query = query.filter(StockMovement.movement_type == movement_type)
    if search:
        query = query.join(Equipment).filter(
            Equipment.name.ilike(f"%{search}%") | StockMovement.reference.ilike(f"%{search}%")
        )

    movements_page = (
        query.order_by(StockMovement.created_at.desc()).paginate(page=page, per_page=25)
    )
    return render_template(
        "movements.html",
        movements=movements_page,
        movement_type=movement_type,
        search=search,
    )


@bp.route("/api/equipment/<int:item_id>")
def api_equipment_detail(item_id):
    item = Equipment.query.get_or_404(item_id)
    return jsonify(item.to_dict())
