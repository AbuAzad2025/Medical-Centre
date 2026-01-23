import argparse
from app_factory import create_app, db
from services.report_service import ReportService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        result = ReportService.capture_weekly_slow_queries(limit=args.limit, created_by=None)
        if not result.get('success'):
            print('failed')
        else:
            print('ok')


if __name__ == '__main__':
    main()
