"""Andy J Sound — Warehouse Stock Dashboard."""

import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from models.database import db

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    db_url = os.environ.get("DATABASE_URL", "sqlite:///warehouse.db")
    # Railway provides postgres:// but SQLAlchemy 2.x requires postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from routes import dashboard, equipment, stock, xero
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(equipment.bp)
    app.register_blueprint(stock.bp)
    app.register_blueprint(xero.bp)

    with app.app_context():
        db.create_all()
        _seed_demo_data()

    return app


def _seed_demo_data():
    """Seed some realistic AV equipment if DB is empty."""
    from models.database import Equipment, StockMovement
    if Equipment.query.count() > 0:
        return

    demo_equipment = [
        ("QSC K12.2 Active Speaker", "QSC-K122", "Speakers", 12, 6, 3, "Bay A1"),
        ("Yamaha DXR15 Speaker", "YAM-DXR15", "Speakers", 6, 4, 2, "Bay A2"),
        ("Soundcraft Signature 22 Mixer", "SND-SIG22", "Mixers", 3, 2, 1, "Rack Room"),
        ("Behringer X32 Digital Mixer", "BEH-X32", "Mixers", 2, 1, 1, "Rack Room"),
        ("Shure SM58 Microphone", "SHR-SM58", "Microphones", 25, 20, 8, "Mic Shelf"),
        ("Shure Beta 52A Kick Mic", "SHR-B52A", "Microphones", 8, 6, 4, "Mic Shelf"),
        ("Crown XTi 4002 Amplifier", "CRW-XTI4002", "Amplifiers", 5, 3, 2, "Amp Rack"),
        ("QSC RMX 2450 Amplifier", "QSC-RMX2450", "Amplifiers", 4, 2, 2, "Amp Rack"),
        ("Chauvet DJ Freedom Par H9 IP", "CHV-FPH9", "Lighting", 16, 12, 4, "Lighting Bay"),
        ("Elation ELAR 108 LED PAR", "ELA-108", "Lighting", 2, 8, 4, "Lighting Bay"),
        ("XLR Cable 10m", "CBL-XLR10", "Cables & Leads", 45, 30, 10, "Cable Wall"),
        ("XLR Cable 20m", "CBL-XLR20", "Cables & Leads", 20, 15, 5, "Cable Wall"),
        ("Speakon NL4 Cable 10m", "CBL-SPK10", "Cables & Leads", 18, 12, 5, "Cable Wall"),
        ("K&M 210/9 Microphone Stand", "KM-2109", "Stands & Mounts", 22, 15, 5, "Stand Bay"),
        ("K&M 19612 Speaker Stand", "KM-19612", "Stands & Mounts", 10, 6, 3, "Stand Bay"),
        ("Pioneer CDJ-3000", "PIO-CDJ3000", "DJ Equipment", 4, 2, 2, "DJ Corner"),
        ("Pioneer DJM-900NXS2", "PIO-DJM900", "DJ Equipment", 3, 1, 1, "DJ Corner"),
        ("Sennheiser EW 100 G4 Wireless", "SEN-EW100G4", "Microphones", 6, 4, 2, "Mic Shelf"),
        ("dbx DriveRack PA2", "DBX-DRPA2", "Effects & Processing", 4, 3, 1, "Rack Room"),
        ("Road Case 4U Rack", "CASE-4U", "Transport & Cases", 8, 5, 2, "Case Storage"),
    ]

    for name, sku, cat, stock, min_stock, reserved, loc in demo_equipment:
        item = Equipment(
            name=name,
            sku=sku,
            category=cat,
            current_stock=stock,
            min_stock_level=min_stock,
            reserved_stock=reserved,
            location=loc,
        )
        db.session.add(item)
        db.session.flush()

        # Opening stock movement
        movement = StockMovement(
            equipment_id=item.id,
            movement_type="adjustment",
            quantity=stock,
            notes="Opening stock",
            reference="Initial setup",
            performed_by="System",
        )
        db.session.add(movement)

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5050)
