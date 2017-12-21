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

CONFIG_OPTION = '--config'
CONFIG_LOGFILE_KEY = 'LOGFILE_PATH'
CONFIG_TIMESTAMP_KEY = 'TIMESTAMP_PATH'
CONFIG_LOGDIR_KEY = 'LOG_DIR'
CONFIG_REPORT_DIR_KEY = 'REPORT_DIR'
CONFIG_REPORT_SIZE_KEY = 'REPORT_SIZE'
CONFIG_ERROR_THRESHOLD = 'ERROR_PERCENTAGE_THRESHOLD'

REPORT_DECIMAL_FIELDS = ['count_perc', 'time_sum', 'time_perc', 'time_avg',
                         'time_max', 'time_med']

config = {'REPORT_SIZE': 1000,
          'REPORT_DIR': '/Users/eborisov/study/data/python_course/hw1/reports',
          'LOG_DIR': '/Users/eborisov/study/data/python_course/hw1/log',
          'TIMESTAMP_PATH': '/var/tmp/log_analyzer.ts',
          'LOGFILE_PATH': '/var/tmp/log_analyzer.log',
          'ERROR_PERCENTAGE_THRESHOLD': 0.05}


def find_latest_log_entry():
    latest_date = None
    latest_log = None
    for f in os.listdir(config[CONFIG_LOGDIR_KEY]):
        match = LOG_FILENAME_PATTERN.match(f)
        if match:
            date_str, gzip_ext = match.groups()
            date = datetime.datetime.strptime(date_str, LOG_DATE_PATTERN)
            if not latest_date or date > latest_date:
                latest_date = date
                latest_log = f
    return latest_log, latest_date


def check_report_exists(report_date):
    date_str = report_date.strftime(REPORT_DATE_PATTERN)
    report = os.path.join(config[CONFIG_REPORT_DIR_KEY],
                          REPORT_FILE_FORMAT % date_str)
    report_exists = os.path.exists(report)
    timestamp_exists = os.path.exists(config[CONFIG_TIMESTAMP_KEY])
    if not report_exists or not timestamp_exists:
        logging.info('Report or timestamp files do not exist,'
                     ' generating report.')
        return False
    try:
        with open(config[CONFIG_TIMESTAMP_KEY]) as f:
            timestamp = int(f.read())
    except (IOError, ValueError) as e:
        logging.exception(e)
        logging.warning('Couldn\'t parce timestamp from timestamp file at'
                        ' %s. Regenerating the report.',
                        config[CONFIG_TIMESTAMP_KEY])
        return False
    date_from_timestamp = datetime.datetime.fromtimestamp(timestamp)
    today = datetime.datetime.now()
    logging.info('Previous report timestamp is %s.', date_from_timestamp)
    return date_from_timestamp.date() == today.date()


def extract_data_from_log(logfile):
    time_per_request = defaultdict(list)
    path = os.path.join(config[CONFIG_LOGDIR_KEY], logfile)
    if logfile.endswith('gz'):
        logging.info('Parsing log from gzip log file %s.', path)
        f = gzip.open(path, encoding='utf-8')
    else:
        logging.info('Parsing logfile %s.', path)
        f = open(path, encoding='utf-8')
    bad_lines_count = 0
    lines_conunt = 0
    try:
        for line in f.readlines():
            lines_conunt += 1
            match = LOG_LINE_PATTERN.match(line)
            if not match:
                bad_lines_count += 1
                continue
            remote_addr, remote_user, http_x_real_ip, time_local, \
            request, status, body_bytes_sent, http_referer, \
            http_user_agent, http_x_forwarded_for, http_X_REQUEST_ID, \
            http_X_RB_USER, request_time = match.groups()

            request_details = request.split(" ")
            if len(request_details) < 2:
                bad_lines_count += 1
                continue
            method, url = request_details[0:2]
            time_per_request[url].append(float(request_time))
    except IOError as e:
        logging.exception('Couldn\'t read from logfile %s: %s', path, e)
        raise
    finally:
        f.close()
    errors_ratio = bad_lines_count / lines_conunt
    threshold = config[CONFIG_ERROR_THRESHOLD]
    if errors_ratio > threshold:
        msg = (' %0.2f percent of lines of the log that weren\'t parsed '
               'exceeds the threshold of %0.2f. Terminating.' %
               (errors_ratio * 100, threshold * 100))
        logging.warning(msg)
        sys.exit(msg)
    return time_per_request


