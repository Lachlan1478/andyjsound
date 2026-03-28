from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.database import db, Equipment, StockMovement
from datetime import datetime

bp = Blueprint("equipment", __name__, url_prefix="/equipment")

CATEGORIES = [
    "Speakers", "Amplifiers", "Microphones", "Mixers", "Lighting",
    "Cables & Leads", "Stands & Mounts", "DJ Equipment", "Recording",
    "Effects & Processing", "Transport & Cases", "General"
]


@bp.route("/")
def list_equipment():
    category_filter = request.args.get("category", "")
    status_filter = request.args.get("status", "")
    search = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")

    query = Equipment.query
    if search:
        query = query.filter(
            Equipment.name.ilike(f"%{search}%") | Equipment.sku.ilike(f"%{search}%")
        )
    if category_filter:
        query = query.filter(Equipment.category == category_filter)
    if status_filter == "low":
        query = query.filter(Equipment.current_stock > 0, Equipment.current_stock <= Equipment.min_stock_level)
    elif status_filter == "out":
        query = query.filter(Equipment.current_stock <= 0)
    elif status_filter == "ok":
        query = query.filter(Equipment.current_stock > Equipment.min_stock_level)

    sort_map = {
        "name": Equipment.name,
        "stock": Equipment.current_stock,
        "min": Equipment.min_stock_level,
        "location": Equipment.location,
        "category": Equipment.category,
    }
    sort_col = sort_map.get(sort, Equipment.name)
    order_expr = sort_col.desc() if direction == "desc" else sort_col.asc()

    pagination = query.order_by(order_expr).paginate(page=page, per_page=20, error_out=False)

    categories = db.session.query(Equipment.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]

    return render_template(
        "equipment.html",
        items=pagination.items,
        pagination=pagination,
        categories=categories,
        all_categories=CATEGORIES,
        current_category=category_filter,
        current_status=status_filter,
        search=search,
        sort=sort,
        direction=direction,
    )


@bp.route("/add", methods=["GET", "POST"])
def add_equipment():
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        if Equipment.query.filter_by(sku=sku).first():
            flash("SKU already exists. Please use a unique SKU.", "error")
            return redirect(url_for("equipment.add_equipment"))

        item = Equipment(
            name=request.form.get("name", "").strip(),
            sku=sku,
            description=request.form.get("description", "").strip(),
            category=request.form.get("category", "General"),
            unit=request.form.get("unit", "unit"),
            current_stock=int(request.form.get("current_stock", 0)),
            min_stock_level=int(request.form.get("min_stock_level", 5)),
            location=request.form.get("location", "").strip(),
            xero_item_code=request.form.get("xero_item_code", "").strip(),
        )
        db.session.add(item)
        db.session.flush()

        if item.current_stock > 0:
            movement = StockMovement(
                equipment_id=item.id,
                movement_type="adjustment",
                quantity=item.current_stock,
                notes="Initial stock entry",
                performed_by="System",
            )
            db.session.add(movement)

        db.session.commit()
        flash(f'"{item.name}" added successfully.', "success")
        return redirect(url_for("equipment.list_equipment"))

    return render_template("equipment_form.html", item=None, categories=CATEGORIES, action="add")


@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
def edit_equipment(item_id):
    item = Equipment.query.get_or_404(item_id)

    if request.method == "POST":
        item.name = request.form.get("name", "").strip()
        item.description = request.form.get("description", "").strip()
        item.category = request.form.get("category", "General")
        item.unit = request.form.get("unit", "unit")
        item.min_stock_level = int(request.form.get("min_stock_level", 5))
        item.location = request.form.get("location", "").strip()
        item.xero_item_code = request.form.get("xero_item_code", "").strip()
        db.session.commit()
        flash(f'"{item.name}" updated successfully.', "success")
        return redirect(url_for("equipment.list_equipment"))

    return render_template("equipment_form.html", item=item, categories=CATEGORIES, action="edit")


@bp.route("/<int:item_id>/delete", methods=["POST"])
def delete_equipment(item_id):
    item = Equipment.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'"{name}" deleted.', "info")
    return redirect(url_for("equipment.list_equipment"))


@bp.route("/<int:item_id>")
def detail(item_id):
    item = Equipment.query.get_or_404(item_id)
    movements = (
        StockMovement.query.filter_by(equipment_id=item_id)
        .order_by(StockMovement.created_at.desc())
        .limit(30)
        .all()
    )
    return render_template("equipment_detail.html", item=item, movements=movements)
