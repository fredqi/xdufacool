from datetime import datetime

from xdufacool.collectors import (
    SubmissionManager,
    SubmissionIdentityResolver,
    LocalSubmissionCollector,
    EmailSubmission,
    EmailSubmissionCollector,
    EmailSubmissionHistory,
)
from xdufacool.mail_helper import MailHelper
from xdufacool.models import (
    Teacher,
    Student,
    Course,
    ReportAssignment,
    CodingAssignment,
    ChallengeAssignment,
    ReportSubmission,
    CodingSubmission,
)


def _build_course(tmp_path):
    teacher = Teacher("T001", "Dr. Smith", "smith@example.com")
    course = Course(
        course_id="CS101",
        abbreviation="PRML",
        topic="Pattern Recognition",
        teachers={teacher.teacher_id: teacher},
        teaching_hours=32,
        credits=2.0,
        start_date=datetime(2024, 9, 1).date(),
        end_date=datetime(2025, 1, 1).date(),
        base_dir=tmp_path,
    )
    return course


def _build_report_assignment(tmp_path):
    course = _build_course(tmp_path)
    exercise_dir = tmp_path / "exercise" / "R01"
    exercise_dir.mkdir(parents=True, exist_ok=True)
    return ReportAssignment(
        assignment_id="HW26S01",
        course=course,
        title="Report 1",
        alias="R01",
        description="Report assignment",
        due_date=datetime(2024, 9, 15),
        instructions="Write a short report.",
    )


def _build_report_assignment_with_course(tmp_path, course, assignment_id, alias):
    exercise_dir = tmp_path / "exercise" / alias
    exercise_dir.mkdir(parents=True, exist_ok=True)
    assignment = ReportAssignment(
        assignment_id=assignment_id,
        course=course,
        title=f"Report {assignment_id}",
        alias=alias,
        description="Report assignment",
        due_date=datetime(2024, 9, 15),
        instructions="Write a short report.",
    )
    course.add_assignment(assignment)
    return assignment


def _build_coding_assignment(tmp_path):
    course = _build_course(tmp_path)
    exercise_dir = tmp_path / "exercise" / "C01"
    exercise_dir.mkdir(parents=True, exist_ok=True)
    (exercise_dir / "env_template.yml").write_text("name: demo\n", encoding="utf-8")
    (exercise_dir / "notebook.py").write_text("print('hello')\n", encoding="utf-8")
    (exercise_dir / "data.csv").write_text("x,y\n1,2\n", encoding="utf-8")

    return CodingAssignment(
        assignment_id="HW26S02",
        course=course,
        title="Coding 1",
        alias="C01",
        description="Coding assignment",
        due_date=datetime(2024, 9, 20),
        environment_template="env_template.yml",
        notebook={"source": "notebook.py", "output": "notebook.ipynb"},
        data=["data.csv"],
        figures=[],
    )


def _build_challenge_assignment(tmp_path):
    course = _build_course(tmp_path)
    exercise_dir = tmp_path / "exercise" / "CH01"
    exercise_dir.mkdir(parents=True, exist_ok=True)
    return ChallengeAssignment(
        assignment_id="HW26E01",
        course=course,
        title="Challenge 1",
        alias="CH01",
        description="Challenge assignment",
        due_date=datetime(2024, 9, 22),
        evaluation_metric="acc",
    )


def test_ingest_saved_file_pdf_calls_add_report(tmp_path):
    manager = SubmissionManager()
    course = _build_course(tmp_path)
    assignment = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R51")
    submission = manager.get_or_create_submission(
        assignment, "14020150004", "David", datetime(2024, 9, 10)
    )

    pdf_path = assignment.dirs["submissions"] / "PRML-HW26S01-14020150004-David.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    result = manager.ingest_saved_file(assignment, submission, pdf_path)

    assert result["status"] == "accepted_document"
    assert submission.report_file is not None


