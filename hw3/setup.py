from setuptools import setup

setup_config = {
    'description': 'Scoring api homework for otus.ru python course.',
    'author': 'Borisov Egor',
    'version': '1.0',
    'packages': ['scoring_server'],
    'install_requires': [],
    'name': 'scoring_server'
}


def main():
    setup(**setup_config)


if __name__ == '__main__':
    main()
