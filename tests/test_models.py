from datetime import datetime
import yaml
import os
import pytest
from pathlib import Path
from xdufacool.models import Teacher, Student, Course, Assignment, ReportAssignment, CodingAssignment, ChallengeAssignment, Submission, ReportSubmission, CodingSubmission, ChallengeSubmission

@pytest.fixture
def setup_data(tmp_path):
    # Create dummy data for testing
    teacher1 = Teacher("T001", "Dr. Smith", "smith@example.com", "Computer Science")
    teacher2 = Teacher("T002", "Dr. Jones", "jones@example.com", "Electrical Engineering")
    student1 = Student("S001", "Alice", "alice@example.com", "Computer Science")
    student2 = Student("S002", "Bob", "bob@example.com", "Electrical Engineering")

    start_date = datetime(2024, 9, 1)
    end_date = datetime(2025, 1, 15)
    
    # Create dummy files for CodingAssignment
    exercise_dir = tmp_path / "exercise" / "Code1"
    exercise_dir.mkdir(parents=True, exist_ok=True)
    (exercise_dir / "env_template.yml").touch()
    (exercise_dir / "notebook.ipynb").touch()
    (exercise_dir / "data.csv").touch()
    (exercise_dir / "figure.png").touch()

    course = Course(
        course_id="CS101",
        abbreviation="MLEN",
        topic="Machine Learning",
        # semester="Fall 2024",
        teachers=[teacher1, teacher2],
        teaching_hours=32,
        credits=2.0,
        start_date=start_date,
        end_date=end_date,
        base_dir=tmp_path
    )

    assignment = Assignment(
        assignment_id="A001",
        course=course,
        title="Assignment 1",
        alias="nonimal-name",
        description="First assignment",
        due_date=datetime(2024, 9, 15)
    )

    report_assignment = ReportAssignment(
        assignment_id="R001",
        course=course,
        title="Report Assignment 1",
        alias="Report1",
        description="First report assignment",
        due_date=datetime(2024, 9, 20),
        instructions="Write a report..."
    )

    coding_assignment = CodingAssignment(
        assignment_id="C001",
        course=course,
        title="Coding Assignment 1",
        alias="Code1",
        description="First coding assignment",
        due_date=datetime(2024, 9, 25),
        environment_template="env_template.yml",
        notebook={'source': 'notebook.ipynb', 'additional_cells': []},
        data=["data.csv"],
        figures=["figure.png"]
    )

    challenge_assignment = ChallengeAssignment(
        assignment_id="CH001",
        course=course,
        title="Challenge Assignment 1",
        alias="Challenge1",
        description="First challenge assignment",
        due_date=datetime(2024, 9, 30),
        evaluation_metric="Accuracy"
    )

    submission = Submission(
        assignment=assignment,
        student=student1,
        submission_date=datetime(2024, 9, 14)
    )

    report_submission = ReportSubmission(
        assignment=report_assignment,
        student=student1,
        submission_date=datetime(2024, 9, 19)
    )

    coding_submission = CodingSubmission(
        assignment=coding_assignment,
        student=student1,
        submission_date=datetime(2024, 9, 24),
    )

    challenge_submission = ChallengeSubmission(
        assignment=challenge_assignment,
        student=student1,
        submission_date=datetime(2024, 9, 29),
        model_file="model.pkl",
        results_file="results.csv"
    )

    return {
        "teacher1": teacher1,
        "teacher2": teacher2,
        "student1": student1,
        "student2": student2,
        "course": course,
        "assignment": assignment,
        "report_assignment": report_assignment,
        "coding_assignment": coding_assignment,
        "challenge_assignment": challenge_assignment,
        "submission": submission,
        "report_submission": report_submission,
        "coding_submission": coding_submission,
        "challenge_submission": challenge_submission,
    }

def test_course_creation(setup_data):
    course = setup_data["course"]
    assert course.course_id == "CS101"
    assert course.abbreviation == "MLEN"
    assert course.topic == "Machine Learning"
    assert course.semester == "2024-2025学年第一学期"
    assert len(course.teachers) == 2
    assert course.course_year == 2024
    assert course.start_date == datetime(2024, 9, 1)

def test_add_assignment(setup_data):
    course = setup_data["course"]
    assignment = setup_data["assignment"]
    course.add_assignment(assignment)
    assert len(course.assignments) == 1
    assert course.assignments[assignment.assignment_id] == assignment

