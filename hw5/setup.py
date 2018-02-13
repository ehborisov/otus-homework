from setuptools import setup

setup_config = {
    'description': 'DIY http web server homework for otus.ru python course.',
    'author': 'Borisov Egor',
    'version': '1.0',
    'packages': ['diy_http_server'],
    'install_requires': [],
    'name': 'diy_http_server'
}


def main():
    setup(**setup_config)


if __name__ == '__main__':
    main()
