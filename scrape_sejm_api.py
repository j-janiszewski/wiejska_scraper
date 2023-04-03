import requests
from models import Member, Politician, Club, Transfer
from sqlalchemy.sql.functions import now

from config import db_session, send_notification


API_URL = "http://api.sejm.gov.pl/sejm/term"

# getting active term
terms = requests.get(API_URL).json()
current_term = [term["num"] for term in terms if term["current"]][0]

# connecting to db
session = db_session(create_tables=True)


# checking if new clubs appeared
clubs = requests.get(API_URL + f"{current_term}/clubs").json()
for club in clubs:
    existing_club = (
        session.query(Club).filter_by(id=club["id"], term=current_term).first()
    )
    if existing_club is None:  # adding new Club
        session.add(Club(id=club["id"], name=club["name"], term=current_term))
    elif existing_club.name != club["name"]:  # Existing club has new name
        existing_club.name = club["name"]


members = requests.get(API_URL + f"{current_term}/MP").json()

for member in members:
    existing_member = (
        session.query(Member).filter_by(id=member["id"], term=current_term).first()
    )
    if existing_member is not None:
        if existing_member.club_id != member["club"]:
            # Someone left club, adding new Transfer
            new_transfer = Transfer(
                term=current_term,
                card_id=existing_member.id,
                date=now(),
                left=existing_member.club_id,
                joined=member["club"],
            )
            session.add(new_transfer)
            existing_member.club_id = member["club"]
        if existing_member.is_active != member["active"]:
            # Someone stopped being active parliament member
            existing_member.is_active = member["active"]
    else:
        # New member in parliament
        new_member = Member(
            id=member["id"],
            term=current_term,
            is_active=member["active"],
            district_name=member["districtName"],
            district_num=member["districtNum"],
            voivodeship=member["voivodeship"],
            club_id=member["club"],
        )
        existing_politician = (
            session.query(Politician)
            .filter_by(
                first_name=member["firstName"],
                second_name=member.get("secondName", None),
                last_name=member["lastName"],
            )
            .first()
        )
        if existing_politician is None:
            # New member is new politician also
            new_politician = Politician(
                first_name=member["firstName"],
                second_name=member.get("secondName", None),
                last_name=member["lastName"],
            )
            send_notification(
                "WIEJSKA ONLINE: New politician appared",
                f"Check if {new_politician.first_name} {new_politician.last_name} from {new_member.club_id} has twitter account.",
            )

            new_member.politician = new_politician
        else:
            # New member already is present in politicians table
            new_member.politician = existing_politician
        session.add(new_member)

try:
    session.commit()
except:
    session.rollback()
session.close()
