import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.entities import Settlement, SettlementFeatureIndex


def fixture_settlements() -> list[dict]:
    rows = [
        {
            "title": "Google Play Store Antitrust Settlement",
            "required_features": ["merchant:google"],
            "states": [],
            "summary_text": "Settlement alleging Google monopolized Android app distribution and in-app billing through Google Play.",
            "eligibility_text": "U.S. consumers who made eligible Google Play purchases during the covered period may qualify for compensation.",
            "deadline": "2026-02-19T23:59:00+00:00",
            "payout_min_cents": 200,
            "payout_max_cents": 50000,
            "website_url": "https://googleplaystateaglitigation.com/",
            "claim_url": "https://googleplaystateaglitigation.com/",
            "tags": ["antitrust", "app-store", "billing"],
        },
        {
            "title": "23andMe Data Breach Settlement",
            "required_features": ["merchant:23andme"],
            "states": [],
            "summary_text": "Data-breach settlement related to unauthorized access to 23andMe customer data.",
            "eligibility_text": "Notified users from covered breach windows may submit claims for documented losses and identity monitoring.",
            "deadline": "2026-02-17T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 1000000,
            "website_url": "https://23andmedatasettlement.com/",
            "claim_url": "https://23andmedatasettlement.com/",
            "tags": ["privacy", "data-breach", "identity-theft"],
        },
        {
            "title": "Lemonaid Health Privacy Settlement",
            "required_features": ["merchant:lemonaid"],
            "states": [],
            "summary_text": "Privacy settlement involving alleged third-party tracking on Lemonaid Health properties.",
            "eligibility_text": "Users who visited covered digital properties in the class period may file for cash benefits.",
            "deadline": "2026-02-23T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 20000,
            "website_url": "https://lemonaidpixelsettlement.com/",
            "claim_url": "https://lemonaidpixelsettlement.com/",
            "tags": ["privacy", "healthcare", "tracking"],
        },
        {
            "title": "Kaiser Permanente TCPA Text Settlement",
            "required_features": ["merchant:kaiser"],
            "states": ["FL"],
            "summary_text": "TCPA settlement regarding allegedly non-compliant automated Kaiser text messages.",
            "eligibility_text": "Class members receiving covered text messages in the class period may claim per-message compensation.",
            "deadline": "2026-02-12T23:59:00+00:00",
            "payout_min_cents": 1000,
            "payout_max_cents": 7500,
            "website_url": "https://www.kaisertcpasettlement.com/",
            "claim_url": "https://www.kaisertcpasettlement.com/",
            "tags": ["tcpa", "text-message", "healthcare"],
        },
        {
            "title": "Tinder Age-Based Pricing Settlement",
            "required_features": ["merchant:tinder"],
            "states": ["CA"],
            "summary_text": "Settlement resolving age-based pricing allegations for Tinder premium subscriptions.",
            "eligibility_text": "California subscribers in covered age/date cohorts may qualify under settlement formulas.",
            "deadline": "2026-05-20T23:59:00+00:00",
            "payout_min_cents": 1000,
            "payout_max_cents": 30000,
            "website_url": "https://tinderclassaction.com/",
            "claim_url": "https://tinderclassaction.com/",
            "tags": ["subscription", "pricing", "consumer"],
        },
        {
            "title": "ZOA Energy False Advertising Settlement",
            "required_features": ["merchant:zoa"],
            "states": [],
            "summary_text": "False-advertising settlement over \"0 preservatives\" marketing for ZOA Energy drinks.",
            "eligibility_text": "Consumers purchasing covered ZOA products during the class period may submit claims.",
            "deadline": "2026-02-20T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 15000,
            "website_url": "https://zoasettlement.com/",
            "claim_url": "https://zoasettlement.com/",
            "tags": ["false-advertising", "food-drink", "labeling"],
        },
        {
            "title": "Ashley HomeStore Pricing Settlement",
            "required_features": ["merchant:ashley"],
            "states": ["CA"],
            "summary_text": "Settlement over allegedly misleading reference pricing practices at Ashley HomeStore.",
            "eligibility_text": "California purchasers in covered periods may claim voucher/cash-equivalent benefits.",
            "deadline": "2026-02-10T23:59:00+00:00",
            "payout_min_cents": 3500,
            "payout_max_cents": 20000,
            "website_url": "https://stoneledgefurnituresettlement.com/",
            "claim_url": "https://stoneledgefurnituresettlement.com/",
            "tags": ["pricing", "retail", "consumer"],
        },
        {
            "title": "Joybird Deceptive Discounts Settlement",
            "required_features": ["merchant:joybird"],
            "states": ["CA", "OR", "WA"],
            "summary_text": "Settlement concerning alleged deceptive discount/reference pricing for Joybird products.",
            "eligibility_text": "Eligible purchasers in covered states and dates may claim cash or credit.",
            "deadline": "2026-02-13T23:59:00+00:00",
            "payout_min_cents": 5000,
            "payout_max_cents": 11500,
            "website_url": "http://joybirdsettlement.com/",
            "claim_url": "http://joybirdsettlement.com/",
            "tags": ["pricing", "retail", "furniture"],
        },
        {
            "title": "Mid America Pet Food Recall Settlement",
            "required_features": ["merchant:mid_america_pet_food"],
            "states": [],
            "summary_text": "Settlement tied to recalled pet food products and associated reimbursement claims.",
            "eligibility_text": "Covered purchasers and owners with documented losses may submit claims for reimbursement.",
            "deadline": "2026-02-05T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 10000000,
            "website_url": "https://www.midamericapetfoodsettlement.com/",
            "claim_url": "https://www.midamericapetfoodsettlement.com/",
            "tags": ["product-recall", "pet-food", "consumer"],
        },
        {
            "title": "Rheem Drain Valve Settlement",
            "required_features": ["merchant:rheem"],
            "states": [],
            "summary_text": "Settlement involving allegedly defective Rheem water-heater drain valves.",
            "eligibility_text": "Owners of covered water heaters may claim valve replacement and documented property-loss reimbursement.",
            "deadline": "2026-03-20T23:59:00+00:00",
            "payout_min_cents": 1000,
            "payout_max_cents": 150000,
            "website_url": "https://www.rheemdrainvalvesettlement.com/",
            "claim_url": "https://www.rheemdrainvalvesettlement.com/",
            "tags": ["product-defect", "home", "water-heater"],
        },
        {
            "title": "McLaren Health Care Data Breach Settlement",
            "required_features": ["merchant:mclaren"],
            "states": [],
            "summary_text": "Healthcare data-breach settlement related to ransomware incidents affecting patient information.",
            "eligibility_text": "Notified impacted individuals may claim documented losses and monitoring benefits.",
            "deadline": "2026-04-21T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 500000,
            "website_url": "http://mhccsettlement.com/",
            "claim_url": "http://mhccsettlement.com/",
            "tags": ["healthcare", "data-breach", "privacy"],
        },
        {
            "title": "Numotion Data Breach Settlement",
            "required_features": ["merchant:numotion"],
            "states": [],
            "summary_text": "Settlement resolving claims around unauthorized access incidents at Numotion.",
            "eligibility_text": "Individuals with qualifying notices may seek documented-loss compensation and credit monitoring.",
            "deadline": "2026-03-18T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 1500000,
            "website_url": "http://numotionsettlement.com/",
            "claim_url": "http://numotionsettlement.com/",
            "tags": ["data-breach", "privacy", "identity-theft"],
        },
        {
            "title": "Kaiser Privacy Breach Settlement",
            "required_features": ["merchant:kaiser"],
            "states": ["CA", "CO", "GA", "HI", "MD", "OR", "VA", "WA", "DC"],
            "summary_text": "Privacy settlement over alleged sharing of Kaiser member web/app data with third parties.",
            "eligibility_text": "Members in covered geographies and periods may file claims under settlement terms.",
            "deadline": "2026-04-30T23:59:00+00:00",
            "payout_min_cents": 2000,
            "payout_max_cents": 4000,
            "website_url": "https://kaiserprivacysettlement.com/",
            "claim_url": "https://kaiserprivacysettlement.com/",
            "tags": ["privacy", "healthcare", "tracking"],
        },
        {
            "title": "OptumRx TCPA Calls Settlement",
            "required_features": ["merchant:optumrx"],
            "states": [],
            "summary_text": "TCPA settlement regarding prerecorded/artificial-voice clinical adherence calls by OptumRx.",
            "eligibility_text": "Recipients of covered calls during the class period may claim fixed cash amounts.",
            "deadline": "2026-02-04T23:59:00+00:00",
            "payout_min_cents": 7200,
            "payout_max_cents": 13500,
            "website_url": "https://optumrxtcpaclassactionsettlement.com/",
            "claim_url": "https://optumrxtcpaclassactionsettlement.com/",
            "tags": ["tcpa", "calls", "healthcare"],
        },
        {
            "title": "Wells Fargo Recurring Billing Settlement",
            "required_features": ["merchant:wells_fargo"],
            "states": [],
            "summary_text": "Settlement over alleged unauthorized recurring billing enrollments tied to designated entities.",
            "eligibility_text": "Eligible individuals enrolled during the covered period may file for flat/pro-rata cash benefits.",
            "deadline": "2026-03-04T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 2000,
            "website_url": "https://www.wfrecurringbillingsettlement.com/",
            "claim_url": "https://www.wfrecurringbillingsettlement.com/",
            "tags": ["financial-services", "billing", "consumer"],
        },
        {
            "title": "Westlake Pay-to-Pay Fee Settlement",
            "required_features": ["merchant:westlake"],
            "states": [],
            "summary_text": "Settlement involving alleged unlawful convenience fees on certain Westlake payments.",
            "eligibility_text": "Borrowers who paid covered convenience fees during the class period may submit claims.",
            "deadline": "2026-04-16T23:59:00+00:00",
            "payout_min_cents": 2000,
            "payout_max_cents": 6000,
            "website_url": "http://klarefeesettlement.com/",
            "claim_url": "http://klarefeesettlement.com/",
            "tags": ["fees", "auto-loan", "financial-services"],
        },
        {
            "title": "Hoosick Falls DuPont PFAS Settlement",
            "required_features": ["merchant:dupont"],
            "states": ["NY"],
            "summary_text": "PFAS contamination settlement related to Hoosick Falls water exposure allegations.",
            "eligibility_text": "Residents meeting exposure/testing criteria from covered years may seek compensation and benefits.",
            "deadline": "2026-02-11T23:59:00+00:00",
            "payout_min_cents": 10000,
            "payout_max_cents": 1000000,
            "website_url": "http://hoosickfallspfoasettlement.com/",
            "claim_url": "http://hoosickfallspfoasettlement.com/",
            "tags": ["pfas", "environmental", "water-contamination"],
        },
        {
            "title": "Delta Flight 89 Fuel Dump Settlement",
            "required_features": ["merchant:delta"],
            "states": ["CA"],
            "summary_text": "Settlement for claims arising from fuel dumping by Delta Flight 89 over Southern California.",
            "eligibility_text": "Property owners/residents in covered impact zones may file claims under allocation rules.",
            "deadline": "2026-02-06T23:59:00+00:00",
            "payout_min_cents": 5000,
            "payout_max_cents": 250000,
            "website_url": "https://dl89settlement.com/",
            "claim_url": "https://dl89settlement.com/",
            "tags": ["environmental", "airline", "property-damage"],
        },
        {
            "title": "Yahoo Data Breach Settlement",
            "required_features": ["merchant:yahoo"],
            "states": [],
            "summary_text": "Settlement linked to large-scale Yahoo account security incidents and related damages claims.",
            "eligibility_text": "Users impacted by covered Yahoo data incidents could claim cash and monitoring benefits.",
            "deadline": "2020-07-20T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 35800,
            "website_url": "https://yahoodatabreachsettlement.com/",
            "claim_url": "https://yahoodatabreachsettlement.com/",
            "tags": ["data-breach", "email", "privacy"],
        },
        {
            "title": "Facebook User Privacy Settlement",
            "required_features": ["merchant:meta"],
            "states": [],
            "summary_text": "Settlement resolving privacy claims tied to alleged Facebook user-data sharing practices.",
            "eligibility_text": "U.S. Facebook users in covered periods were eligible for pro-rata cash distributions.",
            "deadline": "2023-08-25T23:59:00+00:00",
            "payout_min_cents": 500,
            "payout_max_cents": 30000,
            "website_url": "https://www.facebookuserprivacysettlement.com/",
            "claim_url": "https://www.facebookuserprivacysettlement.com/",
            "tags": ["privacy", "social-media", "data-sharing"],
        },
    ]

    settlements: list[dict] = []
    for row in rows:
        deadline = datetime.fromisoformat(row["deadline"]).astimezone(UTC)
        settlements.append(
            {
                "title": row["title"],
                "required_features": row["required_features"],
                "states": row["states"],
                "summary_text": row["summary_text"],
                "eligibility_text": row["eligibility_text"],
                "deadline": deadline,
                "payout_min_cents": row["payout_min_cents"],
                "payout_max_cents": row["payout_max_cents"],
                "website_url": row["website_url"],
                "claim_url": row["claim_url"],
                "tags": row["tags"],
            }
        )
    return settlements


def main() -> None:
    db = SessionLocal()
    try:
        rows = fixture_settlements()
        keep_titles = {row["title"] for row in rows}

        existing_settlements = db.scalars(select(Settlement)).all()
        for existing in existing_settlements:
            if existing.title not in keep_titles:
                db.execute(
                    delete(SettlementFeatureIndex).where(SettlementFeatureIndex.settlement_id == existing.id)
                )
                db.delete(existing)
        db.flush()

        for row in rows:
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
