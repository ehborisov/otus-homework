Log analyzer tool
===========================

Compatible with Python versions 3.3 and higher.

Usage:
Analyzer works in a following way:

    `python log_analyzer.py`

to invoke the script with default configuration that will be read from
/usr/local/etc/log_analyzer.conf by default.

to override configuration file use --config parameter:

    `python log_analyzer.py --config path/to/your/config.conf`

Configuration sample:

    `{
        "REPORT_SIZE": 1000,
        "REPORT_DIR": "/Users/eborisov/study/data/python_course/hw1/reports",
        "LOG_DIR": "/Users/eborisov/study/data/python_course/hw1/log",
        "TIMESTAMP_PATH": "/var/tmp/log_analyzer.ts",
        "LOGFILE_PATH": "/var/tmp/log_analyzer.log"
    }`

By default script outputs it's log to a file /var/tmp/log_analyzer.log. If no
"LOGFILE_PATH" parameter is specified in the config, logging output will be
printed to stdout.
 
Tests
-----
You can execute unit tests from commandline via

    `python -m unittest tests/test_log_analyzer.py`

or by invoking `tox`, that will also perform a flake8 lint check.


Thanks for reading!
------------------