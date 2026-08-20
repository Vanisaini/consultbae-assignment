import os
import re
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "database.db")

NAUKRI_FILE = os.path.join(
    BASE_DIR, "data", "source1_naukri_applicants.csv"
)

GIG_FILE = os.path.join(
    BASE_DIR, "data", "source2_gig_workers.csv"
)

CBNEXUS_FILE = os.path.join(
    BASE_DIR, "data", "source3_cbnexus_contacts.csv"
)


def clean_text(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def normalize_name(value):
    value = clean_text(value)

    if not value:
        return None

    return " ".join(value.lower().split()).title()


def normalize_email(value):
    value = clean_text(value)

    if not value:
        return None

    return value.lower()


def normalize_phone(value):
    value = clean_text(value)

    if not value:
        return None

    phone = re.sub(r"\D", "", value)

    # Keep last 10 digits for Indian phone numbers
    if len(phone) > 10:
        phone = phone[-10:]

    return phone


def normalize_city(value):
    value = clean_text(value)

    if not value:
        return None

    city = value.lower().strip()

    city_mapping = {
        "gurgaon": "Gurugram",
        "gurugram": "Gurugram",
        "new delhi": "Delhi",
        "delhi": "Delhi",
        "delhi ncr": "Delhi NCR",
        "pune": "Pune",
        "noida": "Noida",
        "bengaluru": "Bengaluru",
        "bangalore": "Bengaluru",
    }

    return city_mapping.get(city, city.title())


def normalize_status(value):
    value = clean_text(value)

    if not value:
        return None

    return value.lower()


def normalize_verified(value):
    value = clean_text(value)

    if not value:
        return None

    value = value.lower()

    yes_values = {"y", "yes", "true", "1"}
    no_values = {"n", "no", "false", "0"}

    if value in yes_values:
        return 1

    if value in no_values:
        return 0

    return None


def normalize_date(value):
    value = clean_text(value)

    if not value:
        return None

    parsed = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed):
        return value

    return parsed.strftime("%Y-%m-%d")


def merge_skills(existing, new):
    if not existing:
        return clean_text(new)

    if not new:
        return existing

    existing_list = [
        x.strip() for x in existing.split(",") if x.strip()
    ]

    new_list = [
        x.strip() for x in str(new).split(",") if x.strip()
    ]

    combined = {}

    for skill in existing_list + new_list:
        key = skill.lower()
        combined[key] = skill.lower()

    return ", ".join(combined.values())


def find_existing_person(cursor, email=None, phone=None):
    if email:
        cursor.execute(
            "SELECT * FROM people WHERE lower(email) = lower(?)",
            (email,),
        )

        result = cursor.fetchone()

        if result:
            return result

    if phone:
        cursor.execute(
            "SELECT * FROM people WHERE phone = ?",
            (phone,),
        )

        result = cursor.fetchone()

        if result:
            return result

    return None