def test_ingest_saved_file_zip_calls_generate_report_when_available(tmp_path):
    class DummySubmission:
        def __init__(self):
            self.called = False

        def generate_report(self, _file_path):
            self.called = True

        def add_report(self, _file_path):
            raise AssertionError("add_report should not be called when generate_report exists")

    manager = SubmissionManager()
    course = _build_course(tmp_path)
    assignment = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R51")
    submission = DummySubmission()

    zip_path = assignment.dirs["submissions"] / "PRML-HW26S01-14020150005-Eve.zip"
    zip_path.write_bytes(b"PK\x03\x04")

    result = manager.ingest_saved_file(assignment, submission, zip_path)

    assert result["status"] == "accepted_compressed"
    assert result["action"] == "generate_report"
    assert submission.called is True


def test_ingest_saved_file_unknown_extension_returns_ignore(tmp_path):
    manager = SubmissionManager()
    course = _build_course(tmp_path)
    assignment = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R51")
    submission = manager.get_or_create_submission(
        assignment, "14020150006", "Frank", datetime(2024, 9, 10)
    )

    txt_path = assignment.dirs["submissions"] / "PRML-HW26S01-14020150006-Frank.txt"
    txt_path.write_text("notes", encoding="utf-8")

    result = manager.ingest_saved_file(assignment, submission, txt_path)

    assert result["status"] == "ignored"
    assert result["action"] == "ignore"


def test_identity_resolver_from_subject():
    resolver = SubmissionIdentityResolver()

    identity = resolver.from_subject("PRML-HW23E03-21009100517-谢某甲")

    assert identity is not None
    assert identity["student_id"] == "21009100517"
    assert identity["student_name"] == "谢某甲"


def test_identity_resolver_from_filename():
    resolver = SubmissionIdentityResolver()

    identity = resolver.from_filename("PRML-HW26S01-14020150007-Grace.pdf")

    assert identity is not None
    assert identity["student_id"] == "14020150007"
    assert identity["student_name"] == "Grace"


def test_identity_resolver_from_filename_returns_none_for_malformed_name():
    resolver = SubmissionIdentityResolver()

    identity = resolver.from_filename("invalid-file-name.pdf")

    assert identity is None


def test_local_collector_uses_resolver_for_canonical_filename(tmp_path):
    assignment = _build_report_assignment(tmp_path)
    file_path = assignment.dirs["submissions"] / "PRML-HW26S01-14020150008-Hank.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    collector = LocalSubmissionCollector(assignment)
    collector.collect_submissions()

    assert "14020150008" in assignment.submissions
    submission = assignment.submissions["14020150008"]
    assert submission.student.name == "Hank"
    assert submission.report_file is not None


def test_local_collector_ignores_malformed_filename(tmp_path):
    assignment = _build_report_assignment(tmp_path)
    file_path = assignment.dirs["submissions"] / "PRML-HW26S01-14020150009.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    collector = LocalSubmissionCollector(assignment)
    collector.collect_submissions()

    assert "14020150009" not in assignment.submissions


def test_collectors_inherit_shared_manager_and_resolver(tmp_path):
    assignment = _build_report_assignment(tmp_path)
    local_collector = LocalSubmissionCollector(assignment)
    email_collector = EmailSubmissionCollector(assignment, {})

    assert isinstance(local_collector.submission_manager, SubmissionManager)
    assert isinstance(local_collector.identity_resolver, SubmissionIdentityResolver)
    assert isinstance(email_collector.submission_manager, SubmissionManager)
    assert isinstance(email_collector.identity_resolver, SubmissionIdentityResolver)
    assert local_collector.assignments is assignment.course.assignments
    assert email_collector.assignments is assignment.course.assignments


def test_email_bulk_extract_search_prefix_variants(tmp_path):
    assignment = _build_report_assignment(tmp_path)
    collector = EmailSubmissionCollector(assignment, {"collection_mode": "bulk"})

    assert collector._extract_search_prefix("HW26S01") == "HW26"
    assert collector._extract_search_prefix("HW26F01") == "HW26"
    assert collector._extract_search_prefix("HW26E01") == "HW26"


