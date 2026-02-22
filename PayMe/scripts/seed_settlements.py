import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.entities import Settlement, SettlementFeatureIndex


def fixture_settlements() -> list[dict]:
    now = datetime.now(UTC)
    settlements = []
    rows = [
        ("Amazon Prime Renewal Fee Dispute", ["merchant:amazon", "subscription:prime"], ["CA", "NY", "NJ"]),
        ("Uber Surge Pricing Transparency Settlement", ["merchant:uber"], ["CA", "IL", "NY"]),
        ("AT&T Hidden Fee Billing Settlement", ["merchant:at&t"], ["TX", "FL", "NY"]),
        ("Paramount+ Auto-Billing Settlement", ["merchant:paramount", "subscription:paramount_plus"], ["CA", "NY"]),
        ("Meta In-App Purchase Refund Settlement", ["merchant:meta"], []),
        ("Coca-Cola Labeling Claims Settlement", ["merchant:coca-cola"], ["CA", "WA"]),
        ("TikTok Data Sharing Consumer Settlement", ["merchant:tiktok"], []),
        ("Poppy Delivery Membership Settlement", ["merchant:poppy"], ["NY", "NJ"]),
        ("Walmart Receipt Accuracy Settlement", ["merchant:walmart"], []),
        ("Streaming Bundle Cancellation Settlement", ["subscription:paramount_plus"], ["CA", "MA", "NY"]),
        ("Mobile Carrier Billing Consent Settlement", ["merchant:at&t"], ["CA", "TX"]),
        ("Rideshare Driver Fee Disclosure Settlement", ["merchant:uber"], ["NY", "CA"]),
        ("Online Marketplace Subscription Settlement", ["merchant:amazon"], ["FL", "NY"]),
        ("Retail Coupon Misrepresentation Settlement", ["merchant:walmart"], ["PA", "NJ"]),
        ("Social Platform Ad Disclosure Settlement", ["merchant:meta"], []),
        ("Beverage Health Claims Settlement", ["merchant:coca-cola"], ["CA", "OR"]),
        ("Short Video Commerce Billing Settlement", ["merchant:tiktok"], ["NY", "CA"]),
        ("Grocery Loyalty Program Settlement", ["merchant:walmart"], []),
        ("Cloud Photo Privacy Settlement", ["merchant:meta"], ["IL", "TX"]),
        ("Entertainment Service Renewal Settlement", ["subscription:paramount_plus"], ["CA", "NY", "WA"]),
    ]
    for idx, (title, features, states) in enumerate(rows):
        settlements.append(
            {
                "title": title,
                "required_features": features,
                "states": states,
                "summary_text": f"{title} addresses consumer harm involving billing, disclosures, and refunds.",
                "eligibility_text": "Consumers may qualify if they purchased or subscribed during the covered period and can provide supporting records.",
                "deadline": now + timedelta(days=30 + idx * 7),
                "payout_min_cents": 500 + idx * 20,
                "payout_max_cents": 15000 + idx * 50,
                "website_url": "https://example.com/settlements",
                "claim_url": "https://example.com/settlements/claim",
                "tags": ["consumer", "billing", "class-action"],
            }
        )
    return settlements


def main() -> None:
    db = SessionLocal()
    try:
        for row in fixture_settlements():
            settlement = db.scalar(select(Settlement).where(Settlement.title == row["title"]))
            if not settlement:
                settlement = Settlement(id=uuid.uuid4(), title=row["title"], status="open")
                db.add(settlement)
                db.flush()
            settlement.status = "open"
            settlement.website_url = row["website_url"]
            settlement.claim_url = row["claim_url"]
            settlement.deadline = row["deadline"]
            settlement.payout_min_cents = row["payout_min_cents"]
            settlement.payout_max_cents = row["payout_max_cents"]
            settlement.eligibility_predicates = {
                "required_features": row["required_features"],
                "states": row["states"],
            }
            settlement.covered_brands = [x.replace("merchant:", "") for x in row["required_features"]]
            settlement.tags = row["tags"]
            settlement.summary_text = row["summary_text"]
            settlement.eligibility_text = row["eligibility_text"]

            db.execute(
                delete(SettlementFeatureIndex).where(SettlementFeatureIndex.settlement_id == settlement.id)
            )
            for feature in row["required_features"]:
                db.add(
                    SettlementFeatureIndex(
                        settlement_id=settlement.id,
                        feature_key=feature,
                        feature_kind="required",
                    )
                )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
