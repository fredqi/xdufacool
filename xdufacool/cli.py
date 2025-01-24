import logging
import argparse
from pathlib import Path
from xdufacool.models import Course
from xdufacool.utils import setup_logging

def collect_submissions(args):
    """Handles the 'collect' subcommand."""
    config_file = args.config
    logging.info(f"Collecting submissions...")
    course = Course.from_config(config_file)
    logging.info(f"Course created: {course}")
    submission_dir = Path(args.submission_dir)
    assignment_ids = args.assignment_ids if args.assignment_ids else course.assignments.keys()
    for assignment_id in assignment_ids:
        assignment = course.assignments.get(assignment_id)
        if assignment is None:
            logging.error(f"Assignment with ID {assignment_id} not found.")
            continue
        logging.info(f"Collecting submissions for {assignment}")
        assignment.collect_submissions(submission_dir)
        logging.info("Collection process finished.")
        assignment.merge_submissions(submission_dir)
        logging.info("Merging process finished.")

def create_assignment(args):
    """Handles the 'create' subcommand to create an assignment package."""
    config_file = args.config
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    course = Course.from_config(config_file)
    assignment_ids = args.assignment_ids if args.assignment_ids else course.assignments.keys()
    for assignment_id in assignment_ids:
        assignment = course.assignments.get(assignment_id)
        if assignment is None:
            logging.error(f"Assignment with ID {assignment_id} not found.")
            continue

        logging.info(f"Creating package for {assignment} ...")
        tarball_path = assignment.prepare(output_dir)
        if tarball_path is None:
            logging.error(f"Failed to create distribution tarball for {assignment}.")
            continue
        assignment.generate_notification(output_dir)

def create_summary(args):
    """Handles the 'summary' subcommand to create teaching summaries."""
    config_file = args.config
    course = Course.from_config(config_file)
    for student_group in course.groups:
        logging.info(f"Creating teaching summary for {student_group} ...")
        student_group.create_summary(args.working_dir)
    logging.info(f"Teaching summaries created.")

def main():
    """Parses command-line arguments and dispatches to appropriate subcommands."""
    parser = argparse.ArgumentParser(description="Manage assignments and submissions.")
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-c", "--config", default="config.yml", help="Config file path")
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand", required=True)

    create_parser = subparsers.add_parser("create", parents=[parent_parser],
                                          help="Create assignment for distribution")
    create_parser.add_argument("-o", "--output-dir", default="dist",
                                help="Output directory")
    create_parser.add_argument("assignment_ids", nargs="*",
                                help="Assignment IDs to create (default: all)")
    create_parser.set_defaults(func=create_assignment)

    collect_parser = subparsers.add_parser("collect", parents=[parent_parser],
                                           help="Collect submissions")
    collect_parser.add_argument("submission_dir", help="Submission directory")
    collect_parser.add_argument("assignment_ids", nargs="*",
                                help="Assignment IDs to collect (default: all)")
    collect_parser.set_defaults(func=collect_submissions)

    summary_parser = subparsers.add_parser("summary", parents=[parent_parser],
                                           help="Create teaching summary")
    summary_parser.add_argument("working_dir", default=".", help="Working directory")
    summary_parser.set_defaults(func=create_summary)

    args = parser.parse_args()
    setup_logging('xdufacool.log', logging.DEBUG)
    logging.info("Starting xdufacool ...")
    args.func(args)

if __name__ == "__main__":
    main()