def test_assignment_creation(setup_data):
    assignment = setup_data["assignment"]
    assert assignment.assignment_id == "A001"
    assert assignment.course == setup_data["course"]
    assert assignment.title == "Assignment 1"
    assert assignment.description == "First assignment"
    assert assignment.due_date == datetime(2024, 9, 15)

def test_add_submission(setup_data):
    assignment = setup_data["assignment"]
    submission = setup_data["submission"]
    assignment.add_submission(submission)
    assert len(assignment.submissions) == 1
    assert assignment.submissions[submission.student.student_id] == submission

def test_get_submission(setup_data):
    assignment = setup_data["assignment"]
    submission = setup_data["submission"]
    assignment.add_submission(submission)
    retrieved_submission = assignment.get_submission(submission.student.student_id)
    assert retrieved_submission == submission

def test_report_assignment_creation(setup_data):
    report_assignment = setup_data["report_assignment"]
    assert report_assignment.assignment_id == "R001"
    assert report_assignment.course == setup_data["course"]
    assert report_assignment.title == "Report Assignment 1"
    assert report_assignment.description == "First report assignment"
    assert report_assignment.due_date == datetime(2024, 9, 20)
    assert report_assignment.instructions == "Write a report..."

def test_coding_assignment_creation(setup_data):
    coding_assignment = setup_data["coding_assignment"]
    assert coding_assignment.assignment_id == "C001"
    assert coding_assignment.course == setup_data["course"]
    assert coding_assignment.title == "Coding Assignment 1"
    assert coding_assignment.description == "First coding assignment"
    assert coding_assignment.due_date == datetime(2024, 9, 25)
    assert coding_assignment.environment_template == "env_template.yml"
    assert coding_assignment.notebook == {'source': 'notebook.ipynb', 'additional_cells': []}
    assert coding_assignment.data == ["data.csv"]
    assert coding_assignment.figures == ["figure.png"]
    assert coding_assignment.dirs['exercise'].name == "Code1"

def test_challenge_assignment_creation(setup_data):
    challenge_assignment = setup_data["challenge_assignment"]
    assert challenge_assignment.assignment_id == "CH001"
    assert challenge_assignment.course == setup_data["course"]
    assert challenge_assignment.title == "Challenge Assignment 1"
    assert challenge_assignment.description == "First challenge assignment"
    assert challenge_assignment.due_date == datetime(2024, 9, 30)
    assert challenge_assignment.evaluation_metric == "Accuracy"

def test_update_leaderboard(setup_data):
    challenge_assignment = setup_data["challenge_assignment"]
    student1 = setup_data["student1"]
    student2 = setup_data["student2"]
    submission1 = ChallengeSubmission(challenge_assignment, student1, datetime(2024, 9, 29), "model1.pkl", "results1.csv", 0.9)
    submission2 = ChallengeSubmission(challenge_assignment, student2, datetime(2024, 9, 29), "model2.pkl", "results2.csv", 0.8)
    challenge_assignment.leaderboard = [submission1, submission2]
    challenge_assignment.update_leaderboard()
    assert challenge_assignment.leaderboard[0] == submission1
    assert challenge_assignment.leaderboard[1] == submission2
    assert submission1.rank == 1
    assert submission2.rank == 2

def test_submission_creation(setup_data):
    submission = setup_data["submission"]
    assert submission.assignment == setup_data["assignment"]
    assert submission.student == setup_data["student1"]
    assert submission.submission_date == datetime(2024, 9, 14)
    assert submission.score == 0.0

def test_report_submission_creation(setup_data):
    report_submission = setup_data["report_submission"]
    assert report_submission.assignment == setup_data["report_assignment"]
    assert report_submission.student == setup_data["student1"]
    assert report_submission.submission_date == datetime(2024, 9, 19)
    assert report_submission.score == 0.0

def test_coding_submission_creation(setup_data):
    coding_submission = setup_data["coding_submission"]
    assert coding_submission.assignment == setup_data["coding_assignment"]
    assert coding_submission.student == setup_data["student1"]
    assert coding_submission.submission_date == datetime(2024, 9, 24)
    assert coding_submission.score == 0.0

def test_challenge_submission_creation(setup_data):
    challenge_submission = setup_data["challenge_submission"]
    assert challenge_submission.assignment == setup_data["challenge_assignment"]
    assert challenge_submission.student == setup_data["student1"]
    assert challenge_submission.submission_date == datetime(2024, 9, 29)
    assert challenge_submission.model_file == "model.pkl"
    assert challenge_submission.results_file == "results.csv"
    assert challenge_submission.score == 0.0
    assert challenge_submission.rank is None