def test_email_bulk_build_search_conditions_uses_year_prefix(tmp_path):
    course = _build_course(tmp_path)
    assignment = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R11")
    _build_report_assignment_with_course(tmp_path, course, "HW26F01", "R12")
    collector = EmailSubmissionCollector(assignment, {"collection_mode": "bulk"})

    condition = collector._build_search_conditions()

    assert 'SUBJECT "PRML-HW26"' in condition
    assert 'UNSEEN' in condition


def test_email_search_subject_matches_collection_mode(tmp_path):
    course = _build_course(tmp_path)
    assignment = _build_report_assignment_with_course(tmp_path, course, "HW26E01", "R13")

    bulk_collector = EmailSubmissionCollector(assignment, {"collection_mode": "bulk"})
    single_collector = EmailSubmissionCollector(assignment, {"collection_mode": "single"})

    assert bulk_collector._search_subject() == "PRML-HW26"
    assert single_collector._search_subject() == "PRML-HW26E01"


def test_email_bulk_attachment_routes_to_target_assignment_and_unmatched(tmp_path):
    class FakeMailHelper:
        def fetch_email(self, _uid):
            return "", [
                ("PRML-HW26F01-14020150010-Ivy.pdf", b"%PDF-1.4\n"),
                ("bad.pdf", b"not-canonical"),
            ]

    course = _build_course(tmp_path)
    source_assignment = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R21")
    target_assignment = _build_report_assignment_with_course(tmp_path, course, "HW26F01", "R22")
    unmatched_dir = tmp_path / "unmatched"

    collector = EmailSubmissionCollector(
        source_assignment,
        {
            "collection_mode": "bulk",
            "unmatched_attachments_dir": str(unmatched_dir),
        },
    )
    fake_mail_helper = FakeMailHelper()
    collector.mail_helper = fake_mail_helper

    submission = collector.submission_manager.get_or_create_submission(
        source_assignment,
        "14020150010",
        "Ivy",
        datetime(2024, 9, 10),
    )
    history = EmailSubmissionHistory(submission)
    history.latest_header = {"date": "Mon, 09 Sep 2024 10:00:00 +0800"}

    collector._save_attachments("EMAIL01", "14020150010", history)

    assert "14020150010" in target_assignment.submissions
    routed_submission = target_assignment.submissions["14020150010"]
    assert routed_submission.report_file is not None
    assert (unmatched_dir / "EMAIL01-bad.pdf").exists()


def test_email_submission_downloads_attachments_and_checksums(tmp_path):
    class FakeMailHelper:
        def __init__(self):
            self.fetch_count = 0

        def fetch_email(self, email_uid):
            self.fetch_count += 1
            assert email_uid == "UID1"
            return "body", [
                ("PRML-HW26S01-14020150011-Jane.pdf", b"%PDF-1.4\n"),
                ("notes.txt", b"notes"),
            ]

    assignment = _build_report_assignment(tmp_path)
    submission = SubmissionManager().get_or_create_submission(
        assignment,
        "14020150011",
        "Jane",
        datetime(2024, 9, 10),
    )
    email_submission = EmailSubmission(
        "UID1",
        {
            "from": "jane@example.com",
            "subject": "PRML-HW26S01-14020150011-Jane",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-1@example.com>",
        },
        submission,
    )
    mail_helper = FakeMailHelper()

    attachments = email_submission.download_attachments(mail_helper)
    email_submission.download_attachments(mail_helper)

    assert attachments == [
        ("PRML-HW26S01-14020150011-Jane.pdf", b"%PDF-1.4\n"),
        ("notes.txt", b"notes"),
    ]
    assert email_submission.body == "body"
    assert email_submission.attachments_downloaded is True
    assert set(email_submission.file_checksums.values()) == {
        "PRML-HW26S01-14020150011-Jane.pdf",
        "notes.txt",
    }
    assert mail_helper.fetch_count == 1