def prepare_report_data(time_per_request):
    report_size = config[CONFIG_REPORT_SIZE_KEY]
    time_sums = {url: sum(timings) for url, timings
                 in time_per_request.items()}
    total_hits_count = sum(len(x) for x in time_per_request.values())
    total_time = sum(time_sums.values())
    url_count = len(time_per_request)
    if url_count < report_size:
        logging.warning('Requested report size is greater than actual count'
                        ' of unique urls.')
        report_limit = url_count
    else:
        report_limit = report_size
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
    logging.info('Collected report data for %s urls, limiting to %s',
                 url_count, report_limit)
    return sorted(report_data, reverse=True,
                  key=lambda r: r['time_sum'])[0:report_limit]


def generate_report_from_template(report_data, date):
    try:
        path = os.path.join(config[CONFIG_REPORT_DIR_KEY],
                            REPORT_TEMPLATE_FILE)
        with open(path) as f:
            template = f.read()
        report_table = json.dumps(report_data)
        report = template.replace(TEMPLATE_REPLACEMENT_STRING,
                                  report_table)
        report_data = date.strftime(REPORT_DATE_PATTERN)
        report_file = REPORT_FILE_FORMAT % report_data
        report_path = os.path.join(config[CONFIG_REPORT_DIR_KEY], report_file)
        logging.info('Generating report file to %s', report_path)
        with open(report_path, 'w') as f:
            f.write(report)
    except IOError as e:
        logging.exception('Error while writing a report file: %s', e)
        raise


def build_report():
    latest_log, latest_date = find_latest_log_entry()
    if not latest_log:
        raise Exception('Couldn\'t find any log entries to '
                        'process in specified log directory.')
    report_exists = check_report_exists(latest_date)
    if report_exists:
        logging.info('Report for the latest log entry %s already exists.',
                     latest_log)
        return
    else:
        request_timings = extract_data_from_log(latest_log)
        report_data = prepare_report_data(request_timings)
        generate_report_from_template(report_data, latest_date)


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


def validate_configuration():
    logs_dir = config[CONFIG_LOGDIR_KEY]
    if not os.path.exists(logs_dir):
        raise Exception('Logs directory %s does not exist.'
                        % logs_dir)
    report_dir = config[CONFIG_REPORT_DIR_KEY]
    if not os.path.exists(report_dir):
        raise Exception('Reports directory %s does not exist.'
                        % report_dir)
    try:
        int(config[CONFIG_REPORT_SIZE_KEY])
    except ValueError as e:
        raise Exception('%s configuration parameter must be an'
                        ' integer.' % CONFIG_REPORT_SIZE_KEY, e)


def write_timestamp_file():
    with open(config[CONFIG_TIMESTAMP_KEY], 'w') as f:
        now = datetime.datetime.now()
        timestamp_str = str(int(time.mktime(now.timetuple())))
        f.write(timestamp_str)


def configure_logger():
    logging.basicConfig(filename=config[CONFIG_LOGFILE_KEY], level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')


def get_args():
    parser = argparse.ArgumentParser(
        description='Log analyzer commandline client')
    parser.add_argument('--config', nargs='?', type=str,
                        help='Path to the config file.'
                             ' E.g. /usr/local/etc/log_analyzer.conf')
    return parser.parse_args()


def main():
    args = get_args()
    try:
        if args.config:
            print('Getting config file from %s ' % args.config)
            overrides = read_config_from_file(args.config)
            config.update(overrides)
        validate_configuration()
        configure_logger()
        build_report()
        write_timestamp_file()
    except Exception as e:
        logging.exception(e)
        sys.exit('Log analyzer finished with error: ' + str(e))


if __name__ == "__main__":
    main()
