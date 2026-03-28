from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Equipment(db.Model):
    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(100), default="General")
    unit = db.Column(db.String(50), default="unit")
    current_stock = db.Column(db.Integer, default=0)
    reserved_stock = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=5)
    location = db.Column(db.String(100), default="")
    xero_item_code = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = db.relationship("StockMovement", backref="equipment", lazy=True, cascade="all, delete-orphan")
    xero_orders = db.relationship("XeroOrder", backref="equipment", lazy=True)

    @property
    def available_stock(self):
        return max(0, self.current_stock - self.reserved_stock)

    @property
    def stock_status(self):
        if self.current_stock <= 0:
            return "out_of_stock"
        elif self.current_stock <= self.min_stock_level:
            return "low_stock"
        else:
            return "in_stock"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "description": self.description,
            "category": self.category,
            "unit": self.unit,
            "current_stock": self.current_stock,
            "reserved_stock": self.reserved_stock,
            "available_stock": self.available_stock,
            "min_stock_level": self.min_stock_level,
            "location": self.location,
            "stock_status": self.stock_status,
        }


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=False)
    movement_type = db.Column(db.String(50), nullable=False)  # received, sold, adjustment, xero_sync, reserved, unreserved
    quantity = db.Column(db.Integer, nullable=False)  # positive = in, negative = out
    notes = db.Column(db.Text, default="")
    reference = db.Column(db.String(200), default="")  # Xero invoice/PO number or client name
    performed_by = db.Column(db.String(100), default="Staff")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "equipment_id": self.equipment_id,
            "equipment_name": self.equipment.name if self.equipment else "",
            "movement_type": self.movement_type,
            "quantity": self.quantity,
            "notes": self.notes,
            "reference": self.reference,
            "performed_by": self.performed_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class XeroOrder(db.Model):
    __tablename__ = "xero_orders"

    id = db.Column(db.Integer, primary_key=True)
    xero_invoice_id = db.Column(db.String(200), default="")
    invoice_number = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(200), default="")
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=True)
    item_description = db.Column(db.String(300), default="")
    quantity_ordered = db.Column(db.Integer, default=0)
    quantity_received = db.Column(db.Integer, default=0)
    unit_price = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default="pending")  # pending, partially_received, received
    invoice_date = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def quantity_outstanding(self):
        return max(0, self.quantity_ordered - self.quantity_received)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "contact_name": self.contact_name,
            "item_description": self.item_description,
            "quantity_ordered": self.quantity_ordered,
            "quantity_received": self.quantity_received,
            "quantity_outstanding": self.quantity_outstanding,
            "unit_price": self.unit_price,
            "status": self.status,
            "invoice_date": self.invoice_date.strftime("%Y-%m-%d") if self.invoice_date else "",
        }


class XeroToken(db.Model):
    __tablename__ = "xero_tokens"

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.Float, nullable=False)
    tenant_id = db.Column(db.String(200), nullable=False)
    tenant_name = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
