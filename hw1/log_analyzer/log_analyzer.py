#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import logging
import sys
import os
import re
import gzip
import datetime
from logging.config import dictConfig
from collections import defaultdict
from collections import namedtuple
import json
import time
import math
import multiprocessing

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
                              '(.+)\s'  # request_time
                              )
REPORT_FILE_FORMAT = 'report-%s.html'
LOG_DATE_PATTERN = '%Y%m%d'
REPORT_DATE_PATTERN = '%Y.%m.%d'
REPORT_TEMPLATE_FILE = 'report.html'
TEMPLATE_REPLACEMENT_STRING = '$table_json'

CONFIG_OPTION = '--config'
CONFIG_DEFAULT_PATH = '/usr/local/etc/log_analyzer.conf'
CONFIG_LOGFILE_KEY = 'LOGFILE_PATH'
CONFIG_TIMESTAMP_KEY = 'TIMESTAMP_PATH'
CONFIG_LOGDIR_KEY = 'LOG_DIR'
CONFIG_REPORT_DIR_KEY = 'REPORT_DIR'
CONFIG_REPORT_SIZE_KEY = 'REPORT_SIZE'

REPORT_DECIMAL_FIELDS = ['count_perc', 'time_sum', 'time_perc', 'time_avg',
                         'time_max', 'time_med']


class ReportEntry(namedtuple('ReportEntry',
                             ['count', 'url'] + REPORT_DECIMAL_FIELDS)):
    def __eq__(self, other):
        decimal_fields_match = all(
            math.isclose(float(getattr(self, f)), float(getattr(other, f)))
            for f in REPORT_DECIMAL_FIELDS
        )
        return self.count == other.count and self.url == other.url and \
               decimal_fields_match


class LogAnalyzerException(Exception):
    pass


class LogAnalyzer:

    def __init__(self, conf):
        self._logs_dir = conf[CONFIG_LOGDIR_KEY]
        self._report_dir = conf[CONFIG_REPORT_DIR_KEY]
        self._report_size = conf[CONFIG_REPORT_SIZE_KEY]
        self._timestamp_path = conf[CONFIG_TIMESTAMP_KEY]

    def _find_latest_log_entry(self):
        latest_date = None
        latest_log = None
        for f in os.listdir(self._logs_dir):
            match = LOG_FILENAME_PATTERN.match(f)
            if match:
                date_str, gzip_ext = match.groups()
                date = datetime.datetime.strptime(date_str,
                                                  LOG_DATE_PATTERN)
                if not latest_date or date > latest_date:
                    latest_date = date
                    latest_log = f
        return latest_log, latest_date

    def _check_report_exists(self, report_date):
        date_str = report_date.strftime(REPORT_DATE_PATTERN)
        report = os.path.join(self._report_dir,
                              REPORT_FILE_FORMAT % date_str)
        report_exists = os.path.exists(report)
        timestamp_exists = os.path.exists(self._timestamp_path)
        if not report_exists or not timestamp_exists:
            logging.info('Report or timestamp files do not exist,'
                         ' generating report.')
            return False
        try:
            with open(self._timestamp_path) as f:
                timestamp = int(f.read())
        except (IOError, ValueError) as e:
            logging.warning('Couldn\'t parce timestamp from timestamp file at'
                            ' %s, %s. Regenerating the report.',
                            self._timestamp_path, e)
            return False
        date_from_timestamp = datetime.datetime.fromtimestamp(timestamp)
        today = datetime.datetime.now()
        logging.info('Previous report timestamp is %s.', date_from_timestamp)
        return date_from_timestamp.date() == today.date()

    def _extract_data_from_log(self, logfile):
        time_per_request = defaultdict(list)
        path = os.path.join(self._logs_dir, logfile)
        cpu_count = multiprocessing.cpu_count()
        if logfile.endswith('gz'):
            logging.info('Parsing log from gzip log file %s.', path)
            f = gzip.open(path)
        else:
            logging.info('Parsing logfile %s.', path)
            f = open(path)

        pool = multiprocessing.Pool(cpu_count)
        try:
            url_timings = pool.map(self._process_log_line, f.readlines(),
                                   cpu_count)
        except IOError as e:
            logging.error('Couldn\'t read from logfile %s: %s', path, e)
            raise LogAnalyzerException(e)
        finally:
            f.close()
        for entry in url_timings:
            if entry:
                url, request_time = entry
                time_per_request[url].append(request_time)
        return time_per_request

    def _process_log_line(self, line):
        match = LOG_LINE_PATTERN.match(line)
        if not match:
            logging.warning('Couldn\'t parse log line: %s', line)
            return
        remote_addr, remote_user, http_x_real_ip, time_local, \
        request, status, body_bytes_sent, http_referer, \
        http_user_agent, http_x_forwarded_for, http_X_REQUEST_ID, \
        http_X_RB_USER, request_time = match.groups()

        request_details = request.split(" ")
        if len(request_details) < 2:
            logging.warning("Couldn\'t parse request string from log "
                            "line: \"%s\"", line)
            return
        method, url = request_details[0:2]
        return url, float(request_time)

    def _prepare_report_data(self, time_per_request):
        time_sums = {url: sum(timings) for url, timings
                     in time_per_request.items()}
        total_hits_count = sum(len(x) for x in time_per_request.values())
        total_time = sum(time_sums.values())
        url_count = len(time_per_request)
        if url_count < self._report_size:
            logging.warning('Requested report size is greater than actual count'
                            ' of unique urls.')
            report_limit = url_count
        else:
            report_limit = self._report_size
        report_data = []
        for url, timings in time_per_request.items():
            timings.sort()
            count = len(timings)
            count_perc = count / total_hits_count
            time_sum = sum(timings)
            time_perc = time_sum / total_time
            time_avg = time_sum / count
            time_max = max(timings)
            time_med = timings[int(count / 2)]
            report_data.append(ReportEntry(
                count=count, count_perc=count_perc, time_sum=time_sum,
                time_perc=time_perc, time_avg=time_avg, time_max=time_max,
                time_med=time_med, url=url))
        logging.info('Collected report data for %s urls, limiting to %s',
                     url_count, report_limit)
        return sorted(report_data, reverse=True,
                      key=lambda r: r.time_sum)[0:report_limit]

    def _generate_report_from_template(self, report_data, date):
        try:
            path = os.path.join(self._report_dir, REPORT_TEMPLATE_FILE)
            with open(path) as f:
                template = f.read()
            report_table = json.dumps([e._asdict() for e in report_data])
            report = template.replace(TEMPLATE_REPLACEMENT_STRING,
                                        report_table)
            report_data = date.strftime(REPORT_DATE_PATTERN)
            report_file = REPORT_FILE_FORMAT % report_data
            report_path = os.path.join(self._report_dir, report_file)
            logging.info('Generating report file to %s', report_path)
            with open(report_path, 'w') as f:
                f.write(report)
        except IOError as e:
            logging.error('Error while writing a report file: %s', e)
            raise LogAnalyzerException(e)

    def build_report(self):
        latest_log, latest_date = self._find_latest_log_entry()
        if not latest_log:
            raise LogAnalyzerException('Couldn\'t find any log entries to '
                                       'process in specified log directory.')
        report_exists = self._check_report_exists(latest_date)
        if report_exists:
            logging.info('Report for the latest log entry %s already exists.',
                         latest_log)
            return
        else:
            request_timings = self._extract_data_from_log(latest_log)
            report_data = self._prepare_report_data(request_timings)
            self._generate_report_from_template(report_data, latest_date)


