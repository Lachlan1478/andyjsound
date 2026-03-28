from flask import Blueprint, render_template, jsonify
from sqlalchemy import func
from models.database import db, Equipment, StockMovement, XeroOrder, XeroToken
from datetime import datetime, timedelta

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    total_items = Equipment.query.count()
    out_of_stock = Equipment.query.filter(Equipment.current_stock <= 0).count()
    low_stock = Equipment.query.filter(
        Equipment.current_stock > 0,
        Equipment.current_stock <= Equipment.min_stock_level,
    ).count()
    in_stock = Equipment.query.filter(Equipment.current_stock > Equipment.min_stock_level).count()

    # Recent movements (last 10)
    recent_movements = (
        StockMovement.query.order_by(StockMovement.created_at.desc()).limit(10).all()
    )

    # Pending Xero orders
    pending_orders = XeroOrder.query.filter(XeroOrder.status != "received").count()

    # Low stock items
    low_stock_items = (
        Equipment.query.filter(Equipment.current_stock <= Equipment.min_stock_level)
        .order_by(Equipment.current_stock.asc())
        .limit(8)
        .all()
    )

    # Category breakdown
    categories = (
        db.session.query(Equipment.category, func.count(Equipment.id))
        .group_by(Equipment.category)
        .all()
    )

    # Movement stats for last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    received_week = (
        db.session.query(func.sum(StockMovement.quantity))
        .filter(
            StockMovement.movement_type == "received",
            StockMovement.created_at >= week_ago,
        )
        .scalar()
        or 0
    )
    sold_week = (
        db.session.query(func.sum(StockMovement.quantity))
        .filter(
            StockMovement.movement_type == "sold",
            StockMovement.created_at >= week_ago,
        )
        .scalar()
        or 0
    )

    xero_connected = XeroToken.query.first() is not None

    return render_template(
        "dashboard.html",
        total_items=total_items,
        out_of_stock=out_of_stock,
        low_stock=low_stock,
        in_stock=in_stock,
        recent_movements=recent_movements,
        pending_orders=pending_orders,
        low_stock_items=low_stock_items,
        categories=categories,
        received_week=received_week,
        sold_week=abs(sold_week),
        xero_connected=xero_connected,
    )


@bp.route("/api/stats")
def api_stats():
    total_items = Equipment.query.count()
    out_of_stock = Equipment.query.filter(Equipment.current_stock <= 0).count()
    low_stock = Equipment.query.filter(
        Equipment.current_stock > 0,
        Equipment.current_stock <= Equipment.min_stock_level,
    ).count()

    return jsonify({
        "total_items": total_items,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
    })