def insert_person(cursor, person):
    cursor.execute(
        """
        INSERT INTO people (
            name,
            email,
            phone,
            city,
            skills,
            experience_years,
            current_ctc,
            applied_date,
            gig_rate,
            gig_status,
            verified,
            projects_completed,
            source_naukri,
            source_gig,
            source_cbnexus
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            person.get("name"),
            person.get("email"),
            person.get("phone"),
            person.get("city"),
            person.get("skills"),
            person.get("experience_years"),
            person.get("current_ctc"),
            person.get("applied_date"),
            person.get("gig_rate"),
            person.get("gig_status"),
            person.get("verified"),
            person.get("projects_completed"),
            person.get("source_naukri", 0),
            person.get("source_gig", 0),
            person.get("source_cbnexus", 0),
        ),
    )


def update_person(cursor, person_id, existing, new_data):
    existing_skills = existing["skills"]

    merged_skills = merge_skills(
        existing_skills,
        new_data.get("skills"),
    )

    cursor.execute(
        """
        UPDATE people
        SET
            name = COALESCE(name, ?),
            email = COALESCE(email, ?),
            phone = COALESCE(phone, ?),
            city = COALESCE(city, ?),
            skills = ?,
            experience_years = COALESCE(experience_years, ?),
            current_ctc = COALESCE(current_ctc, ?),
            applied_date = COALESCE(applied_date, ?),
            gig_rate = COALESCE(gig_rate, ?),
            gig_status = COALESCE(gig_status, ?),
            verified = COALESCE(verified, ?),
            projects_completed = COALESCE(projects_completed, ?),
            source_naukri = MAX(source_naukri, ?),
            source_gig = MAX(source_gig, ?),
            source_cbnexus = MAX(source_cbnexus, ?)
        WHERE id = ?
        """,
        (
            new_data.get("name"),
            new_data.get("email"),
            new_data.get("phone"),
            new_data.get("city"),
            merged_skills,
            new_data.get("experience_years"),
            new_data.get("current_ctc"),
            new_data.get("applied_date"),
            new_data.get("gig_rate"),
            new_data.get("gig_status"),
            new_data.get("verified"),
            new_data.get("projects_completed"),
            new_data.get("source_naukri", 0),
            new_data.get("source_gig", 0),
            new_data.get("source_cbnexus", 0),
            person_id,
        ),
    )


def upsert_person(cursor, person):
    existing = find_existing_person(
        cursor,
        email=person.get("email"),
        phone=person.get("phone"),
    )

    if existing:
        update_person(
            cursor,
            existing["id"],
            existing,
            person,
        )

        return "updated"

    insert_person(cursor, person)

    return "inserted"


def load_naukri(cursor):
    df = pd.read_csv(NAUKRI_FILE)

    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        person = {
            "name": normalize_name(row["Full Name"]),
            "email": normalize_email(row["Email"]),
            "phone": normalize_phone(row["Phone"]),
            "city": normalize_city(row["City"]),
            "skills": clean_text(row["Skills"]),
            "experience_years": row["Experience (Years)"]
            if pd.notna(row["Experience (Years)"])
            else None,
            "current_ctc": row["Current CTC"]
            if pd.notna(row["Current CTC"])
            else None,
            "applied_date": normalize_date(row["Applied Date"]),
            "source_naukri": 1,
        }

        result = upsert_person(cursor, person)

        if result == "inserted":
            inserted += 1
        else:
            updated += 1

    print(
        f"Naukri: {inserted} inserted, {updated} updated"
    )


def load_gig(cursor):
    df = pd.read_csv(GIG_FILE)

    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        person = {
            "name": normalize_name(row["worker_name"]),
            "email": normalize_email(row["email_id"]),
            "phone": None,
            "city": normalize_city(row["location"]),
            "skills": clean_text(row["skill_tags"]),
            "gig_rate": clean_text(row["rate"]),
            "gig_status": normalize_status(row["status"]),
            "source_gig": 1,
        }

        result = upsert_person(cursor, person)

        if result == "inserted":
            inserted += 1
        else:
            updated += 1

    print(
        f"Gig: {inserted} inserted, {updated} updated"
    )


def load_cbnexus(cursor):
    df = pd.read_csv(CBNEXUS_FILE)

    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        projects = pd.to_numeric(
            row["Projects Completed"],
            errors="coerce",
        )

        person = {
            "name": normalize_name(row["Name"]),
            "email": None,
            "phone": normalize_phone(row["Phone Number"]),
            "city": normalize_city(row["City"]),
            "verified": normalize_verified(row["Verified"]),
            "projects_completed": int(projects)
            if pd.notna(projects)
            else None,
            "source_cbnexus": 1,
        }

        result = upsert_person(cursor, person)

        if result == "inserted":
            inserted += 1
        else:
            updated += 1

    print(
        f"CBNexus: {inserted} inserted, {updated} updated"
    )


def main():
    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    # Makes the script safe to run again while developing
    cursor.execute("DELETE FROM people")
    cursor.execute(
        "DELETE FROM sqlite_sequence WHERE name = 'people'"
    )

    load_naukri(cursor)
    load_gig(cursor)
    load_cbnexus(cursor)

    connection.commit()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM people"
    )

    total = cursor.fetchone()["total"]

    print("-----------------------------")
    print(f"Final unique people: {total}")
    print("Merge completed successfully.")

    connection.close()


if __name__ == "__main__":
    main()