def test_email_submission_saves_downloaded_attachments(tmp_path):
    assignment = _build_report_assignment(tmp_path)
    submission = SubmissionManager().get_or_create_submission(
        assignment,
        "14020150012",
        "Kate",
        datetime(2024, 9, 10),
    )
    email_submission = EmailSubmission(
        "UID2",
        {
            "from": "kate@example.com",
            "subject": "PRML-HW26S01-14020150012-Kate",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-2@example.com>",
        },
        submission,
    )
    email_submission.attachments = [
        ("PRML-HW26S01-14020150012-Kate.pdf", b"%PDF-1.4\n"),
    ]

    saved_files = email_submission.save_attachments(tmp_path / "saved")

    assert saved_files == [tmp_path / "saved" / "PRML-HW26S01-14020150012-Kate.pdf"]
    assert saved_files[0].read_bytes() == b"%PDF-1.4\n"


def test_email_submission_download_and_save_uses_callback(tmp_path):
    class FakeMailHelper:
        def fetch_email(self, email_uid):
            assert email_uid == "UID2"
            return "", [
                ("first.pdf", b"first"),
                ("second.docx", b"second"),
            ]

    assignment = _build_report_assignment(tmp_path)
    submission = SubmissionManager().get_or_create_submission(
        assignment,
        "14020150012",
        "Kate",
        datetime(2024, 9, 10),
    )
    email_submission = EmailSubmission(
        "UID2",
        {
            "from": "kate@example.com",
            "subject": "PRML-HW26S01-14020150012-Kate",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-2@example.com>",
        },
        submission,
    )
    saved = []

    def save_attachment(email_submission_arg, filename, data):
        assert email_submission_arg is email_submission
        file_path = tmp_path / filename
        file_path.write_bytes(data)
        saved.append((filename, data))
        return file_path

    saved_files = email_submission.download_and_save_attachments(
        FakeMailHelper(),
        save_attachment=save_attachment,
    )

    assert saved == [("first.pdf", b"first"), ("second.docx", b"second")]
    assert saved_files == [tmp_path / "first.pdf", tmp_path / "second.docx"]
    assert set(email_submission.file_checksums.values()) == {"first.pdf", "second.docx"}


def test_email_submission_creates_confirmation_from_own_header_and_checksums(tmp_path):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "email_confirm.txt.j2").write_text(
        "{{ message_id }} {{ checksum }} {{ comment }}",
        encoding="utf-8",
    )
    assignment = _build_report_assignment(tmp_path)
    submission = SubmissionManager().get_or_create_submission(
        assignment,
        "14020150013",
        "Liam",
        datetime(2024, 9, 10),
    )
    email_submission = EmailSubmission(
        "UID3",
        {
            "from": "liam@example.com",
            "subject": "PRML-HW26S01-14020150013-Liam",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-3@example.com>",
        },
        submission,
    )
    email_submission.attachments = [
        ("PRML-HW26S01-14020150013-Liam.pdf", b"%PDF-1.4\n"),
    ]
    email_submission.download_attachments(
        type(
            "FakeMailHelper",
            (),
            {"fetch_email": lambda self, uid: ("", email_submission.attachments)},
        )()
    )

    to_addr, msg = email_submission.create_confirmation_email(
        "Dr. Smith",
        "teacher@example.com",
        "email_confirm.txt.j2",
    )
    body = msg.get_payload()[0].get_payload(decode=True).decode("utf-8")

    assert to_addr == "liam@example.com"
    assert msg["In-Reply-To"] == "<student-3@example.com>"
    assert msg["Subject"] == "PRML-HW26S01-14020150013-Liam"
    assert "<student-3@example.com>" in body
    assert "PRML-HW26S01-14020150013-Liam.pdf" in body
    assert "Missing attachments" not in body


