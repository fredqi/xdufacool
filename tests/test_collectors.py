from datetime import datetime

from xdufacool.collectors import (
    SubmissionManager,
    SubmissionIdentityResolver,
    LocalSubmissionCollector,
    EmailSubmissionCollector,
    EmailSubmissionHistory,
)
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


def test_create_submission_for_report_assignment(tmp_path):
    manager = SubmissionManager()
    assignment = _build_report_assignment(tmp_path)
    student = Student("14020150001", "Alice")

    submission = manager.create_submission_for_assignment(
        assignment, student, datetime(2024, 9, 10)
    )

    assert isinstance(submission, ReportSubmission)


def test_create_submission_for_coding_assignment(tmp_path):
    manager = SubmissionManager()
    assignment = _build_coding_assignment(tmp_path)
    student = Student("14020150002", "Bob")

    submission = manager.create_submission_for_assignment(
        assignment, student, datetime(2024, 9, 10)
    )

    assert isinstance(submission, CodingSubmission)


def test_create_submission_for_challenge_assignment_returns_none(tmp_path):
    manager = SubmissionManager()
    assignment = _build_challenge_assignment(tmp_path)
    student = Student("14020150003", "Carol")

    submission = manager.create_submission_for_assignment(
        assignment, student, datetime(2024, 9, 10)
    )

    assert submission is None


def test_ingest_saved_file_pdf_calls_add_report(tmp_path):
    manager = SubmissionManager()
    assignment = _build_report_assignment(tmp_path)
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
    assignment = _build_report_assignment(tmp_path)
    submission = DummySubmission()

    zip_path = assignment.dirs["submissions"] / "PRML-HW26S01-14020150005-Eve.zip"
    zip_path.write_bytes(b"PK\x03\x04")

    result = manager.ingest_saved_file(assignment, submission, zip_path)

    assert result["status"] == "accepted_compressed"
    assert result["action"] == "generate_report"
    assert submission.called is True


def test_ingest_saved_file_unknown_extension_returns_ignore(tmp_path):
    manager = SubmissionManager()
    assignment = _build_report_assignment(tmp_path)
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
    collector.mail_helper = FakeMailHelper()

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


def test_email_scan_key_dedupes_bulk_prefixes(tmp_path):
    course = _build_course(tmp_path)
    assignment_s = _build_report_assignment_with_course(tmp_path, course, "HW26S01", "R31")
    assignment_f = _build_report_assignment_with_course(tmp_path, course, "HW26F01", "R32")

    key_s = EmailSubmissionCollector.get_scan_key(assignment_s, {"collection_mode": "bulk"})
    key_f = EmailSubmissionCollector.get_scan_key(assignment_f, {"collection_mode": "bulk"})
    key_single = EmailSubmissionCollector.get_scan_key(
        assignment_s,
        {"collection_mode": "single"},
    )

    assert key_s == "PRML-HW26"
    assert key_f == "PRML-HW26"
    assert key_single == "HW26S01"
