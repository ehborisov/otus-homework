from setuptools import setup

setup_config = {
    'description': 'Log analyzer homework for otus.ru python course.',
    'author': 'Borisov Egor',
    'version': '1.0',
    'packages': ['log_analyzer'],
    'install_requires': [],
    'name': 'log_analyzer'
}


def main():
    setup(**setup_config)


if __name__ == '__main__':
    main()