def test_bulk_send_confirmations_processes_unconfirmed_emails_in_order(tmp_path):
    class FakeMailHelper:
        def __init__(self):
            self.sent = []
            self.flags = []
            self.fetched = []

        def fetch_email(self, email_uid):
            self.fetched.append(email_uid)
            return "", {
                "UID1": [("PRML-HW26S01-14020150014-Mina.pdf", b"first")],
                "UID2": [("PRML-HW26F01-14020150014-Mina.docx", b"second")],
            }[email_uid]

        def send_email(self, from_addr, to_addr, msg):
            self.sent.append((from_addr, to_addr, msg))

        def flag(self, email_uid, flags):
            self.flags.append((email_uid, flags))

        def quit(self):
            pass

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "email_confirm.txt.j2").write_text(
        "{{ message_id }} {{ checksum }}",
        encoding="utf-8",
    )

    course = _build_course(tmp_path)
    assignment_s = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R41")
    assignment_f = _build_report_assignment_with_course(tmp_path, course, "HW26F01", "R42")
    collector = EmailSubmissionCollector(
        assignment_s,
        {
            "collection_mode": "bulk",
            "email": "teacher@example.com",
            "email_template": "email_confirm.txt.j2",
        },
    )
    fake_mail_helper = FakeMailHelper()
    collector.mail_helper = fake_mail_helper
    submission = collector.submission_manager.get_or_create_submission(
        assignment_s,
        "14020150014",
        "Mina",
        datetime(2024, 9, 10),
    )
    history = EmailSubmissionHistory(submission)
    headers = [
        {
            "from": "mina@example.com",
            "subject": "PRML-HW26S01-14020150014-Mina",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-1@example.com>",
        },
        {
            "from": "mina@example.com",
            "subject": "PRML-HW26F01-14020150014-Mina",
            "date": "Mon, 09 Sep 2024 11:00:00 +0800",
            "message-id": "<student-2@example.com>",
        },
    ]
    history.update_from_email("UID2", headers[1], "teacher@example.com")
    history.update_from_email("UID1", headers[0], "teacher@example.com")
    collector.email_histories["14020150014"] = history

    collector._process_submissions(["14020150014"])
    collector.send_confirmations()

    assert fake_mail_helper.fetched == ["UID1", "UID2"]
    assert [msg["In-Reply-To"] for _, _, msg in fake_mail_helper.sent] == [
        "<student-1@example.com>",
        "<student-2@example.com>",
    ]
    assert fake_mail_helper.flags == [
        ("UID1", ["Seen", "Answered"]),
        ("UID2", ["Seen", "Answered"]),
    ]
    first_body = fake_mail_helper.sent[0][2].get_payload()[0].get_payload(decode=True).decode("utf-8")
    second_body = fake_mail_helper.sent[1][2].get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert "PRML-HW26S01-14020150014-Mina.pdf" in first_body
    assert "PRML-HW26F01-14020150014-Mina.docx" in second_body
    assert "14020150014" in assignment_s.submissions
    assert "14020150014" in assignment_f.submissions


