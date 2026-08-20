import os
import sqlite3
import uuid
import wave
import math
import audioop

import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="GigVoice",
    page_icon="🎙️",
    layout="centered",
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DB_PATH = os.path.join(
    BASE_DIR,
    "database.db"
)

UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 850px;
        padding-top: 2.5rem;
        padding-bottom: 4rem;
    }

    .hero {
        text-align: center;
        padding: 1rem 0 1.5rem 0;
    }

    .hero h1 {
        font-size: 2.7rem;
        margin-bottom: 0.2rem;
    }

    .hero p {
        color: #9ca3af;
        font-size: 1.05rem;
    }

    .info-box {
        padding: 1rem 1.2rem;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 12px;
        margin-bottom: 1.5rem;
        background: rgba(255,255,255,0.03);
        line-height: 1.8;
    }

    div.stButton > button {
        width: 100%;
        height: 3rem;
        border-radius: 10px;
        font-weight: 600;
    }

    div[data-testid="stFormSubmitButton"] button {
        width: 100%;
        height: 3rem;
        border-radius: 10px;
        font-weight: 600;
    }

    [data-testid="stFileUploader"] {
        border-radius: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA busy_timeout = 30000;"
    )

    return connection


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database():

    connection = get_connection()

    try:

        # WAL reduces many SQLite locking problems.
        connection.execute(
            "PRAGMA journal_mode=WAL;"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audio_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                file_path TEXT NOT NULL,
                duration REAL,
                sample_rate_khz REAL,
                bitrate INTEGER,
                loudness_db REAL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (person_id)
                    REFERENCES people(id)
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


initialize_database()


# ============================================================
# PHONE NORMALIZATION
# ============================================================

def normalize_phone(phone):

    cleaned_phone = "".join(
        character
        for character in str(phone)
        if character.isdigit()
    )

    # If country code exists, keep final 10 digits.
    if len(cleaned_phone) > 10:
        cleaned_phone = cleaned_phone[-10:]

    return cleaned_phone


# ============================================================
# FIND / CREATE PERSON
# ============================================================

def find_or_create_person(name, phone):

    phone = normalize_phone(phone)

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # First try phone match.
        cursor.execute(
            """
            SELECT id, name, phone
            FROM people
            WHERE phone = ?
            LIMIT 1
            """,
            (phone,)
        )

        person = cursor.fetchone()

        if person:

            return person["id"], False

        # No person found -> create one.
        cursor.execute(
            """
            INSERT INTO people (
                name,
                phone
            )
            VALUES (?, ?)
            """,
            (
                name.strip(),
                phone
            )
        )

        person_id = cursor.lastrowid

        connection.commit()

        return person_id, True

    finally:
        connection.close()


# ============================================================
# SAVE AUDIO SUBMISSION
# ============================================================

def save_audio_submission(
    person_id,
    name,
    phone,
    file_path,
    metadata
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO audio_submissions (
                person_id,
                name,
                phone,
                file_path,
                duration,
                sample_rate_khz,
                bitrate,
                loudness_db
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                name.strip(),
                normalize_phone(phone),
                file_path,
                metadata["duration"],
                metadata["sample_rate_khz"],
                metadata["bitrate"],
                metadata["loudness_db"]
            )
        )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# LOAD SUBMISSIONS
# ============================================================

def load_submissions():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                person_id,
                name,
                phone,
                file_path,
                duration,
                sample_rate_khz,
                bitrate,
                loudness_db,
                submitted_at
            FROM audio_submissions
            ORDER BY id DESC
            """
        )

        rows = cursor.fetchall()

        return rows

    finally:
        connection.close()


# ============================================================
# EXTRACT WAV METADATA
# ============================================================

def extract_wav_metadata(file_path):

    with wave.open(
        file_path,
        "rb"
    ) as audio:

        frames = audio.getnframes()

        sample_rate = audio.getframerate()

        sample_width = audio.getsampwidth()

        channels = audio.getnchannels()

        duration = (
            frames / float(sample_rate)
        )

        sample_rate_khz = (
            sample_rate / 1000
        )

        bitrate = (
            sample_rate
            * sample_width
            * 8
            * channels
        )

        raw_audio = audio.readframes(
            frames
        )

        rms = audioop.rms(
            raw_audio,
            sample_width
        )

        max_possible_amplitude = float(
            2 ** (
                (8 * sample_width) - 1
            )
        )

        if rms > 0:

            loudness_db = (
                20
                * math.log10(
                    rms /
                    max_possible_amplitude
                )
            )

        else:

            loudness_db = -100.0

    return {

        "duration": round(
            duration,
            2
        ),

        "sample_rate_khz": round(
            sample_rate_khz,
            2
        ),

        "bitrate": int(
            bitrate
        ),

        "loudness_db": round(
            loudness_db,
            2
        )
    }


# ============================================================
# SAVE UPLOADED AUDIO FILE
# ============================================================

def save_uploaded_file(uploaded_file):

    extension = os.path.splitext(
        uploaded_file.name
    )[1].lower()

    unique_filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    file_path = os.path.join(
        UPLOAD_DIR,
        unique_filename
    )

    with open(
        file_path,
        "wb"
    ) as output_file:

        output_file.write(
            uploaded_file.getbuffer()
        )

    return file_path


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "🎙️ GigVoice"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Submit Audio",
        "Submissions"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "Gig worker audio collection system"
)


# ============================================================
# SUBMIT AUDIO PAGE
# ============================================================

if page == "Submit Audio":

    st.markdown(
        """
        <div class="hero">

            <h1>
                🎙️ GigVoice
            </h1>

            <p>
                Gig Worker Audio Submission Portal
            </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="info-box">

        <b>Audio requirements</b>

        <br>

        • Upload a WAV audio file

        <br>

        • Recommended length: 10–60 seconds

        <br>

        • Speak clearly with low background noise

        </div>
        """,
        unsafe_allow_html=True
    )

    with st.form(
        "audio_submission_form"
    ):

        name = st.text_input(
            "Full Name",
            placeholder="Enter your full name"
        )

        phone = st.text_input(
            "Phone Number",
            placeholder="Enter 10-digit mobile number"
        )

        audio_file = st.file_uploader(
            "Audio Sample",
            type=["wav"],
            help="Upload a WAV audio recording"
        )

        submitted = st.form_submit_button(
            "Submit Audio"
        )

    # --------------------------------------------------------
    # AUDIO PREVIEW
    # --------------------------------------------------------

    if audio_file is not None:

        st.markdown(
            "### 🎧 Preview"
        )

        st.audio(
            audio_file,
            format="audio/wav"
        )

    # --------------------------------------------------------
    # FORM SUBMISSION
    # --------------------------------------------------------

    if submitted:

        cleaned_phone = normalize_phone(
            phone
        )

        if not name.strip():

            st.error(
                "Please enter your full name."
            )

        elif not phone.strip():

            st.error(
                "Please enter your phone number."
            )

        elif len(cleaned_phone) != 10:

            st.error(
                "Please enter a valid "
                "10-digit phone number."
            )

        elif audio_file is None:

            st.error(
                "Please upload a WAV audio file."
            )

        else:

            file_path = None

            try:

                # --------------------------------------------
                # Save physical audio
                # --------------------------------------------

                file_path = save_uploaded_file(
                    audio_file
                )

                # --------------------------------------------
                # Extract metadata
                # --------------------------------------------

                metadata = extract_wav_metadata(
                    file_path
                )

                # --------------------------------------------
                # Person lookup / creation
                # --------------------------------------------

                person_id, created_new = (
                    find_or_create_person(
                        name,
                        cleaned_phone
                    )
                )

                # --------------------------------------------
                # Save submission
                # --------------------------------------------

                save_audio_submission(
                    person_id=person_id,
                    name=name,
                    phone=cleaned_phone,
                    file_path=file_path,
                    metadata=metadata
                )

                # --------------------------------------------
                # Success
                # --------------------------------------------

                st.success(
                    "✅ Audio submitted successfully!"
                )

                if created_new:

                    st.info(
                        "👤 New person record was created."
                    )

                else:

                    st.info(
                        "🔗 Existing person matched "
                        "using phone number."
                    )

                # --------------------------------------------
                # Metadata
                # --------------------------------------------

                st.markdown(
                    "### 📊 Extracted Audio Metadata"
                )

                col1, col2 = st.columns(
                    2
                )

                with col1:

                    st.metric(
                        "Duration",
                        f"{metadata['duration']} sec"
                    )

                    st.metric(
                        "Sample Rate",
                        (
                            f"{metadata['sample_rate_khz']}"
                            " kHz"
                        )
                    )

                with col2:

                    st.metric(
                        "Bitrate",
                        (
                            f"{metadata['bitrate']}"
                            " bps"
                        )
                    )

                    st.metric(
                        "Loudness",
                        (
                            f"{metadata['loudness_db']}"
                            " dB"
                        )
                    )

            except sqlite3.OperationalError as error:

                # Delete orphan audio file if DB save failed.
                if (
                    file_path
                    and os.path.exists(file_path)
                ):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass

                if "locked" in str(error).lower():

                    st.error(
                        "Database is locked. "
                        "Please close DB Browser for SQLite "
                        "and submit again."
                    )

                else:

                    st.error(
                        f"Database error: {error}"
                    )

            except wave.Error:

                if (
                    file_path
                    and os.path.exists(file_path)
                ):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass

                st.error(
                    "The uploaded file is not a valid WAV file."
                )

            except Exception as error:

                if (
                    file_path
                    and os.path.exists(file_path)
                ):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass

                st.error(
                    f"Submission failed: {error}"
                )


# ============================================================
# SUBMISSIONS PAGE
# ============================================================

elif page == "Submissions":

    st.markdown(
        """
        <div style="
            padding: 22px;
            border-radius: 12px;
            background: #171a21;
            text-align: center;
            margin-bottom: 25px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h1 style="margin:0;">🎧 Audio Submissions</h1>
            <p style="margin-top:10px; margin-bottom:0; color:#b8b8b8;">
                Review recordings and extracted metadata
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    try:

        submissions = load_submissions()

    except sqlite3.Error as error:

        st.error(
            f"Unable to load submissions: {error}"
        )

        submissions = []

    if len(submissions) == 0:

        st.info(
            "No audio submissions found."
        )

    else:

        st.success(
            f"{len(submissions)} submission(s) found."
        )

        st.divider()

        for row in submissions:

            with st.container(
                border=True
            ):

                col_name, col_id = st.columns(
                    [3, 1]
                )

                with col_name:

                    st.subheader(
                        f"🎤 {row['name']}"
                    )

                with col_id:

                    st.caption(
                        f"Submission #{row['id']}"
                    )

                st.write(
                    f"📱 **Phone:** {row['phone']}"
                )

                st.caption(
                    f"Submitted: {row['submitted_at']}"
                )

                # --------------------------------------------
                # AUDIO PLAYER
                # --------------------------------------------

                audio_path = row[
                    "file_path"
                ]

                if (
                    audio_path
                    and os.path.exists(audio_path)
                ):

                    st.audio(
                        audio_path,
                        format="audio/wav"
                    )

                else:

                    st.warning(
                        "Audio file could not be found."
                    )

                # --------------------------------------------
                # METADATA
                # --------------------------------------------

                st.markdown(
                    "#### Audio Metadata"
                )

                col1, col2 = st.columns(
                    2
                )

                with col1:

                    st.write(
                        "⏱️ **Duration:** "
                        f"{row['duration']} sec"
                    )

                    st.write(
                        "🎚️ **Sample Rate:** "
                        f"{row['sample_rate_khz']} kHz"
                    )

                with col2:

                    st.write(
                        "📡 **Bitrate:** "
                        f"{row['bitrate']} bps"
                    )

                    st.write(
                        "🔊 **Loudness:** "
                        f"{row['loudness_db']} dB"
                    )

                st.caption(
                    f"Person ID: {row['person_id']}"
                )