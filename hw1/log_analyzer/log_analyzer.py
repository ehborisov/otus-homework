#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import logging
import sys
import os
import re
import gzip
import datetime
from statistics import median
from collections import defaultdict
from collections import namedtuple
import json
import time
import argparse

LOG_FILENAME_PATTERN = re.compile('nginx-access-ui\.log-(\d{8})(?:\.(gz))?')
LOG_LINE_PATTERN = re.compile('(.+)\s'  # remote_addr
                              '(.+)\s'  # remote_user
                              '(.+)\s'  # http_x_real_ip
                              '\[(.+)\]\s'  # time_local
                              '"(.+)"\s'  # request
                              '(\d+)\s'  # status
                              '(\d+)\s'  # body_bytes_sent
                              '"(.+)"\s'  # http_referer
                              '"(.+)"\s'  # http_user_agent
                              '"(.+)"\s'  # http_x_forwarded_for
                              '"(.+)"\s'  # http_X_REQUEST_ID
                              '"(.+)"\s'  # http_X_RB_USER
                              '(.+)\s',  # request_time
                              re.UNICODE)
REPORT_FILE_FORMAT = 'report-%s.html'
LOG_DATE_PATTERN = '%Y%m%d'
REPORT_DATE_PATTERN = '%Y.%m.%d'
REPORT_TEMPLATE_FILE = 'report.html'
TEMPLATE_REPLACEMENT_STRING = '$table_json'

REPORT_DECIMAL_FIELDS = ['count_perc', 'time_sum', 'time_perc', 'time_avg',
                         'time_max', 'time_med']

LogEntry = namedtuple('LogEntry', ['logfile', 'date'])

DEFAULT_CONFIG = {
    'REPORT_SIZE': 1000,
    'REPORT_DIR': '/Users/eborisov/study/data/python_course/hw1/reports',
    'LOG_DIR': '/Users/eborisov/study/data/python_course/hw1/log',
    'TIMESTAMP_PATH': '/var/tmp/log_analyzer.ts',
    'LOGFILE_PATH': '',
    'ERROR_PERCENTAGE_THRESHOLD': 0.05
}


def find_latest_log_entry(log_dir):
    latest_date = None
    latest_log = None
    for f in os.listdir(log_dir):
        match = LOG_FILENAME_PATTERN.match(f)
        if match:
            date_str, gzip_ext = match.groups()
            date = datetime.datetime.strptime(date_str, LOG_DATE_PATTERN)
            if not latest_date or date > latest_date:
                latest_date = date
                latest_log = f
    if not latest_log:
        raise Exception('Couldn\'t find any log entries to '
                        'process in specified log directory.')
    return LogEntry(os.path.join(log_dir, latest_log), latest_date)


def extract_data_from_log(log_lines, error_threshold):
    time_per_request = defaultdict(list)
    bad_lines_count = 0
    lines_conunt = 0
    for line in log_lines:
        lines_conunt += 1
        match = LOG_LINE_PATTERN.match(line)
        if not match:
            bad_lines_count += 1
            continue
        request, request_time = match.groups()[4], match.groups()[12]
        request_details = request.split(" ")
        if len(request_details) < 2:
            bad_lines_count += 1
            continue
        method, url = request_details[0:2]
        time_per_request[url].append(float(request_time))
    errors_ratio = bad_lines_count / lines_conunt
    if errors_ratio > error_threshold:
        msg = (' %0.2f percent of lines of the log that weren\'t parsed '
               'exceeds the threshold of %0.2f. Terminating.' %
               (errors_ratio * 100, error_threshold * 100))
        logging.warning(msg)
        sys.exit(msg)
    return time_per_request


def prepare_report_data(time_per_request, report_size):
    time_sums = {}
    total_hits_count = 0
    for url, timings in time_per_request.items():
        time_sums[url] = sum(timings)
        total_hits_count += len(timings)
    total_time = sum(time_sums.values())
    url_count = len(time_per_request)
    report_data = []
    for url, timings in time_per_request.items():
        count = len(timings)
        count_perc = count / total_hits_count
        time_sum = sum(timings)
        time_perc = time_sum / total_time
        time_avg = time_sum / count
        time_max = max(timings)
        time_med = median(timings)
        report_data.append(
            {'count': count, 'count_perc': count_perc, 'time_sum': time_sum,
             'time_perc': time_perc, 'time_avg': time_avg,
             'time_max': time_max, 'time_med': time_med, 'url': url})
    logging.info('Collected report data for %s urls.', url_count)
    return sorted(report_data, reverse=True,
                  key=lambda r: r['time_sum'])[0:report_size]