def test_bulk_unconfirmed_submissions_overwrite_from_earliest_to_latest(tmp_path):
    class FakeMailHelper:
        def __init__(self):
            self.fetched = []

        def fetch_email(self, email_uid):
            self.fetched.append(email_uid)
            return "", {
                "UID-old": [("PRML-HW26S01-14020150018-Quinn.pdf", b"old")],
                "UID-new": [("PRML-HW26S01-14020150018-Quinn.pdf", b"new")],
            }[email_uid]

        def send_email(self, _from_addr, _to_addr, _msg):
            pass

        def flag(self, _email_uid, _flags):
            pass

        def quit(self):
            pass

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "email_confirm.txt.j2").write_text(
        "{{ message_id }} {{ checksum }}",
        encoding="utf-8",
    )

    course = _build_course(tmp_path)
    assignment = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R51")
    collector = EmailSubmissionCollector(
        assignment,
        {
            "collection_mode": "bulk",
            "email": "teacher@example.com",
            "email_template": "email_confirm.txt.j2",
        },
    )
    fake_mail_helper = FakeMailHelper()
    collector.mail_helper = fake_mail_helper
    submission = collector.submission_manager.get_or_create_submission(
        assignment,
        "14020150018",
        "Quinn",
        datetime(2024, 9, 10),
    )
    history = EmailSubmissionHistory(submission)
    history.update_from_email(
        "UID-new",
        {
            "from": "quinn@example.com",
            "subject": "PRML-HW26S01-14020150018-Quinn new",
            "date": "Mon, 09 Sep 2024 11:00:00 +0800",
            "message-id": "<student-new@example.com>",
        },
        "teacher@example.com",
    )
    history.update_from_email(
        "UID-old",
        {
            "from": "quinn@example.com",
            "subject": "PRML-HW26S01-14020150018-Quinn old",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-old@example.com>",
        },
        "teacher@example.com",
    )
    collector.email_histories["14020150018"] = history

    selected_uids = [
        email_submission.email_uid
        for email_submission in collector._email_submissions_to_confirm(history)
    ]
    collector._process_submissions(["14020150018"])

    file_path = assignment.dirs["submissions"] / "14020150018" / "PRML-HW26S01-14020150018-Quinn.pdf"
    assert selected_uids == ["UID-old", "UID-new"]
    assert fake_mail_helper.fetched == ["UID-old", "UID-new"]
    assert file_path.read_bytes() == b"new"


def test_single_send_confirmations_processes_only_latest_email(tmp_path):
    class FakeMailHelper:
        def __init__(self):
            self.sent = []
            self.flags = []
            self.fetched = []

        def fetch_email(self, email_uid):
            self.fetched.append(email_uid)
            return "", {
                "UID1": [("PRML-HW26S01-14020150015-Nora-old.pdf", b"old")],
                "UID2": [("PRML-HW26S01-14020150015-Nora.pdf", b"new")],
            }[email_uid]

        def send_email(self, from_addr, to_addr, msg):
            self.sent.append((from_addr, to_addr, msg))

        def flag(self, email_uid, flags):
            self.flags.append((email_uid, flags))

        def quit(self):
            pass

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "email_confirm.txt.j2").write_text(
        "{{ message_id }} {{ checksum }}",
        encoding="utf-8",
    )

    assignment = _build_report_assignment(tmp_path)
    collector = EmailSubmissionCollector(
        assignment,
        {
            "email": "teacher@example.com",
            "email_template": "email_confirm.txt.j2",
        },
    )
    fake_mail_helper = FakeMailHelper()
    collector.mail_helper = fake_mail_helper
    submission = collector.submission_manager.get_or_create_submission(
        assignment,
        "14020150015",
        "Nora",
        datetime(2024, 9, 10),
    )
    history = EmailSubmissionHistory(submission)
    history.update_from_email(
        "UID1",
        {
            "from": "nora@example.com",
            "subject": "PRML-HW26S01-14020150015-Nora old",
            "date": "Mon, 09 Sep 2024 10:00:00 +0800",
            "message-id": "<student-old@example.com>",
        },
        "teacher@example.com",
    )
    history.update_from_email(
        "UID2",
        {
            "from": "nora@example.com",
            "subject": "PRML-HW26S01-14020150015-Nora",
            "date": "Mon, 09 Sep 2024 11:00:00 +0800",
            "message-id": "<student-new@example.com>",
        },
        "teacher@example.com",
    )
    collector.email_histories["14020150015"] = history

    collector._process_submissions(["14020150015"])
    collector.send_confirmations()

    assert fake_mail_helper.fetched == ["UID2"]
    assert len(fake_mail_helper.sent) == 1
    assert fake_mail_helper.sent[0][2]["In-Reply-To"] == "<student-new@example.com>"
    assert fake_mail_helper.flags == [("UID2", ["Seen", "Answered"])]
    body = fake_mail_helper.sent[0][2].get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert "PRML-HW26S01-14020150015-Nora.pdf" in body
    assert "Nora-old.pdf" not in body


