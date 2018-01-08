import unittest
from unittest import mock
from .. import log_analyzer
import os
import sys
import datetime


LOG_LINES = ["1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] \"GET /api/v2/banner/25019354 HTTP/1.1\" 200 927 \"-\" \"Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5\" \"-\" \"1498697422-2190034393-4708-9752759\" \"dc7161be3\" 0.390\n",
             "1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] \"GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1\" 200 12 \"-\" \"Python-urllib/2.7\" \"-\" \"1498697422-32900793-4708-9752770\" \"-\" 0.133\n"]

SAMPLE_REPORT_DATA = {
    '/api/url/1': [0.11, 4.55, 0.001, 3.0],
    '/api/url/2': [0.2, 3.21],
    '/api/url/3': [1.0]
}

SAMPLE_REPORT = [
    {'count': 4, 'count_perc': 0.5714285714285714, 'time_sum': 7.661,
     'time_perc': 0.6346615856184242, 'time_avg': 1.91525, 'time_max': 4.55,
     'time_med': 1.555, 'url': '/api/url/1'},
    {'count': 2, 'count_perc': 0.2857142857142857, 'time_sum': 3.41,
     'time_perc': 0.28249523651727276, 'time_avg': 1.705, 'time_max': 3.21,
     'time_med': 1.705, 'url': '/api/url/2'},
    {'count': 1, 'count_perc': 0.14285714285714285, 'time_sum': 1.0,
     'time_perc': 0.08284317786430287, 'time_avg': 1.0, 'time_max': 1.0,
     'time_med': 1.0, 'url': '/api/url/3'}
]


class LogAnalyzerTest(unittest.TestCase):

    @mock.patch.object(os, 'listdir')
    def test_latest_log_is_retrieved(self, listdir_mock):
        listdir_mock.return_value = [
            'nginx-access-ui.log-20170630',
            'nginx-access-ui.log-20170629',
            'some-other.log-20170630',
        ]
        log_entry = log_analyzer.find_latest_log_entry('/opt/logs')
        self.assertEqual(log_entry.logfile,
                         '/opt/logs/nginx-access-ui.log-20170630')
        expected_date = datetime.datetime.strptime(
            '20170630', log_analyzer.LOG_DATE_PATTERN)
        self.assertEqual(log_entry.date, expected_date)

    @mock.patch.object(os, 'listdir')
    def test_gzipped_log_is_retrieved(self, listdir_mock):
        listdir_mock.return_value = [
            'nginx-access-ui.log-20170630.gz',
            'nginx-access-ui.log-20170629',
            'some-other.log-20170631',
        ]
        log_entry = log_analyzer.find_latest_log_entry('/opt/logs')
        self.assertEqual(log_entry.logfile,
                         '/opt/logs/nginx-access-ui.log-20170630.gz')

    @mock.patch.object(os, 'listdir')
    def test_fail_if_no_logs_found(self, listdir_mock):
        listdir_mock.return_value = [
            'non-matching-entry.log'
        ]
        with self.assertRaises(Exception) as c:
            log_analyzer.find_latest_log_entry('/opt/logs')
        self.assertIn('Couldn\'t find any log entries', str(c.exception))

    def test_log_lines_read(self):
        expected_timings = {'/api/v2/banner/25019354': [0.39],
                            '/api/1/photogenic_banners/list/?server_name'
                            '=WIN7RB4': [0.133]}
        error_threshold = 0.05
        url_timings = log_analyzer.extract_data_from_log(LOG_LINES,
                                                         error_threshold)
        self.assertEqual(expected_timings, url_timings)

    @mock.patch.object(sys, 'exit')
    def test_script_is_terminated_on_error_threshold(self, sys_exit_mock):
        lines = LOG_LINES[:]
        lines.append("bad line")
        error_threshold = 0.05
        log_analyzer.extract_data_from_log(lines, error_threshold)
        self.assertTrue(sys_exit_mock.called)

    def test_prepare_report_data(self):
        expected_report = SAMPLE_REPORT
        report_size = 4
        report_data = log_analyzer.prepare_report_data(SAMPLE_REPORT_DATA,
                                                       report_size)
        self.assertEqual(len(expected_report), len(report_data))
        for expected, actual in zip(expected_report, report_data):
            for key in ['count', 'count_perc', 'time_sum', 'time_perc',
                        'time_avg', 'time_max', 'time_med']:
                self.assertAlmostEqual(expected[key], actual[key], msg=key)

    @mock.patch('builtins.open', new_callable=mock.mock_open,
                read_data=''.join(LOG_LINES))
    @mock.patch.object(log_analyzer, 'extract_data_from_log')
    @mock.patch.object(log_analyzer, 'prepare_report_data')
    @mock.patch.object(log_analyzer, 'generate_report_from_template')
    def test_report_is_generated_if_not_exists(
            self, generate_report_mock, prepare_data_mock, extract_data_mock,
            _):
        config = log_analyzer.DEFAULT_CONFIG.copy()
        template_path = '/reports/report.html'
        report_path = '/reports/report-05.01.2018.html'
        log_entry = log_analyzer.LogEntry('/test.log', None)
        report_data = ['test_data']
        prepare_data_mock.return_value = report_data
        log_analyzer.build_report(config, template_path, log_entry,
                                  report_path)
        self.assertTrue(extract_data_mock.called)
        self.assertTrue(prepare_data_mock.called)
        generate_report_mock.assert_called_once_with(template_path, report_path,
                                                     report_data)


if __name__ == '__main__':
    unittest.main()
