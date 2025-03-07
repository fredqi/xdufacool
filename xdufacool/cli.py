import yaml
import logging
import argparse
import sys
import imaplib
from pathlib import Path
from xdufacool.models import Course
from xdufacool.utils import setup_logging, load_config
from xdufacool.collectors import LocalSubmissionCollector, EmailSubmissionCollector


def load_config(config_file, task_name, base_dir):
    """Loads the YAML configuration file, checks its existence, constructs the Course instance,
    and returns the configuration for the specified task.
    """
    config_path = Path(config_file)
    if not config_path.exists():
        logging.error(f"Configuration file not found: {config_file}")
        return None, None

    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if base_dir is None:
        base_dir = config_path.parent
    course = Course.from_dict(data, base_dir)
    logging.info(f"Course created: {course}")
    task_config = data.get('tasks', {}).get(task_name, {})
    logging.debug(f"{task_name} config: {task_config}")
    return course, task_config

def collect_submissions(args):
    """Handles the 'collect' subcommand."""
    course, _ = load_config(args.config, 'collect', args.base_dir)
    if course is None:
        return

    assignment_ids = args.assignment_ids if args.assignment_ids else course.assignments.keys()
    
    for assignment_id in assignment_ids:
        assignment = course.assignments.get(assignment_id)
        if assignment is None:
            logging.error(f"! Assignment with ID {assignment_id} not found.")
            continue
        try:
            logging.info(f"* Collecting submissions for {assignment}")
            collector = LocalSubmissionCollector(assignment)
            collector.collect_submissions()
            logging.info("* Collection process finished.")
            logging.info(f"* Merging submissions for {assignment}")
            assignment.merge_submissions()
            logging.info("* Merging process finished.")
        except Exception as e:
            logging.error(f"! Error processing {assignment_id}: {e}")

def create_assignment(args):
    """Handles the 'create' subcommand to create an assignment package."""
    course, create_config = load_config(args.config, 'create', args.base_dir)
    if course is None:
        return

    assignment_ids = args.assignment_ids if args.assignment_ids else course.assignments.keys()
    for assignment_id in assignment_ids:
        assignment = course.assignments.get(assignment_id)
        if assignment is None:
            logging.error(f"Assignment with ID {assignment_id} not found.")
            continue

        logging.info(f"Creating package for {assignment} ...")
        logging.debug(f"Create config: {create_config}")
        tarball_path = assignment.prepare()
        if tarball_path is None:
            logging.error(f"Failed to create distribution tarball for {assignment}.")
            continue
        notification_template = create_config.get('notification_template', 'notification.md.j2')
        assignment.generate_notification(notification_template)

def create_summary(args):
    """Handles the 'summary' subcommand to create teaching summaries."""
    course, summary_config = load_config(args.config, 'summary', args.base_dir)
    if course is None:
        return
    for student_group in course.groups:
        logging.info(f"* Creating teaching summary for {student_group} ...")
        student_group.create_summary(summary_config)
    logging.info(f"* Teaching summaries created.")

def check_submissions(args):
    """Handles the 'check' subcommand to process email submissions."""
    course, check_config = load_config(args.config, 'check', args.base_dir)
    if course is None:
        return
    try:
        for assignment_id, assignment in course.assignments.items():
            logging.info(f"* Processing {assignment}...")
            collector = EmailSubmissionCollector(assignment, check_config)
            collector.collect_submissions()
            collector.send_confirmations()
            logging.info("* Collection process finished")
    except (KeyboardInterrupt, TimeoutError, AttributeError, 
            ConnectionResetError, imaplib.IMAP4.error) as e:
        logging.error(f"Error: {type(e).__name__}: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {type(e).__name__}: {str(e)}")

def main():
    """Parses command-line arguments and dispatches to appropriate subcommands."""
    parser = argparse.ArgumentParser(description="Manage assignments and submissions.")
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-c", "--config", default="config.yml", help="Config file path")
    parent_parser.add_argument("-b", "--base-dir", default=None, help="Base directory")
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand", required=True)

    create_parser = subparsers.add_parser("create", parents=[parent_parser],
                                          help="Create assignment for distribution")
    # create_parser.add_argument("-o", "--output-dir", default="dist",
    #                             help="Output directory")
    create_parser.add_argument("assignment_ids", nargs="*",
                                help="Assignment IDs to create (default: all)")
    create_parser.set_defaults(func=create_assignment)

    collect_parser = subparsers.add_parser("collect", parents=[parent_parser],
                                           help="Collect submissions")
    # collect_parser.add_argument("submission_dir", help="Submission directory")
    collect_parser.add_argument("assignment_ids", nargs="*",
                                help="Assignment IDs to collect (default: all)")
    collect_parser.set_defaults(func=collect_submissions)

    summary_parser = subparsers.add_parser("summary", parents=[parent_parser],
                                           help="Create teaching summary")
    # summary_parser.add_argument("working_dir", default=".", help="Working directory")
    summary_parser.set_defaults(func=create_summary)

    check_parser = subparsers.add_parser("check", parents=[parent_parser],
                                         help="Check and download email submissions")
    check_parser.set_defaults(func=check_submissions)

    args = parser.parse_args()
    setup_logging('xdufacool.log', logging.INFO)
    logging.info("Starting xdufacool ...")
    logging.debug(f"Args: {args}")
    args.func(args)

if __name__ == "__main__":
    main()