def test_collect_then_send_confirmations_does_not_download_twice(tmp_path):
    class FakeMailHelper:
        def __init__(self):
            self.sent = []
            self.flags = []
            self.fetched = []
            self.headers = {
                "UID1": {
                    "from": "oscar@example.com",
                    "subject": "PRML-HW26S01-14020150016-Oscar",
                    "date": "Mon, 09 Sep 2024 10:00:00 +0800",
                    "message-id": "<student-1@example.com>",
                },
            }

        def search(self, _conditions):
            return ["UID1"]

        def fetch_header(self, email_uid):
            return self.headers[email_uid]

        def get_datetime(self, date_str):
            return MailHelper.get_datetime(date_str)

        def fetch_email(self, email_uid):
            self.fetched.append(email_uid)
            return "", [("PRML-HW26S01-14020150016-Oscar.pdf", b"pdf")]

        def send_email(self, from_addr, to_addr, msg):
            self.sent.append((from_addr, to_addr, msg))

        def flag(self, email_uid, flags):
            self.flags.append((email_uid, flags))

        def quit(self):
            pass

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "email_confirm.txt.j2").write_text(
        "{{ message_id }} {{ checksum }}",
        encoding="utf-8",
    )

    assignment = _build_report_assignment(tmp_path)
    collector = EmailSubmissionCollector(
        assignment,
        {
            "email": "teacher@example.com",
            "email_template": "email_confirm.txt.j2",
        },
    )
    fake_mail_helper = FakeMailHelper()
    collector.mail_helper = fake_mail_helper
    collector.disconnect = lambda: None

    collector.collect_submissions()
    collector.send_confirmations()

    assert fake_mail_helper.fetched == ["UID1"]
    assert len(fake_mail_helper.sent) == 1
    assert fake_mail_helper.flags[-1] == ("UID1", ["Seen", "Answered"])


def test_boolean_batch_mode_downloads_all_and_skips_confirmations(tmp_path):
    class FakeMailHelper:
        def __init__(self):
            self.sent = []
            self.flags = []
            self.fetched = []
            self.headers = {
                "UID1": {
                    "from": "paul@example.com",
                    "subject": "PRML-HW26S01-14020150017-Paul old",
                    "date": "Mon, 09 Sep 2024 10:00:00 +0800",
                    "message-id": "<student-old@example.com>",
                },
                "UID2": {
                    "from": "paul@example.com",
                    "subject": "PRML-HW26S01-14020150017-Paul",
                    "date": "Mon, 09 Sep 2024 11:00:00 +0800",
                    "message-id": "<student-new@example.com>",
                },
            }

        def search(self, _conditions):
            return ["UID1", "UID2"]

        def fetch_header(self, email_uid):
            return self.headers[email_uid]

        def get_datetime(self, date_str):
            return MailHelper.get_datetime(date_str)

        def fetch_email(self, email_uid):
            self.fetched.append(email_uid)
            return "", [(f"PRML-HW26S01-14020150017-Paul-{email_uid}.pdf", b"pdf")]

        def send_email(self, from_addr, to_addr, msg):
            self.sent.append((from_addr, to_addr, msg))

        def flag(self, email_uid, flags):
            self.flags.append((email_uid, flags))

        def quit(self):
            pass

    assignment = _build_report_assignment(tmp_path)
    collector = EmailSubmissionCollector(
        assignment,
        {
            "batch_mode": True,
            "email": "teacher@example.com",
        },
    )
    fake_mail_helper = FakeMailHelper()
    collector.mail_helper = fake_mail_helper
    collector.disconnect = lambda: None

    condition = collector._build_search_conditions()
    collector.collect_submissions()
    collector.send_confirmations()

    assert "UNSEEN" not in condition
    assert fake_mail_helper.fetched == ["UID1", "UID2"]
    assert fake_mail_helper.sent == []
    assert ("UID1", ["Seen"]) in fake_mail_helper.flags
