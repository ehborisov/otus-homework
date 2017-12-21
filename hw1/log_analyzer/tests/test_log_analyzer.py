import unittest
from unittest import mock
from .. import log_analyzer
import os
import datetime
import time

LOG_LINES = "1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] \"GET /api/v2/banner/25019354 HTTP/1.1\" 200 927 \"-\" \"Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5\" \"-\" \"1498697422-2190034393-4708-9752759\" \"dc7161be3\" 0.390\n" +\
            "1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] \"GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1\" 200 12 \"-\" \"Python-urllib/2.7\" \"-\" \"1498697422-32900793-4708-9752770\" \"-\" 0.133\n"

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
        log_file, date = log_analyzer.find_latest_log_entry()
        self.assertEqual(log_file, 'nginx-access-ui.log-20170630')
        expected_date = datetime.datetime.strptime(
            '20170630', log_analyzer.LOG_DATE_PATTERN)
        self.assertEqual(date, expected_date)

    @mock.patch.object(os, 'listdir')
    def test_gzipped_log_is_retrieved(self, listdir_mock):
        listdir_mock.return_value = [
            'nginx-access-ui.log-20170630.gz',
            'nginx-access-ui.log-20170629',
            'some-other.log-20170631',
        ]
        log_file, date = log_analyzer.find_latest_log_entry()
        self.assertEqual(log_file, 'nginx-access-ui.log-20170630.gz')

    @mock.patch.object(os.path, 'exists')
    @mock.patch('builtins.open', new_callable=mock.mock_open,
                read_data='1498777200')
    def test_timestamp_is_from_day_before(self, open_mock, exists_mock):
        exists_mock.return_value = True
        date = datetime.datetime.strptime(
            '20170630', log_analyzer.LOG_DATE_PATTERN)
        report_exists = log_analyzer.check_report_exists(date)
        self.assertFalse(report_exists)
        self.assertTrue(open_mock.called)

    @mock.patch.object(os.path, 'exists')
    @mock.patch('builtins.open', new_callable=mock.mock_open,
                read_data=str(
                    int(time.mktime(datetime.datetime.now().timetuple()))))
    def test_timestamp_is_from_latest_log(self, open_mock, exists_mock):
        exists_mock.return_value = True
        date = datetime.datetime.now()
        report_exists = log_analyzer.check_report_exists(date)
        self.assertTrue(report_exists)
        self.assertTrue(open_mock.called)

    @mock.patch('builtins.open', new_callable=mock.mock_open,
                read_data=LOG_LINES)
    def test_log_lines_read(self, open_mock):
        logfile = 'nginx-access-ui.log-20170629'
        expected_timings = {'/api/v2/banner/25019354': [0.39],
                            '/api/1/photogenic_banners/list/?server_name'
                            '=WIN7RB4': [0.133]}
        url_timings = log_analyzer.extract_data_from_log(logfile)
        self.assertTrue(open_mock.called)
        self.assertEqual(expected_timings, url_timings)

    def test_prepare_report_data(self):
        expected_report = SAMPLE_REPORT
        log_analyzer.config[log_analyzer.CONFIG_REPORT_SIZE_KEY] = 4
        report_data = log_analyzer.prepare_report_data(SAMPLE_REPORT_DATA)
        self.assertEqual(len(expected_report), len(report_data))
        for expected, actual in zip(expected_report, report_data):
            for key in ['count', 'count_perc', 'time_sum', 'time_perc',
                        'time_avg', 'time_max', 'time_med']:
                self.assertAlmostEqual(expected[key], actual[key], msg=key)

    def test_report_data_is_limited(self):
        log_analyzer.config[log_analyzer.CONFIG_REPORT_SIZE_KEY] = 2
        report_data = log_analyzer.prepare_report_data(SAMPLE_REPORT_DATA)
        self.assertEqual(len(report_data), 2)

    @mock.patch.object(log_analyzer, 'find_latest_log_entry')
    def test_fail_if_no_logs_found(self, find_log_mock):
        find_log_mock.return_value = (None, None)
        with self.assertRaises(Exception) as c:
            log_analyzer.build_report()
        self.assertIn('Couldn\'t find any log entries', str(c.exception))

    @mock.patch.object(log_analyzer, 'find_latest_log_entry')
    @mock.patch.object(log_analyzer, 'check_report_exists')
    @mock.patch.object(log_analyzer, 'extract_data_from_log')
    def test_report_is_not_generated_if_exists(self, extract_data_mock,
                                               check_report_mock,
                                               find_log_mock):
        date = datetime.datetime.strptime(
            '20170630', log_analyzer.LOG_DATE_PATTERN)
        find_log_mock.return_value = ('/test.log', date)
        check_report_mock.return_value = True
        log_analyzer.build_report()
        self.assertFalse(extract_data_mock.called)

    @mock.patch.object(log_analyzer, 'find_latest_log_entry')
    @mock.patch.object(log_analyzer, 'check_report_exists')
    @mock.patch.object(log_analyzer, 'extract_data_from_log')
    @mock.patch.object(log_analyzer, 'prepare_report_data')
    @mock.patch.object(log_analyzer, 'generate_report_from_template')
    def test_report_is_generated_if_not_exists(
            self, generate_report_mock, prepare_data_mock, extract_data_mock,
            check_report_mock, find_log_mock):
        date = datetime.datetime.strptime(
            '20170630', log_analyzer.LOG_DATE_PATTERN)
        find_log_mock.return_value = ('/test.log', date)
        report_data = ['test_data']
        prepare_data_mock.return_value = report_data
        check_report_mock.return_value = False
        log_analyzer.build_report()
        self.assertTrue(extract_data_mock.called)
        self.assertTrue(prepare_data_mock.called)
        generate_report_mock.assert_called_once_with(report_data, date)


if __name__ == '__main__':
    unittest.main()