def read_config(config_path):
    if not os.path.exists(config_path):
        raise LogAnalyzerException(
            'Couldn\'t find config file at specified path: %s', config_path)
    try:
        with open(config_path) as f:
            return json.load(f)
    except ValueError as e:
        raise LogAnalyzerException(
            'Couldn\'t parse config file json', e)


def validate_configuration(conf):
    logs_dir = conf[CONFIG_LOGDIR_KEY]
    if not os.path.exists(logs_dir):
        raise LogAnalyzerException('Logs directory %s does not exist.'
                                   % logs_dir)
    report_dir = conf[CONFIG_REPORT_DIR_KEY]
    if not os.path.exists(report_dir):
        raise LogAnalyzerException('Reports directory %s does not exist.'
                                   % report_dir)
    try:
        int(conf[CONFIG_REPORT_SIZE_KEY])
    except ValueError as e:
        raise LogAnalyzerException('%s configuration parameter must be an'
                                   ' integer.' % CONFIG_REPORT_SIZE_KEY, e)


def write_timestamp_file(timestamp_path):
    with open(timestamp_path, 'w') as f:
        now = datetime.datetime.now()
        timestamp_str = str(int(time.mktime(now.timetuple())))
        f.write(timestamp_str)


def configure_logger(logfile_path=''):
    logger_config = {
        'version': 1,
        'formatters': {
            'standard': {
                'format': '[%(asctime)s] %(levelname).1s %(message)s',
                'datefmt': '%Y.%m.%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'level': logging.INFO,
                'stream': 'sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'level': logging.INFO,
                'filename': logfile_path
            }
        },
        'root': {
            'level': logging.INFO,
        }}
    if logfile_path:
        logger_config['root']['handlers'] = ['file']
    else:
        logger_config['root']['handlers'] = ['console']
    dictConfig(logger_config)


def main():
    args = sys.argv
    options = {}
    while args:
        if args[0].startswith('-'):
            options[args[0]] = options[args[1]]
        args = args[1:]
    config_path = CONFIG_DEFAULT_PATH
    if CONFIG_OPTION in options:
        config_path = options[CONFIG_OPTION]
    print('Getting config file from %s ' % config_path)
    if not os.path.exists(config_path):
        sys.exit('Configuration file doesn\'t exist')
    try:
        config = read_config(config_path)
        validate_configuration(config)
        configure_logger(config[CONFIG_LOGFILE_KEY])
        log_analyzer = LogAnalyzer(config)
        log_analyzer.build_report()
        write_timestamp_file(config[CONFIG_TIMESTAMP_KEY])
    except LogAnalyzerException as e:
        sys.exit('Error: ' + str(e))


if __name__ == "__main__":
    main()