def generate_report_from_template(template_path, report_path, report_data):
    try:
        with open(template_path) as f:
            template = f.read()
        report_table = json.dumps(report_data)
        report = template.replace(TEMPLATE_REPLACEMENT_STRING,
                                  report_table)
        logging.info('Generating report file to %s', report_path)
        with open(report_path, 'w') as f:
            f.write(report)
    except IOError as e:
        logging.exception('Error while writing a report file: %s', e)
        raise


def build_report(config, template_path, log_entry, report_path):
        is_zipped = log_entry.logfile.endswith('gz')
        with gzip.open(log_entry.logfile, encoding='utf-8') if \
                is_zipped else open(log_entry.logfile, encoding='utf-8') as f:
            try:
                log_lines = (line for line in f)
                threshold = config['ERROR_PERCENTAGE_THRESHOLD']
                request_timings = extract_data_from_log(log_lines, threshold)
            except IOError as e:
                logging.exception('Couldn\'t read from logfile %s: %s',
                                  log_entry.logfile, e)
                raise
            report_data = prepare_report_data(request_timings,
                                              config['REPORT_SIZE'])
            generate_report_from_template(template_path, report_path,
                                          report_data)


def read_config_from_file(config_path):
    if not os.path.exists(config_path):
        logging.warning(
            'Couldn\'t find config file at specified path: %s', config_path)
        return {}
    try:
        with open(config_path) as f:
            return json.load(f)
    except ValueError as e:
        raise Exception(
            'Couldn\'t parse config file json', e)


def validate_configuration(config):
    logs_dir = config['LOG_DIR']
    if not os.path.exists(logs_dir):
        raise Exception('Logs directory %s does not exist.'
                        % logs_dir)
    report_dir = config['REPORT_DIR']
    if not os.path.exists(report_dir):
        logging.info('Reports directory does not exist, creating a new one.')
        try:
            os.mkdir(report_dir)
        except Exception:
            logging.error("Couldn't create reports directory.")
            raise
    report_template = os.path.join(config['REPORT_DIR'],
                                   REPORT_TEMPLATE_FILE)
    if not os.path.exists(report_template):
        raise Exception('Report template file cannot be found at %s.',
                        report_template)
    try:
        int(config['REPORT_SIZE'])
    except ValueError as e:
        raise Exception('%s configuration parameter must be an'
                        ' integer.' % 'REPORT_SIZE', e)


def write_timestamp_file(path):
    with open(path, 'w') as f:
        now = datetime.datetime.now()
        timestamp_str = str(int(time.mktime(now.timetuple())))
        f.write(timestamp_str)


def configure_logger(log_file_path):
    config_args = {
        'level': logging.INFO,
        'format': '[%(asctime)s] %(levelname).1s %(message)s',
        'datefmt': '%Y.%m.%d %H:%M:%S',
        'filename': log_file_path
    }
    logging.basicConfig(**config_args)


def get_args():
    parser = argparse.ArgumentParser(
        description='Log analyzer commandline client')
    parser.add_argument('--config', nargs='?', type=str,
                        default='',
                        help='Path to the config file.'
                             'Default is /usr/local/etc/log_analyzer.conf')
    return parser.parse_args()


def main():
    args = get_args()
    config = DEFAULT_CONFIG.copy()
    try:
        if not args.config:
            sys.exit('Error: no configuration was passed.')
        print('Getting config file from %s ' % args.config)
        overrides = read_config_from_file(args.config)
        config.update(overrides)
        logfile_path = config.get('LOGFILE_PATH', None)
        configure_logger(logfile_path)
        validate_configuration(config)
        log_entry = find_latest_log_entry(config['LOG_DIR'])
        date_str = log_entry.date.strftime(REPORT_DATE_PATTERN)
        report_dir = config['REPORT_DIR']
        report_path = os.path.join(report_dir, REPORT_FILE_FORMAT % date_str)
        if os.path.exists(report_path):
            logging.info('Report for the latest log entry %s already '
                         'exists.' % log_entry.logfile)
            sys.exit(0)
        template_path = os.path.join(config['REPORT_DIR'],
                                     REPORT_TEMPLATE_FILE)
        build_report(config, template_path, log_entry, report_path)
        write_timestamp_file(config['TIMESTAMP_PATH'])
    except Exception as e:
        logging.exception(e)
        sys.exit('Log analyzer finished with error: ' + str(e))


if __name__ == "__main__":
    main()
