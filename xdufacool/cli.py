import logging
import argparse
from pathlib import Path
import yaml  # Import PyYAML
from xdufacool.models import Course
from xdufacool.utils import setup_logging
from xdufacool.homework_manager import HomeworkManager

def load_config(config_file, task_name):
    """Loads the YAML configuration file, checks its existence, constructs the Course instance,
    and returns the configuration for the specified task.
    """
    config_path = Path(config_file)
    if not config_path.exists():
        logging.error(f"Configuration file not found: {config_file}")
        return None, None  # Or raise an exception

    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)  # Use safe_load for security

    course = Course.from_dict(data)
    logging.info(f"Course created: {course}")
    task_config = data.get('tasks', {}).get(task_name, {})
    return course, task_config

def collect_submissions(args):
    """Handles the 'collect' subcommand."""
    logging.info(f"Collecting submissions...")
    course, collect_config = load_config(args.config, 'collect')
    if course is None:
        return  # load_config will have logged an error

    submission_dir = Path(args.submission_dir)
    if not submission_dir.exists():
        logging.error(f"Submission directory not found: {submission_dir}")
        return

    assignment_ids = args.assignment_ids if args.assignment_ids else course.assignments.keys()
    for assignment_id in assignment_ids:
        assignment = course.assignments.get(assignment_id)
        if assignment is None:
            logging.error(f"Assignment with ID {assignment_id} not found.")
            continue
        logging.info(f"Collecting submissions for {assignment}")
        # TODO: add collect_config
        logging.debug(f"Collect config: {collect_config}")
        assignment.collect_submissions(submission_dir)
        logging.info("Collection process finished.")
        assignment.merge_submissions(submission_dir)
        logging.info("Merging process finished.")

def create_assignment(args):
    """Handles the 'create' subcommand to create an assignment package."""
    course, create_config = load_config(args.config, 'create')
    if course is None:
        return  # load_config will have logged an error

    distribution_dir = Path(create_config.get('distribution_dir', ''))
    distribution_dir.mkdir(parents=True, exist_ok=True)

    assignment_ids = args.assignment_ids if args.assignment_ids else course.assignments.keys()
    for assignment_id in assignment_ids:
        assignment = course.assignments.get(assignment_id)
        if assignment is None:
            logging.error(f"Assignment with ID {assignment_id} not found.")
            continue

        logging.info(f"Creating package for {assignment} ...")
        logging.debug(f"Create config: {create_config}")
        tarball_path = assignment.prepare(distribution_dir)
        if tarball_path is None:
            logging.error(f"Failed to create distribution tarball for {assignment}.")
            continue
        notification_template = create_config.get('notification_template', 'notification.md.j2')
        assignment.generate_notification(distribution_dir, notification_template)

def create_summary(args):
    """Handles the 'summary' subcommand to create teaching summaries."""
    course, summary_config = load_config(args.config, 'summary')
    if course is None:
        return  # load_config will have logged an error
    for student_group in course.groups:
        logging.info(f"Creating teaching summary for {student_group} ...")
        student_group.create_summary(summary_config)
    logging.info(f"Teaching summaries created.")

def check_submissions(args):
    """Handles the 'check' subcommand to process email submissions."""
    course, check_config = load_config(args.config, 'check')
    if course is None:
        return  # load_config will have logged an error

    mgr = None
    try:
        logging.info(f'* Loading {args.config}...')
        mgr = HomeworkManager(course, check_config)
        for hw_key, homework in mgr.homeworks.items():
            logging.info(f'* [{homework.descriptor}] Checking email headers...')
            mgr.check_headers(homework)
            logging.info(f'* [{homework.descriptor}] Sending confirmation emails...')
            mgr.send_confirmation(homework)
            if hasattr(homework, 'leaderboard'):
                homework.leaderboard.save()
    except KeyboardInterrupt as error:
        logging.error("! KeyboardInterrupt: Interrupted by user from keyword.")
        sys.exit(1)
    except TimeoutError as error:
        logging.error(f"! TimeoutError: {error.strerror} when connecting to email server.")
        sys.exit(error.errno)
    except AttributeError as error:
        logging.error(f"! AttributeError: {error}.")
        sys.exit(1)
    except ConnectionResetError as error:
        logging.error(f"{type(error)}: {error}")
    except imaplib.IMAP4.error as err:
        msg = err.args[0].decode()
        logging.error(f"! Log in failed with: {msg}.")
        sys.exit(1)
    except Exception as error:
        logging.error(f"! {type(error)}: {error}")
    finally:
        if mgr:
            logging.info('* Logout email servers...')
            mgr.quit()

def main():
    """Parses command-line arguments and dispatches to appropriate subcommands."""
    parser = argparse.ArgumentParser(description="Manage assignments and submissions.")
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-c", "--config", default="config.yml", help="Config file path")
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
    collect_parser.add_argument("submission_dir", help="Submission directory")
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